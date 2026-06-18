"""Envío de notificaciones a Telegram vía Bot API — Arkana Lead Gen."""
import os
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send_telegram(message):
    """Envía un mensaje Markdown a Telegram. Devuelve True si se entregó."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"\n[Telegram no configurado]\n{message}")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=data, timeout=10)
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"  !  Telegram error: {e}")
        return False
