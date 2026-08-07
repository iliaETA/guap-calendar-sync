import json
import re

from bs4 import BeautifulSoup


DAYS = {
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
}


def parse_pair_info(text):
    match = re.search(
        r"(\d+)\s+пара\s*\((\d{1,2}:\d{2})—(\d{1,2}:\d{2})\)",
        text,
    )

    if not match:
        return None

    return {
        "pair": int(match.group(1)),
        "start": match.group(2),
        "end": match.group(3),
    }


def parse_schedule():
    with open("data/page.html", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    schedule = []
    current_day = None
    current_pair = None

    for tag in soup.find_all(["h4", "div"]):

        # Определяем день недели
        if tag.name == "h4":
            day = tag.get_text(strip=True)

            if day in DAYS:
                current_day = day

        classes = tag.get("class", [])

        # Определяем номер пары и время
        if "mt-3" in classes and "text-danger" in classes:
            pair_info = parse_pair_info(
                tag.get_text(" ", strip=True)
            )

            if pair_info:
                current_pair = pair_info

        # Ищем блок занятия
        if "mb-3" in classes and "gap-2" in classes:

            # Пропускаем занятия вне сетки
            if current_day is None or current_pair is None:
                continue

            subject = tag.find("div", class_="lead lh-sm")

            if not subject:
                continue

            # Тип занятия
            lesson_type = tag.find(
                "div",
                class_="fs-6 lh-sm opacity-50",
            )

            # Неделя
            week_element = tag.find(
                ["div"],
                class_=lambda classes: classes
                and ("week1" in classes or "week2" in classes),
            )

            week = "every"

            if week_element:
                classes = week_element.get("class", [])

                if "week1" in classes:
                    week = "upper"

                elif "week2" in classes:
                    week = "lower"

            # Аудитория
            room = None

            room_link = tag.find(
                "a",
                href=lambda href: href
                and href.startswith("?ad="),
            )

            if room_link:
                room = room_link.get_text(
                    " ",
                    strip=True,
                )

            # Преподаватель
            teacher = None

            teacher_link = tag.find(
                "a",
                href=lambda href: href
                and href.startswith("?pr="),
            )

            if teacher_link:
                teacher = teacher_link.get_text(
                    " ",
                    strip=True,
                ).rstrip(".")

            schedule.append(
                {
                    "day": current_day,
                    "pair": current_pair["pair"],
                    "start": current_pair["start"],
                    "end": current_pair["end"],
                    "type": (
                        lesson_type.get_text(" ", strip=True)
                        if lesson_type
                        else None
                    ),
                    "subject": subject.get_text(
                        " ",
                        strip=True,
                    ),
                    "room": room,
                    "teacher": teacher,
                    "week": week,
                }
            )

    return schedule


schedule = parse_schedule()

with open(
    "data/schedule.json",
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        schedule,
        f,
        ensure_ascii=False,
        indent=2,
    )

print(f"Найдено занятий: {len(schedule)}")