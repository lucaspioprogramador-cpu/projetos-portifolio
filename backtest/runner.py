"""
Backtester simples para executar uma estratÃ©gia em dados histÃ³ricos.
"""
from typing import Callable
import pandas as pd


def run_backtest(df: pd.DataFrame, strategy: Callable[[pd.DataFrame, bool], str]):
    signals = []
    pos_open = False
    for i in range(50, len(df)):
        window = df.iloc[:i]
        signal = strategy(window, pos_open)
        signals.append(signal)
        if signal == "buy":
            pos_open = True
        elif signal == "sell":
            pos_open = False
    out = df.iloc[50:].copy()
    out["signal"] = signals
    return out


