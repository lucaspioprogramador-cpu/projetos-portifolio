# -*- coding: utf-8 -*-

import logging
import hmac
import math
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import time
from datetime import datetime, timedelta
import pytz
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from binance.client import Client
from binance import ThreadedWebsocketManager
from core.execution import executar_ordem_simulada, apply_simulated_fill
from core.risk import position_size, affordable_quantity, exposure_budget
import queue
import os
import json
import tempfile
import uuid
from pathlib import Path
from config.settings import DEFAULT_TIMEFRAME
from db.database import registrar_candle, registrar_candles, get_candles, registrar_trade, count_trades_e_candles, get_trades
from core.data import is_closed_candle
import warnings

warnings.filterwarnings(
    "ignore",
    message=".*sklearn.utils.parallel.delayed.*"
)

# FIX: importa apenas a estrategia melhorada â€” deprecated (ai_strategy.py) removido
from strategies.ai_strategy_melhorada import RuleBasedTrendModel, executar_estrategia_ai_melhorada
from strategies.features import gerar_features_basic, gerar_features_melhorada
from signal_preview_panel import render_signal_panel
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
logger = logging.getLogger(__name__)

BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')
st.set_page_config(page_title="Trading Bot Dashboard", layout="wide")

# Proteção básica opcional para instâncias expostas fora do computador local.
_APP_PASSWORD = os.getenv('APP_PASSWORD', '')
if _APP_PASSWORD:
    if not st.session_state.get('authenticated', False):
        st.title('Acesso ao Trading Bot')
        with st.form('login_form'):
            _password_input = st.text_input('Senha de acesso', type='password')
            _login_submitted = st.form_submit_button('Entrar')
        if _login_submitted and hmac.compare_digest(_password_input, _APP_PASSWORD):
            st.session_state['authenticated'] = True
            st.rerun()
        if _login_submitted:
            st.error('Senha inválida')
        st.stop()


# ---------------------------------------------------------------------------
# Utilitarios
# ---------------------------------------------------------------------------

def carregar_config_telegram():
    return "", ""


def caminho_estado_bot():
    """Retorna snapshot local isolado para a sessão corrente do Streamlit."""
    state_dir = Path(os.getenv('BOT_STATE_DIR', Path.cwd() / '.bot_state'))
    state_dir.mkdir(parents=True, exist_ok=True)
    state_id = st.session_state.setdefault('_snapshot_id', uuid.uuid4().hex)
    return state_dir / f"estado_bot_{state_id}.json"


def salvar_estado_bot():
    """
    Persiste saldo atual e todas as ordens abertas em estado_bot.json.
    Chamado automaticamente quando o bot para, garantindo que o estado
    seja restaurado na proxima vez que o bot ligar.
    """
    try:
        estado_file = caminho_estado_bot()
        posicoes_raw = st.session_state.bot_data.get('posicoes', {})

        # Serializa as ordens — converte timestamps para string
        posicoes_serializadas = {}
        for sym, ordens in posicoes_raw.items():
            if isinstance(ordens, list):
                posicoes_serializadas[sym] = [
                    {k: str(v) if hasattr(v, 'isoformat') else v for k, v in o.items()}
                    for o in ordens
                ]
            else:
                # compatibilidade com formato antigo (dict simples)
                posicoes_serializadas[sym] = ordens

        trades_serializados = []
        for t in st.session_state.bot_data.get('trades', []):
            t_copy = dict(t)
            if hasattr(t_copy.get('timestamp'), 'isoformat'):
                t_copy['timestamp'] = t_copy['timestamp'].isoformat()
            trades_serializados.append(t_copy)

        estado = {
            'saldo_usdt':   st.session_state.bot_data.get('saldo_usdt', 0),
            'saldo_inicial': st.session_state.bot_data.get('saldo_inicial', 0),
            'posicoes':     posicoes_serializadas,
            'trades':       trades_serializados,
            'salvo_em':     datetime.now(BRAZIL_TZ).isoformat(),
        }

        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', delete=False, dir=estado_file.parent,
            prefix='.estado_bot_', suffix='.tmp'
        ) as temp_file:
            json.dump(estado, temp_file, ensure_ascii=False, indent=2)
            temp_path = temp_file.name
        os.replace(temp_path, estado_file)

        logger.info("Estado da sessão salvo localmente")
    except Exception as e:
        logger.exception("Erro ao salvar estado do bot: %s", e)


def carregar_estado_bot():
    """
    Restaura saldo e ordens abertas do arquivo estado_bot.json.
    Chamado na inicializacao do bot se o arquivo existir.
    Retorna True se o estado foi restaurado, False caso contrario.
    """
    try:
        estado_file = caminho_estado_bot()
        if not estado_file.exists():
            return False

        with open(estado_file, 'r', encoding='utf-8') as f:
            estado = json.load(f)

        st.session_state.bot_data['saldo_usdt'] = estado.get('saldo_usdt', st.session_state.bot_data['saldo_usdt'])
        st.session_state.bot_data['saldo_inicial'] = estado.get('saldo_inicial', st.session_state.bot_data['saldo_inicial'])
        posicoes = estado.get('posicoes', {})
        trades = estado.get('trades', [])
        saldo = estado.get('saldo_usdt', st.session_state.bot_data['saldo_usdt'])
        saldo_inicial_salvo = estado.get('saldo_inicial', st.session_state.bot_data['saldo_inicial'])
        if not isinstance(posicoes, dict) or not isinstance(trades, list):
            raise ValueError("Snapshot contém posições ou trades em formato inválido")
        if any(not isinstance(trade, dict) for trade in trades):
            raise ValueError("Snapshot contém trade incompatível")
        if not all(isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 for value in (saldo, saldo_inicial_salvo)):
            raise ValueError("Snapshot contém saldo inválido")
        for sym, ordens in list(posicoes.items()):
            if isinstance(ordens, dict):
                # Migra de forma segura o formato legado de uma posição por par.
                ordens = [{
                    'preco_compra': ordens.get('preco_compra', 0),
                    'quantidade': ordens.get('quantidade', 0),
                    'valor_investido': ordens.get('valor_investido', 0),
                    'timestamp': ordens.get('timestamp', ''),
                }] if ordens.get('aberta') else []
                posicoes[sym] = ordens
            if not isinstance(ordens, list):
                raise ValueError("Snapshot contém posição incompatível; estado não restaurado")
            for ordem in ordens:
                if not isinstance(ordem, dict) or not all(
                    isinstance(ordem.get(key), (int, float))
                    and math.isfinite(ordem[key]) and ordem[key] >= 0
                    for key in ('preco_compra', 'quantidade', 'valor_investido')
                ):
                    raise ValueError("Snapshot contém ordem inválida; estado não restaurado")
        st.session_state.bot_data['saldo_usdt'] = saldo
        st.session_state.bot_data['saldo_inicial'] = saldo_inicial_salvo
        st.session_state.bot_data['posicoes'] = posicoes
        st.session_state.bot_data['trades'] = trades

        salvo_em = estado.get('salvo_em', 'desconhecido')
        logger.info("Snapshot local da sessão restaurado (salvo em: %s)", salvo_em)
        return True

    except Exception as e:
        logger.exception("Erro ao carregar estado do bot: %s", e)
        return False


def enviar_notificacao_telegram(mensagem, force=False):
    try:
        if not force and not st.session_state.get('notificacoes_ativas', False):
            return False
        token = st.session_state.get('telegram_token', '').strip()
        chat_id = st.session_state.get('telegram_chat_id', '').strip()
        if not token or not chat_id:
            logger.warning("Telegram: token ou chat_id vazios")
            return False
        if ':' not in token:
            logger.warning("Telegram: token invalido (sem ':')")
            return False
        if not (chat_id.lstrip('-').isdigit() or chat_id.startswith('@')):
            logger.warning("Telegram: chat_id invalido")
            return False
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}
        logger.info("Enviando mensagem para Telegram...")
        response = requests.post(url, data=data, timeout=10)
        result = response.json()
        if result.get("ok"):
            logger.info("Mensagem Telegram enviada com sucesso")
            return True
        else:
            logger.error("Telegram erro: %s", result.get("description", "Erro desconhecido"))
            return False
    except requests.exceptions.Timeout:
        logger.error("Telegram: timeout na conexao")
        return False
    except requests.exceptions.ConnectionError as e:
        logger.error("Telegram: erro de conexão (%s)", type(e).__name__)
        return False
    except Exception as e:
        # Não incluir mensagem/URL da exceção: a URL da API contém o token.
        logger.error("Telegram: erro geral (%s)", type(e).__name__)
        return False


def now_brazil():
    return datetime.now(BRAZIL_TZ)


def format_time(dt):
    return dt.strftime("%d/%m/%Y %H:%M:%S")


def calcular_posicao(saldo, preco, risco, stop_pct):
    return position_size(saldo, risco, stop_pct, preco)


# ---------------------------------------------------------------------------
# Configuracao de simbolos e pagina
# ---------------------------------------------------------------------------

symbols = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    "LTC/USDT", "PEPE/USDT", "PENDLE/USDT", "JTO/USDT", "BB/USDT", "SUI/USDT"
]

