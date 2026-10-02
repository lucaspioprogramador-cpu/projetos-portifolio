"""
Simulador realista de execuÃ§Ã£o de ordens.
Simula slippage, taxas, ordem book e execuÃ§Ã£o parcial.
"""
import math
from datetime import datetime, timezone

import numpy as np


class OrderSimulator:
    """
    Simula execuÃ§Ã£o realista de ordens considerando:
    - Slippage baseado em volatilidade
    - Taxas de exchange
    - Ordem book (spread bid/ask)
    - ExecuÃ§Ã£o parcial para ordens grandes
    """
    
    def __init__(
        self,
        fee_rate: float = 0.001,  # 0.1% taxa padrÃ£o Binance
        slippage_base: float = 0.0005,  # 0.05% slippage base
        spread_pct: float = 0.0002,  # 0.02% spread bid/ask
        volatility_multiplier: float = 2.0,
        rng: np.random.Generator | None = None,
        max_slippage: float = 0.05,
    ):
        self.fee_rate = fee_rate
        self.slippage_base = slippage_base
        self.spread_pct = spread_pct
        self.volatility_multiplier = volatility_multiplier
        self.rng = rng if rng is not None else np.random.default_rng()
        self.max_slippage = max_slippage
        costs = (fee_rate, slippage_base, spread_pct, volatility_multiplier, max_slippage)
        if not all(math.isfinite(value) for value in costs):
            raise ValueError("Parâmetros do simulador devem ser finitos")
        if not 0 <= fee_rate < 1 or min(slippage_base, spread_pct, volatility_multiplier, max_slippage) < 0 or spread_pct >= 2:
            raise ValueError("Taxa deve estar em [0, 1) e custos não podem ser negativos")
    
    def calcular_slippage(
        self,
        preco_atual: float,
        quantidade: float,
        volume_24h: float | None = None,
        volatilidade: float | None = None,
        lado: str = 'buy'
    ) -> float:
        """
        Calcula slippage baseado em:
        - Tamanho da ordem relativo ao volume
        - Volatilidade do mercado
        - Lado da ordem (compra geralmente tem mais slippage)
        """
        if lado not in {'buy', 'sell'}:
            raise ValueError("lado deve ser 'buy' ou 'sell'")
        if not math.isfinite(preco_atual) or not math.isfinite(quantidade) or preco_atual <= 0 or quantidade <= 0:
            raise ValueError("Preço e quantidade devem ser positivos e finitos")
        if volatilidade is not None and (not math.isfinite(volatilidade) or volatilidade < 0):
            raise ValueError("Volatilidade deve ser finita e não negativa")
        if volume_24h is not None and (not math.isfinite(volume_24h) or volume_24h < 0):
            raise ValueError("Volume 24h deve ser finito e não negativo")

        slippage = self.slippage_base
        
        # Ajuste por volatilidade
        if volatilidade:
            slippage += volatilidade * self.volatility_multiplier
        
        # Ajuste por tamanho da ordem
        if volume_24h:
            ordem_pct_volume = (preco_atual * quantidade) / volume_24h
            # Ordens grandes (>0.1% do volume) tÃªm mais slippage
            if ordem_pct_volume > 0.001:
                slippage += min(ordem_pct_volume * 10, 0.01)  # MÃ¡ximo 1%
        
        # Compra geralmente tem mais slippage (preÃ§o mais alto)
        if lado == 'buy':
            slippage *= 1.2
        
        # Adiciona componente aleatÃ³ria (simula variaÃ§Ã£o do mercado)
        slippage += self.rng.uniform(-0.0001, 0.0001)
        
        return min(max(slippage, 0.0), self.max_slippage)
    
    def calcular_preco_execucao(
        self,
        preco_atual: float,
        lado: str,
        slippage: float
    ) -> float:
        """
        Calcula preÃ§o de execuÃ§Ã£o considerando spread e slippage.
        """
        # Spread bid/ask
        if lado == 'buy':
            # Compra no ask (mais alto)
            preco_exec = preco_atual * (1 + self.spread_pct / 2)
        else:
            # Venda no bid (mais baixo)
            preco_exec = preco_atual * (1 - self.spread_pct / 2)
        
        # Aplica slippage
        if lado == 'buy':
            preco_exec *= (1 + slippage)
        else:
            preco_exec *= (1 - slippage)
        
        return preco_exec
    
    def calcular_taxas(
        self,
        valor: float
    ) -> float:
        """Calcula taxas da exchange."""
        return valor * self.fee_rate
    
    def simular_execucao(
        self,
        lado: str,
        quantidade: float,
        preco_atual: float,
        volume_24h: float | None = None,
        volatilidade: float | None = None,
        timestamp: datetime | None = None
    ) -> dict:
        """
        Simula execuÃ§Ã£o completa de uma ordem.
        
        Retorna dicionÃ¡rio com:
        - preco_execucao: PreÃ§o real de execuÃ§Ã£o
        - quantidade_executada: Quantidade executada (pode ser parcial)
        - valor_total: Valor total da ordem
        - taxas: Taxas pagas
        - slippage_pct: Percentual de slippage
        - timestamp: Timestamp da execuÃ§Ã£o
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        if lado not in {'buy', 'sell'}:
            raise ValueError("lado deve ser 'buy' ou 'sell'")
        
        # Calcular slippage
        slippage_pct = self.calcular_slippage(
            preco_atual, quantidade, volume_24h, volatilidade, lado
        )
        
        # Calcular preÃ§o de execuÃ§Ã£o
        preco_exec = self.calcular_preco_execucao(preco_atual, lado, slippage_pct)
        
        # Simular execuÃ§Ã£o parcial para ordens muito grandes
        quantidade_executada = quantidade
        if volume_24h and quantidade_executada * preco_exec > volume_24h * 0.01:
            # Ordem muito grande (>1% do volume) pode ter execuÃ§Ã£o parcial
            fill_rate = self.rng.uniform(0.7, 1.0)
            quantidade_executada = quantidade * fill_rate
        
        # Calcular valores
        valor_total = preco_exec * quantidade_executada
        taxas = self.calcular_taxas(valor_total)
        valor_liquido = valor_total + taxas if lado == 'buy' else valor_total - taxas
        
        return {
            'lado': lado,
            'preco_solicitado': preco_atual,
            'preco_execucao': preco_exec,
            'quantidade_solicitada': quantidade,
            'quantidade_executada': quantidade_executada,
            'valor_total': valor_total,
            'taxas': taxas,
            'valor_liquido': valor_liquido,
            'slippage_pct': slippage_pct,
            'slippage_valor': abs(preco_exec - preco_atual) * quantidade_executada,
            'timestamp': timestamp,
            'executada_completa': abs(quantidade_executada - quantidade) < 0.0001,
            'executada': quantidade_executada > 0
        }
    
    def simular_ordem_limit(
        self,
        lado: str,
        quantidade: float,
        preco_limit: float,
        preco_atual: float,
        volume_24h: float | None = None
    ) -> dict:
        """
        Simula ordem limitada.
        SÃ³ executa se o preÃ§o atingir o limite.
        """
        if lado not in {'buy', 'sell'}:
            raise ValueError("lado deve ser 'buy' ou 'sell'")
        if not all(math.isfinite(value) for value in (preco_limit, preco_atual, quantidade)):
            raise ValueError("Preços e quantidade devem ser finitos")
        if preco_limit <= 0 or preco_atual <= 0 or quantidade <= 0:
            raise ValueError("Preços e quantidade devem ser positivos")

        # Simula o preço corrente e rejeita fills que ultrapassariam o limite.
        if lado == 'buy' and preco_atual <= preco_limit:
            # Ordem de compra limit sÃ³ executa se preÃ§o <= limite
            resultado = self.simular_execucao(
                lado, quantidade, preco_atual, volume_24h, None
            )
            if resultado['preco_execucao'] <= preco_limit:
                return resultado
            return {'lado': lado, 'executada': False, 'quantidade_executada': 0.0, 'razao': 'Preço limite excedido'}
        elif lado == 'sell' and preco_atual >= preco_limit:
            # Ordem de venda limit sÃ³ executa se preÃ§o >= limite
            resultado = self.simular_execucao(
                lado, quantidade, preco_atual, volume_24h, None
            )
            if resultado['preco_execucao'] >= preco_limit:
                return resultado
            return {'lado': lado, 'executada': False, 'quantidade_executada': 0.0, 'razao': 'Preço limite não atingido'}
        else:
            # Ordem nÃ£o executada
            return {
                'lado': lado,
                'preco_limit': preco_limit,
                'preco_atual': preco_atual,
                'quantidade': quantidade,
                'executada': False,
                'quantidade_executada': 0.0,
                'razao': 'PreÃ§o nÃ£o atingiu o limite'
            }


def criar_simulador_padrao() -> OrderSimulator:
    """Cria simulador com configuraÃ§Ãµes padrÃ£o da Binance."""
    return OrderSimulator(
        fee_rate=0.001,  # 0.1% taxa maker/taker Binance
        slippage_base=0.0005,  # 0.05% slippage base
        spread_pct=0.0002,  # 0.02% spread tÃ­pico
        volatility_multiplier=2.0
    )

