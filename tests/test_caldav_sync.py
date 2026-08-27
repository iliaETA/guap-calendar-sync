import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from src.caldav_sync import DesiredEvent, RemoteEvent, build_plan


class CalDAVPlanTests(unittest.TestCase):
    def desired(self, summary="Математика"):
        tz = ZoneInfo("Europe/Moscow")
        return DesiredEvent(
            source_id="2026-09-01|pair=1|week=upper",
            uid="test@guap-calendar-sync",
            start=datetime(2026, 9, 1, 9, 30, tzinfo=tz),
            end=datetime(2026, 9, 1, 11, 0, tzinfo=tz),
            summary=summary,
            location="ауд. 1",
            description="Лекция",
            source_url="https://guap.ru/rasp?gr=7147",
        )

    def test_new_event_is_created(self):
        wanted = self.desired()
        operations, state = build_plan({wanted.source_id: wanted}, {}, {})
        self.assertEqual([(item.kind, item.source_id) for item in operations], [("create", wanted.source_id)])
        self.assertEqual(state["events"][wanted.source_id]["status"], "managed")

    def test_user_edit_becomes_manual_override(self):
        wanted = self.desired()
        remote = RemoteEvent(
            wanted.source_id,
            wanted.uid,
            fingerprint="user-change",
            managed_fingerprint=wanted.fingerprint,
        )
        operations, state = build_plan({wanted.source_id: wanted}, {wanted.source_id: remote}, {})
        self.assertEqual(operations, [])
        self.assertEqual(state["events"][wanted.source_id]["status"], "manual_override")

    def test_user_deletion_creates_tombstone(self):
        wanted = self.desired()
        old_state = {
            "events": {
                wanted.source_id: {
                    "uid": wanted.uid,
                    "status": "managed",
                    "managed_fingerprint": wanted.fingerprint,
                }
            }
        }
        operations, state = build_plan({wanted.source_id: wanted}, {}, old_state)
        self.assertEqual(operations, [])
        self.assertEqual(state["events"][wanted.source_id]["status"], "deleted_by_user")

    def test_schedule_change_updates_untouched_event(self):
        old = self.desired()
        wanted = self.desired(summary="Новая математика")
        remote = RemoteEvent(old.source_id, old.uid, old.fingerprint, old.fingerprint)
        operations, state = build_plan({wanted.source_id: wanted}, {old.source_id: remote}, {})
        self.assertEqual([item.kind for item in operations], ["update"])
        self.assertEqual(state["events"][wanted.source_id]["managed_fingerprint"], wanted.fingerprint)

    def test_removed_manual_event_is_preserved(self):
        old = self.desired()
        remote = RemoteEvent(old.source_id, old.uid, "user-change", old.fingerprint)
        operations, state = build_plan({}, {old.source_id: remote}, {})
        self.assertEqual(operations, [])
        self.assertEqual(state["events"][old.source_id]["status"], "orphaned_manual")


if __name__ == "__main__":
    unittest.main()
