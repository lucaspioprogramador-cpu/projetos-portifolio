"""
Interface abstrata de Exchange.
"""
from abc import ABC, abstractmethod
from typing import Optional, Any


class Exchange(ABC):
    @abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1d", limit: int = 500):
        ...

    @abstractmethod
    def stream_candles(self, symbol: str, timeframe: str, callback):
        ...

    @abstractmethod
    def place_order(self, symbol: str, side: str, amount: float, price: Optional[float] = None) -> Any:
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> Any:
        ...

    @abstractmethod
    def get_balance(self) -> Any:
        ...