st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #0a0e27; }
    .main { background-color: #0f1419; }
    .sidebar-title { color: #ffffff; font-size: 18px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    if 'telegram_loaded' not in st.session_state:
        telegram_token_loaded, telegram_chat_id_loaded = carregar_config_telegram()
        st.session_state['telegram_token'] = telegram_token_loaded
        st.session_state['telegram_chat_id'] = telegram_chat_id_loaded
        st.session_state['telegram_loaded'] = True

    st.caption("A Binance fornece candles públicos sem API Key. Este app não envia ordens reais.")
    st.markdown("---")
    st.markdown('<div class="sidebar-title">Notificacoes Telegram</div>', unsafe_allow_html=True)

    telegram_token_input = st.text_input(
        "", value=st.session_state.get('telegram_token', ''),
        type="password", placeholder="Cole o token do seu bot",
        label_visibility="collapsed", key="telegram_token_input"
    )
    telegram_chat_id_input = st.text_input(
        "", value=st.session_state.get('telegram_chat_id', ''),
        placeholder="Seu chat ID", label_visibility="collapsed",
        key="telegram_chat_id_input"
    )

    st.markdown("**Notificacoes Ativas**")
    notificacoes_ativas = st.checkbox(
        "Enviar notificacoes no Telegram",
        value=st.session_state.get('notificacoes_ativas', False),
        key="notificacoes_ativas"
    )

    col_test, col_save_telegram = st.columns(2)
    with col_test:
        if st.button("Testar Notificacao", use_container_width=True, key="test_telegram"):
            if telegram_token_input and telegram_chat_id_input:
                st.session_state['telegram_token'] = telegram_token_input
                st.session_state['telegram_chat_id'] = telegram_chat_id_input
                mensagem_teste = (
                    f"TESTE DE NOTIFICACAO\n"
                    f"Configuracao funcionando!\n"
                    f"{datetime.now(BRAZIL_TZ).strftime('%d/%m/%Y %H:%M:%S')}"
                )
                try:
                    resultado = enviar_notificacao_telegram(mensagem_teste, force=True)
                    if resultado:
                        st.success("Mensagem de teste enviada!")
                    else:
                        st.error("Falha ao enviar mensagem de teste")
                except Exception as e:
                    st.error(f"Erro ao enviar teste: {str(e)}")
            else:
                st.warning("Configure o token e chat ID primeiro")
    with col_save_telegram:
        if st.button("Usar Telegram nesta sessão", use_container_width=True, key="save_telegram"):
            st.session_state['telegram_token'] = telegram_token_input
            st.session_state['telegram_chat_id'] = telegram_chat_id_input
            st.success("Telegram disponível apenas nesta sessão; configuração não gravada em disco.")

    with st.expander("Como obter Token e Chat ID do Telegram"):
        st.markdown("""
        ### 1. Criar Bot no Telegram
        - Procure por **@BotFather** no Telegram
        - Digite `/newbot` e siga as instrucoes
        - **Copie o TOKEN** gerado

        ### 2. Obter Chat ID
        - Inicie uma conversa com seu bot
        - Envie qualquer mensagem para ele
        - Acesse: `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates`
        - Procure por `"chat":{"id":XXXXX` na resposta

        ### 3. Testar
        - Use o botao **"Testar Notificacao"** para enviar uma mensagem real
        """)

    st.divider()
    st.markdown('<div class="sidebar-title">Parametros de Operacao</div>', unsafe_allow_html=True)

    st.markdown("**Par de Negociacao**")
    symbol = st.selectbox(
        "", [s.replace("/", "") for s in symbols],
        label_visibility="collapsed", index=0
    )
    symbol = symbol.replace("USDT", "/USDT")
    if symbol not in symbols:
        st.error("Par invalido!")

    st.markdown("**Timeframe**")
    timeframe_options = ["1m", "5m", "15m", "30m", "1h", "4h"]
    timeframe = st.selectbox(
        "", timeframe_options,
        label_visibility="collapsed",
        index=timeframe_options.index(DEFAULT_TIMEFRAME)
        if DEFAULT_TIMEFRAME in timeframe_options else 0,
    )

    st.markdown("**Saldo Inicial (USDT)**")
    saldo_inicial = st.number_input(
        "", min_value=100, value=1000, label_visibility="collapsed"
    )

    st.markdown("**Risco por Trade (%)**")
    risco_por_trade_display = st.slider("", 0.1, 5.0, 1.0, label_visibility="collapsed")
    risco_por_trade = risco_por_trade_display / 100
    st.caption("1/5")

    st.markdown("**Exposição máxima total (%)**")
    max_exposicao_total = st.slider("", 10, 100, 50, label_visibility="collapsed", key="max_exposicao_total") / 100
    st.markdown("**Exposição máxima por par (%)**")
    max_exposicao_par = st.slider("", 5, 100, 25, label_visibility="collapsed", key="max_exposicao_par") / 100

    st.markdown("**Stop Loss (%)**")
    stop_loss_display = st.slider("", 0.1, 10.0, 2.0, label_visibility="collapsed", key="sl")
    stop_loss = stop_loss_display / 100
    st.caption("2/10")

    st.markdown("**Take Profit (%)**")
    take_profit_display = st.slider("", 0.1, 10.0, 3.0, label_visibility="collapsed", key="tp")
    take_profit = take_profit_display / 100
    st.caption("3/15")

    st.divider()

    with st.expander("Configuracoes Avancadas"):
        usar_simulacao = st.checkbox(
            "Aplicar custos realistas na simulação", value=True,
            help="Se desmarcado, continua sendo simulação: usa fill teórico e taxa, sem slippage nem fill parcial. Nunca envia ordens reais."
        )
        usar_estrategia_melhorada = st.checkbox(
            "Usar Estrategia Melhorada (IA)", value=True,
            help="Usa estrategia avancada com multiplos indicadores"
        )
        mostrar_detalhes_execucao = st.checkbox(
            "Mostrar Detalhes de Execucao", value=True,
            help="Mostra slippage, taxas e outros detalhes"
        )

    st.session_state['usar_simulacao'] = usar_simulacao
    st.session_state['usar_estrategia_melhorada'] = usar_estrategia_melhorada
    st.session_state['mostrar_detalhes_execucao'] = mostrar_detalhes_execucao
    st.divider()


# ---------------------------------------------------------------------------
# FIX: config da estrategia melhorada montado a partir dos sliders do sidebar.
# Antes os valores de stop_loss e take_profit eram hardcoded dentro do arquivo
# de estrategia (2% e 1% fixos). Agora chegam diretamente dos controles da UI.
# ---------------------------------------------------------------------------

def build_strategy_config():
    return {
        'min_confidence_buy': 0.70,
        'min_confidence_sell': 0.50,
        'min_rsi_buy': 35,
        'max_rsi_buy': 75,
        'min_rsi_sell': 40,
        'max_rsi_sell': 80,
        'min_adx': 20,
        'min_volume_ratio': 1.0,
        'stop_loss_pct': stop_loss,      # vem do slider do sidebar
        'take_profit_pct': take_profit,  # vem do slider do sidebar
    }


# ---------------------------------------------------------------------------
# Estado do bot
# ---------------------------------------------------------------------------

if 'bot_running' not in st.session_state:
    st.session_state['bot_running'] = False


def ensure_bot_state():
    defaults = {
        'saldo_usdt': saldo_inicial,
        'saldo_inicial': saldo_inicial,
        # MULTI-PAR: estado de posicao por par
        'posicoes': {},
        'trades': [],
        'inicio_operacao': None,
        'ultimo_sinal': None,
        'dados_mercado': {},
        'conexao_websocket': None,
        'client': None,
        'ultima_atualizacao': None,
        'eventos_ws': {}
    }
    if 'bot_data' not in st.session_state or not isinstance(st.session_state.get('bot_data'), dict):
        st.session_state['bot_data'] = defaults
        return
    for key, value in defaults.items():
        st.session_state.bot_data.setdefault(key, value)
    if st.session_state.bot_data.get('saldo_inicial') != saldo_inicial:
        posicoes_abertas = any(
            bool(ordens) if isinstance(ordens, list)
            else bool(isinstance(ordens, dict) and ordens.get('aberta'))
            for ordens in st.session_state.bot_data.get('posicoes', {}).values()
        )
        possui_trades = bool(st.session_state.bot_data.get('trades'))
        st.session_state.bot_data['saldo_inicial'] = saldo_inicial
        if not posicoes_abertas and not possui_trades:
            st.session_state.bot_data['saldo_usdt'] = saldo_inicial


ensure_bot_state()
if '_ws_candle_queue' not in st.session_state:
    st.session_state['_ws_candle_queue'] = queue.Queue(maxsize=500)

# Restaura estado salvo se existir e ainda nao foi carregado nesta sessao
if not st.session_state.get('estado_restaurado', False):
    if carregar_estado_bot():
        st.session_state['estado_restaurado'] = True
        logger.info("Estado anterior do bot restaurado com sucesso")
    else:
        st.session_state['estado_restaurado'] = True  # marca mesmo sem arquivo

# ---------------------------------------------------------------------------
# FIX: cache do modelo RandomForest no session_state.
# Antes o modelo era instanciado e treinado com modelo.fit() dentro de
# executar_estrategia_ai_melhorada() a cada chamada â€” ou seja, a cada candle
# e a cada rerun do Streamlit (200 arvores * centenas de candles = lento).
# Agora o modelo e treinado uma vez e reutilizado. So retreina quando chegam
# pelo menos 10 candles novos desde o ultimo treino.
# ---------------------------------------------------------------------------

def obter_modelo_treinado(df: pd.DataFrame, feature_cols: list, symbol_key: str = 'default'):
    """
    Retorna o modelo RandomForest do cache (session_state) ou treina um novo
    se ainda nao existe ou se chegaram dados novos suficientes.
    """
    cache_key = f'rf_model_cache_{symbol_key}'
    timestamp_key = f'rf_model_ultimo_timestamp_{symbol_key}'
    count_key = f'rf_model_candles_novos_{symbol_key}'
    modelo_cache = st.session_state.get(cache_key)
    idx_atual = len(df)
    timestamp_atual = str(df.iloc[-1].get('timestamp', idx_atual)) if not df.empty else str(idx_atual)

    if isinstance(modelo_cache, RuleBasedTrendModel):
        return modelo_cache

    try:
        from sklearn.ensemble import RandomForestClassifier
    except ImportError as error:
        logger.warning(
            "scikit-learn indisponível (%s); usando fallback heurístico determinístico",
            type(error).__name__,
        )
        st.session_state['ml_fallback_active'] = True
        modelo_cache = RuleBasedTrendModel()
        st.session_state[cache_key] = modelo_cache
        st.session_state[timestamp_key] = timestamp_atual
        st.session_state[count_key] = 0
        return modelo_cache

    timestamp_anterior = st.session_state.get(timestamp_key)
    candles_novos = st.session_state.get(count_key, 0)
    if timestamp_atual != timestamp_anterior:
        candles_novos = 0 if timestamp_anterior is None else candles_novos + 1
        st.session_state[timestamp_key] = timestamp_atual
        st.session_state[count_key] = candles_novos

    deve_treinar = modelo_cache is None or candles_novos >= 10

    if deve_treinar:
        X = df[feature_cols].copy()
        y = (df['close'].shift(-1) > df['close']).astype(int)
        X_train = X[:-1].dropna()
        y_train = y[:-1].loc[X_train.index]

        if len(X_train) < 50:
            return modelo_cache

        modelo = RandomForestClassifier(
            n_estimators=200, max_depth=15,
            min_samples_split=5, random_state=42, n_jobs=-1
        )
        try:
            modelo.fit(X_train, y_train)
        except ImportError as error:
            logger.warning(
                "Runtime compilado do scikit-learn falhou (%s); usando fallback heurístico determinístico",
                type(error).__name__,
            )
            st.session_state['ml_fallback_active'] = True
            modelo = RuleBasedTrendModel()
        st.session_state[cache_key] = modelo
        st.session_state[count_key] = 0
        logger.info("Modelo RF retreinado com %d amostras (idx %d)", len(X_train), idx_atual)
        return modelo

    return modelo_cache


# ---------------------------------------------------------------------------
# MULTI-PAR: helper de estado por par
# ---------------------------------------------------------------------------

def get_ordens(sym: str) -> list:
    """
    Retorna a lista de ordens abertas para um par.
    Cada ordem e um dict com: preco_compra, quantidade, valor_investido, timestamp.
    Uma lista vazia significa sem posicao aberta.
    Migra automaticamente o formato antigo (dict com 'aberta') para lista.
    """
    posicoes = st.session_state.bot_data.setdefault('posicoes', {})
    if sym not in posicoes:
        posicoes[sym] = []
    # migra formato antigo (dict) para lista
    if isinstance(posicoes[sym], dict):
        antiga = posicoes[sym]
        if antiga.get('aberta'):
            posicoes[sym] = [{
                'preco_compra':   antiga.get('preco_compra', 0),
                'quantidade':     antiga.get('quantidade', 0),
                'valor_investido': antiga.get('valor_investido', 0),
                'timestamp':      str(now_brazil()),
            }]
        else:
            posicoes[sym] = []
    return posicoes[sym]


def get_posicao(sym: str) -> dict:
    """
    Compatibilidade retroativa — retorna um dict com 'aberta' e dados da
    primeira ordem aberta. Use get_ordens() para acesso completo a multiplas ordens.
    """
    ordens = get_ordens(sym)
    if ordens:
        return {'aberta': True, **ordens[0]}
    return {'aberta': False, 'preco_compra': None, 'quantidade': 0, 'valor_investido': 0}


# ---------------------------------------------------------------------------
# Logica de trades
# ---------------------------------------------------------------------------

def analisar_e_executar_trades():
    """
    MULTI-PAR: analisa e executa trades para todos os pares com dados suficientes.
    Cada par tem seu proprio estado de posicao via get_posicao(sym).
    O saldo USDT e compartilhado — verificacao de saldo antes de cada compra.
    """
    if not st.session_state.get('bot_running', False):
        return

    usar_melhorada = st.session_state.get('usar_estrategia_melhorada', True)
    config = build_strategy_config()

    pares_com_dados = [
        sym for sym, df in st.session_state.bot_data['dados_mercado'].items()
        if isinstance(df, pd.DataFrame) and not df.empty and len(df) >= 100
    ]

    if not pares_com_dados:
        return

    for sym in pares_com_dados:
        try:
            df = st.session_state.bot_data['dados_mercado'][sym]
            candle_id = str(df.iloc[-1].get('timestamp', len(df)))
            processed_key = f"ultimo_candle_avaliado_{sym}_{timeframe}"
            if st.session_state.get(processed_key) == candle_id:
                continue
            # Cada candle fechado pode gerar no máximo uma decisão por par/timeframe.
            st.session_state[processed_key] = candle_id
            posicao = get_posicao(sym)

            if usar_melhorada:
                resultado = executar_estrategia_ai_melhorada(
                    df,
                    posicao_aberta=posicao['aberta'],
                    preco_compra=posicao['preco_compra'],
                    config=config,
                    modelo_cache_fn=lambda frame, cols, pair=sym: obter_modelo_treinado(frame, cols, pair),
                )
                sinal = resultado.get('sinal', 'hold')
                logger.info(
                    "[%s] sinal=%s confianca=%.2f razao=%s",
                    sym, sinal, resultado.get('confianca', 0), resultado.get('razao', '')
                )
            else:
                df_feat = gerar_features_basic(df)
                if len(df_feat) < 10:
                    continue
                ultimo = df_feat.iloc[-1]
                if not posicao['aberta']:
                    sinal = 'buy' if (
                        ultimo['rsi'] < 65 and
                        ultimo['close'] > ultimo['media_20'] and
                        ultimo['macd'] > ultimo['macd_signal'] and
                        ultimo['volume_spike'] == 1
                    ) else 'hold'
                else:
                    lucro_pct = 0.0
                    if posicao['preco_compra']:
                        lucro_pct = (ultimo['close'] - posicao['preco_compra']) / posicao['preco_compra']
                    sinal = 'sell' if (
                        lucro_pct >= take_profit or
                        lucro_pct <= -stop_loss or
                        ultimo['rsi'] > 70 or
                        ultimo['macd'] < ultimo['macd_signal']
                    ) else 'hold'

            saldo_disponivel = st.session_state.bot_data.get('saldo_usdt', 0)
            ordens_abertas = get_ordens(sym)
            preco_atual = df.iloc[-1]['close']

            if sinal == 'buy':
                total_investido = sum(
                    ordem.get('valor_investido', 0)
                    for ordens_ativas in st.session_state.bot_data.get('posicoes', {}).values()
                    if isinstance(ordens_ativas, list)
                    for ordem in ordens_ativas
                )
                investido_par = sum(
                    ordem.get('valor_investido', 0) for ordem in ordens_abertas
                )
                exposicao_disponivel = exposure_budget(
                    saldo_inicial,
                    total_investido,
                    investido_par,
                    max_exposicao_total,
                    max_exposicao_par,
                )
                caixa_para_entrada = min(saldo_disponivel, exposicao_disponivel)
                quantidade = calcular_posicao(saldo_disponivel, preco_atual, risco_por_trade, stop_loss)
                quantidade_caixa = affordable_quantity(
                    caixa_para_entrada, preco_atual,
                    fee_rate=0.001, max_slippage=0.05, spread_pct=0.0002,
                )
                quantidade = min(quantidade, quantidade_caixa)
                valor_necessario = preco_atual * quantidade

                if valor_necessario <= 0 or valor_necessario > saldo_disponivel:
                    logger.warning(
                        "[%s] Saldo insuficiente para nova compra: necessario=%.2f disponivel=%.2f",
                        sym, valor_necessario, saldo_disponivel
                    )
                else:
                    trade = executar_ordem('COMPRA', preco_atual, quantidade, sym=sym)
                    logger.info(
                        "[%s] COMPRA #%d: preco=%.2f qtd=%.4f (ordens abertas: %d)",
                        sym, len(get_ordens(sym)), preco_atual, quantidade, len(get_ordens(sym))
                    )

            elif sinal == 'sell' and ordens_abertas:
                # Vende TODAS as ordens abertas do par de uma vez
                for ordem in list(ordens_abertas):
                    if ordem.get('quantidade', 0) > 0:
                        trade = executar_ordem(
                            'VENDA', preco_atual, ordem['quantidade'],
                            sym=sym, ordem_ref=ordem
                        )
                        logger.info(
                            "[%s] VENDA: preco=%.2f qtd=%.4f lucro=%.2f%%",
                            sym, preco_atual, ordem['quantidade'],
                            trade.get('retorno', 0)
                        )

        except Exception as e:
            logger.exception("[%s] Erro na analise de trades: %s", sym, e)


def executar_ordem(tipo, preco, quantidade, usar_simulacao=None, sym=None, ordem_ref=None):
    """
    MULTI-ORDEM: executa uma ordem para o par especificado.
    - COMPRA: adiciona uma nova entrada na lista get_ordens(sym)
    - VENDA: remove a ordem referenciada (ordem_ref) da lista e calcula lucro
    O limite de ordens abertas e o saldo disponivel — nao ha teto fixo.
    """
    sym = sym or symbol

    if usar_simulacao is None:
        usar_simulacao = st.session_state.get('usar_simulacao', True)

    lado = 'buy' if tipo == 'COMPRA' else 'sell'
    volatilidade = None
    volume_24h = None

    if sym in st.session_state.bot_data['dados_mercado']:
        df = st.session_state.bot_data['dados_mercado'][sym]
        if len(df) >= 20:
            volatilidade = df['close'].pct_change().std()
            timeframe_minutes = {'1m': 1, '5m': 5, '15m': 15, '30m': 30, '1h': 60, '4h': 240}.get(timeframe, 1)
            bars_per_day = 1_440 // timeframe_minutes
            recent_volume = df['volume'].tail(min(len(df), bars_per_day))
            # Estima 24h pela média recente caso o buffer de 500 barras seja menor.
            volume_24h = (recent_volume.mean() * bars_per_day * preco) if not recent_volume.empty else None

    if usar_simulacao:
        execucao = executar_ordem_simulada(
            lado=lado, quantidade=quantidade, preco_atual=preco,
            symbol=sym, volume_24h=volume_24h, volatilidade=volatilidade
        )
        preco_exec = execucao['preco_execucao']
        quantidade_exec = execucao['quantidade_executada']
        taxas = execucao['taxas']
        slippage_pct = execucao['slippage_pct']
        valor_total = execucao['valor_total']
        valor_liquido = execucao['valor_liquido']
    else:
        preco_exec = preco
        quantidade_exec = quantidade
        taxas = preco * quantidade * 0.001
        slippage_pct = 0.0
        valor_total = preco * quantidade
        if tipo == 'COMPRA':
            valor_liquido = valor_total + taxas
        else:
            valor_liquido = valor_total - taxas

        execucao = {
            'preco_execucao': preco_exec,
            'quantidade_executada': quantidade_exec,
            'valor_total': valor_total,
            'taxas': taxas,
            'valor_liquido': valor_liquido,
            'executada': True,
            'executada_completa': True,
        }

    quantidade_exec = execucao.get('quantidade_executada', 0.0)
    if quantidade_exec <= 0:
        logger.warning("[%s] Fill vazio; nenhuma posição ou trade foi registrado", sym)
        return None

    trade = {
        'timestamp': now_brazil(),
        'symbol': sym,
        'tipo': tipo,
        'preco_solicitado': preco,
        'preco_execucao': preco_exec,
        'quantidade_solicitada': quantidade,
        'quantidade_executada': quantidade_exec,
        'valor_total': valor_total,
        'taxas': taxas,
        'slippage_pct': slippage_pct,
        'valor_liquido': valor_liquido
    }

    ordens = get_ordens(sym)
    fill_result = apply_simulated_fill(
        balance=st.session_state.bot_data['saldo_usdt'],
        positions=ordens,
        side=lado,
        execution=execucao,
        order_ref=ordem_ref,
    )
    st.session_state.bot_data['saldo_usdt'] = fill_result['balance']

    if tipo == 'COMPRA':
        fill_result['position']['timestamp'] = str(now_brazil())
        logger.info("[%s] Fill de compra aplicado; posições abertas: %d", sym, len(ordens))
    else:
        trade['lucro'] = fill_result['pnl']
        trade['lucro_liquido'] = trade['lucro']
        cost_basis = fill_result['cost_basis']
        trade['retorno'] = (trade['lucro'] / cost_basis * 100) if cost_basis > 0 else 0
        trade['retorno_liquido'] = trade['retorno']
        logger.info("[%s] Fill de venda aplicado. Restam posições: %d", sym, len(ordens))

    trade['valor_liquido'] = execucao['valor_liquido']

    st.session_state.bot_data['trades'].append(trade)

    try:
        registrar_trade(trade)
    except Exception as e:
        logger.error("Falha ao persistir trade no banco — ordem executada mas nao salva: %s", e)

    logger.info(
        "Ordem executada - [%s] Tipo: %s | Preco: %.2f | Qtd: %.4f | Valor Liquido: %.2f",
        sym, tipo, preco_exec, quantidade_exec, valor_liquido
    )
    enviar_notificacao_telegram(
        f"Ordem executada - {sym}\n"
        f"Tipo: {tipo}\n"
        f"Preco: {preco_exec:.2f}\n"
        f"Quantidade: {quantidade_exec:.4f}\n"
        f"Valor Liquido: {valor_liquido:.2f}"
    )
    return trade


def atualizar_dados_mercado(symbol_proc, novo_dado):
    if symbol_proc not in st.session_state.bot_data['dados_mercado']:
        st.session_state.bot_data['dados_mercado'][symbol_proc] = pd.DataFrame([novo_dado])
    else:
        st.session_state.bot_data['dados_mercado'][symbol_proc] = pd.concat([
            st.session_state.bot_data['dados_mercado'][symbol_proc],
            pd.DataFrame([novo_dado])
        ]).drop_duplicates().tail(500)
    st.session_state['dados_grafico_atualizados'] = True


# ---------------------------------------------------------------------------
# Conexao WebSocket
# ---------------------------------------------------------------------------

def carregar_historico_par(client, sym: str, tf: str, limit: int = 500):
    """
    Busca os ultimos `limit` candles de `sym` via REST e carrega direto
    no dados_mercado do session_state. Chamado uma vez na inicializacao
    para cada par selecionado — o bot nao precisa esperar os candles chegarem
    tick a tick pelo websocket para comecar a analisar.
    """
    try:
        sym_rest = sym.replace('/', '')
        logger.info("[%s] Buscando %d candles historicos (timeframe=%s)...", sym, limit, tf)

        bars = client.get_klines(symbol=sym_rest, interval=tf, limit=limit)
        if not bars:
            logger.warning("[%s] Nenhum candle retornado", sym)
            return None

        registros = []
        for b in bars:
            # A REST API também retorna o candle corrente, ainda incompleto.
            if len(b) > 6 and int(b[6]) >= int(time.time() * 1000):
                continue
            registros.append({
                'timestamp': pd.to_datetime(
                    b[6] if len(b) > 6 else b[0], unit='ms'
                ).tz_localize('UTC').tz_convert(BRAZIL_TZ).strftime('%Y-%m-%d %H:%M:%S'),
                'open':   float(b[1]),
                'high':   float(b[2]),
                'low':    float(b[3]),
                'close':  float(b[4]),
                'volume': float(b[5]),
                'timeframe': tf,
            })

        df_hist = pd.DataFrame(registros)
        if df_hist.empty:
            return None
        df_hist['timestamp'] = pd.to_datetime(df_hist['timestamp'])

        logger.info("[%s] %d candles carregados com sucesso", sym, len(df_hist))

        # Persiste no banco em background (nao bloqueia a UI)
        try:
            registrar_candles(sym_rest, registros)
        except Exception as e:
            logger.warning("[%s] Erro ao persistir historico no banco: %s", sym, e)
        return df_hist

    except Exception as e:
        logger.exception("[%s] Erro ao carregar historico: %s", sym, e)
        return None


def iniciar_conexao(selected_symbols):
    if not selected_symbols:
        st.error("Selecione ao menos um par para monitorar.")
        return False

    candle_queue: queue.Queue = queue.Queue(maxsize=500)
    st.session_state['_ws_candle_queue'] = candle_queue
    twm = None

    try:
        logger.info("Iniciando conexao com Binance para pares: %s", selected_symbols)
        # Market data é público. Chaves são opcionais e não habilitam execução real.
        client = Client(ping=False)

        # ---------------------------------------------------------------------
        # CARGA HISTORICA: busca 500 candles de cada par selecionado em paralelo
        # antes de ligar o websocket, para o bot ja comecar com dados suficientes.
        # Sem isso o bot ficaria aguardando ~100 candles chegarem tick a tick
        # pelo websocket antes de poder analisar qualquer sinal.
        # ---------------------------------------------------------------------
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with st.spinner(f"Carregando historico de {len(selected_symbols)} par(es)..."):
            with ThreadPoolExecutor(max_workers=min(len(selected_symbols), 5)) as executor:
                futures = {
                    executor.submit(carregar_historico_par, client, sym, timeframe, 500): sym
                    for sym in selected_symbols
                }
                for future in as_completed(futures):
                    sym_done = futures[future]
                    try:
                        hist = future.result()
                        if hist is not None:
                            # Somente a thread principal acessa o estado da sessão Streamlit.
                            st.session_state.bot_data['dados_mercado'][sym_done] = hist
                        logger.info("[%s] Historico carregado", sym_done)
                    except Exception as e:
                        logger.error("[%s] Falha ao carregar historico: %s", sym_done, e)

        # ---------------------------------------------------------------------
        # WEBSOCKET: inicia apos o historico estar carregado
        # ---------------------------------------------------------------------
        twm = ThreadedWebsocketManager()

        try:
            twm.start()
        except Exception as e_start:
            logger.warning("Erro ao iniciar WebsocketManager (tentativa 1): %s", e_start)
            try:
                twm.stop()
                twm = ThreadedWebsocketManager()
                twm.start()
            except Exception as e_retry:
                raise RuntimeError(f"WebsocketManager falhou apos retry: {e_retry}")

        logger.info("ThreadedWebsocketManager iniciado.")

        def handle_socket_message(msg):
            if msg.get('e') == 'error' or 'error' in msg:
                logger.error("Erro reportado pelo WebSocket da Binance: evento de conexão falhou")
                return
            if msg['e'] == 'kline':
                kline = msg['k']
                if not is_closed_candle(kline):
                    return
                symbol_ws = msg['s'] if 's' in msg else symbol.replace("/", "")
                novo_dado = {
                    'timestamp': pd.to_datetime(
                        kline['T'], unit='ms'
                    ).tz_localize('UTC').tz_convert(BRAZIL_TZ).strftime('%Y-%m-%d %H:%M:%S'),
                    'open':   float(kline['o']),
                    'high':   float(kline['h']),
                    'low':    float(kline['l']),
                    'close':  float(kline['c']),
                    'volume': float(kline['v']),
                    'timeframe': timeframe
                }
                try:
                    registrar_candle(
                        symbol_ws, novo_dado['timestamp'],
                        novo_dado['open'], novo_dado['high'],
                        novo_dado['low'], novo_dado['close'],
                        novo_dado['volume'], novo_dado['timeframe']
                    )
                except Exception as e:
                    logger.warning("Erro ao registrar candle no DB: %s", e)

                try:
                    candle_queue.put_nowait({'symbol': symbol_ws, 'dado': novo_dado})
                except queue.Full:
                    logger.warning("Fila de candles cheia para esta sessão; candle descartado")
                except Exception as e:
                    logger.exception("Erro ao enfileirar candle: %s", e)

        for symb in selected_symbols:
            symbol_socket = symb.replace("/", "")
            twm.start_kline_socket(
                symbol=symbol_socket, interval=timeframe,
                callback=handle_socket_message
            )

        st.session_state.bot_data['client'] = client
        st.session_state.bot_data['conexao_websocket'] = twm
        st.session_state.bot_data['inicio_operacao'] = now_brazil()
        return True

    except Exception as e:
        if twm is not None:
            try:
                twm.stop()
            except Exception:
                logger.exception("Falha ao encerrar WebSocket após erro na conexão")
        st.error(f"Erro na conexao: {str(e)}")
        logger.exception("Erro ao iniciar conexao Binance: %s", e)
        return False


def parar_conexao():
    if 'conexao_websocket' in st.session_state.bot_data and st.session_state.bot_data['conexao_websocket']:
        try:
            st.session_state.bot_data['conexao_websocket'].stop()
        finally:
            st.session_state.bot_data['conexao_websocket'] = None


# ---------------------------------------------------------------------------
# Dashboard principal
# ---------------------------------------------------------------------------

st.markdown("# Trading Bot Dashboard")
st.warning("Modo simulado: este aplicativo não envia ordens reais para a Binance.")
if st.session_state.get('ml_fallback_active', False):
    st.warning("scikit-learn não pôde carregar neste ambiente; sinais usam fallback heurístico, não IA treinada.")
if not _APP_PASSWORD:
    st.warning("Acesso sem autenticação. Não exponha este dashboard publicamente sem configurar APP_PASSWORD ou um provedor de identidade.")

col1, col2, col3, col4 = st.columns(4)

saldo_usdt = st.session_state.bot_data.get('saldo_usdt', saldo_inicial)
saldo_total = saldo_usdt

# MULTI-ORDEM: soma valor de mercado de todas as ordens abertas de todos os pares
for sym_pos, ordens_pos in st.session_state.bot_data.get('posicoes', {}).items():
    df_pos = st.session_state.bot_data['dados_mercado'].get(sym_pos, pd.DataFrame())
    if df_pos.empty:
        continue
    preco_pos = df_pos.iloc[-1]['close']
    if isinstance(ordens_pos, list):
        for o in ordens_pos:
            saldo_total += preco_pos * o.get('quantidade', 0)
    elif isinstance(ordens_pos, dict) and ordens_pos.get('aberta'):
        saldo_total += preco_pos * ordens_pos.get('quantidade', 0)

with col1:
    st.metric("Saldo Atual (USDT)", f"{saldo_usdt:.2f}")
with col2:
    st.metric("Saldo Total (USDT)", f"{saldo_total:.2f}")
with col3:
    variacao_pct = ((saldo_total - saldo_inicial) / saldo_inicial * 100) if saldo_inicial > 0 else 0
    st.metric("Variacao (%)", f"{variacao_pct:.1f}%", "Variacao em relacao ao periodo...")

col_status1, col_status2, col_status3 = st.columns([2, 1, 1])

with col_status1:
    st.markdown("**Aguardando dados...**")
with col_status2:
    status = "OPERANDO" if st.session_state['bot_running'] else "PARADO"
    st.markdown(f"**{status}**")
with col_status3:
    dados_count = len(st.session_state.bot_data.get('dados_mercado', {}).get(symbol, []))
    logger.debug("Candles carregados: %d", dados_count)
    if dados_count == 200:
        logger.info("Checkpoint 200 candles â€” total trades/candles: %s", count_trades_e_candles())
    if dados_count >= 500:
        st.markdown("**Limite de 500 candles mantido em memória**")
    st.markdown(f"**Dados:** {dados_count} candles")

st.markdown("### Visao da IA - Analise Tecnica")

col_ia_btn = st.columns([0.2, 0.8])[0]
with col_ia_btn:
    if st.button("Iniciar simulação", use_container_width=True, disabled=st.session_state['bot_running']):
        if not st.session_state.get('bot_running', False):
            st.session_state['bot_running'] = True
            st.session_state.bot_data['inicio_operacao'] = now_brazil()

st.markdown("Aguardando dados do mercado...")
st.divider()

st.markdown("### Grafico")

# ---------------------------------------------------------------------------
# Filtros do gráfico — buscam direto do banco para refletir todo o historico
# ---------------------------------------------------------------------------
_filtro_cols = st.columns([3, 1])

with _filtro_cols[0]:
    _filtro_tempo = st.radio(
        "Periodo",
        ["Agora (ultimos 500 candles)", "Ultima hora", "Ultimas 6 horas", "Ultimo dia", "Ultimos 7 dias", "Tudo"],
        horizontal=True,
        label_visibility="collapsed",
    )

with _filtro_cols[1]:
    _mostrar_sinais = st.toggle("Mostrar sinais", value=True)

_chart_controls = st.columns([1.25, 1, 1, 1])
with _chart_controls[0]:
    _tipo_grafico = st.selectbox("Visualização", ["Candles", "Linha"], label_visibility="collapsed")
with _chart_controls[1]:
    _mostrar_trades = st.toggle("Trades", value=True)
with _chart_controls[2]:
    _mostrar_medias = st.toggle("Médias móveis", value=True)
with _chart_controls[3]:
    _mostrar_bollinger = st.toggle("Bandas de Bollinger", value=False)

# Calcula o `since` baseado no filtro escolhido
_now = now_brazil()
_since_map = {
    "Agora (ultimos 500 candles)": None,
    "Ultima hora":    (_now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
    "Ultimas 6 horas": (_now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"),
    "Ultimo dia":     (_now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
    "Ultimos 7 dias": (_now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"),
    "Tudo":           None,
}
_since = _since_map[_filtro_tempo]
_limit = 500 if _filtro_tempo == "Agora (ultimos 500 candles)" else None

main_df = pd.DataFrame()
try:
    # Sempre busca do banco — fonte de verdade completa
    df_db = get_candles(
        symbol.replace('/', ''),
        limit=_limit,
        since=_since,
        timeframe=timeframe,
    )
    if not df_db.empty:
        main_df = df_db.copy()
    else:
        # Fallback para dados em memória se o banco estiver vazio
        main_df = st.session_state.bot_data['dados_mercado'].get(symbol, pd.DataFrame()).copy()
except Exception as e:
    logger.warning("Erro ao carregar dados para grafico: %s", e)
    main_df = st.session_state.bot_data['dados_mercado'].get(symbol, pd.DataFrame()).copy()

if not main_df.empty:
    df = main_df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.dropna(subset=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df = df.sort_values('timestamp').drop_duplicates('timestamp').reset_index(drop=True)

    if not df.empty:
        _preco_inicial = float(df['close'].iloc[0])
        _preco_atual = float(df['close'].iloc[-1])
        _variacao_periodo = ((_preco_atual / _preco_inicial) - 1) * 100 if _preco_inicial else 0.0
        _metric_cols = st.columns(4)
        _metric_cols[0].metric("Último preço", f"{_preco_atual:,.4f}")
        _metric_cols[1].metric("Variação no período", f"{_variacao_periodo:+.2f}%")
        _metric_cols[2].metric("Máxima", f"{df['high'].max():,.4f}")
        _metric_cols[3].metric("Mínima", f"{df['low'].min():,.4f}")

        fig = make_subplots(
            rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.035,
            row_heights=[0.62, 0.20, 0.18],
            subplot_titles=("Preço", "Volume", "RSI (14)"),
        )
        if _tipo_grafico == "Candles":
            fig.add_trace(go.Candlestick(
                x=df['timestamp'], open=df['open'], high=df['high'],
                low=df['low'], close=df['close'], name='OHLC',
                increasing_line_color='#2dd4a7', decreasing_line_color='#ff647c',
                increasing_fillcolor='rgba(45,212,167,0.72)',
                decreasing_fillcolor='rgba(255,100,124,0.72)',
                whiskerwidth=0.45,
                hoverlabel=dict(namelength=0),
            ), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['close'], mode='lines',
                line=dict(color='#38d9c0', width=2.2), fill='tozeroy',
                fillcolor='rgba(56,217,192,0.08)', name='Fechamento',
                hovertemplate='%{x|%d/%m %H:%M}<br>Fechamento: %{y:,.4f}<extra></extra>',
            ), row=1, col=1)

        _volume_colors = [
            '#2dd4a7' if close >= open_ else '#ff647c'
            for open_, close in zip(df['open'], df['close'])
        ]
        fig.add_trace(go.Bar(
            x=df['timestamp'], y=df['volume'], name='Volume',
            marker_color=_volume_colors, opacity=0.72,
            hovertemplate='%{x|%d/%m %H:%M}<br>Volume: %{y:,.4g}<extra></extra>',
        ), row=2, col=1)

        try:
            _chart_features = gerar_features_melhorada(df)
            if not _chart_features.empty:
                fig.add_trace(go.Scatter(
                    x=_chart_features['timestamp'], y=_chart_features['rsi'],
                    mode='lines', name='RSI 14',
                    line=dict(color='#b794f6', width=1.7),
                    hovertemplate='%{x|%d/%m %H:%M}<br>RSI: %{y:.1f}<extra></extra>',
                ), row=3, col=1)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("Não foi possível calcular RSI do gráfico: %s", e)

        if _mostrar_medias or _mostrar_bollinger:
            _ma20 = df['close'].rolling(20, min_periods=1).mean()
            _ma50 = df['close'].rolling(50, min_periods=1).mean()
            if _mostrar_medias:
                fig.add_trace(go.Scatter(
                    x=df['timestamp'], y=_ma20, mode='lines', name='MM 20',
                    line=dict(color='#ffd166', width=1.3),
                    hovertemplate='MM 20: %{y:,.4f}<extra></extra>',
                ), row=1, col=1)
                fig.add_trace(go.Scatter(
                    x=df['timestamp'], y=_ma50, mode='lines', name='MM 50',
                    line=dict(color='#7aa2ff', width=1.3),
                    hovertemplate='MM 50: %{y:,.4f}<extra></extra>',
                ), row=1, col=1)
            if _mostrar_bollinger:
                _bb_mid = df['close'].rolling(20, min_periods=1).mean()
                _bb_std = df['close'].rolling(20, min_periods=2).std().fillna(0)
                _bb_upper = _bb_mid + 2 * _bb_std
                _bb_lower = _bb_mid - 2 * _bb_std
                fig.add_trace(go.Scatter(
                    x=df['timestamp'], y=_bb_upper, mode='lines', name='Bollinger sup.',
                    line=dict(color='rgba(167,139,250,0.7)', width=1, dash='dot'),
                    hovertemplate='Banda sup.: %{y:,.4f}<extra></extra>',
                ), row=1, col=1)
                fig.add_trace(go.Scatter(
                    x=df['timestamp'], y=_bb_lower, mode='lines', name='Bollinger inf.',
                    line=dict(color='rgba(167,139,250,0.7)', width=1, dash='dot'),
                    fill='tonexty', fillcolor='rgba(167,139,250,0.06)',
                    hovertemplate='Banda inf.: %{y:,.4f}<extra></extra>',
                ), row=1, col=1)

        fig.add_hline(y=70, line_dash='dot', line_color='rgba(255,100,124,0.55)', row=3, col=1)
        fig.add_hline(y=30, line_dash='dot', line_color='rgba(45,212,167,0.55)', row=3, col=1)

        # Trades reais do banco — compras e vendas executadas pelo bot
        try:
            _trades_df = get_trades(symbol=symbol, since=_since) if _mostrar_trades else pd.DataFrame()
            if not _trades_df.empty:
                _compras = _trades_df[_trades_df['tipo'] == 'COMPRA']
                _vendas  = _trades_df[_trades_df['tipo'] == 'VENDA']

                if not _compras.empty:
                    fig.add_trace(go.Scatter(
                        x=_compras['timestamp'],
                        y=_compras['preco_execucao'],
                        mode='markers',
                        marker=dict(
                            symbol='triangle-up',
                            size=16,
                            color='#26a69a',
                            line=dict(color='white', width=1.5),
                        ),
                        name='Compra executada',
                        customdata=_compras[['quantidade_executada', 'valor_liquido']].values,
                        hovertemplate=(
                            '<b>COMPRA</b><br>'
                            '%{x}<br>'
                            'Preco: %{y:,.2f}<br>'
                            'Qtd: %{customdata[0]:.4f}<br>'
                            'Valor: %{customdata[1]:,.2f}<extra></extra>'
                        ),
                    ), row=1, col=1)

                if not _vendas.empty:
                    _vdf = _vendas.copy()
                    _vdf['lucro'] = _vdf['lucro'].fillna(0)
                    _vdf['retorno'] = _vdf['retorno'].fillna(0)
                    fig.add_trace(go.Scatter(
                        x=_vdf['timestamp'],
                        y=_vdf['preco_execucao'],
                        mode='markers',
                        marker=dict(
                            symbol='triangle-down',
                            size=16,
                            color='#ef5350',
                            line=dict(color='white', width=1.5),
                        ),
                        name='Venda executada',
                        customdata=_vdf[['quantidade_executada', 'valor_liquido', 'lucro', 'retorno']].values,
                        hovertemplate=(
                            '<b>VENDA</b><br>'
                            '%{x}<br>'
                            'Preco: %{y:,.2f}<br>'
                            'Qtd: %{customdata[0]:.4f}<br>'
                            'Valor: %{customdata[1]:,.2f}<br>'
                            'Lucro: %{customdata[2]:,.2f} (%{customdata[3]:.2f}%)<extra></extra>'
                        ),
                    ), row=1, col=1)

        except Exception as e:
            logger.warning("Erro ao carregar trades para grafico: %s", e)

        # FIX: sinais cacheados no session_state â€” calcula apenas candles novos,
        # nao recalcula todos a cada rerun. Usa estrategia melhorada com config do sidebar.
        try:
            if len(df) >= 100:
                signal_index_key = f"signals_ultimo_idx_{symbol}"
                signal_cache_key = f"signals_cache_{symbol}"
                ultimo_idx_calculado = st.session_state.get(signal_index_key, 99)
                signals_cache = st.session_state.get(signal_cache_key, [])
                novo_inicio = max(100, ultimo_idx_calculado + 1)

                if novo_inicio < len(df):
                    config_sinais = build_strategy_config()
                    for i in range(novo_inicio, len(df)):
                        window_df = df.iloc[i - 100:i + 1].copy()
                        try:
                            res = executar_estrategia_ai_melhorada(
                                window_df, False, None,
                                config=config_sinais,
                                modelo_cache_fn=lambda frame, cols: obter_modelo_treinado(frame, cols, f"{symbol}_chart"),
                            )
                            s = res.get('sinal', 'hold')
                        except Exception:
                            s = 'hold'
                        if s == 'buy':
                            signals_cache.append(('buy', df.iloc[i]['timestamp'], df.iloc[i]['close']))
                        elif s == 'sell':
                            signals_cache.append(('sell', df.iloc[i]['timestamp'], df.iloc[i]['close']))

                    st.session_state[signal_cache_key] = signals_cache[-200:]
                    st.session_state[signal_index_key] = len(df) - 1

                # Filtra sinais pelo periodo selecionado e pelo toggle
                if _mostrar_sinais:
                    _since_dt = pd.to_datetime(_since) if _since else None
                    _filtered = [
                        (st2, t, p) for st2, t, p in signals_cache
                        if _since_dt is None or pd.to_datetime(t) >= _since_dt
                    ]
                    _buys  = [(t, p) for st2, t, p in _filtered if st2 == 'buy']
                    _sells = [(t, p) for st2, t, p in _filtered if st2 == 'sell']

                    if _buys:
                        _bx, _by = zip(*_buys)
                        fig.add_trace(go.Scatter(
                            x=list(_bx), y=list(_by),
                            mode='markers',
                            marker=dict(
                                symbol='triangle-up',
                                size=14,
                                color='#26a69a',
                                line=dict(color='white', width=1),
                            ),
                            name='Compra',
                            hovertemplate='COMPRA<br>%{x}<br>%{y:,.2f}<extra></extra>',
                        ), row=1, col=1)

                    if _sells:
                        _sx, _sy = zip(*_sells)
                        fig.add_trace(go.Scatter(
                            x=list(_sx), y=list(_sy),
                            mode='markers',
                            marker=dict(
                                symbol='triangle-down',
                                size=14,
                                color='#ef5350',
                                line=dict(color='white', width=1),
                            ),
                            name='Venda',
                            hovertemplate='VENDA<br>%{x}<br>%{y:,.2f}<extra></extra>',
                        ), row=1, col=1)

                try:
                    usar_melhorada = st.session_state.get('usar_estrategia_melhorada', True)

                    if usar_melhorada:
                        # FIX: gerar_features_melhorada (19 features) em vez de basic (5)
                        indicadores_df = gerar_features_melhorada(df)
                        ultimo_indicador = indicadores_df.iloc[-1].to_dict()

                        # FIX: config com stop/take dos sliders passado para a estrategia
                        config_atual = build_strategy_config()
                        _pos_sidebar = get_posicao(symbol)
                        resultado_ai = executar_estrategia_ai_melhorada(
                            df,
                            posicao_aberta=_pos_sidebar.get('aberta', False),
                            preco_compra=_pos_sidebar.get('preco_compra'),
                            config=config_atual,
                            modelo_cache_fn=lambda frame, cols: obter_modelo_treinado(frame, cols, f"{symbol}_chart"),
                        )

                        st.markdown("### Indicadores Atuais")

                        def _build_indicator_html(ind: dict) -> str:
                            def cor_rsi(v):
                                return '#ef5350' if v >= 70 else ('#26a69a' if v <= 30 else '#ffe082')
                            def cor_bb(v):
                                return '#ef5350' if v >= 0.8 else ('#26a69a' if v <= 0.2 else '#ffe082')
                            def cor_vol(v):
                                return '#26a69a' if v >= 1.0 else '#ef5350'
                            def cor_adx(v):
                                return '#26a69a' if v >= 25 else '#ffe082'
                            def cor_macd(m, s):
                                return '#26a69a' if m > s else '#ef5350'
                            def cor_ma(close, ma):
                                return '#26a69a' if close > ma else '#ef5350'

                            rsi  = ind.get('rsi', 50)
                            adx  = ind.get('adx', 0)
                            macd = ind.get('macd', 0)
                            msig = ind.get('macd_signal', 0)
                            mhst = ind.get('macd_hist', 0)
                            bbp  = ind.get('bb_position', 0.5)
                            bbw  = ind.get('bb_width', 0)
                            volr = ind.get('volume_ratio', 1)
                            obv  = ind.get('obv_trend', 0)
                            ma5  = ind.get('ma_5', 0)
                            ma20 = ind.get('ma_20', 0)
                            cls  = ind.get('close', 0)
                            atrp = ind.get('atr_pct', 0) * 100
                            volp = ind.get('volatility_pct', 0) * 100

                            cards = [
                                ("RSI", f"{rsi:.1f}", cor_rsi(rsi),
                                "RSI — Relative Strength Index<br>Oscilador de momento entre 0 e 100.<br><b>&gt;70</b>: sobrecomprado — possivel queda.<br><b>&lt;30</b>: sobrevendido — possivel alta.<br><b>30-70</b>: zona neutra."),
                                ("ADX", f"{adx:.1f}", cor_adx(adx),
                                "ADX — Average Directional Index<br>Forca da tendencia (nao a direcao).<br><b>&gt;25</b>: tendencia forte — sinais confiaveis.<br><b>&lt;20</b>: mercado lateral — sinais fracos."),
                                ("MACD", f"{macd:.4f}", cor_macd(macd, msig),
                                "MACD — Moving Avg Convergence Divergence<br>Diferenca entre EMA12 e EMA26.<br><b>MACD &gt; Sinal</b>: momentum de alta.<br><b>MACD &lt; Sinal</b>: momentum de queda."),
                                ("MACD Hist", f"{mhst:.4f}", '#26a69a' if mhst > 0 else '#ef5350',
                                "MACD Histograma<br>Distancia entre MACD e linha de sinal.<br><b>Positivo e crescendo</b>: forca compradora.<br><b>Negativo e caindo</b>: forca vendedora."),
                                ("BB Position", f"{bbp:.2f}", cor_bb(bbp),
                                "Bollinger Band Position<br>Posicao do preco nas bandas (0=base, 1=topo).<br><b>&gt;0.8</b>: perto do topo — possivel sobrecompra.<br><b>&lt;0.2</b>: perto da base — possivel sobrevenda."),
                                ("BB Width", f"{bbw:.4f}", '#ffe082',
                                "Bollinger Band Width<br>Largura das bandas relativa ao preco.<br><b>Alta</b>: alta volatilidade.<br><b>Baixa</b>: squeeze — possivel movimento brusco em breve."),
                                ("Volume Ratio", f"{volr:.2f}x", cor_vol(volr),
                                "Volume Ratio<br>Volume atual vs media dos ultimos 10 periodos.<br><b>&gt;1.5</b>: spike de volume — movimento com convicção.<br><b>&lt;0.8</b>: volume fraco — sinal menos confiavel."),
                                ("OBV Trend", "Alta" if obv == 1 else "Baixa", '#26a69a' if obv == 1 else '#ef5350',
                                "OBV Trend — On-Balance Volume<br>Volume acumulado vs sua media.<br><b>Alta</b>: pressao compradora — dinheiro entrando.<br><b>Baixa</b>: pressao vendedora — dinheiro saindo."),
                                ("MA5", f"{ma5:.2f}", cor_ma(cls, ma5),
                                "MA5 — Media Movel de 5 periodos<br>Media dos ultimos 5 fechamentos.<br><b>Preco &gt; MA5</b>: tendencia de curto prazo positiva.<br><b>Preco &lt; MA5</b>: tendencia de curto prazo negativa."),
                                ("MA20", f"{ma20:.2f}", cor_ma(cls, ma20),
                                "MA20 — Media Movel de 20 periodos<br>Referencia de tendencia de medio prazo.<br><b>Cruzamento MA5/MA20</b>: sinal classico de reversao (golden/death cross)."),
                                ("ATR %", f"{atrp:.2f}%", '#ffe082',
                                "ATR % — Average True Range em %<br>Volatilidade media do periodo.<br><b>Alto</b>: movimentos grandes — stop loss mais largo.<br><b>Baixo</b>: mercado calmo — stops mais curtos."),
                                ("Volatilidade", f"{volp:.2f}%", '#ffe082',
                                "Volatilidade %<br>Desvio padrao dos retornos dos ultimos 20 periodos.<br><b>Alta</b>: mercado instavel — risco e oportunidade maiores.<br><b>Baixa</b>: mercado estavel — movimento mais previsivel."),
                            ]

                            css = (
                                "<style>"
                                ".ind-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:0.5rem 0 0}"
                                ".ind-card{position:relative;background:rgba(255,255,255,0.04);border:0.5px solid rgba(255,255,255,0.1);border-radius:10px;padding:12px 14px;cursor:default}"
                                ".ind-label{font-size:11px;color:rgba(255,255,255,0.5);margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px}"
                                ".ind-value{font-size:18px;font-weight:600}"
                                ".ind-dot{width:6px;height:6px;border-radius:50%;display:inline-block;margin-right:4px;margin-bottom:2px}"

                               
                                ".ind-tip{position:fixed;display:none;background:#1e2530;border:0.5px solid rgba(255,255,255,0.2);border-radius:8px;padding:10px 13px;font-size:12px;color:rgba(255,255,255,0.85);line-height:1.6;width:220px;z-index:999999;pointer-events:none;box-shadow:0 6px 24px rgba(0,0,0,0.7)}"
                                "</style>"

                                "<script>"
                                "(function initTooltips(){"
                                "function applyTooltips(){"
                                "document.querySelectorAll('.ind-card').forEach(function(c){"
                                "if (c.dataset.tooltipReady) return;"

                                "var tip = c.querySelector('.ind-tip');"
                                "if(!tip) return;"

                                "document.body.appendChild(tip);"

                                "c.addEventListener('mouseenter', function(){ tip.style.display='block'; });"
                                "c.addEventListener('mouseleave', function(){ tip.style.display='none'; });"

                                "c.addEventListener('mousemove', function(e){"
                                "var x = e.pageX + 14;"
                                "var y = e.pageY + 14;"

                                "if (x + 240 > window.innerWidth + window.scrollX) {"
                                "x = e.pageX - 250;"
                                "}"

                                "if (y + 180 > window.innerHeight + window.scrollY) {"
                                "    y = e.pageY - 190;"
                                "}"

                                "tip.style.left = x + 'px';"
                                "tip.style.top  = y + 'px';"
                                "});"
                                "c.dataset.tooltipReady = 'true';"
                                "});"
                                "}"

                                
                                "let tries = 0;"
                                "const interval = setInterval(function(){"
                                "applyTooltips();"
                                "tries++;"
                                "if (tries > 10) clearInterval(interval);"
                                "}, 300);"

                                "})();"
                                "</script>"
                            )

                            html = css + '<div class="ind-grid">'
                            for label, value, color, tip in cards:
                                html += (
                                    '<div class="ind-card">'
                                    f'<div class="ind-label">{label}</div>'
                                    f'<div class="ind-value"><span class="ind-dot" style="background:{color}"></span>'
                                    f'<span style="color:{color}">{value}</span></div>'
                                    f'<div class="ind-tip">{tip}</div>'
                                    '</div>'
                                )
                            html += '</div>'
                            return html

                        components.html(
                            _build_indicator_html(ultimo_indicador),
                            height=260, scrolling=False
                        )

                        st.markdown("### Preview de Sinais")
                        # FIX: config com stop/take do sidebar passado para o painel visual
                        _posicao_sidebar = get_posicao(symbol)
                        render_signal_panel(
                            indicadores=ultimo_indicador,
                            posicao_aberta=_posicao_sidebar.get('aberta', False),
                            preco_compra=_posicao_sidebar.get('preco_compra'),
                            config=config_atual,
                            confianca=resultado_ai.get('confianca', 0.0),
                            sinal_atual=resultado_ai.get('sinal', 'hold'),
                        )

                    else:
                        indicadores_df = gerar_features_basic(df)
                        ultimo_indicador = indicadores_df.iloc[-1]
                        st.markdown("### Indicadores Atuais")
                        c1, c2, c3 = st.columns(3)
                        c1.metric("RSI", f"{ultimo_indicador['rsi']:.1f}")
                        c1.metric("Volume", f"{int(ultimo_indicador['volume']):,}")
                        c2.metric("MACD", f"{ultimo_indicador['macd']:.4f}")
                        c2.metric("MACD Signal", f"{ultimo_indicador['macd_signal']:.4f}")
                        c3.metric("Media 20", f"{ultimo_indicador['media_20']:.4f}")
                        c3.metric("Volume Spike", "Sim" if ultimo_indicador['volume_spike'] == 1 else "Nao")

                except Exception as e:
                    logger.warning("Erro ao gerar indicadores: %s", e)

        except Exception as e:
            logger.warning("Erro ao processar sinais do grafico: %s", e)

        _y_min = float(df['low'].min())
        _y_max = float(df['high'].max())
        _y_span = _y_max - _y_min
        _y_pad = _y_span * 0.06 if _y_span else max(abs(_y_max) * 0.005, 0.01)
        fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='#0b1220',
            font=dict(color='#dbe5f0', family='Inter, sans-serif', size=12),
            height=760,
            margin=dict(l=12, r=24, t=48, b=20),
            legend=dict(
                orientation='h', yanchor='bottom', y=1.02,
                xanchor='left', x=0, bgcolor='rgba(0,0,0,0)',
                font=dict(size=11),
            ),
            hovermode='x unified',
            hoverlabel=dict(bgcolor='#111827', bordercolor='#334155', font_color='#f8fafc'),
            showlegend=True,
            xaxis_rangeslider_visible=False,
        )
        fig.update_xaxes(showgrid=True, gridcolor='rgba(148,163,184,0.10)', zeroline=False, rangeslider_visible=False)
        fig.update_yaxes(showgrid=True, gridcolor='rgba(148,163,184,0.10)', zeroline=False)
        fig.update_yaxes(range=[_y_min - _y_pad, _y_max + _y_pad], tickformat=',.4~f', side='right', row=1, col=1)
        fig.update_yaxes(tickformat='~s', side='right', row=2, col=1)
        fig.update_yaxes(range=[0, 100], tickvals=[0, 30, 50, 70, 100], side='right', row=3, col=1)
        fig.update_xaxes(title_text='Horário', row=3, col=1)

        if st.session_state.get('dados_grafico_atualizados', False):
            st.session_state['dados_grafico_atualizados'] = False
            st.rerun()

        st.plotly_chart(
            fig, use_container_width=True,
            config={
                'displaylogo': False,
                'scrollZoom': True,
                'responsive': True,
                'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
            },
        )

    else:
        st.info("Aguardando dados suficientes para plotar o grafico...")

else:
    st.info("Aguardando dados do mercado...")

st.divider()

col_principal, col_historico = st.columns([0.7, 0.3])

with col_principal:
    st.markdown("### Status do Bot")
    col_status, col_controle = st.columns([0.7, 0.3])
    with col_status:
        if st.session_state['bot_running']:
            st.success("Simulação ativa - recebendo candles públicos")
            st.markdown(f"**Atualizacao:** {format_time(now_brazil())}")
            posicoes_ui = st.session_state.bot_data.get('posicoes', {})
            resumo_ordens = []
            for s, ordens_ui in posicoes_ui.items():
                n = len(ordens_ui) if isinstance(ordens_ui, list) else (1 if (isinstance(ordens_ui, dict) and ordens_ui.get('aberta')) else 0)
                if n > 0:
                    resumo_ordens.append(f"{s} ({n})")
            st.markdown(f"**Ordens abertas:** {', '.join(resumo_ordens) if resumo_ordens else 'nenhuma'}")
            pares_monitorados_ui = list(st.session_state.bot_data.get('dados_mercado', {}).keys())
            st.markdown(f"**Monitorando:** {', '.join(pares_monitorados_ui) if pares_monitorados_ui else '-'}")
        else:
            st.markdown("**Par:** -")
            st.markdown(f"**Atualizacao:** {format_time(now_brazil())}")

    with col_controle:
        if st.session_state['bot_running'] and st.button("Parar simulação", use_container_width=True):
            st.session_state['bot_running'] = False

with col_historico:
    st.markdown("### Historico")
    trades = st.session_state.bot_data.get('trades', [])
    if trades:
        st.markdown(f"**Total de trades: {len(trades)}**")
        for i, trade in enumerate(trades[-5:]):
            emoji = "\U0001f7e2" if trade.get('tipo') == 'COMPRA' else "\U0001f534"
            lucro = trade.get('retorno', 0)
            st.markdown(
                f"{emoji} {trade.get('tipo')} {trade.get('symbol')} - "
                f"${trade.get('preco_execucao', 0):.2f} - {lucro:.2f}%"
            )
    else:
        st.markdown("**Nenhum trade executado**")

    col_stats1, col_stats2 = st.columns(2)
    with col_stats1:
        st.markdown("[Estatisticas]")
    with col_stats2:
        st.markdown("[Configuracoes]")

st.markdown("")

selected_symbols = st.multiselect(
    "Selecione os pares para monitorar em tempo real:",
    symbols, default=[symbols[0]]
)

conexao_status = st.empty()

if st.session_state['bot_running']:
    current_ws_symbols = st.session_state.get('ws_symbols', [])
    if st.session_state.get('ws_iniciado', False) and current_ws_symbols != selected_symbols:
        parar_conexao()
        st.session_state['ws_iniciado'] = False
    if not st.session_state.get('ws_iniciado', False):
        if iniciar_conexao(selected_symbols):
            conexao_status.success("Conexao com Binance estabelecida!")
            st.session_state['ws_iniciado'] = True
            st.session_state['ws_symbols'] = list(selected_symbols)
        else:
            conexao_status.error("Falha ao conectar com Binance.")
            st.session_state['bot_running'] = False
            st.session_state['ws_iniciado'] = False
else:
    if st.session_state.get('ws_iniciado', False):
        salvar_estado_bot()   # persiste saldo e ordens abertas antes de parar
        parar_conexao()
        st.session_state['ws_iniciado'] = False
        st.session_state['ws_symbols'] = []

# ---------------------------------------------------------------------------
# Loop de atualizacao â€” fila thread-safe do websocket
# ---------------------------------------------------------------------------

if 'ultima_atualizacao_ui' not in st.session_state:
    st.session_state['ultima_atualizacao_ui'] = now_brazil()
if 'dados_grafico_atualizados' not in st.session_state:
    st.session_state['dados_grafico_atualizados'] = False

status_update_placeholder = st.empty()
dados_novos = False
notify_placeholder = st.empty()

# Drena todos os candles pendentes da fila thread-safe.
# Substitui a leitura de arquivos temporarios (que causava erros no Windows).
_ws_queue = st.session_state['_ws_candle_queue']
_processed_symbols = set()
while True:
    try:
        item = _ws_queue.get_nowait()
    except queue.Empty:
        break
    try:
        sym_item = item['symbol']
        dado = item['dado']
        sym_fmt = sym_item if '/' in sym_item else sym_item[:-4] + '/' + sym_item[-4:]
        dado['timestamp'] = pd.to_datetime(dado['timestamp'])
        atualizar_dados_mercado(sym_fmt, dado)
        dados_novos = True
        _processed_symbols.add(sym_item)
    except Exception as e:
        logger.exception("Erro ao processar candle da fila: %s", e)

if _processed_symbols:
    try:
        notify_placeholder.toast(
            f"Candle(s) recebido(s): {', '.join(_processed_symbols)}", icon="\U0001f4ca"
        )
    except Exception:
        notify_placeholder.info("Novos candles recebidos")

# Fallback REST se nenhum dado do websocket chegou
if st.session_state['bot_running'] and not dados_novos:
    try:
        client = st.session_state.bot_data.get('client')
        if client:
            sym_rest = symbol.replace('/', '')
            bars = client.get_klines(symbol=sym_rest, interval=timeframe, limit=1)
            b = bars[-1] if bars else None
            if b is not None and len(b) > 6 and int(b[6]) >= int(time.time() * 1000):
                b = None
            if b:
                novo = {
                    'timestamp': pd.to_datetime(
                        b[6] if len(b) > 6 else b[0], unit='ms'
                    ).tz_localize('UTC').tz_convert(BRAZIL_TZ).strftime('%Y-%m-%d %H:%M:%S'),
                    'open': float(b[1]),
                    'high': float(b[2]),
                    'low': float(b[3]),
                    'close': float(b[4]),
                    'volume': float(b[5])
                }
                atualizar_dados_mercado(symbol, novo)
    except Exception as e:
        logger.warning("Erro no fallback REST: %s", e)

if st.session_state['bot_running']:
    analisar_e_executar_trades()

# FIX: st_autorefresh substitui o time.sleep() + st.rerun() manual.
# O sleep bloqueava a thread principal do Streamlit, causando perda de
# heartbeat com o navegador e fazendo a sessao parecer "morta" ou parada.
# st_autorefresh injeta um componente JS que dispara o rerun pelo cliente
# a cada intervalo â€” sem bloquear nenhuma thread Python.
# So ativa quando o bot esta rodando para economizar recursos.
if st.session_state.get('bot_running', False):
    st_autorefresh(interval=10_000, key="bot_autorefresh")  # rerun a cada 10s