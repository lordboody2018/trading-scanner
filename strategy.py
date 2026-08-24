import pandas as pd

from indicators import atr, ema, htf_bull_series, macd, rsi


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
    df["atr_pct"] = df["atr14"] / df["close"] * 100
    df["htf_bull"] = htf_bull_series(df)
    return df


MIN_ATR_PCT = 0.15
MAX_ATR_PCT = 6.0


def signal_at(row, vol_required: bool, fng_val=None):
    """v3: strict v1 core + higher-timeframe agreement + volatility band + sentiment filter."""
    if pd.isna(row["ema200"]) or pd.isna(row["macd_hist_prev"]) or pd.isna(row["atr14"]):
        return None
    if vol_required and (pd.isna(row["vol_sma20"]) or not row["volume"] > row["vol_sma20"]):
        return None

    close = float(row["close"])
    atr_pct = float(row["atr_pct"])
    if pd.isna(atr_pct) or atr_pct < MIN_ATR_PCT or atr_pct > MAX_ATR_PCT:
        return None

    mh = float(row["macd_hist"])
    mhp = float(row["macd_hist_prev"])
    rsi_v = float(row["rsi14"])

    long_ok = (
        close > float(row["ema200"])
        and float(row["ema50"]) > float(row["ema200"])
        and mh > 0
        and mh > mhp
        and 48 <= rsi_v <= 68
        and close > float(row["ema20"])
    )
    short_ok = (
        close < float(row["ema200"])
        and float(row["ema50"]) < float(row["ema200"])
        and mh < 0
        and mh < mhp
        and 32 <= rsi_v <= 52
        and close < float(row["ema20"])
    )

    if long_ok:
        direction = "LONG"
    elif short_ok:
        direction = "SHORT"
    else:
        return None

    htf_bull = row["htf_bull"]
    if not pd.isna(htf_bull):
        if direction == "LONG" and not bool(htf_bull):
            return None
        if direction == "SHORT" and bool(htf_bull):
            return None

    if fng_val is not None:
        if direction == "LONG" and fng_val <= 25:
            return None
        if direction == "SHORT" and fng_val >= 75:
            return None

    return direction


def evaluate(df: pd.DataFrame, cfg: dict, fng_val=None):
    d = prepare(df)
    last = d.iloc[-1]
    vol_required = bool(last["has_volume"])
    direction = signal_at(last, vol_required, fng_val)
    if direction is None:
        return None

    close = float(last["close"])
    atr_val = float(last["atr14"])
    sl_mult = cfg.get("sl_atr_mult", 2.0)
    tp_mult = cfg.get("tp_atr_mult", 1.0)

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
        "atr_pct": round(float(last["atr_pct"]), 2),
    }
