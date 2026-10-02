"""Funções de gerenciamento de risco e tamanho de posição."""

import math


def position_size(balance: float, risk_pct: float, stop_pct: float, price: float) -> float:
    """Calcula a quantidade para arriscar ``balance * risk_pct`` no stop.

    ``risk_pct`` e ``stop_pct`` são frações (por exemplo, 0.01 = 1%).
    Entradas inválidas levantam ValueError em vez de gerar quantidades infinitas.
    """
    if not all(math.isfinite(value) for value in (balance, risk_pct, stop_pct, price)):
        raise ValueError("Os parâmetros de risco devem ser números finitos")
    if balance < 0 or not 0 < risk_pct <= 1 or not 0 < stop_pct < 1 or price <= 0:
        raise ValueError("Saldo, risco, stop ou preço fora dos limites permitidos")
    return (balance * risk_pct) / (price * stop_pct)


def affordable_quantity(
    balance: float,
    price: float,
    fee_rate: float,
    max_slippage: float,
    spread_pct: float = 0.0,
) -> float:
    """Retorna quantidade máxima que cabe no caixa com custos conservadores."""
    values = (balance, price, fee_rate, max_slippage, spread_pct)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Os parâmetros de custo devem ser números finitos")
    if balance < 0 or price <= 0 or min(fee_rate, max_slippage, spread_pct) < 0:
        raise ValueError("Saldo e custos devem ser não negativos e o preço positivo")
    worst_case_price = price * (1 + spread_pct / 2) * (1 + max_slippage)
    return balance / (worst_case_price * (1 + fee_rate))


def exposure_budget(
    initial_balance: float,
    total_invested: float,
    symbol_invested: float,
    total_cap_fraction: float,
    symbol_cap_fraction: float,
) -> float:
    """Retorna orçamento restante respeitando os limites total e por ativo."""
    values = (
        initial_balance,
        total_invested,
        symbol_invested,
        total_cap_fraction,
        symbol_cap_fraction,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Parâmetros de exposição devem ser finitos")
    if min(initial_balance, total_invested, symbol_invested) < 0:
        raise ValueError("Saldo investido não pode ser negativo")
    if not 0 <= total_cap_fraction <= 1 or not 0 <= symbol_cap_fraction <= 1:
        raise ValueError("Limites de exposição devem estar entre 0 e 1")
    return max(
        0.0,
        min(
            initial_balance * total_cap_fraction - total_invested,
            initial_balance * symbol_cap_fraction - symbol_invested,
        ),
    )


def apply_stop_take(entry_price: float, stop_pct: float, take_pct: float) -> tuple[float, float]:
    """Calcula níveis de stop loss e take profit."""
    if not all(math.isfinite(value) for value in (entry_price, stop_pct, take_pct)):
        raise ValueError("Os parâmetros de stop/take devem ser números finitos")
    if entry_price <= 0 or not 0 < stop_pct < 1 or take_pct <= 0:
        raise ValueError("Preço de entrada, stop ou take fora dos limites permitidos")
    stop = entry_price * (1 - stop_pct)
    take = entry_price * (1 + take_pct)
    return stop, take
