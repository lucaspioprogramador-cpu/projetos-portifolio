"""
Engine orchestration layer.
ResponsÃ¡vel por conectar dados, estratÃ©gias, risco e execuÃ§Ã£o.
"""
from typing import Optional, Protocol

from core.state import PortfolioState


class Strategy(Protocol):
    def on_bar(self, df):
        ...


class Exchange(Protocol):
    def place_order(self, symbol: str, side: str, amount: float, price: Optional[float] = None):
        ...


class TradingEngine:
    def __init__(self, strategy: Strategy, exchange: Exchange, state: PortfolioState):
        self.strategy = strategy
        self.exchange = exchange
        self.state = state

    def on_new_data(self, df):
        """
        Recebe novo dataframe de candles, chama estratÃ©gia e delega execuÃ§Ã£o.
        """
        signal = self.strategy.on_bar(df)
        return signal


