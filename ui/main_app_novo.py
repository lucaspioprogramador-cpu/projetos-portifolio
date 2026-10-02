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
from db.database import registrar_candle

# global websocket manager to persist across reruns
_ws_manager = None

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

# Configurações iniciais
st.set_page_config(page_title="Trading Bot Dashboard", layout="wide")
st.title("?? Trading Bot Dashboard")

# Configuração do fuso horário do Brasil
BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')

# Sidebar com configurações - NOVO LAYOUT
with st.sidebar:
    st.title("?? Credenciais")
    
    # Funções para salvar/carregar credenciais
    def salvar_credenciais(api_key, api_secret):
        with open("binance_api.json", "w", encoding="utf-8") as f:
            json.dump({"api_key": api_key, "api_secret": api_secret}, f)

    def carregar_credenciais():
        if os.path.exists("binance_api.json"):
            with open("binance_api.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("api_key", ""), data.get("api_secret", "")
        return "", ""

    # Carregar credenciais se existirem
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

    # Inputs de credenciais
    api_key = st.text_input("API Key Binance", value=st.session_state.get('api_key', ''), type="password", placeholder="Intra sua API Key")
    api_secret = st.text_input("API Secret Binance", value=st.session_state.get('api_secret', ''), type="password", placeholder="Intra seu API Secret")

    # Botões para salvar/carregar
    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button("?? Salvar", key="save_creds", use_container_width=True):
            salvar_credenciais(api_key, api_secret)
            st.session_state['api_key'] = api_key
            st.session_state['api_secret'] = api_secret
            st.success("Credenciais salvas!")
    with col_cancel:
        if st.button("? Cancelar", key="cancel_creds", use_container_width=True):
            pass

    # Feedback visual das credenciais
    if api_key and api_secret:
        if BINANCE_API_KEY and BINANCE_API_SECRET:
            st.success("? Credenciais do arquivo .env")
        else:
            st.success("? Credenciais salvas localmente")
    else:
        st.warning("?? Credenciais não configuradas")
    
    st.divider()
    
    # Parâmetros de Operação
    st.subheader("?? Parâmetros de Operação")
    
    # Par de Negociação
    st.write("**Par de Negociação**")
    symbol = st.selectbox("", [s.replace("/", "") for s in symbols], label_visibility="collapsed")
    symbol = symbol.replace("USDT", "/USDT")
    if symbol not in symbols:
        st.error("Par de negociação inválido!")
    
    # Timeframe
    st.write("**Timeframe**")
    timeframe = st.selectbox("", ["1m", "5m", "15m", "30m", "1h", "4h"], label_visibility="collapsed")
    
    # Saldo Inicial
    st.write("**Saldo Inicial (USDT)**")
    saldo_inicial = st.number_input("", min_value=100, value=1000, label_visibility="collapsed")
    
    # Risco por Trade
    st.write("**Risco por Trade (%)**")
    risco_por_trade_display = st.slider("", 0.1, 5.0, 1.0, label_visibility="collapsed")
    risco_por_trade = risco_por_trade_display / 100
    st.caption(f"{risco_por_trade_display/5}")
    
    # Stop Loss
    st.write("**Stop Loss (%)**")
    stop_loss_display = st.slider("", 0.1, 10.0, 2.0, label_visibility="collapsed", key="sl")
    stop_loss = stop_loss_display / 100
    st.caption(f"2/10")
    
    # Take Profit
    st.write("**Take Profit (%)**")
    take_profit_display = st.slider("", 0.1, 10.0, 3.0, label_visibility="collapsed", key="tp")
    take_profit = take_profit_display / 100
    st.caption(f"3/15")
    
    st.divider()
    
    # Configurações avançadas
    with st.expander("?? Configurações Avançadas"):
        usar_simulacao = st.checkbox("Usar Simulação Realista", value=True, 
                                     help="Simula slippage, taxas e execução parcial")
        usar_estrategia_melhorada = st.checkbox("Usar Estratégia Melhorada (IA)", value=True,
                                                help="Usa estratégia avançada com múltiplos indicadores")
        mostrar_detalhes_execucao = st.checkbox("Mostrar Detalhes de Execução", value=True,
                                                help="Mostra slippage, taxas e outros detalhes")
    
    # Salvar configurações no session_state
    st.session_state['usar_simulacao'] = usar_simulacao
    st.session_state['usar_estrategia_melhorada'] = usar_estrategia_melhorada
    st.session_state['mostrar_detalhes_execucao'] = mostrar_detalhes_execucao
    
    st.divider()
    
    # Controles
    col_start, col_stop = st.columns(2)
    with col_start:
        if st.button("?? Iniciar Bot", key="start", use_container_width=True):
            st.session_state['bot_running'] = True
            # record start time immediately for display
            st.session_state.bot_data['inicio_operacao'] = now_brazil()
            st.rerun()
    with col_stop:
        if st.button("?? Parar Bot", key="stop", use_container_width=True):
            st.session_state['bot_running'] = False
            st.rerun()

# Inicialização do estado da sessão
if 'bot_running' not in st.session_state:
    st.session_state['bot_running'] = False


def ensure_bot_state():
    """Garante que o dicionário bot_data exista e tenha todas as chaves padrão."""
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

# --- Funções principais ---
def now_brazil():
    return datetime.now(BRAZIL_TZ)

def format_time(dt):
    return dt.strftime("%d/%m/%Y %H:%M:%S")

def calcular_posicao(saldo, preco, risco, stop_pct):
    return (saldo * risco) / (preco * stop_pct)

def executar_ordem(tipo, preco, quantidade, usar_simulacao=None):
    """
    Executa uma ordem com simulação realista de execução.
    """
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
    """Atualiza o DataFrame de mercado para o símbolo informado"""
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
    global _ws_manager
    _api_key = st.session_state.get('api_key', '')
    _api_secret = st.session_state.get('api_secret', '')
    
    # if already created earlier, just return success
    if _ws_manager is not None:
        return True
    
    if _api_key and _api_secret:
        try:
            print(f"[DEBUG] Iniciando conexão com Binance para pares: {selected_symbols}")
            client = Client(_api_key, _api_secret)
            twm = ThreadedWebsocketManager(api_key=_api_key, api_secret=_api_secret)
            twm.start()
            print("[DEBUG] ThreadedWebsocketManager iniciado.")
            
            def handle_socket_message(msg):
                print(f"[DEBUG] Mensagem recebida no WebSocket: {msg}")
                if msg['e'] == 'kline':
                    kline = msg['k']
                    symbol_ws = msg['s'] if 's' in msg else symbol.replace("/", "")
                    symbol_fmt = symbol_ws[:-4] + "/USDT" if symbol_ws.endswith("USDT") else symbol_ws
                    novo_dado = {
                        'timestamp': pd.to_datetime(kline['t'], unit='ms').tz_localize('UTC').tz_convert(BRAZIL_TZ).strftime('%Y-%m-%d %H:%M:%S'),
                        'open': float(kline['o']),
                        'high': float(kline['h']),
                        'low': float(kline['l']),
                        'close': float(kline['c']),
                        'volume': float(kline['v']),
                        'timeframe': timeframe
                    }
                    # persist candle to database
                    try:
                        registrar_candle(symbol_ws, novo_dado['timestamp'], novo_dado['open'], novo_dado['high'], novo_dado['low'], novo_dado['close'], novo_dado['volume'], novo_dado['timeframe'])
                    except Exception as _:
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
                        print(f"[DEBUG] Erro ao salvar arquivo temporário: {e}")
            
            for symb in selected_symbols:
                symbol_socket = symb.replace("/", "")
                print(f"[DEBUG] Iniciando socket para: {symbol_socket}, timeframe: {timeframe}")
                twm.start_kline_socket(
                    symbol=symbol_socket,
                    interval=timeframe,
                    callback=handle_socket_message
                )
            # keep instance globally so reruns don't recreate it
            _ws_manager = twm
            st.session_state.bot_data['inicio_operacao'] = now_brazil()
            print("[DEBUG] Todos os sockets iniciados.")
            return True
        except Exception as e:
            print(f"[DEBUG] Erro na conexão: {str(e)}")
            st.error(f"Erro na conexão: {str(e)}")
            return False
    return False

def parar_conexao():
    global _ws_manager
    if _ws_manager:
        try:
            _ws_manager.stop()
        except Exception:
            pass
        _ws_manager = None

def calcular_macd(df, fast=12, slow=26, signal=9):
    df['EMA_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
    df['EMA_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
    df['MACD'] = df['EMA_fast'] - df['EMA_slow']
    df['MACD_signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']
    return df

def calcular_bollinger(df, window=20, num_std=2):
    df['BB_MA'] = df['close'].rolling(window=window).mean()
    df['BB_STD'] = df['close'].rolling(window=window).std()
    df['BB_upper'] = df['BB_MA'] + num_std * df['BB_STD']
    df['BB_lower'] = df['BB_MA'] - num_std * df['BB_STD']
    return df

def processar_sinais(symbol_proc=None, usar_estrategia_melhorada=None):
    """Processa sinais usando estratégia melhorada de IA."""
    if usar_estrategia_melhorada is None:
        usar_estrategia_melhorada = st.session_state.get('usar_estrategia_melhorada', True)
    symbol_proc = symbol_proc or symbol
    df_dict = st.session_state.bot_data['dados_mercado']
    if symbol_proc not in df_dict or df_dict[symbol_proc].empty:
        return
    df = df_dict[symbol_proc].copy()
    preco_atual = df.iloc[-1]['close']
    
    # Verificar stop loss e take profit primeiro
    if st.session_state.bot_data['posicao_aberta']:
        preco_compra = st.session_state.bot_data['preco_compra']
        if preco_atual <= preco_compra * (1 - stop_loss):
            executar_ordem('VENDA', preco_atual, st.session_state.bot_data['quantidade'])
            st.toast(f"?? STOP LOSS ATIVADO: {preco_atual:.2f}", icon="??")
            return
        elif preco_atual >= preco_compra * (1 + take_profit * 1.5):
            executar_ordem('VENDA', preco_atual, st.session_state.bot_data['quantidade'])
            st.toast(f"?? TAKE PROFIT ATIVADO: {preco_atual:.2f}", icon="??")
            return
    
    # Usar estratégia melhorada de IA
    if usar_estrategia_melhorada:
        try:
            from strategies.ai_strategy_melhorada import executar_estrategia_ai_melhorada
            
            config = {
                'min_confidence_buy': 0.60,
                'min_confidence_sell': 0.50,
                'min_rsi_buy': 30,
                'max_rsi_buy': 75,
                'min_rsi_sell': 40,
                'max_rsi_sell': 80,
                'min_adx': 20,
                'min_volume_ratio': 1.0,
                'stop_loss_pct': stop_loss,
                'take_profit_pct': take_profit
            }
            
            resultado = executar_estrategia_ai_melhorada(
                df=df,
                posicao_aberta=st.session_state.bot_data['posicao_aberta'],
                preco_compra=st.session_state.bot_data.get('preco_compra'),
                config=config
            )
            
            sinal = resultado['sinal']
            confianca = resultado['confianca']
            razao = resultado['razao']
            
            if sinal == 'buy' and not st.session_state.bot_data['posicao_aberta']:
                quantidade = calcular_posicao(
                    st.session_state.bot_data['saldo_usdt'],
                    preco_atual,
                    risco_por_trade,
                    stop_loss
                )
                if quantidade > 0:
                    trade = executar_ordem('COMPRA', preco_atual, quantidade)
                    st.toast(
                        f"?? COMPRA: {preco_atual:.2f} | Confiança: {confianca:.1%} | {razao}",
                        icon="?"
                    )
            
            elif sinal == 'sell' and st.session_state.bot_data['posicao_aberta']:
                trade = executar_ordem('VENDA', preco_atual, st.session_state.bot_data['quantidade'])
                st.toast(
                    f"?? VENDA: {preco_atual:.2f} | Confiança: {confianca:.1%} | {razao}",
                    icon="??"
                )
            
            st.session_state.bot_data['ultimo_sinal'] = {
                'sinal': sinal,
                'confianca': confianca,
                'razao': razao,
                'timestamp': now_brazil()
            }
            
        except Exception as e:
            st.warning(f"Erro na estratégia melhorada: {e}. Usando estratégia simples.")
            usar_estrategia_melhorada = False
    
    # Fallback para estratégia simples
    if not usar_estrategia_melhorada:
        df['MA_5'] = df['close'].rolling(window=5).mean()
        df['MA_20'] = df['close'].rolling(window=20).mean()
        
        if not st.session_state.bot_data['posicao_aberta'] and df['MA_5'].iloc[-1] > df['MA_20'].iloc[-1]:
            quantidade = calcular_posicao(
                st.session_state.bot_data['saldo_usdt'],
                preco_atual,
                risco_por_trade,
                stop_loss
            )
            executar_ordem('COMPRA', preco_atual, quantidade)
            st.toast(f"?? COMPRA EXECUTADA: {preco_atual:.2f}", icon="?")
        elif st.session_state.bot_data['posicao_aberta'] and df['MA_5'].iloc[-1] < df['MA_20'].iloc[-1]:
            executar_ordem('VENDA', preco_atual, st.session_state.bot_data['quantidade'])
            st.toast(f"?? VENDA EXECUTADA: {preco_atual:.2f}", icon="??")

# --- NOVO LAYOUT PRINCIPAL ---
# Cards de Status no Topo
st.markdown("## ?? Trading Bot Dashboard")

# Cards de métricas
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
    st.metric("?? Saldo USDT", f"${saldo_usdt:,.2f}", "Current balance")

with col2:
    st.metric("?? Saldo Total", f"${saldo_total:,.2f}", "Position + Balance")
    if st.session_state.bot_data.get('posicao_aberta'):
        st.caption(f"Posição: ${valor_posicao_atual:,.2f}")

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
    variacao_pct = (lucro_total / saldo_inicial * 100) if saldo_inicial > 0 else 0
    st.metric("?? Lucro/Prejuízo", f"${lucro_total:,.2f}", f"{variacao_pct:.2f}%")

with col4:
    # status and live timer
    status = "?? OPERANDO" if st.session_state['bot_running'] else "?? PARADO"
    if st.session_state.bot_data.get('inicio_operacao'):
        tempo_operacao = now_brazil() - st.session_state.bot_data['inicio_operacao']
        tempo_str = str(tempo_operacao).split('.')[0]
    else:
        tempo_str = "00:00:00"
    # prepare placeholder for timer if not present
    if 'timer_header_ph' not in st.session_state:
        st.session_state['timer_header_ph'] = st.empty()
    timer_header_ph = st.session_state['timer_header_ph']
    timer_header_ph.markdown(f"**Tempo: {tempo_str}**")
    st.metric("?? Status", status, tempo_str)

st.divider()

# Seção de IA - Análise Técnica
col_ia, col_btn = st.columns([0.95, 0.05])

with col_ia:
    st.subheader("?? Visão da IA - Análise Técnica")
    st.caption("Aguardando dados do mercado...")

with col_btn:
    if st.button("?? Interpretar", use_container_width=True):
        # behave like starting the bot so user sees activity
        if not st.session_state.get('bot_running', False):
            st.session_state['bot_running'] = True
            st.session_state.bot_data['inicio_operacao'] = now_brazil()
        st.info("""
        **Legenda do Gráfico:**
        - **Linha Branca:** Preço de fechamento
        - **Linha Azul (MA 5):** Média móvel de 5 períodos
        - **Linha Laranja (MA 20):** Média móvel de 20 períodos
        - **Seta Verde:** Sinal de compra
        - **Seta Vermelha:** Sinal de venda
        """)

# Gráfico principal de preços
main_df = st.session_state.bot_data['dados_mercado'].get(symbol, pd.DataFrame())
if not main_df.empty:
    df = main_df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.dropna(subset=['timestamp', 'close'])
    if not df.empty:
        # basic price plot removed; combined indicators will be drawn below
        # build combined indicator subplot
        try:
            from strategies.features import calcular_rsi, calcular_macd, calcular_bollinger_bands
            tmp = df.copy()
            tmp['rsi'] = calcular_rsi(tmp)
            tmp['macd'], tmp['macd_signal'], tmp['macd_hist'] = calcular_macd(tmp)
            tmp['bb_upper'], tmp['bb_lower'] = calcular_bollinger_bands(tmp)
            from plotly.subplots import make_subplots
            fig_all = make_subplots(rows=3, cols=1, shared_xaxes=True,
                                     row_heights=[0.5,0.2,0.3], vertical_spacing=0.02)
            fig_all.add_trace(go.Scatter(x=tmp['timestamp'], y=tmp['close'], name='Preco', line=dict(color='white', width=2)), row=1, col=1)
            fig_all.add_trace(go.Scatter(x=tmp['timestamp'], y=tmp['bb_upper'], name='BB U', line=dict(color='blue', width=1), opacity=0.5), row=1, col=1)
            fig_all.add_trace(go.Scatter(x=tmp['timestamp'], y=tmp['bb_lower'], name='BB L', line=dict(color='blue', width=1), opacity=0.5), row=1, col=1)
            fig_all.add_trace(go.Scatter(x=tmp['timestamp'], y=tmp['rsi'], name='RSI', line=dict(color='orange')), row=2, col=1)
            fig_all.add_hline(y=70, line=dict(dash='dash',color='red'), row=2, col=1)
            fig_all.add_hline(y=30, line=dict(dash='dash',color='green'), row=2, col=1)
            fig_all.add_trace(go.Bar(x=tmp['timestamp'], y=tmp['macd_hist'], name='Hist', marker_color='grey'), row=3, col=1)
            fig_all.add_trace(go.Scatter(x=tmp['timestamp'], y=tmp['macd'], name='MACD', line=dict(color='cyan')), row=3, col=1)
            fig_all.add_trace(go.Scatter(x=tmp['timestamp'], y=tmp['macd_signal'], name='Signal', line=dict(color='magenta')), row=3, col=1)
            fig_all.update_layout(height=800, template='plotly_dark', showlegend=False, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig_all, use_container_width=True, key='combined_chart')
        except Exception as e:
            print(f"Erro ao desenhar indicadores: {e}")

st.divider()

# Seções inferiores: Monitoramento e Histórico
col_monitor, col_historico = st.columns(2)

with col_monitor:
    st.subheader("?? Monitoramento")
    if st.session_state.bot_data.get('posicao_aberta'):
        st.info(f"?? Par: **{symbol}** | Quantidade: {st.session_state.bot_data.get('quantidade', 0):.6f}")
        st.info(f"?? Preço de Compra: **${st.session_state.bot_data.get('preco_compra', 0):.2f}**")
        if not main_df.empty:
            preco_atual = main_df.iloc[-1]['close']
            variacao = ((preco_atual / st.session_state.bot_data.get('preco_compra', 1)) - 1) * 100
            st.info(f"?? Preço Atual: **${preco_atual:.2f}** ({variacao:+.2f}%)")
    else:
        st.info("Sem posição aberta no momento")
    
    status_update_placeholder = st.empty()
    status_update_placeholder.caption(f"?? Última atualização: {format_time(now_brazil())}")

with col_historico:
    st.subheader("?? Histórico")
    if st.session_state.bot_data.get('trades'):
        df_trades = pd.DataFrame(st.session_state.bot_data['trades'])
        df_vendas = df_trades[df_trades['tipo'] == 'VENDA']
        
        if not df_vendas.empty and 'lucro' in df_vendas.columns:
            col_total, col_sucesso = st.columns(2)
            with col_total:
                st.metric("?? Total de Trades", len(df_vendas))
            with col_sucesso:
                trades_lucrativos = len(df_vendas[df_vendas['lucro'] > 0])
                st.metric("? Trades Lucrativos", f"{trades_lucrativos}/{len(df_vendas)}")
        else:
            st.info("Nenhum trade concluído ainda")
    else:
        st.info("Nenhum trade executado ainda")

st.divider()

# Seleção de múltiplos pares
selected_symbols = st.multiselect(
    "?? Selecione os pares para monitorar em tempo real:",
    symbols,
    default=[symbols[0]]
)

# Controle de conexão
conexao_status = st.empty()
if st.session_state['bot_running']:
    if not st.session_state.get('ws_iniciado', False):
        if iniciar_conexao(selected_symbols):
            conexao_status.success("? Conexão com Binance estabelecida!")
            st.session_state['ws_iniciado'] = True
        else:
            conexao_status.error("? Falha ao conectar com Binance.")
            st.session_state['bot_running'] = False
            st.session_state['ws_iniciado'] = False
else:
    if st.session_state.get('ws_iniciado', False):
        parar_conexao()
        st.session_state['ws_iniciado'] = False
    conexao_status.info("?? Bot parado.")

# Atualização automática
if 'ultima_atualizacao_ui' not in st.session_state:
    st.session_state['ultima_atualizacao_ui'] = now_brazil()

status_update_placeholder = st.empty()

dados_novos = False
# placeholder to show toast notifications
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
                        # show a brief toast/notification for this candle
                        try:
                            notify_placeholder.toast(f"Candle {symbol_socket} recebido", icon="🔔")
                        except Exception:
                            notify_placeholder.info(f"Candle {symbol_socket} recebido")
                # clear file after reading
                with open(tmpfile, 'w', encoding='utf-8') as f:
                    json.dump([], f)
        except Exception as e:
            print(f"[DEBUG] Erro ao ler arquivo temporário: {e}")

# if nothing came through websocket, try REST to keep UI moving
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
    # display a live timer for the next minute before fetching again
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
