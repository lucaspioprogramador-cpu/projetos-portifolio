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
import asyncio
from telegram import Bot
import requests

# global websocket manager persists across reruns
_ws_manager = None

def salvar_config_telegram(token, chat_id):
    """Salva as configuracoes do Telegram em um arquivo JSON"""
    config = {"telegram_token": token, "telegram_chat_id": chat_id}
    try:
        with open("telegram_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f)
        return True
    except Exception as e:
        print(f"Erro ao salvar config Telegram: {e}")
        return False

def carregar_config_telegram():
    """Carrega as configuracoes do Telegram do arquivo JSON"""
    try:
        if os.path.exists("telegram_config.json"):
            with open("telegram_config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("telegram_token", ""), config.get("telegram_chat_id", "")
    except Exception as e:
        print(f"Erro ao carregar config Telegram: {e}")
    return "", ""

def testar_credenciais_telegram(token, chat_id):
    """Testa se o token e chat_id do Telegram sao validos"""
    try:
        if not token or not chat_id:
            return False, "Token ou Chat ID vazios"

        # Testar token fazendo uma chamada getMe
        url_me = f"https://api.telegram.org/bot{token}/getMe"
        response_me = requests.get(url_me, timeout=10)
        result_me = response_me.json()

        if not result_me.get("ok"):
            return False, f"Token invalido: {result_me.get('description', 'Erro desconhecido')}"

        # Testar chat_id fazendo uma chamada getChat
        url_chat = f"https://api.telegram.org/bot{token}/getChat"
        data_chat = {"chat_id": chat_id}
        response_chat = requests.post(url_chat, data=data_chat, timeout=10)
        result_chat = response_chat.json()

        if not result_chat.get("ok"):
            return False, f"Chat ID invalido: {result_chat.get('description', 'Erro desconhecido')}"

        return True, "Credenciais validas"

    except requests.exceptions.Timeout:
        return False, "Timeout na conexao"
    except requests.exceptions.ConnectionError:
        return False, "Erro de conexao"
    except Exception as e:
        return False, f"Erro: {str(e)}"

def enviar_notificacao_telegram(mensagem):
    """Envia notificacao para o Telegram de forma sincrona"""
    try:
        token = st.session_state.get('telegram_token', '')
        chat_id = st.session_state.get('telegram_chat_id', '')

        print(f"Debug - Token: {token[:10]}... Chat ID: {chat_id[:5]}...")  # Debug log

        if not token or not chat_id:
            print("Debug - Token ou Chat ID vazios")
            return False

        # Validar formato do token (deve começar com número e ter pelo menos 35 caracteres)
        if not token.startswith(('1', '2', '3', '4', '5', '6', '7', '8', '9', '0')) or len(token) < 35:
            print("Debug - Token parece invalido (formato incorreto)")
            return False

        # Validar formato do chat_id (deve ser numérico negativo ou começar com @)
        if not (chat_id.startswith('-') and chat_id[1:].isdigit()) and not chat_id.startswith('@') and not chat_id.isdigit():
            print("Debug - Chat ID parece invalido (formato incorreto)")
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
            print("Debug - Mensagem enviada com sucesso")
            return True
        else:
            error_description = result.get("description", "Erro desconhecido")
            print(f"Debug - Erro da API Telegram: {error_description}")
            return False

    except requests.exceptions.Timeout:
        print("Debug - Timeout na conexao com Telegram")
        return False
    except requests.exceptions.ConnectionError:
        print("Debug - Erro de conexao com Telegram")
        return False
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

    # Carregar configuracoes do Telegram
    if 'telegram_loaded' not in st.session_state:
        telegram_token_loaded, telegram_chat_id_loaded = carregar_config_telegram()
        st.session_state['telegram_token'] = telegram_token_loaded
        st.session_state['telegram_chat_id'] = telegram_chat_id_loaded
        st.session_state['telegram_loaded'] = True

    st.markdown("**API Key Binance**")
    api_key = st.text_input("", value=st.session_state.get('api_key', ''), type="password", placeholder="Intra sua API Key", label_visibility="collapsed")
    
    st.markdown("**API Secret Binance**")
    api_secret = st.text_input("", value=st.session_state.get('api_secret', ''), type="password", placeholder="Intra seu API Secret", label_visibility="collapsed")

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

    st.markdown("Credenciais carregadas do arquivo .env")

    st.divider()
    
    st.markdown('<div class="sidebar-title">Notificacoes Telegram</div>', unsafe_allow_html=True)
    
    # Usar valores temporarios para evitar conflitos com session state
    telegram_token_input = st.text_input("", value=st.session_state.get('telegram_token', ''), type="password", placeholder="Cole o token do seu bot", label_visibility="collapsed", key="telegram_token_input")
    
    telegram_chat_id_input = st.text_input("", value=st.session_state.get('telegram_chat_id', ''), placeholder="Seu chat ID", label_visibility="collapsed", key="telegram_chat_id_input")
    
    st.markdown("**Notificacoes Ativas**")
    notificacoes_ativas = st.checkbox("Enviar notificacoes no Telegram", value=st.session_state.get('notificacoes_ativas', False), key="notificacoes_ativas")
    
    col_test, col_test_creds, col_save_telegram = st.columns([0.3, 0.3, 0.4])
    with col_test:
        if st.button("Testar Notificacao", use_container_width=True, key="test_telegram"):
            if telegram_token_input and telegram_chat_id_input:
                # Atualizar session state temporariamente para o teste
                st.session_state['telegram_token'] = telegram_token_input
                st.session_state['telegram_chat_id'] = telegram_chat_id_input
                mensagem_teste = f"TESTE DE NOTIFICACAO\nConfiguracao funcionando!\n{datetime.now(BRAZIL_TZ).strftime('%d/%m/%Y %H:%M:%S')}"

                st.write(f"Debug - Token: {telegram_token_input[:10]}...")
                st.write(f"Debug - Chat ID: {telegram_chat_id_input[:5]}...")

                try:
                    resultado = enviar_notificacao_telegram(mensagem_teste)
                    if resultado:
                        st.success("Mensagem de teste enviada!")
                    else:
                        st.error("Falha ao enviar mensagem de teste - verifique token e chat ID")
                except Exception as e:
                    st.error(f"Erro ao enviar teste: {str(e)}")
            else:
                st.warning("Configure o token e chat ID primeiro")

    with col_test_creds:
        if st.button("Testar Credenciais", use_container_width=True, key="test_creds"):
            if telegram_token_input and telegram_chat_id_input:
                with st.spinner("Testando credenciais..."):
                    valido, mensagem = testar_credenciais_telegram(telegram_token_input, telegram_chat_id_input)
                    if valido:
                        st.success(f"? Credenciais validas! {mensagem}")
                    else:
                        st.error(f"? Credenciais invalidas: {mensagem}")
            else:
                st.warning("Configure o token e chat ID primeiro")

    with col_save_telegram:
        if st.button("Salvar Telegram", use_container_width=True, key="save_telegram"):
            st.session_state['telegram_token'] = telegram_token_input
            st.session_state['telegram_chat_id'] = telegram_chat_id_input
            if salvar_config_telegram(telegram_token_input, telegram_chat_id_input):
                st.success("Configuracoes do Telegram salvas!")
            else:
                st.error("Erro ao salvar configuracoes!")

    st.markdown("---")
    with st.expander("?? Como obter Token e Chat ID do Telegram"):
        st.markdown("""
        ### 1. Criar Bot no Telegram
        - Procure por **@BotFather** no Telegram
        - Digite `/newbot` e siga as instruções
        - **Copie o TOKEN** gerado (ex: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

        ### 2. Obter Chat ID
        - Inicie uma conversa com seu bot recém-criado
        - Envie qualquer mensagem para ele
        - Acesse: `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates`
        - Procure por `"chat":{"id":XXXXX` na resposta
        - **Copie o ID** (geralmente negativo, ex: `-123456789`)

        ### 3. Testar
        - Use o botão **"Testar Credenciais"** primeiro
        - Depois use **"Testar Notificacao"** para enviar uma mensagem real

        ?? **Dicas:**
        - O token deve ter ~35-45 caracteres
        - O chat ID deve ser numérico (pode ser negativo)
        - Certifique-se de que iniciou uma conversa com o bot
        """)
    
    st.divider()
    
    st.markdown('<div class="sidebar-title">Parametros de Operacao</div>', unsafe_allow_html=True)
    
    st.markdown("**Par de Negociacao**")
    symbol = st.selectbox("", [s.replace("/", "") for s in symbols], label_visibility="collapsed", index=0)
    symbol = symbol.replace("USDT", "/USDT")
    if symbol not in symbols:
        st.error("Par invalido!")
    
    st.markdown("**Timeframe**")
    timeframe = st.selectbox("", ["1m", "5m", "15m", "30m", "1h", "4h"], label_visibility="collapsed", index=0)
    
    st.markdown("**Saldo Inicial (USDT)**")
    saldo_inicial = st.number_input("", min_value=100, value=1000, label_visibility="collapsed")
    
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
        # Verificar se ha dados suficientes
        df = st.session_state.bot_data['dados_mercado'].get(symbol, pd.DataFrame())
        if df.empty or len(df) < 100:
            return
            
        # Executar estrategia AI
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
                
                # Enviar notificacao
                if st.session_state.get('notificacoes_ativas', False):
                    mensagem = f"COMPRA EXECUTADA\nPar: {symbol}\nPreco: ${preco_atual:.2f}\nQuantidade: {quantidade:.6f}\n{format_time(now_brazil())}"
                    enviar_notificacao_telegram(mensagem)
                    
        elif sinal == 'sell' and posicao_aberta:
            # Executar venda
            preco_atual = df.iloc[-1]['close']
            quantidade = st.session_state.bot_data.get('quantidade', 0)
            
            if quantidade > 0:
                trade = executar_ordem('VENDA', preco_atual, quantidade)
                
                # Calcular lucro
                preco_compra = st.session_state.bot_data.get('preco_compra', preco_atual)
                lucro_pct = (preco_atual - preco_compra) / preco_compra * 100
                
                # Enviar notificacao
                if st.session_state.get('notificacoes_ativas', False):
                    emoji = "LUCRO" if lucro_pct > 0 else "PREJUIZO"
                    mensagem = f"VENDA EXECUTADA - {emoji}\nPar: {symbol}\nPreco: ${preco_atual:.2f}\nQuantidade: {quantidade:.6f}\nLucro: {lucro_pct:.2f}%\n{format_time(now_brazil())}"
                    enviar_notificacao_telegram(mensagem)
                    
    except Exception as e:
        print(f"Erro na analise de trades: {e}")

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
    
    if 'eventos_ws' in st.session_state.bot_data:
        st.session_state.bot_data['eventos_ws'][symbol_proc] = st.session_state.bot_data['eventos_ws'].get(symbol_proc, 0) + 1

file_write_lock = threading.Lock()

def iniciar_conexao(selected_symbols):
    _api_key = st.session_state.get('api_key', '')
    _api_secret = st.session_state.get('api_secret', '')
    
    if _api_key and _api_secret:
        try:
            print(f"Iniciando conexao com Binance para pares: {selected_symbols}")
            client = Client(_api_key, _api_secret)
            twm = ThreadedWebsocketManager(api_key=_api_key, api_secret=_api_secret)
            twm.start()
            print("ThreadedWebsocketManager iniciado.")
            
            def handle_socket_message(msg):
                if msg['e'] == 'kline':
                    kline = msg['k']
                    symbol_ws = msg['s'] if 's' in msg else symbol.replace("/", "")
                    novo_dado = {
                        'timestamp': pd.to_datetime(kline['t'], unit='ms').tz_localize('UTC').tz_convert(BRAZIL_TZ).strftime('%Y-%m-%d %H:%M:%S'),
                        'open': float(kline['o']),
                        'high': float(kline['h']),
                        'low': float(kline['l']),
                        'close': float(kline['c']),
                        'volume': float(kline['v']),
                        'timeframe': timeframe
                    }
                    try:
                        registrar_candle(symbol_ws, novo_dado['timestamp'], novo_dado['open'], novo_dado['high'], novo_dado['low'], novo_dado['close'], novo_dado['volume'], novo_dado['timeframe'])
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
                        print(f"Erro ao salvar arquivo temporario: {e}")
            
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
            st.error(f"Erro na conexao: {str(e)}")
            return False
    return False

def parar_conexao():
    if 'conexao_websocket' in st.session_state.bot_data and st.session_state.bot_data['conexao_websocket']:
        st.session_state.bot_data['conexao_websocket'].stop()
        st.session_state.bot_data['conexao_websocket'] = None

st.markdown("# Trading Bot Dashboard")

col1, col2, col3, col4 = st.columns(4)

saldo_usdt = st.session_state.bot_data.get('saldo_usdt', saldo_inicial)
valor_posicao_atual = 0
if st.session_state.bot_data.get('posicao_aberta'):
    preco_atual_posicao = st.session_state.bot_data['dados_mercado'].get(symbol, pd.DataFrame())
    if not preco_atual_posicao.empty:
        preco_atual_posicao_valor = preco_atual_posicao.iloc[-1]['close']
        quantidade_posicao = st.session_state.bot_data.get('quantidade', 0)
        valor_posicao_atual = preco_atual_posicao_valor * quantidade_posicao

saldo_total = saldo_usdt + valor_posicao_atual

with col1:
    st.metric("Saldo USDT", f"${saldo_usdt:,.2f}", "Current balance")

with col2:
    st.metric("Saldo Total", f"${saldo_total:,.2f}", "Current balance")

with col3:
    lucro_realizado = 0
    if st.session_state.bot_data.get('trades'):
        df_trades = pd.DataFrame(st.session_state.bot_data['trades'])
        df_vendas = df_trades[df_trades['tipo'] == 'VENDA']
        if not df_vendas.empty and 'lucro' in df_vendas.columns:
            lucro_realizado = df_vendas['lucro'].sum()
    
    lucro_nao_realizado = 0
    if st.session_state.bot_data.get('posicao_aberta'):
        valor_investido = st.session_state.bot_data.get('valor_investido', 0)
        lucro_nao_realizado = valor_posicao_atual - valor_investido
    
    lucro_total = lucro_realizado + lucro_nao_realizado
    st.metric("Lucro/Prejuizo", f"${lucro_total:,.2f}", "No periodo selecionado")

with col4:
    variacao_pct = ((saldo_total - saldo_inicial) / saldo_inicial * 100) if saldo_inicial > 0 else 0
    st.metric("Variacao (%)", f"{variacao_pct:.1f}%", "Variacao em relacao ao periodo...")

col_status1, col_status2, col_status3 = st.columns([2, 1, 1])
with col_status1:
    st.markdown("")
with col_status2:
    status = "OPERANDO" if st.session_state['bot_running'] else "PARADO"
    st.markdown(f"**{status}**")
with col_status3:
    # placeholder will be updated by the timer loop below
    if 'timer_header_ph' not in st.session_state:
        st.session_state['timer_header_ph'] = st.empty()
    timer_header_ph = st.session_state['timer_header_ph']
    # initialize display
    if st.session_state.bot_data.get('inicio_operacao'):
        tempo_operacao = now_brazil() - st.session_state.bot_data['inicio_operacao']
        tempo_str = str(tempo_operacao).split('.')[0]
    else:
        tempo_str = "00:00:00"
    timer_header_ph.markdown(f"**Tempo: {tempo_str}**")

st.divider()

col_ia_title, col_ia_btn = st.columns([0.85, 0.15])
with col_ia_title:
    st.markdown("### Visao da IA - Analise Tecnica")
with col_ia_btn:
    if st.button("Interpretar", use_container_width=True):
        if not st.session_state.get('bot_running', False):
            st.session_state['bot_running'] = True
            st.session_state.bot_data['inicio_operacao'] = now_brazil()
        st.info("Legenda: Linha Branca=Preco, Seta Verde=Compra, Seta Vermelha=Venda")

st.markdown("Aguardando dados do mercado...")

st.divider()

st.markdown("### Grafico")
col_viz, col_dropdown = st.columns([0.8, 0.2])
with col_dropdown:
    viz_type = st.selectbox("Visualizacao", ["Preco"], label_visibility="collapsed")

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
            fillcolor='rgba(255,99,132,0.2)',
            name='Preco'
        ))
        fig.update_layout(
            title=None,
            xaxis_rangeslider_visible=False,
            height=350,
            template='plotly_dark',
            uirevision='main-chart',
            margin=dict(l=0, r=0, t=0, b=0)
        )
        # build a single subplot figure containing price, RSI and MACD
        try:
            from strategies.features import calcular_rsi, calcular_macd, calcular_bollinger_bands
            calc_df = df.copy()
            calc_df['rsi'] = calcular_rsi(calc_df)
            calc_df['macd'], calc_df['macd_signal'], calc_df['macd_hist'] = calcular_macd(calc_df)
            calc_df['bb_upper'], calc_df['bb_lower'] = calcular_bollinger_bands(calc_df)

            from plotly.subplots import make_subplots
            fig_all = make_subplots(rows=3, cols=1, shared_xaxes=True,
                                     row_heights=[0.5, 0.2, 0.3], vertical_spacing=0.02,
                                     specs=[[{}],[{}],[{}]])
            # price with bollinger
            fig_all.add_trace(go.Scatter(x=calc_df['timestamp'], y=calc_df['close'],
                                         name='Preco', line=dict(color='white', width=2)), row=1, col=1)
            fig_all.add_trace(go.Scatter(x=calc_df['timestamp'], y=calc_df['bb_upper'],
                                         name='BB Upper', line=dict(color='blue', width=1), opacity=0.5), row=1, col=1)
            fig_all.add_trace(go.Scatter(x=calc_df['timestamp'], y=calc_df['bb_lower'],
                                         name='BB Lower', line=dict(color='blue', width=1), opacity=0.5), row=1, col=1)
            # RSI
            fig_all.add_trace(go.Scatter(x=calc_df['timestamp'], y=calc_df['rsi'],
                                         name='RSI', line=dict(color='orange')), row=2, col=1)
            fig_all.add_hline(y=70, line=dict(dash='dash', color='red'), row=2, col=1)
            fig_all.add_hline(y=30, line=dict(dash='dash', color='green'), row=2, col=1)
            # MACD
            fig_all.add_trace(go.Bar(x=calc_df['timestamp'], y=calc_df['macd_hist'],
                                      name='MACD Hist', marker_color='grey'), row=3, col=1)
            fig_all.add_trace(go.Scatter(x=calc_df['timestamp'], y=calc_df['macd'],
                                         name='MACD', line=dict(color='cyan')), row=3, col=1)
            fig_all.add_trace(go.Scatter(x=calc_df['timestamp'], y=calc_df['macd_signal'],
                                         name='Signal', line=dict(color='magenta')), row=3, col=1)

            fig_all.update_layout(height=800, template='plotly_dark', showlegend=False,
                                  xaxis_rangeslider_visible=False)
            st.plotly_chart(fig_all, use_container_width=True, key='combined_chart')
        except Exception as e:
            print(f"Erro ao desenhar indicadores: {e}")

