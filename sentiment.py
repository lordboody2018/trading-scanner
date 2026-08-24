import requests

FNG_URL = "https://api.alternative.me/fng/"


def get_fng_map(limit: int = 90):
    """Returns dict date_str(YYYY-MM-DD UTC) -> int value"""
    try:
        r = requests.get(FNG_URL, params={"limit": limit, "format": "json"}, timeout=15)
        r.raise_for_status()
        out = {}
        for row in r.json().get("data", []):
            ts = int(row["timestamp"])
            import datetime
            d = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
            out[d] = int(row["value"])
        return out
    except Exception:
        return {}


def get_current_fng():
    try:
        r = requests.get(FNG_URL, params={"limit": 1, "format": "json"}, timeout=15)
        r.raise_for_status()
        return int(r.json()["data"][0]["value"])
    except Exception:
        return None
