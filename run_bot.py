import json
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd

from exchange import fetch_market
from backtest import quick_stats
from sentiment import get_current_fng
from strategy import evaluate
import tracker
from telegram_alert import format_signal, send_message

BASE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE, "signals_state.json")
LOG_FILE = os.path.join(BASE, "signals_log.csv")


def load_cfg():
    with open(os.path.join(BASE, "config.json"), encoding="utf-8-sig") as f:
        return json.load(f)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def log_signal(cfg, symbol, sig):
    new_file = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        if new_file:
            f.write("time,market,symbol,timeframe,direction,entry,stop_loss,take_profit,rsi\n")
        f.write(
            f"{datetime.now(timezone.utc).isoformat()},{sig.get('source')},{symbol},{cfg['timeframe']},"
            f"{sig['direction']},{sig['entry']},{sig['stop_loss']},{sig['take_profit']},{sig['rsi']}\n"
        )


def pretty(symbol: str) -> str:
    if symbol.endswith("=X"):
        s = symbol[:-2]
        if len(s) == 6:
            return f"{s[:3]}/{s[3:]}"
    if symbol.startswith("^"):
        return {"^GSPC": "S&P 500", "^NDX": "NASDAQ"}.get(symbol, symbol)
    if symbol == "CL=F":
        return "النفط"
    if symbol == "GC=F":
        return "الذهب"
    return symbol


def scan_once(cfg, state):
    now = time.time()
    cooldown_sec = cfg.get("cooldown_hours", 6) * 3600
    try:
        outcomes, _ = tracker.check_trades(cfg)
        for o in outcomes:
            msg = tracker.format_outcome(o)
            if send_message(cfg["telegram_bot_token"], cfg["telegram_chat_id"], msg):
                print(f"[{o['name']}] outcome sent: {o['outcome']} ({o['r']:+.2f}R)")
    except Exception as e:
        print(f"tracker error: {e}")

    jobs = [("binance", s) for s in cfg.get("crypto_symbols", cfg.get("symbols", []))]
    jobs += [("yahoo", s) for s in cfg.get("market_symbols", [])]

    for source, symbol in jobs:
        try:
            raw = fetch_market(source, symbol, cfg["timeframe"], limit=1000)
        except Exception as e:
            print(f"[{symbol}] data error: {e}")
            continue
        raw = {k: v[:-1] for k, v in raw.items()}
        df = pd.DataFrame(raw)
        fng_val = get_current_fng() if source == "binance" else None
        sig = evaluate(df, cfg, fng_val)
        if sig is None:
            print(f"[{pretty(symbol)}] لا إشارة")
            continue

        key = f"{source}_{symbol}_{sig['direction']}"
        last_sent = state.get(key, 0)
        if now - last_sent < cooldown_sec:
            print(f"[{pretty(symbol)}] {sig['direction']} on cooldown")
            continue

        sig["source"] = source
        st = quick_stats(cfg, source, symbol)
        if st:
            sig["win_rate"] = st["win_rate"]
            sig["hist_trades"] = st["trades"]
        min_wr = float(cfg.get("min_win_rate", 60))
        if not st or sig.get("win_rate", 0) < min_wr:
            print(f"[{pretty(symbol)}] {sig['direction']} skipped: WR={sig.get('win_rate', '?')}% < {min_wr}%")
            continue
        msg = f"🌐 {pretty(symbol)}\n" + format_signal(symbol, cfg["timeframe"], sig)
        if send_message(cfg["telegram_bot_token"], cfg["telegram_chat_id"], msg):
            state[key] = now
            save_state(state)
            log_signal(cfg, symbol, sig)
            tracker.add_trade(sig, source, symbol, pretty(symbol))
            print(f"[{pretty(symbol)}] ALERT sent: {sig['direction']} entry={sig['entry']}")


def main():
    cfg = load_cfg()
    token = cfg.get("telegram_bot_token", "")
    chat_id = cfg.get("telegram_chat_id", "")

    if "--test" in sys.argv:
        ok = send_message(token, chat_id, "\u2705 البوت شغال ومرتبط بحسابك على تليجرام")
        print("telegram test:", "OK" if ok else "FAILED - راجع التوكن والشات ايدي في config.json")
        return

    state = load_state()

    if "--once" in sys.argv:
        scan_once(cfg, state)
        return
    interval = int(cfg.get("scan_interval_sec", 90))
    n_crypto = len(cfg.get("crypto_symbols", cfg.get("symbols", [])))
    n_market = len(cfg.get("market_symbols", []))
    print(f"Bot started | crypto: {n_crypto} | forex/metals/indices: {n_market} | every {interval}s")
    while True:
        try:
            scan_once(cfg, state)
        except Exception as e:
            print(f"scan error: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
