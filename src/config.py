"""Environment-driven application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]


def _date(name: str, default: str) -> date:
    return date.fromisoformat(os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    schedule_url: str
    academic_week_one_monday: date
    semester_start: date
    semester_end: date
    timezone: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    caldav_url: str
    caldav_username: str | None
    caldav_app_password: str | None
    caldav_calendar_name: str
    schedule_file: Path
    previous_file: Path
    metadata_file: Path
    calendar_file: Path
    caldav_state_file: Path

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(ROOT / ".env")
        settings = cls(
            schedule_url=os.getenv("GUAP_SCHEDULE_URL", "https://guap.ru/rasp?gr=7147"),
            academic_week_one_monday=_date("ACADEMIC_WEEK_ONE_MONDAY", "2026-08-31"),
            semester_start=_date("SEMESTER_START", "2026-09-01"),
            semester_end=_date("SEMESTER_END", "2027-01-31"),
            timezone=os.getenv("TIMEZONE", "Europe/Moscow"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            caldav_url=os.getenv("MAIL_CALDAV_URL", "https://calendar.mail.ru"),
            caldav_username=os.getenv("MAIL_CALDAV_USERNAME"),
            caldav_app_password=os.getenv("MAIL_CALDAV_APP_PASSWORD"),
            caldav_calendar_name=os.getenv("MAIL_CALENDAR_NAME", "ГУАП"),
            schedule_file=ROOT / "data" / "schedule.json",
            previous_file=ROOT / "data" / "schedule_previous.json",
            metadata_file=ROOT / "data" / "metadata.json",
            calendar_file=ROOT / "docs" / "calendar.ics",
            caldav_state_file=ROOT / "data" / "caldav_state.json",
        )
        if settings.academic_week_one_monday.weekday() != 0:
            raise ValueError("ACADEMIC_WEEK_ONE_MONDAY должен быть понедельником")
        if settings.semester_start > settings.semester_end:
            raise ValueError("SEMESTER_START не может быть позже SEMESTER_END")
        if bool(settings.caldav_username) != bool(settings.caldav_app_password):
            raise ValueError("MAIL_CALDAV_USERNAME и MAIL_CALDAV_APP_PASSWORD задаются вместе")
        return settings
