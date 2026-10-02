import warnings
warnings.warn("'ai_strategy_corrigido.py' is deprecated. Use strategies/features.py and ai_strategy_melhorada.py instead.", DeprecationWarning)

from strategies.features import gerar_features_corrigido as gerar_features, calcular_rsi
from sklearn.ensemble import RandomForestClassifier
import pandas as pd

# EstratÃ©gia com controle de posiÃ§Ã£o: sÃ³ vende se jÃ¡ tiver comprado
def executar_estrategia_ai(df, posicao_aberta=False):
    df = gerar_features(df)
    df['target'] = (df['close'].shift(-1) > df['close']).astype(int)

    if len(df) < 100:
        return 'hold'

    X = df[['retorno', 'media_5', 'media_10', 'rsi', 'media_diff']]
    y = df['target']

    modelo = RandomForestClassifier(n_estimators=100, random_state=42)
    modelo.fit(X[:-1], y[:-1])

    previsao = modelo.predict(X.iloc[[-1]])[0]
    ultimo_rsi = df.iloc[-1]['rsi']
    media_diff = df.iloc[-1]['media_diff']

    # CritÃ©rios adicionais baseados em indicadores:
    if not posicao_aberta and previsao == 1 and ultimo_rsi < 70 and media_diff > 0:
        return 'buy'
    elif posicao_aberta and previsao == 0 and ultimo_rsi > 30 and media_diff < 0:
        return 'sell'
    else:
        return 'hold'
