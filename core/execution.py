"""
Camada de execuÃ§Ã£o: responsÃ¡vel por transformar sinais em ordens.
Inclui simulaÃ§Ã£o realista de execuÃ§Ã£o.
"""
from typing import Optional, Dict
from datetime import datetime
from .simulator import OrderSimulator, criar_simulador_padrao


def build_order(symbol: str, side: str, amount: float, price: Optional[float] = None) -> dict:
    """
    Retorna um dicionÃ¡rio de ordem simples.
    """
    return {
        "symbol": symbol,
        "side": side,
        "amount": amount,
        "price": price,
        "type": "limit" if price else "market",
    }


def executar_ordem_simulada(
    lado: str,
    quantidade: float,
    preco_atual: float,
    symbol: str,
    simulador: Optional[OrderSimulator] = None,
    volume_24h: Optional[float] = None,
    volatilidade: Optional[float] = None
) -> Dict:
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
    
    resultado = simulador.simular_execucao(
        lado=lado,
        quantidade=quantidade,
        preco_atual=preco_atual,
        volume_24h=volume_24h,
        volatilidade=volatilidade,
        timestamp=datetime.now()
    )
    
    resultado['symbol'] = symbol
    return resultado


