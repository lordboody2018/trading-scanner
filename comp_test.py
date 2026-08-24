"""Controlled A/B/C/D comparison of signal layers on identical fresh data."""
import pandas as pd

from backtest import _has_volume, _iter_symbols, _simulate, _tf_minutes
from exchange import fetch_market
from sentiment import get_fng_map
from strategy import MAX_ATR_PCT, MIN_ATR_PCT, prepare, signal_at


def _base_ok(row):
    if pd.isna(row["ema200"]) or pd.isna(row["macd_hist_prev"]) or pd.isna(row["atr14"]):
        return None, None
    mh, mhp, rsi_v = float(row["macd_hist"]), float(row["macd_hist_prev"]), float(row["rsi14"])
    close = float(row["close"])
    long_ok = (
        close > float(row["ema200"])
        and float(row["ema50"]) > float(row["ema200"])
        and mh > 0 and mh > mhp
        and 48 <= rsi_v <= 68
        and close > float(row["ema20"])
    )
    short_ok = (
        close < float(row["ema200"])
        and float(row["ema50"]) < float(row["ema200"])
        and mh < 0 and mh < mhp
        and 32 <= rsi_v <= 52
        and close < float(row["ema20"])
    )
    if long_ok:
        return "LONG", None
    if short_ok:
        return "SHORT", None
    return None, None


def sig_a(row, vol_required, fng_val=None):
    if vol_required and (pd.isna(row["vol_sma20"]) or not row["volume"] > row["vol_sma20"]):
        return None
    d, _ = _base_ok(row)
    return d


def sig_b(row, vol_required, fng_val=None):
    s = sig_a(row, vol_required)
    if s is None:
        return None
    ap = float(row["atr_pct"])
    if pd.isna(ap) or ap < MIN_ATR_PCT or ap > MAX_ATR_PCT:
        return None
    return s


def sig_c(row, vol_required, fng_val=None):
    s = sig_b(row, vol_required)
    if s is None:
        return None
    bull = bool(row["htf_bull"])
    if s == "LONG" and not bull:
        return None
    if s == "SHORT" and bull:
        return None
    return s


VARIANTS = [("A: v1 خام", sig_a), ("B: +ATR%", sig_b), ("C: +HTF", sig_c), ("D: +FNG (v3)", signal_at)]


def run_variant(d, cfg, sig_fn, fng_vals):
    vol_required = _has_volume(d)
    d = d.assign(_sig=[sig_fn(d.iloc[i], vol_required, fng_vals[i]) for i in range(len(d))])
    trades = wins = 0
    pnl_r = 0.0
    cooldown_bars = int(cfg.get("cooldown_hours", 6) * (60 / max(_tf_minutes(cfg["timeframe"]), 1)))
    cooldown_end = -1
    for i in range(210, len(d) - 2):
        if i <= cooldown_end or d.iloc[i]["_sig"] is None:
            continue
        result = _simulate(d, i, cfg)
        if result is None:
            continue
        outcome, r, exit_j = result
        trades += 1
        pnl_r += r
        wins += outcome == "WIN"
        cooldown_end = exit_j + cooldown_bars
    return trades, wins, round(pnl_r, 2)


def main():
    import json
    with open("config.json", encoding="utf-8-sig") as f:
        cfg = json.load(f)

    fng_map = get_fng_map(limit=90)
    totals = {name: [0, 0, 0.0] for name, _ in VARIANTS}

    print(f"{'symbol':14s} " + " ".join(f"{n:>22s}" for n, _ in VARIANTS))
    for source, symbol in _iter_symbols(cfg):
        try:
            raw = fetch_market(source, symbol, cfg["timeframe"], limit=1000)
            df = prepare(pd.DataFrame(raw))
        except Exception as e:
            print(f"{symbol:14s} data error: {e}")
            continue
        dates = pd.to_datetime(df["open_time"].astype("int64"),
                               unit="ms" if df["open_time"].astype("int64").iloc[-1] > 1e12 else "s",
                               utc=True).dt.strftime("%Y-%m-%d")
        fng_vals = [fng_map.get(x) if source == "binance" else None for x in dates]
        cells = []
        for name, fn in VARIANTS:
            t, w, p = run_variant(df, cfg, fn, fng_vals)
            totals[name][0] += t
            totals[name][1] += w
            totals[name][2] += p
            wr = f"{w / t * 100:4.1f}%" if t else "  - "
            cells.append(f"t={t:<3d} wr={wr:>5s} R={p:+8.2f}")
        print(f"{symbol:14s} " + " ".join(f"{c:>22s}" for c in cells))

    print("\n===== TOTALS =====")
    for name, _ in VARIANTS:
        t, w, p = totals[name]
        wr = f"{w / t * 100:.1f}%" if t else "-"
        print(f"{name:14s} trades={t:<5d} win_rate={wr:>6s} pnl_R={p:+.2f} avgR={(p / t if t else 0):+.3f}")


if __name__ == "__main__":
    main()
