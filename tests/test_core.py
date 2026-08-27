import unittest
from datetime import date
from pathlib import Path

from src.calendar_export import academic_week_type, build_calendar
from src.diff import diff_schedules
from src.parse_schedule import parse_page_info, parse_pair_info, parse_schedule, validate_schedule


ROOT = Path(__file__).resolve().parents[1]


class ParserTests(unittest.TestCase):
    def test_pair_time_accepts_single_digit_hour(self):
        self.assertEqual(parse_pair_info("1 пара (9:30—11:00)"), {"pair": 1, "start": "9:30", "end": "11:00"})

    def test_saved_guap_page(self):
        html = (ROOT / "data" / "page.html").read_text(encoding="utf-8")
        self.assertGreaterEqual(len(parse_schedule(html)), 1)
        self.assertTrue(parse_page_info(html)["build_date"])

    def test_empty_schedule_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_schedule([])


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.lesson = {
            "day": "Понедельник", "pair": 1, "start": "9:30", "end": "11:00",
            "type": "Лекция", "subject": "Тест", "room": "1",
            "teacher": "Иванов И.И.", "week": "upper",
        }

    def test_week_parity(self):
        anchor = date(2026, 8, 31)
        self.assertEqual(academic_week_type(anchor, anchor), "upper")
        self.assertEqual(academic_week_type(date(2026, 9, 7), anchor), "lower")

    def test_calendar_only_contains_matching_week(self):
        calendar = build_calendar(
            [self.lesson], date(2026, 8, 31), date(2026, 9, 14), date(2026, 8, 31),
            "Europe/Moscow", "https://guap.ru/rasp?gr=7147", "ГУАП", date(2026, 8, 27),
        )
        self.assertEqual(calendar.count("BEGIN:VEVENT"), 2)
        self.assertIn("DTSTART:20260831T063000Z", calendar)
        self.assertNotIn("DTSTART:20260907T063000Z", calendar)
        self.assertLessEqual(max(len(line) for line in calendar.encode().split(b"\r\n")), 75)

    def test_diff(self):
        changed = {**self.lesson, "room": "2"}
        added, removed = diff_schedules([self.lesson], [changed])
        self.assertEqual((len(added), len(removed)), (1, 1))


if __name__ == "__main__":
    unittest.main()
