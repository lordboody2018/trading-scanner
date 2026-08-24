import pandas as pd

from indicators import atr, ema, macd, rsi


def _round_price(p: float) -> float:
    if p < 20:
        return round(p, 5)
    if p < 200:
        return round(p, 4)
    if p < 2000:
        return round(p, 3)
    return round(p, 2)


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["ema200"] = ema(df["close"], 200)
    df["rsi14"] = rsi(df["close"], 14)
    _, _, df["macd_hist"] = macd(df["close"])
    df["macd_hist_prev"] = df["macd_hist"].shift(1)
    df["atr14"] = atr(df, 14)
    df["vol_sma20"] = df["volume"].rolling(20).mean()
    recent_vol = df["volume"].tail(30).fillna(0).sum()
    df["has_volume"] = recent_vol > 0
    return df


def evaluate(df: pd.DataFrame, cfg: dict):
    d = prepare(df)
    last = d.iloc[-1]
    if any(pd.isna(last[col]) for col in ["ema200", "rsi14", "macd_hist", "macd_hist_prev", "atr14"]):
        return None
    vol_ok = bool(last["has_volume"]) and last["volume"] > last["vol_sma20"]
    if bool(last["has_volume"]) and not vol_ok:
        return None

    close = float(last["close"])
    atr_val = float(last["atr14"])
    if atr_val <= 0:
        return None
    sl_mult = cfg.get("sl_atr_mult", 2.0)
    tp_mult = cfg.get("tp_atr_mult", 1.0)

    long_ok = (
        close > float(last["ema200"])
        and float(last["ema50"]) > float(last["ema200"])
        and float(last["macd_hist"]) > 0
        and float(last["macd_hist"]) > float(last["macd_hist_prev"])
        and 48 <= float(last["rsi14"]) <= 68
        and close > float(last["ema20"])
    )
    short_ok = (
        close < float(last["ema200"])
        and float(last["ema50"]) < float(last["ema200"])
        and float(last["macd_hist"]) < 0
        and float(last["macd_hist"]) < float(last["macd_hist_prev"])
        and 32 <= float(last["rsi14"]) <= 52
        and close < float(last["ema20"])
    )

    if long_ok:
        direction = "LONG"
    elif short_ok:
        direction = "SHORT"
    else:
        return None

    if direction == "LONG":
        sl = _round_price(close - sl_mult * atr_val)
        tp = _round_price(close + tp_mult * atr_val)
    else:
        sl = _round_price(close + sl_mult * atr_val)
        tp = _round_price(close - tp_mult * atr_val)

    return {
        "direction": direction,
        "entry": _round_price(close),
        "stop_loss": sl,
        "take_profit": tp,
        "rsi": round(float(last["rsi14"]), 1),
        "atr_pct": round(atr_val / close * 100, 2),
    }
