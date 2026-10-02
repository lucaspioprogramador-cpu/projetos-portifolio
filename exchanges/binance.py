import ccxt
import pandas as pd

from exchanges.base import Exchange


class BinanceExchange(Exchange):
    def __init__(self):
        self.client = ccxt.binance()

    def fetch_ohlcv(self, symbol, timeframe='1d', limit=500):
        symbol_binance = symbol.replace('USDT', '/USDT') if '/' not in symbol else symbol
        ohlcv = self.client.fetch_ohlcv(symbol_binance, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    # Placeholders para implementar streaming e ordens reais
    def stream_candles(self, symbol: str, timeframe: str, callback):
        raise NotImplementedError("stream_candles nÃ£o implementado")

    def place_order(self, symbol: str, side: str, amount: float, price=None):
        raise NotImplementedError("place_order nÃ£o implementado")

    def cancel_order(self, order_id: str):
        raise NotImplementedError("cancel_order nÃ£o implementado")

    def get_balance(self):
        raise NotImplementedError("get_balance nÃ£o implementado")
