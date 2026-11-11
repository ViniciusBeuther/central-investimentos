import unittest
from decimal import Decimal as D

from app.quotes import parse_brapi


class ParseBrapiTest(unittest.TestCase):
    def test_valid_response(self):
        q = parse_brapi("PETR4", {"results": [{"symbol": "PETR4", "regularMarketPrice": 43.93,
                                               "regularMarketTime": "2026-11-11T19:38:30.000Z"}]})
        self.assertEqual((q.ticker, q.price), ("PETR4", D("43.93")))
        self.assertEqual(q.quoted_at.isoformat(), "2026-11-11T19:38:30+00:00")

    def test_empty_results_fail(self):
        with self.assertRaises(ValueError):
            parse_brapi("X", {"results": []})

    def test_missing_price_or_time_fails(self):
        with self.assertRaises(ValueError):
            parse_brapi("X", {"results": [{"regularMarketPrice": None, "regularMarketTime": "2026-01-01T00:00:00Z"}]})
        with self.assertRaises(ValueError):
            parse_brapi("X", {"results": [{"regularMarketPrice": 10}]})

    def test_zero_or_negative_price_fails(self):
        with self.assertRaises(ValueError):
            parse_brapi("X", {"results": [{"regularMarketPrice": 0, "regularMarketTime": "2026-01-01T00:00:00Z"}]})


if __name__ == "__main__":
    unittest.main()
