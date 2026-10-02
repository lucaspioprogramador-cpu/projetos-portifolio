# exchanges/mock_exchange.py
import pandas as pd
import numpy as np

from exchanges.base import Exchange


class MockExchange(Exchange):
    def fetch_ohlcv(self, symbol):
        np.random.seed(42)
        if symbol == "BTC/USDT":
            base_price = 30000
            volatility = 500  # Aumenta a volatilidade
        elif symbol == "PEPE/USDT":
            base_price = 0.00001
            volatility = 0.000005  # Aumenta a volatilidade relativa
        else:
            base_price = 100
            volatility = 10
        precos = np.cumsum(np.random.randn(500) * volatility) + base_price
        df = pd.DataFrame({
            'timestamp': pd.date_range(end=pd.Timestamp.today(), periods=500),
            'open': precos,
            'high': precos + np.abs(np.random.randn(500) * volatility * 0.5),
            'low': precos - np.abs(np.random.randn(500) * volatility * 0.5),
            'close': precos + np.random.randn(500) * volatility * 0.2,
            'volume': np.random.rand(500) * 1000
        })
        return df

    # Mock placeholders
    def stream_candles(self, symbol: str, timeframe: str, callback):
        raise NotImplementedError("stream_candles nÃ£o implementado no mock")

    def place_order(self, symbol: str, side: str, amount: float, price=None):
        return {"mock": True, "symbol": symbol, "side": side, "amount": amount, "price": price}

    def cancel_order(self, order_id: str):
        return {"mock": True, "cancelled": order_id}

    def get_balance(self):
        return {"mock": True, "balance": 100000}