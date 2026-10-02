"""
Interface bÃ¡sica de estratÃ©gia.
"""
from abc import ABC, abstractmethod


class Strategy(ABC):
    @abstractmethod
    def on_bar(self, df):
        """
        Recebe dataframe de candles e retorna sinal ('buy', 'sell', 'hold', etc.).
        """
        ...


