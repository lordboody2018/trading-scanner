import json
import os
import sys
import time

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(BASE, "config.json")


def load_cfg():
    with open(CONFIG, encoding="utf-8-sig") as f:
        return json.load(f)


def save_cfg(cfg):
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)


def main():
    print("=" * 50)
    print("   إعداد البوت التلقائي - خطوتين وخلاص")
    print("=" * 50)

    token = input("\n1) الصق التوكن من @BotFather ثم اضغط Enter:\n> ").strip()
    if not token or ":" not in token:
        print("❌ التوكن غير صحيح - لازم يكون زي: 7123456789:AAHxxx...")
        sys.exit(1)

    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15).json()
        if not r.get("ok"):
            raise RuntimeError(r)
        bot_name = r["result"]["username"]
        print(f"\n✅ التوكن سليم - البوت اسمه: @{bot_name}")
    except Exception as e:
        print(f"❌ فشل التحقق من التوكن: {e}")
        sys.exit(1)

    print(f"\n2) افتح تليجرام دلوقتي وافتح بوتك @{bot_name}")
    print("   وابعتله أي رسالة (مثلاً: hi)")
    print("   استنى... عمودرد على رسالتك تلقائي...")

    chat_id = None
    offset = 0
    for _ in range(60):
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"timeout": 5, "offset": offset},
                timeout=20,
            ).json()
            for upd in r.get("result", []):
                offset = max(offset, upd["update_id"] + 1)
                msg = upd.get("message") or upd.get("edited_message")
                if msg and msg.get("chat", {}).get("id"):
                    chat_id = msg["chat"]["id"]
                    break
            if chat_id:
                break
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(1)

    if not chat_id:
        print("\n❌ مجيتش رسالة - اتأكد إنك بعتت رسالة للبوت وحاول تاني")
        sys.exit(1)

    cfg = load_cfg()
    cfg["telegram_bot_token"] = token
    cfg["telegram_chat_id"] = str(chat_id)
    save_cfg(cfg)

    ok = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": "\u2705 تم الربط بنجاح! البوت جاهز يبعتلك الإشارات"},
        timeout=15,
    ).json()

    print(f"\n\n✅ تم الربط! الشات ايدي: {chat_id}")
    if ok.get("ok"):
        print("✅ بعتلتك رسالة تأكيد على تليجرام")
    print("\n🚀 شغّل البوت بكتابة:  python run_bot.py")
    print("   أو دبل كليك على ملف:  تشغيل_البوت.bat")


if __name__ == "__main__":
    main()
