import unittest
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from src.caldav_sync import (
    DesiredEvent,
    RemoteEvent,
    build_plan,
    mail_principal_url,
    sync_to_mail_caldav,
)


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

    @patch("src.caldav_sync.get_davclient")
    def test_mail_connection_forces_basic_auth(self, get_davclient):
        client = MagicMock()
        get_davclient.return_value.__enter__.return_value = client
        client.principal.return_value.get_calendars.return_value = []
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "не найден"):
                sync_to_mail_caldav(
                    [],
                    url="https://calendar.mail.ru/",
                    username="calendar@example.com",
                    password="app-password",
                    calendar_name="ГУАП",
                    semester_start=date(2026, 9, 1),
                    semester_end=date(2027, 1, 31),
                    week_one_monday=date(2026, 8, 31),
                    tz_name="Europe/Moscow",
                    source_url="https://guap.ru/rasp?gr=7147",
                    state_file=Path(directory) / "state.json",
                )
        get_davclient.assert_called_once_with(
            url="https://calendar.mail.ru/",
            username="calendar@example.com",
            password="app-password",
            auth_type="basic",
        )
        client.principal.assert_called_once_with(
            url="https://calendar.mail.ru/principals/example.com/calendar/"
        )

    def test_mail_principal_url_requires_full_email(self):
        self.assertEqual(
            mail_principal_url("https://calendar.mail.ru/", "user.name@MAIL.RU"),
            "https://calendar.mail.ru/principals/mail.ru/user.name/",
        )
        with self.assertRaisesRegex(ValueError, "полным email"):
            mail_principal_url("https://calendar.mail.ru/", "user.name")


if __name__ == "__main__":
    unittest.main()
