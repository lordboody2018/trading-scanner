import pandas as pd

from exchange import fetch_market
from strategy import prepare


def _has_volume(d: pd.DataFrame) -> bool:
    return bool(d["volume"].tail(30).fillna(0).sum() > 0)


def _signal_at(row, vol_required: bool):
    if pd.isna(row["ema200"]) or pd.isna(row["macd_hist_prev"]):
        return None
    if vol_required and (pd.isna(row["vol_sma20"]) or not row["volume"] > row["vol_sma20"]):
        return None
    close = row["close"]
    long_ok = (
        close > row["ema200"]
        and row["ema50"] > row["ema200"]
        and row["macd_hist"] > 0
        and row["macd_hist"] > row["macd_hist_prev"]
        and 48 <= row["rsi14"] <= 68
        and close > row["ema20"]
    )
    short_ok = (
        close < row["ema200"]
        and row["ema50"] < row["ema200"]
        and row["macd_hist"] < 0
        and row["macd_hist"] < row["macd_hist_prev"]
        and 32 <= row["rsi14"] <= 52
        and close < row["ema20"]
    )
    if long_ok:
        return "LONG"
    if short_ok:
        return "SHORT"
    return None


def _simulate(d: pd.DataFrame, start_idx: int, cfg: dict):
    row = d.iloc[start_idx]
    direction = _signal_at(row, _has_volume(d))
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
        df = pd.DataFrame(raw)
        d = prepare(df)

        trades = wins = 0
        pnl_r = 0.0
        cooldown_end = -1
        cooldown = int(6 * (60 / max(_tf_minutes(cfg["timeframe"]), 1)))

        for i in range(210, len(d) - 2):
            if i <= cooldown_end:
                continue
            if _signal_at(d.iloc[i], _has_volume(d)) is None:
                continue
            result = _simulate(d, i, cfg)
            if result is None:
                continue
            outcome, r, exit_j = result
            trades += 1
            pnl_r += r
            if outcome == "WIN":
                wins += 1
            cooldown_end = exit_j

        total_trades += trades
        total_wins += wins
        total_pnl_r += pnl_r
        if verbose and trades:
            wr = round(wins / trades * 100, 1)
            print(f"{source:7s} {symbol:12s} trades={trades:3d} wins={wins:3d} win_rate={wr:5.1f}% pnl_R={round(pnl_r, 2)}")

    losses = total_trades - total_wins
    return {
        "trades": total_trades,
        "wins": total_wins,
        "losses": losses,
        "win_rate": round(total_wins / total_trades * 100, 1) if total_trades else 0,
        "pnl_r": round(total_pnl_r, 2),
        "avg_r": round(total_pnl_r / total_trades, 3) if total_trades else 0,
    }


def _tf_minutes(tf: str) -> int:
    num = int(tf[:-1])
    unit = tf[-1]
    return num * {"m": 1, "h": 60, "d": 1440}[unit]
