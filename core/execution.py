"""
Camada de execuÃ§Ã£o: responsÃ¡vel por transformar sinais em ordens.
Inclui simulaÃ§Ã£o realista de execuÃ§Ã£o.
"""
import math
from datetime import datetime, timezone
from typing import Any

from .simulator import OrderSimulator, criar_simulador_padrao


def build_order(symbol: str, side: str, amount: float, price: float | None = None) -> dict:
    """
    Retorna um dicionÃ¡rio de ordem simples.
    """
    if side not in {"buy", "sell"}:
        raise ValueError("side deve ser 'buy' ou 'sell'")
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("amount deve ser positivo e finito")
    if price is not None and (not math.isfinite(price) or price <= 0):
        raise ValueError("price deve ser positivo e finito")
    return {
        "symbol": symbol,
        "side": side,
        "amount": amount,
        "price": price,
        "type": "limit" if price is not None else "market",
    }


def apply_simulated_fill(
    balance: float,
    positions: list[dict[str, Any]],
    side: str,
    execution: dict[str, Any],
    order_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aplica um fill ao caixa e às posições, preservando fills parciais."""
    if side not in {"buy", "sell"}:
        raise ValueError("side deve ser 'buy' ou 'sell'")
    qty = float(execution.get("quantidade_executada", 0))
    gross = float(execution.get("valor_total", 0))
    fee = float(execution.get("taxas", 0))
    price = float(execution.get("preco_execucao", gross / qty if qty else 0))
    if not all(math.isfinite(value) for value in (balance, qty, gross, fee, price)):
        raise ValueError("Saldo e valores do fill devem ser finitos")
    if balance < 0 or qty <= 0 or gross <= 0 or fee < 0 or fee > gross or price <= 0:
        raise ValueError("O fill deve ter quantidade e valor positivos e taxa não negativa")

    if side == "buy":
        cash_cost = gross + fee
        if cash_cost > balance + 1e-9:
            raise ValueError("Caixa insuficiente para cobrir o fill e as taxas")
        position = {
            "preco_compra": price,
            "quantidade": qty,
            "valor_investido": cash_cost,
        }
        positions.append(position)
        return {"balance": max(0.0, balance - cash_cost), "position": position, "pnl": None}

    if order_ref is None:
        if not positions:
            raise ValueError("Não há posição aberta para vender")
        order_ref = positions[0]
    if order_ref not in positions:
        raise ValueError("A posição informada não está aberta")
    open_qty = float(order_ref.get("quantidade", 0))
    invested = float(order_ref.get("valor_investido", 0))
    if open_qty <= 0 or qty > open_qty + 1e-9:
        raise ValueError("Quantidade do fill excede a posição aberta")

    sold_qty = min(qty, open_qty)
    cost_basis = invested * (sold_qty / open_qty)
    proceeds = gross - fee
    remaining_qty = open_qty - sold_qty
    if remaining_qty <= 1e-9:
        positions.remove(order_ref)
    else:
        order_ref["quantidade"] = remaining_qty
        order_ref["valor_investido"] = max(0.0, invested - cost_basis)
    return {
        "balance": balance + proceeds,
        "position": order_ref if remaining_qty > 1e-9 else None,
        "pnl": proceeds - cost_basis,
        "cost_basis": cost_basis,
    }


def executar_ordem_simulada(
    lado: str,
    quantidade: float,
    preco_atual: float,
    symbol: str,
    simulador: OrderSimulator | None = None,
    volume_24h: float | None = None,
    volatilidade: float | None = None
) -> dict:
    """
    Executa uma ordem usando simulaÃ§Ã£o realista.
    
    Args:
        lado: 'buy' ou 'sell'
        quantidade: Quantidade a negociar
        preco_atual: PreÃ§o atual do mercado
        symbol: SÃ­mbolo do par
        simulador: InstÃ¢ncia do OrderSimulator (usa padrÃ£o se None)
        volume_24h: Volume 24h para cÃ¡lculo de slippage
        volatilidade: Volatilidade atual para cÃ¡lculo de slippage
    
    Returns:
        DicionÃ¡rio com detalhes da execuÃ§Ã£o simulada
    """
    if simulador is None:
        simulador = criar_simulador_padrao()

    if lado not in {"buy", "sell"}:
        raise ValueError("lado deve ser 'buy' ou 'sell'")
    if not all(math.isfinite(value) for value in (quantidade, preco_atual)):
        raise ValueError("Quantidade e preço devem ser finitos")
    if quantidade <= 0 or preco_atual <= 0:
        raise ValueError("Quantidade e preço devem ser positivos")
    
    resultado = simulador.simular_execucao(
        lado=lado,
        quantidade=quantidade,
        preco_atual=preco_atual,
        volume_24h=volume_24h,
        volatilidade=volatilidade,
        timestamp=datetime.now(timezone.utc)
    )
    
    resultado['symbol'] = symbol
    return resultado


