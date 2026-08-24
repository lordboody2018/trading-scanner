import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def htf_bull_series(df: pd.DataFrame) -> pd.Series:
    """1h EMA50>EMA200 trend mapped onto source index. NaN = insufficient history."""
    ts = df["open_time"].astype("int64")
    unit = "ms" if ts.iloc[-1] > 1e12 else "s"
    dt = pd.to_datetime(ts, unit=unit, utc=True)
    h1 = pd.Series(df["close"].values, index=dt).resample("1h").last().dropna()
    out = pd.Series(float("nan"), index=df.index)
    if len(h1) >= 210:
        bull = (ema(h1, 50) > ema(h1, 200)).astype(float)
        out.iloc[:] = bull.reindex(dt, method="ffill").to_numpy()
    return out
