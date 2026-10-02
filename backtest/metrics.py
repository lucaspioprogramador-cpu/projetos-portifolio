"""
MÃ©tricas bÃ¡sicas de backtest.
"""
import pandas as pd


def basic_metrics(df: pd.DataFrame):
    """
    Calcula mÃ©tricas simples a partir de coluna 'signal' e 'close'.
    Placeholder para expansÃ£o.
    """
    trades = df[df["signal"].isin(["buy", "sell"])]
    return {"num_signals": len(trades)}


