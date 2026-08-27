"""One complete schedule synchronization run."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

from .calendar_export import build_calendar
from .config import Settings
from .diff import diff_schedules, format_changes
from .download_schedule import download_schedule
from .parse_schedule import parse_page_info, parse_schedule
from .sync import send_telegram


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def write_json_atomic(path: Path, value) -> None:
    write_text_atomic(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def run(settings: Settings) -> tuple[int, int]:
    print(f"Скачиваем расписание: {settings.schedule_url}")
    html = download_schedule(settings.schedule_url)
    schedule = parse_schedule(html)
    metadata = parse_page_info(html)
    print(f"Группа {metadata.get('group') or 'не определена'}: найдено занятий — {len(schedule)}")

    old_schedule = read_json(settings.schedule_file, [])
    added, removed = diff_schedules(old_schedule, schedule)
    stamp = date.fromisoformat(metadata["build_date"]) if metadata.get("build_date") else settings.semester_start
    calendar = build_calendar(
        schedule=schedule,
        semester_start=settings.semester_start,
        semester_end=settings.semester_end,
        week_one_monday=settings.academic_week_one_monday,
        tz_name=settings.timezone,
        source_url=settings.schedule_url,
        calendar_name=f"ГУАП — {metadata.get('group') or 'расписание'}",
        stamp=stamp,
    )
    write_text_atomic(settings.calendar_file, calendar)
    write_json_atomic(settings.metadata_file, {**metadata, "source_url": settings.schedule_url})

    if added or removed:
        print(f"Изменения: +{len(added)} / -{len(removed)}")
        if settings.telegram_bot_token and settings.telegram_chat_id:
            send_telegram(format_changes(added, removed), settings.telegram_bot_token, settings.telegram_chat_id)
            print("Telegram-уведомление отправлено")
        else:
            print("Telegram не настроен; уведомление пропущено")

        if settings.schedule_file.exists():
            settings.previous_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(settings.schedule_file, settings.previous_file)
        write_json_atomic(settings.schedule_file, schedule)
    else:
        print("Изменений нет")

    print(f"Календарь обновлён: {settings.calendar_file}")
    return len(added), len(removed)


def main() -> None:
    run(Settings.from_env())


if __name__ == "__main__":
    main()
