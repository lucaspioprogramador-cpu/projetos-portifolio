"""
MÃ³dulo de features compartilhadas para as estratÃ©gias.
ContÃ©m cÃ¡lculos de indicadores e geradores de features para as variantes de estratÃ©gia.
"""
import pandas as pd
import numpy as np

def calcular_rsi(df: pd.DataFrame, periodo: int = 14) -> pd.Series:
    delta = df['close'].diff()
    ganho = delta.clip(lower=0).rolling(window=periodo).mean()
    perda = -delta.clip(upper=0).rolling(window=periodo).mean()
    rs = ganho / perda
    return 100 - (100 / (1 + rs))

def calcular_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    macd_hist = macd - macd_signal
    return macd, macd_signal, macd_hist

def calcular_bollinger_bands(df: pd.DataFrame, window: int = 20, num_std: int = 2):
    rolling_mean = df['close'].rolling(window=window).mean()
    rolling_std = df['close'].rolling(window=window).std()
    upper_band = rolling_mean + (rolling_std * num_std)
    lower_band = rolling_mean - (rolling_std * num_std)
    return upper_band, lower_band

def calcular_obv(df: pd.DataFrame) -> pd.Series:
    obv = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
    return obv

def calcular_atr(df: pd.DataFrame, periodo: int = 14) -> pd.Series:
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(periodo).mean()

def calcular_adx(df: pd.DataFrame, periodo: int = 14) -> pd.Series:
    atr = calcular_atr(df, periodo)
    plus_dm = df['high'].diff()
    minus_dm = -df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_di = 100 * (plus_dm.rolling(periodo).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(periodo).mean() / atr)
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(periodo).mean()
    return adx


def gerar_features_basic(df: pd.DataFrame) -> pd.DataFrame:
    """Gera as features usadas pela `ai_strategy.py` (versÃ£o bÃ¡sica)."""
    df = df.copy()
    df['retorno'] = df['close'].pct_change()
    df['media_5'] = df['close'].rolling(window=5).mean()
    df['media_10'] = df['close'].rolling(window=10).mean()
    df['rsi'] = calcular_rsi(df)
    df['media_diff'] = df['media_5'] - df['media_10']
    df['media_20'] = df['close'].rolling(window=20).mean()
    df['media_50'] = df['close'].rolling(window=50).mean()
    df['bollinger_upper'], df['bollinger_lower'] = calcular_bollinger_bands(df)
    df['macd'], df['macd_signal'], df['macd_hist'] = calcular_macd(df)
    df['obv'] = calcular_obv(df)
    df['volume_ma'] = df['volume'].rolling(window=10).mean()
    df['volume_spike'] = (df['volume'] > 1.5 * df['volume_ma']).astype(int)
    df = df.dropna()
    return df


def gerar_features_corrigido(df: pd.DataFrame) -> pd.DataFrame:
    """Gera as features usadas pela versÃ£o corrigida (ai_strategy_corrigido.py)."""
    df = df.copy()
    df['retorno'] = df['close'].pct_change()
    df['media_5'] = df['close'].rolling(window=5).mean()
    df['media_10'] = df['close'].rolling(window=10).mean()
    df['rsi'] = calcular_rsi(df)
    df['media_diff'] = df['media_5'] - df['media_10']
    df = df.dropna()
    return df


def gerar_features_melhorada(df: pd.DataFrame) -> pd.DataFrame:
    """Gera as features usadas pela versÃ£o melhorada (ai_strategy_melhorada.py)."""
    df = df.copy()
    # Retornos
    df['retorno'] = df['close'].pct_change()
    df['retorno_5'] = df['close'].pct_change(5)
    df['retorno_10'] = df['close'].pct_change(10)
    # MÃ©dias mÃ³veis
    df['ma_5'] = df['close'].rolling(window=5).mean()
    df['ma_10'] = df['close'].rolling(window=10).mean()
    df['ma_20'] = df['close'].rolling(window=20).mean()
    df['ma_50'] = df['close'].rolling(window=50).mean()
    df['ma_diff'] = df['ma_5'] - df['ma_20']
    df['ma_ratio'] = df['ma_5'] / df['ma_20']
    # RSI, MACD, Bollinger, OBV, ATR, ADX
    df['rsi'] = calcular_rsi(df)
    df['macd'], df['macd_signal'], df['macd_hist'] = calcular_macd(df)
    df['bb_upper'], df['bb_lower'] = calcular_bollinger_bands(df)
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['close']
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    df['volume_ma'] = df['volume'].rolling(window=10).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma']
    df['volume_spike'] = (df['volume'] > 1.5 * df['volume_ma']).astype(int)
    df['obv'] = calcular_obv(df)
    df['obv_ma'] = df['obv'].rolling(window=10).mean()
    df['obv_trend'] = (df['obv'] > df['obv_ma']).astype(int)
    df['atr'] = calcular_atr(df)
    df['atr_pct'] = df['atr'] / df['close']
    df['adx'] = calcular_adx(df)
    df['volatility'] = df['close'].rolling(window=20).std()
    df['volatility_pct'] = df['volatility'] / df['close']
    df['price_vs_ma5'] = (df['close'] - df['ma_5']) / df['ma_5']
    df['price_vs_ma20'] = (df['close'] - df['ma_20']) / df['ma_20']
    df = df.dropna()
    return df
