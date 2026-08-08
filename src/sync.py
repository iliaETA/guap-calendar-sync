import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": text,
        },
    )


with open("data/schedule_previous.json", encoding="utf-8") as f:
    old_schedule = json.load(f)

with open("data/schedule.json", encoding="utf-8") as f:
    new_schedule = json.load(f)

old_set = {
    json.dumps(item, ensure_ascii=False, sort_keys=True)
    for item in old_schedule
}

new_set = {
    json.dumps(item, ensure_ascii=False, sort_keys=True)
    for item in new_schedule
}

added = new_set - old_set
removed = old_set - new_set

if not added and not removed:
    print("Изменений нет")
else:
    message = (
        f"Обнаружены изменения в расписании\n\n"
        f"Добавлено: {len(added)}\n"
        f"Удалено: {len(removed)}"
    )

    send_telegram(message)

    print(message)