import datetime

import pandas as pd

from exchange import fetch_market
from sentiment import get_fng_map
from strategy import prepare, signal_at


def _has_volume(d: pd.DataFrame) -> bool:
    return bool(d["volume"].tail(30).fillna(0).sum() > 0)


def _row_dates(d: pd.DataFrame):
    ts = d["open_time"].astype("int64")
    unit = "ms" if ts.iloc[-1] > 1e12 else "s"
    return pd.to_datetime(ts, unit=unit, utc=True).dt.strftime("%Y-%m-%d")


def _simulate(d: pd.DataFrame, start_idx: int, cfg: dict):
    row = d.iloc[start_idx]
    direction = row["_sig"]
    if direction is None:
        return None
    entry = float(d.iloc[start_idx + 1]["open"])
    atr_val = float(row["atr14"])
    if direction == "LONG":
        sl = entry - cfg.get("sl_atr_mult", 2.0) * atr_val
        tp = entry + cfg.get("tp_atr_mult", 1.0) * atr_val
    else:
        sl = entry + cfg.get("sl_atr_mult", 2.0) * atr_val
        tp = entry - cfg.get("tp_atr_mult", 1.0) * atr_val
    risk = abs(entry - sl)
    if risk <= 0:
        return None

    max_bars = cfg.get("max_hold_bars", 20)
    end = min(start_idx + 1 + max_bars, len(d) - 1)
    for j in range(start_idx + 2, end + 1):
        lo = d.iloc[j]["low"]
        hi = d.iloc[j]["high"]
        if direction == "LONG":
            if lo <= sl:
                return "LOSS", -cfg.get("sl_atr_mult", 2.0), j
            if hi >= tp:
                return "WIN", cfg.get("tp_atr_mult", 1.0), j
        else:
            if hi >= sl:
                return "LOSS", -cfg.get("sl_atr_mult", 2.0), j
            if lo <= tp:
                return "WIN", cfg.get("tp_atr_mult", 1.0), j
    exit_close = float(d.iloc[end]["close"])
    r = (exit_close - entry) / risk
    if direction == "SHORT":
        r = -r
    return ("WIN" if r > 0 else "LOSS"), round(r, 3), end


def _iter_symbols(cfg: dict):
    for s in cfg.get("crypto_symbols", cfg.get("symbols", [])):
        yield "binance", s
    for s in cfg.get("market_symbols", []):
        yield "yahoo", s


def _stats_for_symbol(cfg: dict, source: str, symbol: str, raw):
    df = pd.DataFrame(raw)
    d = prepare(df)
    vol_required = _has_volume(d)

    fng_map = {}
    if source == "binance":
        fng_map = get_fng_map(limit=90)
    dates = _row_dates(d)
    fng_vals = dates.map(lambda x: fng_map.get(x)).to_numpy() if len(fng_map) else [None] * len(d)

    sigs = [
        signal_at(d.iloc[i], vol_required, fng_vals[i])
        for i in range(len(d))
    ]
    d = d.assign(_sig=sigs)

    trades = wins = 0
    pnl_r = 0.0
    cooldown_bars = int(cfg.get("cooldown_hours", 6) * (60 / max(_tf_minutes(cfg["timeframe"]), 1)))
    cooldown_end = -1

    for i in range(210, len(d) - 2):
        if i <= cooldown_end:
            continue
        if d.iloc[i]["_sig"] is None:
            continue
        result = _simulate(d, i, cfg)
        if result is None:
            continue
        outcome, r, exit_j = result
        trades += 1
        pnl_r += r
        if outcome == "WIN":
            wins += 1
        cooldown_end = exit_j + cooldown_bars

    return trades, wins, pnl_r


def run_backtest(cfg: dict, bars: int = 1000, verbose: bool = False) -> dict:
    total_trades = 0
    total_wins = 0
    total_pnl_r = 0.0

    for source, symbol in _iter_symbols(cfg):
        try:
            raw = fetch_market(source, symbol, cfg["timeframe"], limit=min(bars + 10, 1000))
        except Exception as e:
            print(f"{symbol}: data error {e}")
            continue

        trades, wins, pnl_r = _stats_for_symbol(cfg, source, symbol, raw)

        total_trades += trades
        total_wins += wins
        total_pnl_r += pnl_r
        if verbose:
            if trades:
                wr = round(wins / trades * 100, 1)
                print(f"{source:7s} {symbol:12s} trades={trades:3d} wins={wins:3d} win_rate={wr:5.1f}% pnl_R={round(pnl_r, 2)}")
            else:
                print(f"{source:7s} {symbol:12s} no signals")

    losses = total_trades - total_wins
    return {
        "trades": total_trades,
        "wins": total_wins,
        "losses": losses,
        "win_rate": round(total_wins / total_trades * 100, 1) if total_trades else 0,
        "pnl_r": round(total_pnl_r, 2),
        "avg_r": round(total_pnl_r / total_trades, 3) if total_trades else 0,
    }


def quick_stats(cfg: dict, source: str, symbol: str, bars: int = 1000):
    try:
        raw = fetch_market(source, symbol, cfg["timeframe"], limit=min(bars + 10, 1000))
        trades, wins, pnl_r = _stats_for_symbol(cfg, source, symbol, raw)
        if not trades:
            return None
        return {
            "trades": trades,
            "win_rate": round(wins / trades * 100),
            "pnl_r": round(pnl_r, 2),
        }
    except Exception:
        return None


def _tf_minutes(tf: str) -> int:
    num = int(tf[:-1])
    unit = tf[-1]
    return num * {"m": 1, "h": 60, "d": 1440}[unit]
