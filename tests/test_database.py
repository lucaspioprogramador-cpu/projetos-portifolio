import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from db import database


class DatabaseTests(unittest.TestCase):
    def test_candles_are_unique_and_queries_are_symbol_scoped(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(database, "BASE_DIR", Path(temp_dir)):
            rows = [{
                "timestamp": "2026-01-01T00:00:00Z", "open": 1, "high": 2,
                "low": 0.5, "close": 1.5, "volume": 10, "timeframe": "1m",
            }]
            database.registrar_candles("BTC/USDT", rows)
            database.registrar_candles("BTCUSDT", rows)
            candles = database.get_candles("BTC/USDT")
            self.assertEqual(len(candles), 1)
            self.assertEqual(candles.iloc[0]["close"], 1.5)
            self.assertEqual(database.count_trades_e_candles(), (0, 1))


if __name__ == "__main__":
    unittest.main()
