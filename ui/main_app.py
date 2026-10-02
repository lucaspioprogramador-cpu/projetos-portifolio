# -*- coding: utf-8 -*-

import logging
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
import pytz
import plotly.graph_objects as go
from binance.client import Client
from binance import ThreadedWebsocketManager
from core.execution import executar_ordem_simulada
import threading
import queue
import os
import json
import tempfile
from config.settings import BINANCE_API_KEY, BINANCE_API_SECRET
from db.database import registrar_candle, get_candles, registrar_trade, count_trades_e_candles, get_trades
import warnings

warnings.filterwarnings(
    "ignore",
    message=".*sklearn.utils.parallel.delayed.*"
)

# FIX: importa apenas a estrategia melhorada â€” deprecated (ai_strategy.py) removido
from strategies.ai_strategy_melhorada import executar_estrategia_ai_melhorada
from strategies.features import gerar_features_basic, gerar_features_melhorada
from signal_preview_panel import render_signal_panel
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
logger = logging.getLogger(__name__)

_ws_manager = None
BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')


# ---------------------------------------------------------------------------
# Utilitarios
# ---------------------------------------------------------------------------

def salvar_credenciais(api_key, api_secret):
    try:
        with open("binance_api.json", "w", encoding="utf-8") as f:
            json.dump({"api_key": api_key, "api_secret": api_secret}, f)
    except Exception as e:
        logger.exception("Erro ao salvar credenciais Binance: %s", e)


