"""
NormalizaÃ§Ã£o e schema de candles.
"""
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

REQUIRED_COLUMNS: list[str] = ["timestamp", "open", "high", "low", "close", "volume"]


def is_closed_candle(kline: Mapping[str, Any]) -> bool:
    """Binance marca candles finalizados com ``x=True``."""
    return kline.get("x") is True


def normalize_candles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Garante colunas padrÃ£o e timestamp como datetime.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Colunas ausentes: {missing}")
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    if out["timestamp"].isna().any():
        raise ValueError("Candles contêm timestamps inválidos")
    numeric_columns = ["open", "high", "low", "close", "volume"]
    for column in numeric_columns:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    values = out[numeric_columns].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Candles contêm preços/volumes inválidos ou não finitos")
    if (out[["open", "high", "low", "close"]] <= 0).any().any() or (out["volume"] < 0).any():
        raise ValueError("Preços devem ser positivos e volume não pode ser negativo")
    if (out["high"] < out[["open", "low", "close"]].max(axis=1)).any():
        raise ValueError("High deve ser maior ou igual a open, low e close")
    if (out["low"] > out[["open", "high", "close"]].min(axis=1)).any():
        raise ValueError("Low deve ser menor ou igual a open, high e close")
    return out


