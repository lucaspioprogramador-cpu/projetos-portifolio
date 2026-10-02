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

    def test_trade_query_returns_reference_and_execution_cost_breakdown(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(database, "BASE_DIR", Path(temp_dir)):
            database.registrar_trade({
                "symbol": "BTC/USDT", "tipo": "COMPRA",
                "preco_solicitado": 85_230.62, "preco_execucao": 85_315.85,
                "quantidade_solicitada": 0.0028, "quantidade_executada": 0.0028,
                "valor_total": 238.88438, "taxas": 0.238884,
                "valor_liquido": 239.123264, "slippage_pct": 0.001,
                "timestamp": "2026-10-02T13:32:38-03:00",
            })
            trade = database.get_trades(symbol="BTC/USDT").iloc[0]
            self.assertEqual(trade["preco_solicitado"], 85_230.62)
            self.assertEqual(trade["preco_execucao"], 85_315.85)
            self.assertAlmostEqual(trade["slippage_pct"], 0.001)
            self.assertGreater(trade["valor_liquido"], trade["valor_total"])


if __name__ == "__main__":
    unittest.main()