st.divider()

col_monitor, col_historico = st.columns(2)

with col_monitor:
    st.markdown("### Monitoramento")
    if st.session_state.bot_data.get('posicao_aberta'):
        st.markdown(f"**Par:** {symbol}")
        st.markdown(f"**Atualizacao:** {format_time(now_brazil())}")
        st.markdown(f"**Proxima em:** 4s")
    else:
        st.markdown("**Par:** -")
        st.markdown(f"**Atualizacao:** {format_time(now_brazil())}")
        st.markdown("**Proxima em:** -")

    # Debug: mostrar contagem de eventos WebSocket e Aoltimo dado recebido
    try:
        eventos = st.session_state.bot_data.get('eventos_ws', {})
        st.markdown("**Eventos WS (contagem por par):**")
        st.write(eventos)

        ultimo_df = st.session_state.bot_data['dados_mercado'].get(symbol, pd.DataFrame())
        if not ultimo_df.empty:
            st.markdown("**Ultimo dado recebido:**")
            ultimo = ultimo_df.tail(1).iloc[0].to_dict()
            st.write(ultimo)
    except Exception as e:
        st.write(f"Erro ao mostrar debug WS: {e}")

with col_historico:
    st.markdown("### Historico")
    if st.session_state.bot_data.get('trades'):
        st.markdown("**Nenhum trade executado**")
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
    symbols,
    default=[symbols[0]]
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
        parar_conexao()
        st.session_state['ws_iniciado'] = False

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
            print(f"Erro ao ler arquivo temporario: {e}")

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
                    'timestamp': pd.to_datetime(b[0], unit='ms').tz_localize('UTC').tz_convert(BRAZIL_TZ).strftime('%Y-%m-%d %H:%M:%S'),
                    'open': float(b[1]),
                    'high': float(b[2]),
                    'low': float(b[3]),
                    'close': float(b[4]),
                    'volume': float(b[5]),
                    'timeframe': timeframe
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
