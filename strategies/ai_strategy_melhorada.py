"""
Estrategia de IA melhorada com multiplos indicadores tecnicos e filtros avancados.

FIX: todas as funcoes de calculo de indicadores foram removidas deste arquivo.
Elas existiam como copias exatas de features.py — qualquer correcao em um lugar
nao se propagava para o outro. Agora importamos diretamente de features.py.

FIX: suporte a modelo_cache_fn — permite que o chamador (main_app.py) injete
uma funcao de cache do session_state, evitando retreino a cada chamada.
"""

from typing import Dict, Optional, Callable
import pandas as pd
import numpy as np

# FIX: importa de features.py em vez de duplicar as funcoes localmente
from strategies.features import gerar_features_melhorada


def executar_estrategia_ai_melhorada(
    df: pd.DataFrame,
    posicao_aberta: bool = False,
    preco_compra: Optional[float] = None,
    config: Optional[Dict] = None,
    modelo_cache_fn: Optional[Callable] = None,
) -> Dict:
    """
    Executa estrategia de IA melhorada com multiplos filtros.

    Parametros:
        df              : DataFrame com colunas OHLCV
        posicao_aberta  : True se ha posicao aberta
        preco_compra    : preco de entrada na posicao (ou None)
        config          : dicionario com parametros da estrategia.
                          stop_loss_pct e take_profit_pct devem vir dos
                          sliders do sidebar via build_strategy_config().
        modelo_cache_fn : funcao opcional com assinatura (df, feature_cols) -> modelo.
                          Se fornecida, e usada para obter/treinar o modelo com cache
                          no session_state do Streamlit, evitando retreino a cada rerun.
                          Se None, treina um modelo novo a cada chamada (sem cache).

    Retorna um dicionario com:
        'sinal'    : 'buy', 'sell' ou 'hold'
        'confianca': 0.0 a 1.0
        'razao'    : string explicando a decisao
    """
    if config is None:
        config = {
            'min_confidence_buy': 0.70,
            'min_confidence_sell': 0.60,
            'min_rsi_buy': 35,
            'max_rsi_buy': 65,
            'min_rsi_sell': 40,
            'max_rsi_sell': 75,
            'min_adx': 25,
            'min_volume_ratio': 1.2,
            'stop_loss_pct': 0.02,
            'take_profit_pct': 0.03,
        }

    # FIX: usa gerar_features_melhorada de features.py (sem duplicacao)
    df = gerar_features_melhorada(df)

    if len(df) < 100:
        return {'sinal': 'hold', 'confianca': 0.0, 'razao': 'Dados insuficientes'}

    feature_cols = [
        'retorno', 'retorno_5', 'retorno_10',
        'ma_diff', 'ma_ratio', 'price_vs_ma5', 'price_vs_ma20',
        'rsi', 'macd', 'macd_signal', 'macd_hist',
        'bb_position', 'bb_width',
        'volume_ratio', 'volume_spike', 'obv_trend',
        'atr_pct', 'adx', 'volatility_pct'
    ]

    available_cols = [col for col in feature_cols if col in df.columns]
    if len(available_cols) < 10:
        return {'sinal': 'hold', 'confianca': 0.0, 'razao': 'Features insuficientes'}

    X = df[available_cols]

    # -------------------------------------------------------------------------
    # FIX: obtencao do modelo via cache ou treino local
    # Se modelo_cache_fn for fornecida (caso normal no main_app.py), usa o
    # session_state para evitar retreino a cada rerun do Streamlit.
    # Se nao for fornecida (uso standalone / testes), treina localmente.
    # -------------------------------------------------------------------------
    if modelo_cache_fn is not None:
        modelo = modelo_cache_fn(df, available_cols)
    else:
        from sklearn.ensemble import RandomForestClassifier
        y = (df['close'].shift(-1) > df['close']).astype(int)
        X_train = X[:-1].dropna()
        y_train = y[:-1].loc[X_train.index]
        if len(X_train) < 50:
            return {'sinal': 'hold', 'confianca': 0.0, 'razao': 'Dados de treino insuficientes'}
        modelo = RandomForestClassifier(
            n_estimators=200, max_depth=15,
            min_samples_split=5, random_state=42, n_jobs=-1
        )
        modelo.fit(X_train, y_train)

    if modelo is None:
        return {'sinal': 'hold', 'confianca': 0.0, 'razao': 'Modelo nao disponivel ainda'}

    # Previsao para o ultimo ponto
    X_last = X.iloc[[-1]]
    try:
        previsao = modelo.predict(X_last)[0]
        previsao_proba = modelo.predict_proba(X_last)[0]
        confianca = max(previsao_proba)
    except Exception:
        return {'sinal': 'hold', 'confianca': 0.0, 'razao': 'Erro na previsao do modelo'}

    ultimo = df.iloc[-1]

    # =========================================================================
    # LOGICA DE COMPRA
    # =========================================================================
    if not posicao_aberta:
        condicoes_obrigatorias = [
            previsao == 1,
            confianca >= config.get('min_confidence_buy', 0.60),
        ]

        condicoes_secundarias = [
            ultimo['rsi'] <= config.get('max_rsi_buy', 75),
            ultimo['adx'] >= config.get('min_adx', 20),
            ultimo['volume_ratio'] >= config.get('min_volume_ratio', 1.0),
            ultimo['macd'] > ultimo['macd_signal'] or ultimo['macd_hist'] > 0,
            ultimo['close'] > ultimo['ma_5'] or ultimo['ma_5'] > ultimo['ma_20'],
            ultimo['bb_position'] < 0.85,
        ]

        if all(condicoes_obrigatorias) and sum(condicoes_secundarias) >= 3:
            return {
                'sinal': 'buy',
                'confianca': confianca,
                'razao': (
                    f"Compra: Confianca {confianca:.1%}, "
                    f"RSI {ultimo['rsi']:.1f}, ADX {ultimo['adx']:.1f}, "
                    f"Condicoes {sum(condicoes_secundarias)}/6"
                )
            }

    # =========================================================================
    # LOGICA DE VENDA
    # =========================================================================
    elif posicao_aberta and preco_compra:
        lucro_pct = (ultimo['close'] - preco_compra) / preco_compra

        # Venda por stop loss — usa valor do sidebar via config
        if lucro_pct <= -config['stop_loss_pct']:
            return {
                'sinal': 'sell',
                'confianca': 1.0,
                'razao': f"Stop Loss: {lucro_pct:.2%} (limite: -{config['stop_loss_pct']:.2%})"
            }

        # Venda por take profit — usa valor do sidebar via config (com fator 1.5x)
        take_profit_ajustado = config.get('take_profit_pct', 0.03) * 1.5
        if lucro_pct >= take_profit_ajustado:
            return {
                'sinal': 'sell',
                'confianca': 1.0,
                'razao': f"Take Profit: {lucro_pct:.2%} (alvo: +{take_profit_ajustado:.2%})"
            }

        # Venda por sinais tecnicos — requer pelo menos 4 de 6 condicoes
        condicoes_venda_fortes = [
            previsao == 0 and confianca < config.get('min_confidence_sell', 0.50),
            ultimo['rsi'] >= config.get('max_rsi_sell', 80),
            ultimo['macd'] < ultimo['macd_signal'] and ultimo['macd_hist'] < 0,
            ultimo['close'] < ultimo['ma_5'] and ultimo['ma_5'] < ultimo['ma_20'],
            ultimo['bb_position'] > 0.9,
            ultimo['volume_ratio'] < 0.8,
        ]

        reversao_clara = (
            ultimo['macd'] < ultimo['macd_signal'] and
            ultimo['close'] < ultimo['ma_5'] and
            ultimo['rsi'] > 70
        )

        if sum(condicoes_venda_fortes) >= 4 or reversao_clara:
            return {
                'sinal': 'sell',
                'confianca': confianca,
                'razao': (
                    f"Venda tecnica: {sum(condicoes_venda_fortes)}/6 sinais fortes, "
                    f"Lucro {lucro_pct:.2%}"
                )
            }

    # =========================================================================
    # HOLD
    # =========================================================================
    return {
        'sinal': 'hold',
        'confianca': confianca,
        'razao': f"Hold: Confianca {confianca:.1%}, aguardando sinais mais claros"
    }
