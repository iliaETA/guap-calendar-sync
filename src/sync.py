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


def lesson_to_text(item):
    return (
        f"{item['day']}\n"
        f"{item['pair']} пара ({item['start']}-{item['end']})\n"
        f"{item['subject']}\n"
        f"{item['room']}"
    )


with open("data/schedule_previous.json", encoding="utf-8") as f:
    old_schedule = json.load(f)

with open("data/schedule.json", encoding="utf-8") as f:
    new_schedule = json.load(f)

old_set = {
    json.dumps(item, ensure_ascii=False, sort_keys=True): item
    for item in old_schedule
}

new_set = {
    json.dumps(item, ensure_ascii=False, sort_keys=True): item
    for item in new_schedule
}

added_keys = set(new_set.keys()) - set(old_set.keys())
removed_keys = set(old_set.keys()) - set(new_set.keys())

if not added_keys and not removed_keys:
    print("Изменений нет")

else:

    message = "🔔 Изменения в расписании\n\n"

    if added_keys:
        message += "➕ Добавлено\n\n"

        for key in added_keys:
            message += lesson_to_text(new_set[key])
            message += "\n\n"

    if removed_keys:
        message += "➖ Удалено\n\n"

        for key in removed_keys:
            message += lesson_to_text(old_set[key])
            message += "\n\n"

    send_telegram(message)

    print(message)