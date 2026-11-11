import unittest
from datetime import datetime, timedelta, timezone

from app.worker import BRASILIA, due, is_market_window


def brt(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute, tzinfo=BRASILIA)


class WorkerScheduleTest(unittest.TestCase):
    def test_window_on_a_weekday(self):
        self.assertTrue(is_market_window(brt(2026, 11, 11, 10, 0)))   # Wednesday open
        self.assertTrue(is_market_window(brt(2026, 11, 11, 14, 15)))
        self.assertTrue(is_market_window(brt(2026, 11, 11, 18, 30)))  # closing run
        self.assertFalse(is_market_window(brt(2026, 11, 11, 9, 59)))
        self.assertFalse(is_market_window(brt(2026, 11, 11, 18, 45)))
        self.assertFalse(is_market_window(brt(2026, 11, 11, 23, 0)))

    def test_closed_on_weekends(self):
        self.assertFalse(is_market_window(brt(2026, 11, 14, 12, 0)))  # Saturday
        self.assertFalse(is_market_window(brt(2026, 11, 15, 12, 0)))  # Sunday

    def test_utc_is_converted_to_brasilia(self):
        # 13:00 UTC is 10:00 in Brasília
        self.assertTrue(is_market_window(datetime(2026, 11, 11, 13, 0, tzinfo=timezone.utc)))
        self.assertFalse(is_market_window(datetime(2026, 11, 11, 12, 59, tzinfo=timezone.utc)))

    def test_due_respects_the_interval(self):
        now = brt(2026, 11, 11, 11, 0)
        self.assertTrue(due(now, None))
        self.assertFalse(due(now, now - timedelta(minutes=10)))
        self.assertTrue(due(now, now - timedelta(minutes=30)))
        self.assertFalse(due(brt(2026, 11, 11, 20, 0), None))  # outside the window


if __name__ == "__main__":
    unittest.main()
