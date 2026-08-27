"""Stable schedule comparison and human-readable change messages."""

from __future__ import annotations

import json

from .parse_schedule import DAYS


def _key(item: dict) -> str:
    return json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def diff_schedules(old: list[dict], new: list[dict]) -> tuple[list[dict], list[dict]]:
    old_map = {_key(item): item for item in old}
    new_map = {_key(item): item for item in new}
    sort_key = lambda item: (DAYS.get(item["day"], 99), item["pair"], item["week"], item["subject"])
    added = sorted((new_map[key] for key in new_map.keys() - old_map.keys()), key=sort_key)
    removed = sorted((old_map[key] for key in old_map.keys() - new_map.keys()), key=sort_key)
    return added, removed


def lesson_to_text(item: dict) -> str:
    week = {"upper": "верхняя неделя", "lower": "нижняя неделя", "every": "каждую неделю"}[item["week"]]
    details = [
        f"{item['day']}, {item['pair']} пара ({item['start']}–{item['end']})",
        f"{item['subject']} — {week}",
    ]
    if item.get("room"):
        details.append(f"Аудитория: {item['room']}")
    if item.get("teacher"):
        details.append(f"Преподаватель: {item['teacher']}")
    return "\n".join(details)


def format_changes(added: list[dict], removed: list[dict]) -> str:
    sections = ["🔔 Изменения в расписании"]
    if added:
        sections.append("➕ Добавлено\n\n" + "\n\n".join(lesson_to_text(item) for item in added))
    if removed:
        sections.append("➖ Удалено\n\n" + "\n\n".join(lesson_to_text(item) for item in removed))
    return "\n\n".join(sections)
