# exchanges/mock_exchange.py
import numpy as np
import pandas as pd

from exchanges.base import Exchange


class MockExchange(Exchange):
    def fetch_ohlcv(self, symbol, timeframe="1d", limit=500):
        if limit <= 0:
            raise ValueError("limit deve ser positivo")
        duration_by_timeframe = {
            "1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
            "1h": "1h", "4h": "4h", "1d": "1d",
        }
        if timeframe not in duration_by_timeframe:
            raise ValueError(f"Timeframe não suportado pelo mock: {timeframe}")
        rng = np.random.default_rng(42)
        if symbol == "BTC/USDT":
            base_price = 30000
            volatility = 500  # Aumenta a volatilidade
        elif symbol == "PEPE/USDT":
            base_price = 0.00001
            volatility = 0.000005  # Aumenta a volatilidade relativa
        else:
            base_price = 100
            volatility = 10
        precos = np.maximum(
            np.cumsum(rng.standard_normal(limit) * volatility) + base_price,
            base_price * 0.1,
        )
        close = np.maximum(precos + rng.standard_normal(limit) * volatility * 0.2, base_price * 0.05)
        high = np.maximum(precos, close) + np.abs(rng.standard_normal(limit) * volatility * 0.5)
        low = np.maximum(
            np.minimum(precos, close) - np.abs(rng.standard_normal(limit) * volatility * 0.5),
            base_price * 0.01,
        )
        df = pd.DataFrame({
            'timestamp': pd.date_range(
                end=pd.Timestamp.now(tz="UTC"), periods=limit,
                freq=duration_by_timeframe[timeframe],
            ),
            'open': precos,
            'high': high,
            'low': low,
            'close': close,
            'volume': rng.random(limit) * 1000
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