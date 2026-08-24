import requests

BINANCE_HOSTS = [
    "https://api.binance.com",
    "https://data-api.binance.vision",
]

YAHOO_HOSTS = [
    "https://query1.finance.yahoo.com",
    "https://query2.finance.yahoo.com",
]

YAHOO_INTERVAL_MAP = {
    "5m": ("5m", "30d"),
    "15m": ("15m", "30d"),
    "30m": ("30m", "60d"),
    "1h": ("1h", "90d"),
}

UA_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _empty():
    return {
        "open_time": [], "open": [], "high": [],
        "low": [], "close": [], "volume": [], "close_time": [],
    }


def _fill(data, o, h, l, c, v, t=None):
    for i in range(len(c)):
        if c[i] is None or o[i] is None or h[i] is None or l[i] is None:
            continue
        data["open_time"].append(int(t[i]) if t is not None else len(data["close"]))
        data["open"].append(float(o[i]))
        data["high"].append(float(h[i]))
        data["low"].append(float(l[i]))
        data["close"].append(float(c[i]))
        data["volume"].append(float(v[i]) if v and v[i] is not None else 0.0)


def fetch_binance(symbol: str, interval: str, limit: int = 300):
    last_err = None
    for host in BINANCE_HOSTS:
        try:
            r = requests.get(
                f"{host}/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": min(limit, 1000)},
                timeout=15,
            )
            r.raise_for_status()
            rows = r.json()
            data = _empty()
            for row in rows:
                data["open_time"].append(int(row[0]))
                data["open"].append(float(row[1]))
                data["high"].append(float(row[2]))
                data["low"].append(float(row[3]))
                data["close"].append(float(row[4]))
                data["volume"].append(float(row[5]))
                data["close_time"].append(int(row[6]))
            return data
        except Exception as e:
            last_err = e
    raise RuntimeError(f"binance failed for {symbol}: {last_err}")


def fetch_yahoo(symbol: str, interval: str):
    yi, rng = YAHOO_INTERVAL_MAP.get(interval, ("15m", "30d"))
    last_err = None
    for host in YAHOO_HOSTS:
        try:
            r = requests.get(
                f"{host}/v8/finance/chart/{symbol}",
                params={"interval": yi, "range": rng, "includePrePost": "false"},
                headers=UA_HEADERS,
                timeout=15,
            )
            r.raise_for_status()
            res = r.json()["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            data = _empty()
            _fill(
                data,
                q["open"], q["high"], q["low"], q["close"],
                q.get("volume"), res["timestamp"],
            )
            if len(data["close"]) < 50:
                raise RuntimeError("too few candles")
            if not data["close_time"]:
                data.pop("close_time")
            return data
        except Exception as e:
            last_err = e
    raise RuntimeError(f"yahoo failed for {symbol}: {last_err}")


def fetch_market(source: str, symbol: str, interval: str, limit: int = 300):
    if source == "binance":
        return fetch_binance(symbol, interval, limit)
    return fetch_yahoo(symbol, interval)
