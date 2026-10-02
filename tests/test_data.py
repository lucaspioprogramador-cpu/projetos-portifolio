import unittest

import pandas as pd

from core.data import is_closed_candle, normalize_candles


class DataTests(unittest.TestCase):
    def test_normalize_preserves_extra_columns_and_uses_utc(self):
        frame = pd.DataFrame({
            "timestamp": ["2026-01-01T00:00:00-03:00"],
            "open": [10], "high": [12], "low": [9], "close": [11], "volume": [3],
            "source": ["test"],
        })
        result = normalize_candles(frame)
        self.assertIn("source", result.columns)
        self.assertEqual(str(result.iloc[0]["timestamp"].tz), "UTC")

    def test_rejects_invalid_ohlcv(self):
        frame = pd.DataFrame({
            "timestamp": ["not a date"],
            "open": [10], "high": [9], "low": [8], "close": [11], "volume": [-1],
        })
        with self.assertRaises(ValueError):
            normalize_candles(frame)

    def test_only_explicit_final_kline_is_closed(self):
        self.assertTrue(is_closed_candle({"x": True}))
        self.assertFalse(is_closed_candle({"x": False}))
        self.assertFalse(is_closed_candle({}))


if __name__ == "__main__":
    unittest.main()
