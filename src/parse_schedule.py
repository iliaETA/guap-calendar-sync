"""Parse and validate the extended GUAP schedule page."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


DAYS = {
    "Понедельник": 0,
    "Вторник": 1,
    "Среда": 2,
    "Четверг": 3,
    "Пятница": 4,
    "Суббота": 5,
}
WEEKS = {"upper", "lower", "every"}
PAIR_RE = re.compile(r"(\d+)\s+пара\s*\((\d{1,2}:\d{2})\s*[—–-]\s*(\d{1,2}:\d{2})\)")


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip() or None


def parse_pair_info(text: str) -> dict[str, Any] | None:
    match = PAIR_RE.search(text)
    if not match:
        return None
    return {"pair": int(match.group(1)), "start": match.group(2), "end": match.group(3)}


def parse_page_info(html: str) -> dict[str, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    build = re.search(r"сборка:\s*(\d{4}-\d{2}-\d{2})", text)
    result = soup.select_one("#result")
    group = None
    if result:
        group_match = re.search(r"гр\.\s*(.+)$", clean_text(result.get_text(" ")) or "")
        group = group_match.group(1) if group_match else None
    semester = soup.select_one("p.lead.text-success")
    return {
        "build_date": build.group(1) if build else None,
        "group": group,
        "semester": clean_text(semester.get_text(" ")) if semester else None,
    }


def parse_schedule(html: str | None = None, path: str | Path = "data/page.html") -> list[dict[str, Any]]:
    if html is None:
        html = Path(path).read_text(encoding="utf-8")

    soup = BeautifulSoup(html, "html.parser")
    schedule: list[dict[str, Any]] = []
    current_day: str | None = None
    current_pair: dict[str, Any] | None = None

    for tag in soup.find_all(["h4", "div"]):
        if tag.name == "h4":
            heading = clean_text(tag.get_text(" "))
            if heading in DAYS:
                current_day = heading
                current_pair = None

        classes = set(tag.get("class", []))
        if {"mt-3", "text-danger"}.issubset(classes):
            current_pair = parse_pair_info(tag.get_text(" ", strip=True))
            continue

        if not {"mb-3", "gap-2"}.issubset(classes) or not current_day or not current_pair:
            continue

        subject = tag.select_one("div.lead.lh-sm")
        if not subject:
            continue

        marker = tag.select_one("div.week1, div.week2")
        marker_classes = set(marker.get("class", [])) if marker else set()
        week = "upper" if "week1" in marker_classes else "lower" if "week2" in marker_classes else "every"
        lesson_type = tag.select_one("div.fs-6.lh-sm.opacity-50")
        room_link = tag.find("a", href=lambda href: bool(href and href.startswith("?ad=")))
        teacher_link = tag.find("a", href=lambda href: bool(href and href.startswith("?pr=")))
        teacher = clean_text(teacher_link.get_text(" ")) if teacher_link else None

        schedule.append(
            {
                "day": current_day,
                **current_pair,
                "type": clean_text(lesson_type.get_text(" ")) if lesson_type else None,
                "subject": clean_text(subject.get_text(" ")),
                "room": clean_text(room_link.get_text(" ")) if room_link else None,
                "teacher": teacher.rstrip(".") if teacher else None,
                "week": week,
            }
        )

    validate_schedule(schedule)
    return schedule


def validate_schedule(schedule: list[dict[str, Any]]) -> None:
    if not schedule:
        raise ValueError("Парсер не нашёл ни одного занятия; старые данные сохранены")

    seen: set[tuple[Any, ...]] = set()
    identity_keys = ("day", "pair", "start", "end", "type", "subject", "room", "teacher", "week")
    for number, lesson in enumerate(schedule, start=1):
        if lesson.get("day") not in DAYS:
            raise ValueError(f"Занятие {number}: неизвестный день")
        if lesson.get("week") not in WEEKS:
            raise ValueError(f"Занятие {number}: неизвестный тип недели")
        if not lesson.get("subject"):
            raise ValueError(f"Занятие {number}: нет названия дисциплины")
        start = datetime.strptime(lesson["start"], "%H:%M").time()
        end = datetime.strptime(lesson["end"], "%H:%M").time()
        if start >= end:
            raise ValueError(f"Занятие {number}: некорректное время")
        identity = tuple(lesson.get(key) for key in identity_keys)
        if identity in seen:
            raise ValueError(f"Парсер создал дубликат занятия: {lesson['subject']}")
        seen.add(identity)
