import json
import os
import time

from exchange import fetch_market

BASE = os.path.dirname(os.path.abspath(__file__))
TRADES_FILE = os.path.join(BASE, "open_trades.json")


def _load():
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save(trades):
    with open(TRADES_FILE, "w", encoding="utf-8") as f:
        json.dump(trades, f, ensure_ascii=False)


def add_trade(sig, source, symbol, name):
    trades = _load()
    trades.append({
        "id": f"{source}_{symbol}_{sig['direction']}_{int(time.time())}",
        "source": source,
        "symbol": symbol,
        "name": name,
        "direction": sig["direction"],
        "entry": float(sig["entry"]),
        "sl": float(sig["stop_loss"]),
        "tp": float(sig["take_profit"]),
        "sent_at": time.time(),
    })
    _save(trades)


def _tf_minutes(tf):
    return int(tf[:-1]) * {"m": 1, "h": 60, "d": 1440}[tf[-1]]


def check_trades(cfg):
    """Resolve open trades against recent candles. Returns (results, still_open)."""
    trades = _load()
    if not trades:
        return [], []
    max_bars = int(cfg.get("max_hold_bars", 20))
    remaining = []
    results = []
    for t in trades:
        outcome = None
        exit_price = None
        r_val = 0.0
        try:
            raw = fetch_market(t["source"], t["symbol"], cfg["timeframe"], limit=100)
            ts = [int(x) for x in raw["open_time"]]
            unit_ms = ts[-1] > 1e12
            sent_ms = t["sent_at"] * 1000
            start_idx = len(ts) - 1
            for i, v in enumerate(ts):
                if (v if unit_ms else v * 1000) >= sent_ms:
                    start_idx = i
                    break
            risk = abs(t["entry"] - t["sl"])
            long_dir = t["direction"] == "LONG"
            resolved = False
            j = start_idx + 1
            while j < len(ts):
                lo, hi = float(raw["low"][j]), float(raw["high"][j])
                if long_dir:
                    if lo <= t["sl"]:
                        outcome, exit_price, r_val = "SL", t["sl"], -1.0
                        resolved = True
                        break
                    if hi >= t["tp"]:
                        outcome, exit_price, r_val = "TP", t["tp"], round(abs(t["tp"] - t["entry"]) / risk, 2)
                        resolved = True
                        break
                else:
                    if hi >= t["sl"]:
                        outcome, exit_price, r_val = "SL", t["sl"], -1.0
                        resolved = True
                        break
                    if lo <= t["tp"]:
                        outcome, exit_price, r_val = "TP", t["tp"], round(abs(t["entry"] - t["tp"]) / risk, 2)
                        resolved = True
                        break
                j += 1
            if not resolved and (len(ts) - 1 - start_idx) >= max_bars:
                close = float(raw["close"][-1])
                r_val = round(((close - t["entry"]) / risk) * (1 if long_dir else -1), 2)
                outcome = "TIME_WIN" if r_val > 0 else "TIME_LOSS"
                exit_price = close
        except Exception:
            outcome = None
        if outcome:
            results.append({**t, "outcome": outcome, "exit": exit_price, "r": r_val})
        else:
            remaining.append(t)
    if results:
        _save(remaining)
    return results, remaining


def format_outcome(o):
    labels = {
        "TP": "✅ حققت الهدف!",
        "SL": "❌ ضربت وقف الخسارة",
        "TIME_WIN": "⏱️ انتهت المدة — إغلاق بربح",
        "TIME_LOSS": "⏱️ انتهت المدة — إغلاق بخسارة",
    }
    d = "🟢 شراء LONG" if o["direction"] == "LONG" else "🔴 بيع SHORT"
    lines = [
        f"📊 نتيجة صفقة {o['name']}",
        d,
        f"الدخول: {o['entry']} | الخروج: {o['exit']}",
        f"{labels[o['outcome']]} ({o['r']:+.2f}R)",
    ]
    return "\n".join(lines)
