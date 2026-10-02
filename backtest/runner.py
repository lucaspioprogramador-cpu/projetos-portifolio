"""
Backtester simples para executar uma estratÃ©gia em dados histÃ³ricos.
"""
import math
from collections.abc import Callable

import pandas as pd


def run_backtest(
    df: pd.DataFrame,
    strategy: Callable[[pd.DataFrame, bool], str],
    initial_balance: float = 10_000.0,
    fee_rate: float = 0.001,
    slippage_rate: float = 0.0005,
    position_fraction: float = 1.0,
    lookback: int = 50,
) -> pd.DataFrame:
    """Backtest sem lookahead, executando sinais no open da barra seguinte.

    A estratégia recebe apenas barras anteriores à barra de execução. Compras
    usam a fração configurada do caixa; vendas fecham a posição inteira. Taxas
    e slippage são debitados e o patrimônio é marcado a mercado no close.
    """
    required = {"open", "close"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Colunas ausentes: {sorted(missing)}")
    params = (initial_balance, fee_rate, slippage_rate, position_fraction)
    if not all(math.isfinite(value) for value in params):
        raise ValueError("Parâmetros do backtest devem ser finitos")
    if initial_balance <= 0 or not 0 <= fee_rate < 1 or not 0 <= slippage_rate < 1:
        raise ValueError("Saldo deve ser positivo e taxas/slippage estar entre 0 e 1")
    if not 0 < position_fraction <= 1 or lookback < 1:
        raise ValueError("position_fraction deve estar em (0, 1] e lookback ser positivo")
    prices = df[["open", "close"]].to_numpy(dtype=float)
    if not math.isfinite(float(prices.sum())) or not (prices > 0).all():
        raise ValueError("Preços open/close devem ser positivos e não nulos")

    cash = float(initial_balance)
    quantity = 0.0
    position_cost = 0.0
    closed_trade_returns: list[float] = []
    rows: list[dict] = []

    for i in range(min(lookback, len(df)), len(df)):
        window = df.iloc[:i].copy()
        signal = strategy(window, quantity > 0)
        if signal not in {"buy", "sell", "hold"}:
            raise ValueError(f"Sinal inválido: {signal!r}")

        execution_price = float(df.iloc[i]["open"])
        realized_pnl = 0.0
        trade_return = None
        if signal == "buy" and quantity == 0:
            execution_price *= 1 + slippage_rate
            budget = cash * position_fraction
            quantity = budget / (execution_price * (1 + fee_rate))
            gross = quantity * execution_price
            fee = gross * fee_rate
            position_cost = gross + fee
            cash -= position_cost
        elif signal == "sell" and quantity > 0:
            execution_price *= 1 - slippage_rate
            gross = quantity * execution_price
            fee = gross * fee_rate
            proceeds = gross - fee
            realized_pnl = proceeds - position_cost
            trade_return = realized_pnl / position_cost if position_cost else 0.0
            closed_trade_returns.append(trade_return)
            cash += proceeds
            quantity = 0.0
            position_cost = 0.0

        equity = cash + quantity * float(df.iloc[i]["close"])
        rows.append({
            "signal": signal,
            "execution_price": execution_price if signal in {"buy", "sell"} else None,
            "cash": cash,
            "position_quantity": quantity,
            "realized_pnl": realized_pnl,
            "trade_return": trade_return,
            "portfolio_value": equity,
        })

    out = df.iloc[min(lookback, len(df)):].copy()
    if rows:
        out = pd.concat([out.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    else:
        out = out.reset_index(drop=True)
        out["signal"] = pd.Series(dtype="object")
        out["execution_price"] = pd.Series(dtype="float64")
        out["cash"] = pd.Series(dtype="float64")
        out["position_quantity"] = pd.Series(dtype="float64")
        out["realized_pnl"] = pd.Series(dtype="float64")
        out["trade_return"] = pd.Series(dtype="float64")
        out["portfolio_value"] = pd.Series(dtype="float64")
    out.attrs["initial_balance"] = initial_balance
    out.attrs["closed_trade_returns"] = closed_trade_returns
    return out


