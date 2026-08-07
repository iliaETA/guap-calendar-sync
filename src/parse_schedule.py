import json
from bs4 import BeautifulSoup

with open("data/page.html", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

schedule = []

current_day = None
current_pair = None
current_time = None

for tag in soup.find_all(["h4", "div"]):

    if tag.name == "h4":
        day = tag.get_text(strip=True)

        if day in [
            "Понедельник",
            "Вторник",
            "Среда",
            "Четверг",
            "Пятница",
            "Суббота",
        ]:
            current_day = day

    classes = tag.get("class", [])

    if "mt-3" in classes and "text-danger" in classes:
        text = tag.get_text(" ", strip=True)

        current_pair = text

    if "mb-3" in classes and "gap-2" in classes:

        subject = tag.find("div", class_="lead lh-sm")

        if subject:

            schedule.append(
                {
                    "day": current_day,
                    "pair_info": current_pair,
                    "subject": subject.get_text(strip=True),
                }
            )

with open("data/schedule.json", "w", encoding="utf-8") as f:
    json.dump(schedule, f, ensure_ascii=False, indent=2)

print(f"Найдено занятий: {len(schedule)}")