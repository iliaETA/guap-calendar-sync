import json

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

print("Добавлено:", len(added))
print("Удалено:", len(removed))

if not added and not removed:
    print("Изменений нет")