def carregar_credenciais():
    try:
        if os.path.exists("binance_api.json"):
            with open("binance_api.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("api_key", ""), data.get("api_secret", "")
    except Exception as e:
        logger.exception("Erro ao carregar credenciais Binance: %s", e)
    return "", ""


def salvar_config_telegram(token, chat_id):
    config = {"telegram_token": token, "telegram_chat_id": chat_id}
    try:
        with open("telegram_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f)
        return True
    except Exception as e:
        logger.exception("Erro ao salvar config Telegram: %s", e)
        return False


def carregar_config_telegram():
    try:
        if os.path.exists("telegram_config.json"):
            with open("telegram_config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("telegram_token", ""), config.get("telegram_chat_id", "")
    except Exception as e:
        logger.exception("Erro ao carregar config Telegram: %s", e)
    return "", ""


ESTADO_BOT_FILE = "estado_bot.json"


def salvar_estado_bot():
    """
    Persiste saldo atual e todas as ordens abertas em estado_bot.json.
    Chamado automaticamente quando o bot para, garantindo que o estado
    seja restaurado na proxima vez que o bot ligar.
    """
    try:
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

        with open(ESTADO_BOT_FILE, 'w', encoding='utf-8') as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)

        logger.info("Estado do bot salvo em %s", ESTADO_BOT_FILE)
    except Exception as e:
        logger.exception("Erro ao salvar estado do bot: %s", e)


def carregar_estado_bot():
    """
    Restaura saldo e ordens abertas do arquivo estado_bot.json.
    Chamado na inicializacao do bot se o arquivo existir.
    Retorna True se o estado foi restaurado, False caso contrario.
    """
    try:
        if not os.path.exists(ESTADO_BOT_FILE):
            return False

        with open(ESTADO_BOT_FILE, 'r', encoding='utf-8') as f:
            estado = json.load(f)

        st.session_state.bot_data['saldo_usdt'] = estado.get('saldo_usdt', st.session_state.bot_data['saldo_usdt'])
        st.session_state.bot_data['saldo_inicial'] = estado.get('saldo_inicial', st.session_state.bot_data['saldo_inicial'])
        st.session_state.bot_data['posicoes'] = estado.get('posicoes', {})
        st.session_state.bot_data['trades'] = estado.get('trades', [])

        salvo_em = estado.get('salvo_em', 'desconhecido')
        logger.info("Estado do bot restaurado de %s (salvo em: %s)", ESTADO_BOT_FILE, salvo_em)
        return True

    except Exception as e:
        logger.exception("Erro ao carregar estado do bot: %s", e)
        return False


def enviar_notificacao_telegram(mensagem):
    try:
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
        logger.error("Telegram: erro de conexao: %s", e)
        return False
    except Exception as e:
        logger.exception("Telegram: erro geral: %s", e)
        return False


def now_brazil():
    return datetime.now(BRAZIL_TZ)


def format_time(dt):
    return dt.strftime("%d/%m/%Y %H:%M:%S")


def calcular_posicao(saldo, preco, risco, stop_pct):
    return (saldo * risco) / (preco * stop_pct)


# ---------------------------------------------------------------------------
# Configuracao de simbolos e pagina
# ---------------------------------------------------------------------------

symbols = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    "LTC/USDT", "PEPE/USDT", "PENDLE/USDT", "JTO/USDT", "BB/USDT", "SUI/USDT"
]

st.set_page_config(page_title="Trading Bot Dashboard", layout="wide")

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
    st.markdown('<div class="sidebar-title">Credenciais</div>', unsafe_allow_html=True)

    if 'api_loaded' not in st.session_state:
        api_key_env = BINANCE_API_KEY or ""
        api_secret_env = BINANCE_API_SECRET or ""
        if not api_key_env or not api_secret_env:
            api_key_loaded, api_secret_loaded = carregar_credenciais()
            api_key_env = api_key_env or api_key_loaded
            api_secret_env = api_secret_env or api_secret_loaded
        st.session_state['api_key'] = api_key_env
        st.session_state['api_secret'] = api_secret_env
        st.session_state['api_loaded'] = True

    if 'telegram_loaded' not in st.session_state:
        telegram_token_loaded, telegram_chat_id_loaded = carregar_config_telegram()
        st.session_state['telegram_token'] = telegram_token_loaded
        st.session_state['telegram_chat_id'] = telegram_chat_id_loaded
        st.session_state['telegram_loaded'] = True

    st.markdown("**API Key Binance**")
    api_key = st.text_input(
        "", value=st.session_state.get('api_key', ''),
        type="password", placeholder="Digite sua API Key",
        label_visibility="collapsed"
    )
    st.markdown("**API Secret Binance**")
    api_secret = st.text_input(
        "", value=st.session_state.get('api_secret', ''),
        type="password", placeholder="Digite seu API Secret",
        label_visibility="collapsed"
    )

    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button("Salvar", key="save_creds", use_container_width=True):
            salvar_credenciais(api_key, api_secret)
            st.session_state['api_key'] = api_key
            st.session_state['api_secret'] = api_secret
            st.success("Credenciais salvas!")
    with col_cancel:
        if st.button("Cancelar", key="cancel_creds", use_container_width=True):
            pass

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
                    resultado = enviar_notificacao_telegram(mensagem_teste)
                    if resultado:
                        st.success("Mensagem de teste enviada!")
                    else:
                        st.error("Falha ao enviar mensagem de teste")
                except Exception as e:
                    st.error(f"Erro ao enviar teste: {str(e)}")
            else:
                st.warning("Configure o token e chat ID primeiro")
    with col_save_telegram:
        if st.button("Salvar Telegram", use_container_width=True, key="save_telegram"):
            salvar_config_telegram(telegram_token_input, telegram_chat_id_input)
            st.session_state['telegram_token'] = telegram_token_input
            st.session_state['telegram_chat_id'] = telegram_chat_id_input
            st.success("Configuracoes do Telegram salvas!")

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
    timeframe = st.selectbox(
        "", ["1m", "5m", "15m", "30m", "1h", "4h"],
        label_visibility="collapsed", index=0
    )

    st.markdown("**Saldo Inicial (USDT)**")
    saldo_inicial = st.number_input(
        "", min_value=100, value=1000, label_visibility="collapsed"
    )

    st.markdown("**Risco por Trade (%)**")
    risco_por_trade_display = st.slider("", 0.1, 5.0, 1.0, label_visibility="collapsed")
    risco_por_trade = risco_por_trade_display / 100
    st.caption("1/5")

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
            "Usar Simulacao Realista", value=True,
            help="Simula slippage, taxas e execucao parcial"
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
        st.session_state.bot_data['saldo_inicial'] = saldo_inicial
        if not st.session_state.bot_data.get('posicao_aberta', False):
            st.session_state.bot_data['saldo_usdt'] = saldo_inicial


ensure_bot_state()

# Restaura estado salvo se existir e ainda nao foi carregado nesta sessao
if not st.session_state.get('estado_restaurado', False):
    if carregar_estado_bot():
        st.session_state['estado_restaurado'] = True
        logger.info("Estado anterior do bot restaurado com sucesso")
    else:
        st.session_state['estado_restaurado'] = True  # marca mesmo sem arquivo

websocket_data_global = {}
websocket_data_lock = threading.Lock()
file_write_lock = threading.Lock()

# Fila global thread-safe para comunicacao websocket -> Streamlit.
# DEVE ser variavel global Python pura â€” st.session_state nao e acessivel
# fora da thread principal do Streamlit (callbacks do websocket rodam em outra thread).
_WS_CANDLE_QUEUE: queue.Queue = queue.Queue(maxsize=500)


# ---------------------------------------------------------------------------
# FIX: cache do modelo RandomForest no session_state.
# Antes o modelo era instanciado e treinado com modelo.fit() dentro de
# executar_estrategia_ai_melhorada() a cada chamada â€” ou seja, a cada candle
# e a cada rerun do Streamlit (200 arvores * centenas de candles = lento).
# Agora o modelo e treinado uma vez e reutilizado. So retreina quando chegam
# pelo menos 10 candles novos desde o ultimo treino.
# ---------------------------------------------------------------------------

def obter_modelo_treinado(df: pd.DataFrame, feature_cols: list):
    """
    Retorna o modelo RandomForest do cache (session_state) ou treina um novo
    se ainda nao existe ou se chegaram dados novos suficientes.
    """
    from sklearn.ensemble import RandomForestClassifier

    cache_key = 'rf_model_cache'
    cache_idx_key = 'rf_model_ultimo_treino_idx'

    modelo_cache = st.session_state.get(cache_key)
    ultimo_treino_idx = st.session_state.get(cache_idx_key, 0)
    idx_atual = len(df)

    deve_treinar = modelo_cache is None or (idx_atual - ultimo_treino_idx) >= 10

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
        modelo.fit(X_train, y_train)
        st.session_state[cache_key] = modelo
        st.session_state[cache_idx_key] = idx_atual
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
            posicao = get_posicao(sym)

            if usar_melhorada:
                resultado = executar_estrategia_ai_melhorada(
                    df,
                    posicao_aberta=posicao['aberta'],
                    preco_compra=posicao['preco_compra'],
                    config=config,
                    modelo_cache_fn=obter_modelo_treinado,
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
                # MULTI-ORDEM: compra sempre que houver sinal e saldo suficiente
                # nao ha limite de ordens por par — so para quando o saldo acabar
                quantidade = calcular_posicao(saldo_disponivel, preco_atual, risco_por_trade, stop_loss)
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
            volume_24h = df['volume'].sum() * preco

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

    if tipo == 'COMPRA':
        # Debita saldo e registra nova ordem na lista do par
        st.session_state.bot_data['saldo_usdt'] -= valor_liquido
        nova_ordem = {
            'preco_compra':    preco_exec,
            'quantidade':      quantidade_exec,
            'valor_investido': valor_liquido,
            'timestamp':       str(now_brazil()),
        }
        ordens.append(nova_ordem)
        logger.info("[%s] Nova ordem adicionada. Total abertas: %d", sym, len(ordens))

    else:
        # Credita saldo e remove a ordem vendida da lista
        st.session_state.bot_data['saldo_usdt'] += valor_liquido

        # Determina o valor investido desta ordem especifica
        if ordem_ref and ordem_ref in ordens:
            valor_investido = ordem_ref.get('valor_investido', preco_exec * quantidade_exec)
            ordens.remove(ordem_ref)
        elif ordens:
            # fallback: remove a ordem mais antiga (FIFO)
            valor_investido = ordens[0].get('valor_investido', preco_exec * quantidade_exec)
            ordens.pop(0)
        else:
            valor_investido = preco_exec * quantidade_exec

        trade['lucro'] = valor_liquido - valor_investido
        trade['lucro_liquido'] = trade['lucro']
        trade['retorno'] = (trade['lucro'] / valor_investido * 100) if valor_investido > 0 else 0
        trade['retorno_liquido'] = trade['retorno']
        logger.info("[%s] Ordem vendida. Restam abertas: %d", sym, len(ordens))

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

def carregar_historico_par(client, sym: str, tf: str, limit: int = 500) -> None:
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
            return

        registros = []
        for b in bars:
            registros.append({
                'timestamp': pd.to_datetime(
                    b[0], unit='ms'
                ).tz_localize('UTC').tz_convert(BRAZIL_TZ).strftime('%Y-%m-%d %H:%M:%S'),
                'open':   float(b[1]),
                'high':   float(b[2]),
                'low':    float(b[3]),
                'close':  float(b[4]),
                'volume': float(b[5]),
                'timeframe': tf,
            })

        df_hist = pd.DataFrame(registros)
        df_hist['timestamp'] = pd.to_datetime(df_hist['timestamp'])

        # Carrega diretamente no dados_mercado — substitui qualquer dado anterior
        st.session_state.bot_data['dados_mercado'][sym] = df_hist

        logger.info("[%s] %d candles carregados com sucesso", sym, len(df_hist))

        # Persiste no banco em background (nao bloqueia a UI)
        try:
            for r in registros:
                registrar_candle(
                    sym_rest, r['timestamp'],
                    r['open'], r['high'], r['low'],
                    r['close'], r['volume'], r['timeframe']
                )
        except Exception as e:
            logger.warning("[%s] Erro ao persistir historico no banco: %s", sym, e)

    except Exception as e:
        logger.exception("[%s] Erro ao carregar historico: %s", sym, e)


def iniciar_conexao(selected_symbols):
    _api_key = st.session_state.get('api_key', '')
    _api_secret = st.session_state.get('api_secret', '')

    if not _api_key or not _api_secret:
        return False

    try:
        logger.info("Iniciando conexao com Binance para pares: %s", selected_symbols)
        client = Client(api_key=_api_key, api_secret=_api_secret, ping=False)

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
                        future.result()
                        logger.info("[%s] Historico carregado", sym_done)
                    except Exception as e:
                        logger.error("[%s] Falha ao carregar historico: %s", sym_done, e)

        # ---------------------------------------------------------------------
        # WEBSOCKET: inicia apos o historico estar carregado
        # ---------------------------------------------------------------------
        twm = ThreadedWebsocketManager(api_key=_api_key, api_secret=_api_secret)

        try:
            twm.start()
        except Exception as e_start:
            logger.warning("Erro ao iniciar WebsocketManager (tentativa 1): %s", e_start)
            try:
                twm.stop()
                twm = ThreadedWebsocketManager(api_key=_api_key, api_secret=_api_secret)
                twm.start()
            except Exception as e_retry:
                raise RuntimeError(f"WebsocketManager falhou apos retry: {e_retry}")

        logger.info("ThreadedWebsocketManager iniciado.")

        def handle_socket_message(msg):
            if msg['e'] == 'kline':
                kline = msg['k']
                symbol_ws = msg['s'] if 's' in msg else symbol.replace("/", "")
                novo_dado = {
                    'timestamp': pd.to_datetime(
                        kline['t'], unit='ms'
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
                    _WS_CANDLE_QUEUE.put_nowait({'symbol': symbol_ws, 'dado': novo_dado})
                except queue.Full:
                    logger.warning("Fila _WS_CANDLE_QUEUE cheia, candle descartado")
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
        st.error(f"Erro na conexao: {str(e)}")
        logger.exception("Erro ao iniciar conexao Binance: %s", e)
        return False


def parar_conexao():
    if 'conexao_websocket' in st.session_state.bot_data and st.session_state.bot_data['conexao_websocket']:
        st.session_state.bot_data['conexao_websocket'].stop()
        st.session_state.bot_data['conexao_websocket'] = None


# ---------------------------------------------------------------------------
# Dashboard principal
# ---------------------------------------------------------------------------

st.markdown("# Trading Bot Dashboard")

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
        st.session_state.bot_data['dados_mercado'][symbol] = pd.DataFrame()
        # Invalida cache do modelo ao resetar dados
        st.session_state.pop('rf_model_cache', None)
        st.session_state.pop('rf_model_ultimo_treino_idx', None)
        st.markdown("**Dados resetados para evitar sobrecarga**")
        enviar_notificacao_telegram("Processo rodando, atingido limite de 500 candles")
    st.markdown(f"**Dados:** {dados_count} candles")

st.markdown("### Visao da IA - Analise Tecnica")

col_ia_btn = st.columns([0.2, 0.8])[0]
with col_ia_btn:
    if st.button("Interpretar", use_container_width=True):
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
    df = df.dropna(subset=['timestamp', 'close'])

    if not df.empty:
        fig = go.Figure()
        # Linha de preço
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['close'],
            mode='lines',
            line=dict(color='#26a69a', width=2),
            name='Preco',
            hovertemplate='%{x}<br>Preco: %{y:,.2f}<extra></extra>',
        ))

        # Trades reais do banco — compras e vendas executadas pelo bot
        try:
            _trades_df = get_trades(symbol=symbol, since=_since)
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
                    ))

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
                    ))

                # Conecta pares compra-venda com linha tracejada
                _c_times  = _compras['timestamp'].tolist()
                _v_times  = _vendas['timestamp'].tolist()
                _c_prices = _compras['preco_execucao'].tolist()
                _v_prices = _vendas['preco_execucao'].tolist()
                for i in range(min(len(_c_times), len(_v_times))):
                    lucro_val = _vendas.iloc[i]['lucro'] if i < len(_vendas) else 0
                    cor_linha = '#26a69a' if (lucro_val or 0) >= 0 else '#ef5350'
                    fig.add_trace(go.Scatter(
                        x=[_c_times[i], _v_times[i]],
                        y=[_c_prices[i], _v_prices[i]],
                        mode='lines',
                        line=dict(color=cor_linha, width=1, dash='dot'),
                        showlegend=False,
                        hoverinfo='skip',
                    ))

        except Exception as e:
            logger.warning("Erro ao carregar trades para grafico: %s", e)

        # FIX: sinais cacheados no session_state â€” calcula apenas candles novos,
        # nao recalcula todos a cada rerun. Usa estrategia melhorada com config do sidebar.
        try:
            if len(df) >= 100:
                ultimo_idx_calculado = st.session_state.get('signals_ultimo_idx', 99)
                signals_cache = st.session_state.get('signals_cache', [])
                novo_inicio = max(100, ultimo_idx_calculado + 1)

                if novo_inicio < len(df):
                    config_sinais = build_strategy_config()
                    for i in range(novo_inicio, len(df)):
                        window_df = df.iloc[i - 100:i + 1].copy()
                        try:
                            res = executar_estrategia_ai_melhorada(
                                window_df, False, None,
                                config=config_sinais,
                                modelo_cache_fn=obter_modelo_treinado,
                            )
                            s = res.get('sinal', 'hold')
                        except Exception:
                            s = 'hold'
                        if s == 'buy':
                            signals_cache.append(('buy', df.iloc[i]['timestamp'], df.iloc[i]['close']))
                        elif s == 'sell':
                            signals_cache.append(('sell', df.iloc[i]['timestamp'], df.iloc[i]['close']))

                    st.session_state['signals_cache'] = signals_cache[-200:]
                    st.session_state['signals_ultimo_idx'] = len(df) - 1

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
                        ))

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
                        ))

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
                            modelo_cache_fn=obter_modelo_treinado,
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

        _y_min = df['close'].min()
        _y_max = df['close'].max()
        _y_pad = (_y_max - _y_min) * 0.08
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(15,20,25,1)',
            font_color='white',
            xaxis=dict(
                showgrid=True,
                gridcolor='rgba(255,255,255,0.05)',
                rangeslider=dict(visible=False),
                rangeselector=dict(
                    buttons=[
                        dict(count=50,  label='50c',  step='minute', stepmode='backward'),
                        dict(count=100, label='100c', step='minute', stepmode='backward'),
                        dict(count=200, label='200c', step='minute', stepmode='backward'),
                        dict(label='Tudo', step='all'),
                    ],
                    bgcolor='rgba(255,255,255,0.05)',
                    activecolor='#26a69a',
                    font=dict(color='white'),
                ),
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(255,255,255,0.05)',
                range=[_y_min - _y_pad, _y_max + _y_pad],
                tickformat=',.2f',
                side='right',
            ),
            margin=dict(l=0, r=60, t=10, b=0),
            legend=dict(bgcolor='rgba(0,0,0,0)'),
            hovermode='x unified',
        )

        if st.session_state.get('dados_grafico_atualizados', False):
            st.session_state['dados_grafico_atualizados'] = False
            st.rerun()

        st.plotly_chart(fig, use_container_width=True)

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
            st.success("Bot operando - recebendo dados em tempo real")
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
    if not st.session_state.get('ws_iniciado', False):
        if iniciar_conexao(selected_symbols):
            conexao_status.success("Conexao com Binance estabelecida!")
            st.session_state['ws_iniciado'] = True
        else:
            conexao_status.error("Falha ao conectar com Binance.")
            st.session_state['bot_running'] = False
            st.session_state['ws_iniciado'] = False
else:
    if st.session_state.get('ws_iniciado', False):
        salvar_estado_bot()   # persiste saldo e ordens abertas antes de parar
        parar_conexao()
        st.session_state['ws_iniciado'] = False

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
_ws_queue = _WS_CANDLE_QUEUE
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
            if bars:
                b = bars[-1]
                novo = {
                    'timestamp': pd.to_datetime(
                        b[0], unit='ms'
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