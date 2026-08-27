"""Two-way synchronization with a dedicated Mail.ru CalDAV calendar.

Events edited by the user are treated as manual overrides. Events deleted by
the user receive a local tombstone and are not recreated on the next run.
Only VEVENT objects carrying X-GUAP-SOURCE-ID are ever modified or deleted.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from caldav import get_davclient
from icalendar import Calendar as ICalendar
from icalendar import Event as IEvent

from .calendar_export import event_dates


STATE_VERSION = 1
SOURCE_ID_PROPERTY = "X-GUAP-SOURCE-ID"
MANAGED_FP_PROPERTY = "X-GUAP-MANAGED-FP"


@dataclass(frozen=True)
class DesiredEvent:
    source_id: str
    uid: str
    start: datetime
    end: datetime
    summary: str
    location: str
    description: str
    source_url: str

    @property
    def fingerprint(self) -> str:
        return event_fingerprint(
            self.start,
            self.end,
            self.summary,
            self.location,
            self.description,
        )


@dataclass
class RemoteEvent:
    source_id: str
    uid: str
    fingerprint: str
    managed_fingerprint: str | None
    resource: Any = None


@dataclass(frozen=True)
class Operation:
    kind: str
    source_id: str


def _normalized_datetime(value: datetime | date) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return value.isoformat()


def event_fingerprint(start, end, summary, location, description) -> str:
    payload = {
        "start": _normalized_datetime(start),
        "end": _normalized_datetime(end),
        "summary": str(summary or "").strip(),
        "location": str(location or "").strip(),
        "description": str(description or "").strip(),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_desired_events(
    schedule: list[dict],
    semester_start: date,
    semester_end: date,
    week_one_monday: date,
    tz_name: str,
    source_url: str,
) -> dict[str, DesiredEvent]:
    tz = ZoneInfo(tz_name)
    candidates: list[tuple[str, dict, date]] = []
    for lesson in schedule:
        for event_date in event_dates(lesson, semester_start, semester_end, week_one_monday):
            base_id = f"{event_date.isoformat()}|pair={lesson['pair']}|week={lesson['week']}"
            candidates.append((base_id, lesson, event_date))

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1]["subject"],
            item[1].get("type") or "",
            item[1].get("room") or "",
        )
    )
    totals: dict[str, int] = {}
    for base_id, _, _ in candidates:
        totals[base_id] = totals.get(base_id, 0) + 1

    indexes: dict[str, int] = {}
    desired: dict[str, DesiredEvent] = {}
    for base_id, lesson, event_date in candidates:
        indexes[base_id] = indexes.get(base_id, 0) + 1
        source_id = base_id if totals[base_id] == 1 else f"{base_id}|slot={indexes[base_id]}"
        start_time = datetime.strptime(lesson["start"], "%H:%M").time()
        end_time = datetime.strptime(lesson["end"], "%H:%M").time()
        starts = datetime.combine(event_date, start_time, tz)
        ends = datetime.combine(event_date, end_time, tz)
        uid_hash = hashlib.sha256(f"guap|{source_id}".encode()).hexdigest()[:32]
        description = "\n".join(
            part for part in (lesson.get("type"), lesson.get("teacher"), source_url) if part
        )
        desired[source_id] = DesiredEvent(
            source_id=source_id,
            uid=f"{uid_hash}@guap-calendar-sync",
            start=starts,
            end=ends,
            summary=lesson["subject"],
            location=lesson.get("room") or "",
            description=description,
            source_url=source_url,
        )
    return desired


def build_plan(
    desired: dict[str, DesiredEvent],
    remote: dict[str, RemoteEvent],
    old_state: dict,
) -> tuple[list[Operation], dict]:
    state_events = dict(old_state.get("events", {}))
    new_events: dict[str, dict] = {}
    operations: list[Operation] = []

    for source_id in sorted(set(desired) | set(remote) | set(state_events)):
        wanted = desired.get(source_id)
        found = remote.get(source_id)
        previous = state_events.get(source_id)
        previous_status = previous.get("status") if previous else None

        if wanted:
            if not found:
                if previous_status == "deleted_by_user":
                    new_events[source_id] = previous
                elif previous_status in {"managed", "manual_override", "orphaned_manual"}:
                    new_events[source_id] = {
                        **previous,
                        "status": "deleted_by_user",
                    }
                else:
                    operations.append(Operation("create", source_id))
                    new_events[source_id] = {
                        "uid": wanted.uid,
                        "status": "managed",
                        "managed_fingerprint": wanted.fingerprint,
                    }
                continue

            baseline = found.managed_fingerprint or (previous or {}).get("managed_fingerprint")
            if baseline and found.fingerprint != baseline:
                new_events[source_id] = {
                    "uid": found.uid,
                    "status": "manual_override",
                    "managed_fingerprint": baseline,
                }
            elif found.fingerprint != wanted.fingerprint:
                operations.append(Operation("update", source_id))
                new_events[source_id] = {
                    "uid": found.uid,
                    "status": "managed",
                    "managed_fingerprint": wanted.fingerprint,
                }
            else:
                new_events[source_id] = {
                    "uid": found.uid,
                    "status": "managed",
                    "managed_fingerprint": wanted.fingerprint,
                }
            continue

        if found:
            baseline = found.managed_fingerprint or (previous or {}).get("managed_fingerprint")
            if baseline and found.fingerprint != baseline:
                new_events[source_id] = {
                    "uid": found.uid,
                    "status": "orphaned_manual",
                    "managed_fingerprint": baseline,
                }
            else:
                operations.append(Operation("delete", source_id))
        elif previous_status == "deleted_by_user":
            # Keep date-specific tombstones through the configured semester.
            new_events[source_id] = previous

    return operations, {"version": STATE_VERSION, "events": new_events}


def _event_component(resource):
    calendar = resource.get_icalendar_instance()
    components = calendar.walk("VEVENT")
    if not components:
        raise ValueError("CalDAV вернул объект без VEVENT")
    return components[0]


def _component_datetime(component, name: str):
    value = component.decoded(name)
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time(), timezone.utc)
    return value


def _component_text(component, name: str) -> str:
    value = component.get(name)
    return str(value).strip() if value is not None else ""


def read_remote_events(calendar, old_state: dict) -> dict[str, RemoteEvent]:
    state_by_uid = {
        item.get("uid"): source_id
        for source_id, item in old_state.get("events", {}).items()
        if item.get("uid")
    }
    result: dict[str, RemoteEvent] = {}
    for resource in calendar.get_events():
        component = _event_component(resource)
        uid = _component_text(component, "UID")
        source_id = _component_text(component, SOURCE_ID_PROPERTY) or state_by_uid.get(uid)
        if not source_id:
            continue
        if source_id in result:
            raise ValueError(f"В Mail-календаре найден дубликат управляемой пары: {source_id}")
        result[source_id] = RemoteEvent(
            source_id=source_id,
            uid=uid,
            fingerprint=event_fingerprint(
                _component_datetime(component, "DTSTART"),
                _component_datetime(component, "DTEND"),
                _component_text(component, "SUMMARY"),
                _component_text(component, "LOCATION"),
                _component_text(component, "DESCRIPTION"),
            ),
            managed_fingerprint=_component_text(component, MANAGED_FP_PROPERTY) or None,
            resource=resource,
        )
    return result


def _ical_for(desired: DesiredEvent) -> bytes:
    calendar = ICalendar()
    calendar.add("prodid", "-//guap-calendar-sync//RU")
    calendar.add("version", "2.0")
    event = IEvent()
    event.add("uid", desired.uid)
    event.add("dtstamp", datetime.now(timezone.utc))
    event.add("dtstart", desired.start)
    event.add("dtend", desired.end)
    event.add("summary", desired.summary)
    event.add("location", desired.location)
    event.add("description", desired.description)
    event.add("url", desired.source_url)
    event.add(SOURCE_ID_PROPERTY, desired.source_id)
    event.add(MANAGED_FP_PROPERTY, desired.fingerprint)
    calendar.add_component(event)
    return calendar.to_ical()


def _update_resource(resource, desired: DesiredEvent) -> None:
    with resource.edit_icalendar_instance() as calendar:
        component = calendar.walk("VEVENT")[0]
        for name in (
            "DTSTART",
            "DTEND",
            "SUMMARY",
            "LOCATION",
            "DESCRIPTION",
            "URL",
            SOURCE_ID_PROPERTY,
            MANAGED_FP_PROPERTY,
        ):
            if name in component:
                del component[name]
        component.add("dtstart", desired.start)
        component.add("dtend", desired.end)
        component.add("summary", desired.summary)
        component.add("location", desired.location)
        component.add("description", desired.description)
        component.add("url", desired.source_url)
        component.add(SOURCE_ID_PROPERTY, desired.source_id)
        component.add(MANAGED_FP_PROPERTY, desired.fingerprint)
    resource.save()


def _write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def sync_to_mail_caldav(
    schedule: list[dict],
    *,
    url: str,
    username: str,
    password: str,
    calendar_name: str,
    semester_start: date,
    semester_end: date,
    week_one_monday: date,
    tz_name: str,
    source_url: str,
    state_file: Path,
) -> dict[str, int]:
    old_state = (
        json.loads(state_file.read_text(encoding="utf-8"))
        if state_file.exists()
        else {"version": STATE_VERSION, "events": {}}
    )
    desired = build_desired_events(
        schedule,
        semester_start,
        semester_end,
        week_one_monday,
        tz_name,
        source_url,
    )

    with get_davclient(url=url, username=username, password=password) as client:
        principal = client.principal()
        calendars = principal.get_calendars()
        calendar_names = [str(item.get_display_name() or "") for item in calendars]
        matches = [item for item, name in zip(calendars, calendar_names) if name == calendar_name]
        if not matches:
            available = ", ".join(name or "<без имени>" for name in calendar_names)
            raise ValueError(f"Mail-календарь '{calendar_name}' не найден. Доступны: {available}")
        if len(matches) > 1:
            raise ValueError(f"Найдено несколько Mail-календарей с именем '{calendar_name}'")
        mail_calendar = matches[0]
        remote = read_remote_events(mail_calendar, old_state)
        operations, new_state = build_plan(desired, remote, old_state)

        counts = {"created": 0, "updated": 0, "deleted": 0, "manual": 0, "skipped": 0}
        for operation in operations:
            wanted = desired.get(operation.source_id)
            found = remote.get(operation.source_id)
            if operation.kind == "create" and wanted:
                mail_calendar.add_event(ical=_ical_for(wanted))
                counts["created"] += 1
            elif operation.kind == "update" and wanted and found:
                _update_resource(found.resource, wanted)
                counts["updated"] += 1
            elif operation.kind == "delete" and found:
                found.resource.delete()
                counts["deleted"] += 1

        for item in new_state["events"].values():
            if item["status"] in {"manual_override", "orphaned_manual"}:
                counts["manual"] += 1
            elif item["status"] == "deleted_by_user":
                counts["skipped"] += 1

    _write_state(state_file, new_state)
    return counts
