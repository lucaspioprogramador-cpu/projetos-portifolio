import ccxt
import pandas as pd

from exchanges.base import Exchange


def normalize_binance_symbol(symbol: str) -> str:
    """Converte IDs concatenados comuns em símbolos CCXT com barra."""
    if '/' in symbol:
        return symbol
    quotes = ('USDT', 'USDC', 'BUSD', 'FDUSD', 'BTC', 'ETH', 'BNB')
    quote = next((item for item in quotes if symbol.endswith(item)), None)
    if quote is None or len(symbol) <= len(quote):
        raise ValueError(f"Símbolo Binance inválido: {symbol}")
    return f"{symbol[:-len(quote)]}/{quote}"


class BinanceExchange(Exchange):
    def __init__(self):
        self.client = ccxt.binance()

    def fetch_ohlcv(self, symbol, timeframe='1d', limit=500):
        symbol_binance = normalize_binance_symbol(symbol)
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
