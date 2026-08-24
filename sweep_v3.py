"""Sweep SL/TP ATR multiples using full v3 signals on identical fresh data."""
import json

import pandas as pd

from backtest import _has_volume, _iter_symbols, _tf_minutes
from exchange import fetch_market
from sentiment import get_fng_map
from strategy import prepare


def simulate(d, start_idx, sl_m, tp_m, max_bars=20):
    row = d.iloc[start_idx]
    direction = row["_sig"]
    if direction is None:
        return None
    entry = float(d.iloc[start_idx + 1]["open"])
    atr_val = float(row["atr14"])
    if direction == "LONG":
        sl, tp = entry - sl_m * atr_val, entry + tp_m * atr_val
    else:
        sl, tp = entry + sl_m * atr_val, entry - tp_m * atr_val
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    end = min(start_idx + 1 + max_bars, len(d) - 1)
    for j in range(start_idx + 2, end + 1):
        lo, hi = d.iloc[j]["low"], d.iloc[j]["high"]
        if direction == "LONG":
            if lo <= sl:
                return "LOSS", -sl_m, j
            if hi >= tp:
                return "WIN", tp_m, j
        else:
            if hi >= sl:
                return "LOSS", -sl_m, j
            if lo <= tp:
                return "WIN", tp_m, j
    exit_close = float(d.iloc[end]["close"])
    r = (exit_close - entry) / risk
    if direction == "SHORT":
        r = -r
    return ("WIN" if r > 0 else "LOSS"), round(r, 3), end


def main():
    with open("config.json", encoding="utf-8-sig") as f:
        cfg = json.load(f)
    fng_map = get_fng_map(limit=90)

    datasets = []
    for source, symbol in _iter_symbols(cfg):
        try:
            raw = fetch_market(source, symbol, cfg["timeframe"], limit=1000)
            d = prepare(pd.DataFrame(raw))
        except Exception:
            continue
        ts = d["open_time"].astype("int64")
        dates = pd.to_datetime(ts, unit="ms" if ts.iloc[-1] > 1e12 else "s", utc=True).dt.strftime("%Y-%m-%d")
        fng_vals = [fng_map.get(x) if source == "binance" else None for x in dates]
        vol_required = _has_volume(d)
        from strategy import signal_at
        d = d.assign(_sig=[signal_at(d.iloc[i], vol_required, fng_vals[i]) for i in range(len(d))])
        datasets.append((source, symbol, d))

    cooldown_bars = int(cfg.get("cooldown_hours", 6) * (60 / max(_tf_minutes(cfg["timeframe"]), 1)))
    results = []
    for sl_m in (1.0, 1.5, 2.0, 2.5, 3.0):
        for tp_m in (1.0, 1.5, 2.0, 2.5, 3.0):
            trades = wins = 0
            pnl = 0.0
            for _, _, d in datasets:
                cooldown_end = -1
                for i in range(210, len(d) - 2):
                    if i <= cooldown_end or d.iloc[i]["_sig"] is None:
                        continue
                    res = simulate(d, i, sl_m, tp_m, cfg.get("max_hold_bars", 20))
                    if res is None:
                        continue
                    outcome, r, exit_j = res
                    trades += 1
                    pnl += r
                    wins += outcome == "WIN"
                    cooldown_end = exit_j + cooldown_bars
            results.append((pnl, trades, wins / trades * 100 if trades else 0, sl_m, tp_m))

    results.sort(reverse=True)
    print(f"{'SLxATR':>6s} {'TPxATR':>6s} {'trades':>7s} {'winrate':>8s} {'pnl_R':>9s} {'avgR':>7s}")
    for pnl, t, wr, s, tp in results[:12]:
        print(f"{s:>6.1f} {tp:>6.1f} {t:>7d} {wr:>7.1f}% {pnl:>+9.2f} {pnl / t if t else 0:>+7.3f}")
    print("...")
    for pnl, t, wr, s, tp in results[-3:]:
        print(f"{s:>6.1f} {tp:>6.1f} {t:>7d} {wr:>7.1f}% {pnl:>+9.2f} {pnl / t if t else 0:>+7.3f}")


if __name__ == "__main__":
    main()
