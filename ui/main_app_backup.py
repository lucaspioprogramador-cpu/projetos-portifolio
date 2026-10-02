# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
import pytz
import plotly.graph_objects as go
from binance.client import Client
from binance import ThreadedWebsocketManager
import threading
import os
import json
import tempfile
from config.settings import BINANCE_API_KEY, BINANCE_API_SECRET
from db.database import registrar_candle, get_candles
from strategies.ai_strategy import executar_estrategia_ai
from strategies.features import gerar_features_basic
import requests
# global websocket manager persists across reruns
_ws_manager = None

def salvar_config_telegram(token, chat_id):
    """Salva as configuraes do Telegram em um arquivo JSON"""

    config = {"telegram_token": token, "telegram_chat_id": chat_id}
    try:
        with open("telegram_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f)
        return True
    except Exception as e:
        print(f"Erro ao salvar config Telegram: {e}")
        return False

def carregar_config_telegram():
    """Carrega as configuraes do Telegram do arquivo JSON"""

    try:
        if os.path.exists("telegram_config.json"):
            with open("telegram_config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("telegram_token", ""), config.get("telegram_chat_id", "")
    except Exception as e:
        print(f"Erro ao carregar config Telegram: {e}")
    return "", ""

def testar_credenciais_telegram(token, chat_id):
    """Testa se o token e chat_id do Telegram so vlidos"""

    try:
        if not token or not chat_id:
            return False, "Token ou Chat ID vazios"
        # Testar token fazendo uma chamada getMe
        url_me = f"https://api.telegram.org/bot{token}/getMe"
        response_me = requests.get(url_me, timeout=10)
        result_me = response_me.json()
        if not result_me.get("ok"):
            return False, f"Token invlido: {result_me.get('description', 'Erro desconhecido')}"
        # Testar chat_id fazendo uma chamada getChat
        url_chat = f"https://api.telegram.org/bot{token}/getChat"
        data_chat = {"chat_id": chat_id}
        response_chat = requests.post(url_chat, data=data_chat, timeout=10)
        result_chat = response_chat.json()
        if not result_chat.get("ok"):
            return False, f"Chat ID inválido: {result_chat.get('description', 'Erro desconhecido')}"
        return True, "Credenciais válidas"
    except requests.exceptions.Timeout:
        return False, "Timeout na conexão"
    except requests.exceptions.ConnectionError:
        return False, "Erro de conexão"
    except Exception as e:
        return False, f"Erro: {str(e)}"

def enviar_notificacao_telegram(mensagem):
    """Envia notificação para o Telegram de forma síncrona"""

    try:
        token = st.session_state.get('telegram_token', '')
        chat_id = st.session_state.get('telegram_chat_id', '')
        if not token or not chat_id:
            return False
        # Validar formato do token (deve comear com nmero e ter pelo menos 35 caracteres)
        if not token.startswith(('1', '2', '3', '4', '5', '6', '7', '8', '9', '0')) or len(token) < 35:
            return False
        # Validar formato do chat_id (deve ser numrico negativo ou comear com @)
        if not (
            chat_id.startswith('-') and chat_id[1:].isdigit()
        ) and not chat_id.startswith('@') and not chat_id.isdigit():
            return False
        # Usar requests para enviar mensagem diretamente via HTTP
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": mensagem,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=data, timeout=10)
        result = response.json()
        if result.get("ok"):
            return True
        else:
            return False
    except requests.exceptions.Timeout:

        return False
    except requests.exceptions.ConnectionError:

        return False
symbols = [
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "LTC/USDT",
    "PEPE/USDT",
    "PENDLE/USDT",
    "JTO/USDT",
    "BB/USDT",
    "SUI/USDT"
]
st.set_page_config(page_title="Trading Bot Dashboard", layout="wide")
BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: #0a0e27;
    }
    .main {
        background-color: #0f1419;
    }
    .sidebar-title {
        color: #ffffff;
        font-size: 18px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)
with st.sidebar:
    st.markdown('<div class="sidebar-title">Credenciais</div>', unsafe_allow_html=True)
    def salvar_credenciais(api_key, api_secret):
        with open("binance_api.json", "w", encoding="utf-8") as f:
            json.dump({"api_key": api_key, "api_secret": api_secret}, f)
    def carregar_credenciais():
        if os.path.exists("binance_api.json"):
            with open("binance_api.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("api_key", ""), data.get("api_secret", "")
        return "", ""
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
    # Carregar configuraes do Telegram
    if 'telegram_loaded' not in st.session_state:
        telegram_token_loaded, telegram_chat_id_loaded = carregar_config_telegram()
        st.session_state['telegram_token'] = telegram_token_loaded
        st.session_state['telegram_chat_id'] = telegram_chat_id_loaded
        st.session_state['telegram_loaded'] = True
    st.markdown("**API Key Binance**")
    api_key = st.text_input(
        "",
        value=st.session_state.get('api_key', ''),
        type="password",
        placeholder="Digite sua API Key",
        label_visibility="collapsed"
    )
    st.markdown("**API Secret Binance**")
    api_secret = st.text_input(
        "",
        value=st.session_state.get('api_secret', ''),
        type="password",
        placeholder="Digite seu API Secret",
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
    st.markdown('<div class="sidebar-title">Notificaes Telegram</div>', unsafe_allow_html=True)
    # Usar valores temporrios para evitar conflitos com session state
    telegram_token_input = st.text_input(
        "",
        value=st.session_state.get('telegram_token', ''),
        type="password",
        placeholder="Cole o token do seu bot",
        label_visibility="collapsed",
        key="telegram_token_input"
    )
    telegram_chat_id_input = st.text_input(
        "",
        value=st.session_state.get('telegram_chat_id', ''),
        placeholder="Seu chat ID",
        label_visibility="collapsed",
        key="telegram_chat_id_input"
    )
    st.markdown("**Notificaes Ativas**")
    notificaes_ativas = st.checkbox(
        "Enviar notificaes no Telegram",
        value=st.session_state.get('notificaes_ativas', False),
        key="notificaes_ativas"
    )
    col_test, col_save_telegram = st.columns(2)
    with col_test:
        if st.button(
            "Testar Notificao",
            use_container_width=True,
            key="test_telegram"
        ):
            if telegram_token_input and telegram_chat_id_input:
                # Atualizar session state temporariamente para o teste
                st.session_state['telegram_token'] = telegram_token_input
                st.session_state['telegram_chat_id'] = telegram_chat_id_input
                mensagem_teste = (
                    f"TESTE DE NOTIFICAÃÂÃÂO\n"
                    f"ConfiguraÃÂ§ÃÂ£o funcionando!\n"
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
        if st.button(
            "Salvar Telegram",
            use_container_width=True,
            key="save_telegram"
        ):
            salvar_config_telegram(telegram_token_input, telegram_chat_id_input)
            st.session_state['telegram_token'] = telegram_token_input
            st.session_state['telegram_chat_id'] = telegram_chat_id_input
            st.success("Configuraes do Telegram salvas!")
    with st.expander("?? Como obter Token e Chat ID do Telegram"):
        st.markdown("""
        ### 1. Criar Bot no Telegram
        - Procure por **@BotFather** no Telegram
        - Digite `/newbot` e siga as instrues
        - **Copie o TOKEN** gerado (ex: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)
        ### 2. Obter Chat ID
        - Inicie uma conversa com seu bot recm-criado
        - Envie qualquer mensagem para ele
        - Acesse: `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates`
        - Procure por `"chat":{"id":XXXXX` na resposta
        - **Copie o ID** (geralmente negativo, ex: `-123456789`)
        ### 3. Testar
        - Use o boto **"Testar Credenciais"** primeiro
        - Depois use **"Testar Notificao"** para enviar uma mensagem real
        **Dicas:**
        - O token deve ter ~35-45 caracteres
        - O chat ID deve ser numrico (pode ser negativo)
        - Certifique-se de que iniciou uma conversa com o bot
        """)
    st.divider()
    st.markdown('<div class="sidebar-title">Parmetros de Operao</div>', unsafe_allow_html=True)
    st.markdown("**Par de Negociao**")
    symbol = st.selectbox(
        "",
        [s.replace("/", "") for s in symbols],
        label_visibility="collapsed",
        index=0
    )
    symbol = symbol.replace("USDT", "/USDT")

    if symbol not in symbols:
        st.error("Par invlido!")
    st.markdown("**Timeframe**")
    timeframe = st.selectbox(
        "",
        ["1m", "5m", "15m", "30m", "1h", "4h"],
        label_visibility="collapsed",
        index=0
    )
    st.markdown("**Saldo Inicial (USDT)**")
    saldo_inicial = st.number_input(
        "",
        min_value=100,
        value=1000,
        label_visibility="collapsed"
    )
    st.markdown("**Risco por Trade (%)**")
    risco_por_trade_display = st.slider(
        "",
        0.1,
        5.0,
        1.0,
        label_visibility="collapsed"
    )
    risco_por_trade = risco_por_trade_display / 100
    st.caption("1/5")
    st.markdown("**Stop Loss (%)**")
    stop_loss_display = st.slider(
        "",
        0.1,
        10.0,
        2.0,
        label_visibility="collapsed",
        key="sl"
    )
    stop_loss = stop_loss_display / 100
    st.caption("2/10")
    st.markdown("**Take Profit (%)**")
    take_profit_display = st.slider(
        "",
        0.1,
        10.0,
        3.0,
        label_visibility="collapsed",
        key="tp"
    )
    take_profit = take_profit_display / 100
    st.caption("3/15")
    st.divider()
    # ConfiguraÃÂ§ÃÂµes avanÃ§adas
    with st.expander("ConfiguraÃÂ§ÃÂµes AvanÃÂ§adas"):
        usar_simulacao = st.checkbox(
            "Usar SimulaÃÂ§ÃÂ£o Realista",
            value=True,
            help="Simula slippage, taxas e execuÃ§Ã£o parcial"
        )
        usar_estrategia_melhorada = st.checkbox(
            "Usar EstratÃÂ©gia Melhorada (IA)",
            value=True,
            help="Usa estratÃ©gia avanÃÂ§ada com mÃÂºltiplos indicadores"
        )
        mostrar_detalhes_execucao = st.checkbox(
            "Mostrar Detalhes de ExecuÃÂ§ÃÂ£o",
            value=True,
            help="Mostra slippage, taxas e outros detalhes"
        )
    # Salvar configuraÃ§Ãµes no session_state
    st.session_state['usar_simulacao'] = usar_simulacao
    st.session_state['usar_estrategia_melhorada'] = usar_estrategia_melhorada
    st.session_state['mostrar_detalhes_execucao'] = mostrar_detalhes_execucao
    st.divider()

if 'bot_running' not in st.session_state:
    st.session_state['bot_running'] = False

def ensure_bot_state():
    defaults = {
        'saldo_usdt': saldo_inicial,
        'saldo_inicial': saldo_inicial,
        'posicao_aberta': False,
        'preco_compra': None,
        'quantidade': 0,
        'valor_investido': 0,
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
websocket_data_global = {}
websocket_data_lock = threading.Lock()

def now_brazil():
    return datetime.now(BRAZIL_TZ)

def format_time(dt):
    return dt.strftime("%d/%m/%Y %H:%M:%S")

def calcular_posicao(saldo, preco, risco, stop_pct):
    return (saldo * risco) / (preco * stop_pct)

def analisar_e_executar_trades():
    """Analisa os dados do mercado e executa trades automaticamente"""

    if not st.session_state.get('bot_running', False):
        return
    try:
        # Verificar se h dados suficientes
        df = st.session_state.bot_data['dados_mercado'].get(symbol, pd.DataFrame())
        if df.empty or len(df) < 100:
            return
        # Executar estratÃ©gia AI
        posicao_aberta = st.session_state.bot_data.get('posicao_aberta', False)
        ultimo_preco_compra = st.session_state.bot_data.get('preco_compra')
        sinal = executar_estrategia_ai(df, posicao_aberta, ultimo_preco_compra)
        if sinal == 'buy' and not posicao_aberta:
            # Calcular quantidade baseada no risco
            saldo = st.session_state.bot_data.get('saldo_usdt', saldo_inicial)
            preco_atual = df.iloc[-1]['close']
            quantidade = calcular_posicao(saldo, preco_atual, risco_por_trade, stop_loss)
            if quantidade > 0:
                # Executar compra
                trade = executar_ordem('COMPRA', preco_atual, quantidade)
        elif sinal == 'sell' and posicao_aberta:
            # Executar venda
            preco_atual = df.iloc[-1]['close']
            quantidade = st.session_state.bot_data.get('quantidade', 0)
            if quantidade > 0:
                trade = executar_ordem('VENDA', preco_atual, quantidade)
    except Exception as e:
        print(f"Erro na anlise de trades: {e}")

def executar_ordem(tipo, preco, quantidade, usar_simulacao=None):
    from core.execution import executar_ordem_simulada

    if usar_simulacao is None:
        usar_simulacao = st.session_state.get('usar_simulacao', True)
    lado = 'buy' if tipo == 'COMPRA' else 'sell'
    volatilidade = None
    volume_24h = None

    if symbol in st.session_state.bot_data['dados_mercado']:
        df = st.session_state.bot_data['dados_mercado'][symbol]
        if len(df) >= 20:
            volatilidade = df['close'].pct_change().std()
            volume_24h = df['volume'].sum() * preco
    if usar_simulacao:
        execucao = executar_ordem_simulada(
            lado=lado,
            quantidade=quantidade,
            preco_atual=preco,
            symbol=symbol,
            volume_24h=volume_24h,
            volatilidade=volatilidade
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
        valor_liquido = valor_total - taxas if tipo == 'COMPRA' else valor_total - taxas
    trade = {
        'timestamp': now_brazil(),
        'symbol': symbol,
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

    if tipo == 'COMPRA':
        st.session_state.bot_data['saldo_usdt'] -= valor_liquido
        st.session_state.bot_data['posicao_aberta'] = True
        st.session_state.bot_data['preco_compra'] = preco_exec
        st.session_state.bot_data['quantidade'] = quantidade_exec
        st.session_state.bot_data['valor_investido'] = valor_liquido
    else:
        st.session_state.bot_data['saldo_usdt'] += valor_liquido
        st.session_state.bot_data['posicao_aberta'] = False
        preco_compra = st.session_state.bot_data.get('preco_compra', preco_exec)
        valor_investido = st.session_state.bot_data.get('valor_investido', preco_compra * quantidade_exec)
        trade['lucro'] = valor_liquido - valor_investido
        trade['lucro_liquido'] = trade['lucro']
        trade['retorno'] = (trade['lucro'] / valor_investido * 100) if valor_investido > 0 else 0
        trade['retorno_liquido'] = trade['retorno']
        st.session_state.bot_data['valor_investido'] = 0
        st.session_state.bot_data['preco_compra'] = None
        st.session_state.bot_data['quantidade'] = 0
    st.session_state.bot_data['trades'].append(trade)
    return trade

def atualizar_dados_mercado(symbol_proc, novo_dado):
    if symbol_proc not in st.session_state.bot_data['dados_mercado']:
        st.session_state.bot_data['dados_mercado'][symbol_proc] = pd.DataFrame([novo_dado])
    else:
        st.session_state.bot_data['dados_mercado'][symbol_proc] = pd.concat([
            st.session_state.bot_data['dados_mercado'][symbol_proc],
            pd.DataFrame([novo_dado])
        ]).drop_duplicates().tail(500)
file_write_lock = threading.Lock()

def iniciar_conexao(selected_symbols):
    _api_key = st.session_state.get('api_key', '')
    _api_secret = st.session_state.get('api_secret', '')

    if _api_key and _api_secret:
        try:
            print(f"Iniciando conexÃ£o com Binance para pares: {selected_symbols}")
            client = Client(_api_key, _api_secret)
            twm = ThreadedWebsocketManager(api_key=_api_key, api_secret=_api_secret)
            twm.start()
            print("ThreadedWebsocketManager iniciado.")
            def handle_socket_message(msg):
                if msg['e'] == 'kline':
                    kline = msg['k']
                    symbol_ws = msg['s'] if 's' in msg else symbol.replace("/", "")
                    novo_dado = {
                        'timestamp': pd.to_datetime(
                            kline['t'], unit='ms'
                        ).tz_localize('UTC').tz_convert(BRAZIL_TZ).strftime('%Y-%m-%d %H:%M:%S'),
                        'open': float(kline['o']),
                        'high': float(kline['h']),
                        'low': float(kline['l']),
                        'close': float(kline['c']),
                        'volume': float(kline['v']),
                        'timeframe': timeframe
                    }
                    try:
                        registrar_candle(
                            symbol_ws,
                            novo_dado['timestamp'],
                            novo_dado['open'],
                            novo_dado['high'],
                            novo_dado['low'],
                            novo_dado['close'],
                            novo_dado['volume'],
                            novo_dado['timeframe']
                        )
                    except Exception:
                        pass
                    tmpfile = os.path.join(tempfile.gettempdir(), f"tmp_ws_{symbol_ws}.json")
                    try:
                        with file_write_lock:
                            if os.path.exists(tmpfile):
                                with open(tmpfile, 'r', encoding='utf-8') as f:
                                    try:
                                        dados = json.load(f)
                                        if not isinstance(dados, list):
                                            dados = []
                                    except Exception:
                                        dados = []
                            else:
                                dados = []
                            dados.append(novo_dado)
                            with open(tmpfile, 'w', encoding='utf-8') as f:
                                json.dump(dados, f)
                    except Exception as e:
                        print(f"Erro ao salvar arquivo temporrio: {e}")
            for symb in selected_symbols:
                symbol_socket = symb.replace("/", "")
                twm.start_kline_socket(
                    symbol=symbol_socket,
                    interval=timeframe,
                    callback=handle_socket_message
                )
            st.session_state.bot_data['client'] = client
            st.session_state.bot_data['conexao_websocket'] = twm
            st.session_state.bot_data['inicio_operacao'] = now_brazil()
            return True
        except Exception as e:
            st.error(f"Erro na conexÃ£o: {str(e)}")
            return False
    return False

def parar_conexao():
    if 'conexao_websocket' in st.session_state.bot_data and st.session_state.bot_data['conexao_websocket']:
        st.session_state.bot_data['conexao_websocket'].stop()
        st.session_state.bot_data['conexao_websocket'] = None
st.markdown("# Trading Bot Dashboard")
col1, col2, col3, col4 = st.columns(4)
saldo_usdt = st.session_state.bot_data.get('saldo_usdt', saldo_inicial)
saldo_total = saldo_usdt
if st.session_state.bot_data.get('posicao_aberta', False):
    preco_atual = st.session_state.bot_data['dados_mercado'].get(symbol, pd.DataFrame())

    if not preco_atual.empty:
        preco_atual = preco_atual.iloc[-1]['close']
        quantidade = st.session_state.bot_data.get('quantidade', 0)
        saldo_total += preco_atual * quantidade
with col1:
    st.metric("Saldo Atual (USDT)", f"{saldo_usdt:.2f}")
with col2:
    st.metric("Saldo Total (USDT)", f"{saldo_total:.2f}")
with col3:
    variacao_pct = ((saldo_total - saldo_inicial) / saldo_inicial * 100) if saldo_inicial > 0 else 0
    st.metric("Variao (%)", f"{variacao_pct:.1f}%", "Variao em relao ao perodo...")
col_status1, col_status2, col_status3 = st.columns([2, 1, 1])
with col_status1:
    st.markdown("**Aguardando dados...**")
with col_status2:
    status = "OPERANDO" if st.session_state['bot_running'] else "PARADO"
    st.markdown(f"**{status}**")
with col_status3:
    dados_count = len(st.session_state.bot_data.get('dados_mercado', {}).get(symbol, []))
    st.markdown(f"**Dados:** {dados_count} candles")
st.markdown("### Viso da IA - Anlise Tcnica")
col_ia_btn = st.columns([0.2, 0.8])[0]
with col_ia_btn:
    if st.button(
        "Interpretar",
        use_container_width=True
    ):
        if not st.session_state.get('bot_running', False):
            st.session_state['bot_running'] = True
            st.session_state.bot_data['inicio_operacao'] = now_brazil()
        st.info("Legenda: Linha Branca=PreÃ§o, Seta Verde=Compra, Seta Vermelha=Venda")
st.markdown("Aguardando dados do mercado...")
st.divider()
st.markdown("### Grfico")
col_viz, col_dropdown = st.columns([0.8, 0.2])
with col_dropdown:
    viz_type = st.selectbox(
        "Visualizao",
        ["Preo"],
        label_visibility="collapsed"
    )
main_df = pd.DataFrame()
try:
    # prioritize DB-backed candles for plotting
    df_db = get_candles(symbol.replace('/', ''), limit=500, timeframe=timeframe)

    if not df_db.empty:
        main_df = df_db.copy()
    else:
        main_df = st.session_state.bot_data['dados_mercado'].get(symbol, pd.DataFrame())
except Exception:
    main_df = st.session_state.bot_data['dados_mercado'].get(symbol, pd.DataFrame())

if not main_df.empty:
    df = main_df.copy()
    # ensure timestamp is datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.dropna(subset=['timestamp', 'close'])

    if not df.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['close'],
            mode='lines',
            line=dict(color='rgba(255,255,255,1)', width=2),
            fill='tozeroy',
            fillcolor='rgba(255,255,255,0.1)',
            name='Preo'
        ))
        # Add buy/sell signals if available
        try:
            from strategies.ai_strategy import executar_estrategia_ai

            if len(df) >= 100:
                signals = []
                for i in range(100, len(df)):
                    window_df = df.iloc[i-100:i+1].copy()
                    posicao_aberta = False  # For visualization, assume no position
                    ultimo_preco_compra = None
                    sinal = executar_estrategia_ai(window_df, posicao_aberta, ultimo_preco_compra)
                    if sinal == 'buy':
                        signals.append(('buy', df.iloc[i]['timestamp'], df.iloc[i]['close']))
                    elif sinal == 'sell':
                        signals.append(('sell', df.iloc[i]['timestamp'], df.iloc[i]['close']))
                for signal_type, timestamp, price in signals[-20:]:  # Show last 20 signals
                    color = 'green' if signal_type == 'buy' else 'red'
                    symbol_marker = 'triangle-up' if signal_type == 'buy' else 'triangle-down'
                    fig.add_trace(go.Scatter(
                        x=[timestamp],
                        y=[price],
                        mode='markers',
                        marker=dict(color=color, size=10, symbol=symbol_marker),
                        name=f'Sinal {signal_type.upper()}',
                        showlegend=False
                    ))
                try:
                    indicadores_df = gerar_features_basic(df)
                    ultimo_indicador = indicadores_df.iloc[-1]
                    st.markdown("### Indicadores Atuais")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("RSI", f"{ultimo_indicador['rsi']:.1f}")
                    c1.metric("Volume", f"{int(ultimo_indicador['volume']):,}")
                    c2.metric("MACD", f"{ultimo_indicador['macd']:.4f}")
                    c2.metric("MACD Signal", f"{ultimo_indicador['macd_signal']:.4f}")
                    c3.metric("MÃ©dia 20", f"{ultimo_indicador['media_20']:.4f}")
                    c3.metric("Volume Spike", "Sim" if ultimo_indicador['volume_spike'] == 1 else "NÃ£o")
                except Exception:
                    pass
        except Exception as e:
            pass
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color='white',
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=False),
            margin=dict(l=0, r=0, t=0, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aguardando dados suficientes para plotar o grfico...")
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
            st.markdown(f"**Par:** {symbol}")
            st.markdown(f"**Atualizao:** {format_time(now_brazil())}")
            st.markdown("**Prxima em:** -")
        else:
            st.markdown("**Par:** -")
            st.markdown(f"**Atualizao:** {format_time(now_brazil())}")
            st.markdown("**Prxima em:** -")
with col_historico:
    st.markdown("### Histrico")
    trades = st.session_state.bot_data.get('trades', [])

    if trades:
        st.markdown(f"**Total de trades: {len(trades)}**")
        for i, trade in enumerate(trades[-5:]):  # Mostra os ltimos 5 trades
            emoji = "??" if trade.get('tipo') == 'COMPRA' else "??"
            lucro = trade.get('retorno', 0)
            st.markdown(
                f"{emoji} {trade.get('tipo')} {trade.get('symbol')} - "
                f"${trade.get('preco_execucao', 0):.2f} - {lucro:.2f}%"
            )
    else:
        st.markdown("**Nenhum trade executado**")
    col_stats1, col_stats2 = st.columns(2)
    with col_stats1:
        st.markdown("[Estatsticas]")
    with col_stats2:
        st.markdown("[Configuraes]")
st.markdown("")
selected_symbols = st.multiselect(
    "Selecione os pares para monitorar em tempo real:",
    symbols,
    default=[symbols[0]]
)
conexao_status = st.empty()
if st.session_state['bot_running']:
    if not st.session_state.get('ws_iniciado', False):
        if iniciar_conexao(selected_symbols):
            conexao_status.success("Conexo com Binance estabelecida!")
            st.session_state['ws_iniciado'] = True
        else:
            conexao_status.error("Falha ao conectar com Binance.")
            st.session_state['bot_running'] = False
            st.session_state['ws_iniciado'] = False
else:
    if st.session_state.get('ws_iniciado', False):
        parar_conexao()
        st.session_state['ws_iniciado'] = False
if __name__ == "__main__":
    # Este cdigo s executa quando o arquivo  executado diretamente
    # No quando importado pelo Streamlit
    pass
# Cdigo principal da aplicao Streamlit
# Tudo abaixo s executa quando chamado pelo Streamlit
# Verificar se estamos no contexto do Streamlit
try:
    # S executar se st estiver disponvel (contexto Streamlit)
    st.write("")  # Teste se st est disponvel
except:
    # Se no estiver no contexto Streamlit, sair
    exit(0)
# Agora podemos usar st.session_state com segurana
if 'ultima_atualizacao_ui' not in st.session_state:
    st.session_state['ultima_atualizacao_ui'] = now_brazil()
status_update_placeholder = st.empty()
dados_novos = False
notify_placeholder = st.empty()
for symb in selected_symbols:
    symbol_socket = symb.replace("/", "")
    tmpfile = os.path.join(tempfile.gettempdir(), f"tmp_ws_{symbol_socket}.json")

    if os.path.exists(tmpfile):
        try:
            with file_write_lock:
                with open(tmpfile, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                if dados:
                    for dado in dados:
                        dado['timestamp'] = pd.to_datetime(dado['timestamp'])
                        atualizar_dados_mercado(symb, dado)
                        dados_novos = True
                        try:
                            notify_placeholder.toast(f"Candle {symbol_socket} recebido", icon="??")
                        except Exception:
                            notify_placeholder.info(f"Candle {symbol_socket} recebido")
                with open(tmpfile, 'w', encoding='utf-8') as f:
                    json.dump([], f)
        except Exception as e:
            print(f"Erro ao ler arquivo temporrio: {e}")
# try REST if no websocket data received
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
    except Exception:
        pass
if st.session_state['bot_running']:
    # Analisar e executar trades automaticamente
    analisar_e_executar_trades()
    # display live timer for next minute using header placeholder
    start_time = st.session_state.bot_data.get('inicio_operacao') or now_brazil()
    end_wait = now_brazil() + timedelta(seconds=60)
    ph = st.session_state.get('timer_header_ph')

    while now_brazil() < end_wait and st.session_state.get('bot_running', False):
        elapsed = now_brazil() - start_time
        if ph:
            ph.markdown(f"**Tempo: {str(elapsed).split('.')[0]}**")
        time.sleep(1)
    st.session_state['ultima_atualizacao_ui'] = now_brazil()
    st.rerun()