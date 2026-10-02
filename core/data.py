"""
NormalizaÃ§Ã£o e schema de candles.
"""
from typing import List
import pandas as pd

REQUIRED_COLUMNS: List[str] = ["timestamp", "open", "high", "low", "close", "volume"]


def normalize_candles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Garante colunas padrÃ£o e timestamp como datetime.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Colunas ausentes: {missing}")
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    return out[REQUIRED_COLUMNS]


