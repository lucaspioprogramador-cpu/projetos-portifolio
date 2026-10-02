import warnings
warnings.warn("'ai_strategy.py' is deprecated. Use strategies/features.py and ai_strategy_melhorada.py instead.", DeprecationWarning)

from strategies.features import (
    gerar_features_basic as gerar_features,
    calcular_rsi,
    calcular_bollinger_bands,
    calcular_macd,
    calcular_obv,
)
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import numpy as np

def executar_estrategia_ai(df, posicao_aberta=False, ultimo_preco_compra=None):
    df = gerar_features(df)
    df['target'] = (df['close'].shift(-1) > df['close']).astype(int)

    if len(df) < 100:
        return 'hold'

    X = df[['retorno', 'media_5', 'media_10', 'media_20', 'media_50', 
            'rsi', 'media_diff', 'macd', 'macd_signal', 'obv', 'volume_spike']]
    y = df['target']

    modelo = RandomForestClassifier(n_estimators=200, random_state=42, max_depth=10)
    modelo.fit(X[:-1], y[:-1])

    previsao_proba = modelo.predict_proba(X.iloc[[-1]])[0][1]
    ultimo = df.iloc[-1]

    # CritÃ©rios de compra
    if not posicao_aberta:
        condicoes_compra = (
            previsao_proba > 0.65 and
            ultimo['rsi'] < 65 and
            ultimo['close'] > ultimo['media_20'] and
            ultimo['macd'] > ultimo['macd_signal'] and
            ultimo['volume_spike'] == 1
        )
        if condicoes_compra:
            return 'buy'
    
    # CritÃ©rios de venda
    elif posicao_aberta:
        # Venda por lucro
        lucro_percentual = (ultimo['close'] - ultimo_preco_compra) / ultimo_preco_compra * 100
        venda_lucro = lucro_percentual > 2  # 2% de lucro
        
        # Venda por stop loss
        stop_loss = lucro_percentual < -1  # 1% de perda
        
        # Venda por indicadores
        venda_indicadores = (
            previsao_proba < 0.35 or
            ultimo['rsi'] > 70 or
            ultimo['close'] < ultimo['media_20'] or
            ultimo['macd'] < ultimo['macd_signal']
        )
        
        if venda_lucro or stop_loss or venda_indicadores:
            return 'sell'
    
    return 'hold'

def calcular_posicao_size(saldo, risco_por_trade=0.01, stop_loss_pct=0.01):
    """
    Calcula o tamanho da posiÃ§Ã£o baseado no risco por trade
    """
    risco_maximo = saldo * risco_por_trade
    tamanho_posicao = risco_maximo / stop_loss_pct
    return tamanho_posicao

def atualizar_saldo(saldo, tipo_operacao, preco_entrada, preco_saida, quantidade):
    """
    Atualiza o saldo apÃ³s uma operaÃ§Ã£o
    """
    if tipo_operacao == 'buy':
        return saldo - (preco_entrada * quantidade)
    elif tipo_operacao == 'sell':
        return saldo + (preco_saida * quantidade)
    return saldo