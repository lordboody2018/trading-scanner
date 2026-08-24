import requests


def send_message(token: str, chat_id: str, text: str) -> bool:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=15,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[telegram] send failed: {e}")
        return False


def format_signal(symbol: str, tf: str, sig: dict) -> str:
    emoji = "\U0001F7E2" if sig["direction"] == "LONG" else "\U0001F534"
    lines = [
        f"{emoji} <b>{sig['direction']} {symbol}</b> ({tf})",
        f"\U0001F3AF الدخول: <code>{sig['entry']}</code>",
        f"\U0001F6E1️ وقف الخسارة: <code>{sig['stop_loss']}</code>",
        f"\U0001F4B0 الهدف: <code>{sig['take_profit']}</code>",
        f"RSI: {sig['rsi']} | تقلب: {sig['atr_pct']}%",
    ]
    return "\n".join(lines)
