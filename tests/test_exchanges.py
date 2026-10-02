import unittest

import numpy as np

from core.data import normalize_candles
from exchanges.binance import normalize_binance_symbol
from exchanges.mock import MockExchange


class ExchangeTests(unittest.TestCase):
    def test_binance_symbol_normalization(self):
        self.assertEqual(normalize_binance_symbol("BTCUSDT"), "BTC/USDT")
        self.assertEqual(normalize_binance_symbol("ETHBTC"), "ETH/BTC")
        self.assertEqual(normalize_binance_symbol("BTC/USDT"), "BTC/USDT")
        with self.assertRaises(ValueError):
            normalize_binance_symbol("USDT")

    def test_mock_matches_exchange_contract_and_is_deterministic(self):
        exchange = MockExchange()
        first = exchange.fetch_ohlcv("PEPE/USDT", timeframe="5m", limit=25)
        second = exchange.fetch_ohlcv("PEPE/USDT", timeframe="5m", limit=25)
        self.assertEqual(len(first), 25)
        self.assertTrue(np.array_equal(first.drop(columns="timestamp").to_numpy(), second.drop(columns="timestamp").to_numpy()))
        self.assertEqual(len(normalize_candles(first)), 25)
        with self.assertRaises(ValueError):
            exchange.fetch_ohlcv("BTC/USDT", limit=0)
        with self.assertRaises(ValueError):
            exchange.fetch_ohlcv("BTC/USDT", timeframe="3m")


if __name__ == "__main__":
    unittest.main()
