"""Build a subscription-friendly iCalendar feed."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .parse_schedule import DAYS


def academic_week_type(day: date, week_one_monday: date) -> str:
    number = ((day - week_one_monday).days // 7) + 1
    return "upper" if number % 2 else "lower"


def _escape(value: str | None) -> str:
    return (value or "").replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


def _fold(line: str) -> list[str]:
    chunks: list[str] = []
    remaining = line
    first = True
    while remaining:
        byte_limit = 75 if first else 74  # one byte is reserved for the continuation space
        used = 0
        index = 0
        for char in remaining:
            size = len(char.encode("utf-8"))
            if used + size > byte_limit:
                break
            used += size
            index += 1
        if index == 0:
            index = 1
        chunk, remaining = remaining[:index], remaining[index:]
        chunks.append(chunk if first else " " + chunk)
        first = False
    return chunks or [""]


def _event_dates(lesson: dict, start: date, end: date, anchor: date):
    current = start
    target_weekday = DAYS[lesson["day"]]
    current += timedelta(days=(target_weekday - current.weekday()) % 7)
    while current <= end:
        if lesson["week"] == "every" or lesson["week"] == academic_week_type(current, anchor):
            yield current
        current += timedelta(days=7)


def build_calendar(
    schedule: list[dict],
    semester_start: date,
    semester_end: date,
    week_one_monday: date,
    tz_name: str,
    source_url: str,
    calendar_name: str,
    stamp: date | None = None,
) -> str:
    tz = ZoneInfo(tz_name)
    stamp_value = datetime.combine(stamp or semester_start, time(), timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//guap-calendar-sync//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(calendar_name)}",
        f"X-WR-TIMEZONE:{tz_name}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
        "X-PUBLISHED-TTL:PT1H",
    ]

    for lesson in schedule:
        start_time = datetime.strptime(lesson["start"], "%H:%M").time()
        end_time = datetime.strptime(lesson["end"], "%H:%M").time()
        for event_date in _event_dates(lesson, semester_start, semester_end, week_one_monday):
            starts = datetime.combine(event_date, start_time, tz).astimezone(timezone.utc)
            ends = datetime.combine(event_date, end_time, tz).astimezone(timezone.utc)
            raw_uid = "|".join(str(lesson.get(key) or "") for key in ("day", "pair", "week", "subject", "room", "teacher"))
            uid = hashlib.sha256(f"{event_date}|{raw_uid}".encode()).hexdigest()[:32]
            description = " · ".join(filter(None, [lesson.get("type"), lesson.get("teacher")]))
            event = [
                "BEGIN:VEVENT",
                f"UID:{uid}@guap-calendar-sync",
                f"DTSTAMP:{stamp_value}",
                f"DTSTART:{starts.strftime('%Y%m%dT%H%M%SZ')}",
                f"DTEND:{ends.strftime('%Y%m%dT%H%M%SZ')}",
                f"SUMMARY:{_escape(lesson['subject'])}",
                f"LOCATION:{_escape(lesson.get('room'))}",
                f"DESCRIPTION:{_escape(description)}",
                f"URL:{source_url}",
                "STATUS:CONFIRMED",
                "END:VEVENT",
            ]
            for line in event:
                lines.extend(_fold(line))

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
