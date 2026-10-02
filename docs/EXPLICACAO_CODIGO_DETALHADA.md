# ?? Explicação Detalhada do Código - L-Trade-AI

## ?? Índice
1. [main_app.py - Estrutura Geral](#main_app)
2. [Importações e Configurações](#importacoes)
3. [Gerenciamento de Estado (Session State)](#session-state)
4. [Funções Principais](#funcoes)
5. [Fluxo de Execução](#fluxo)
6. [viz_app.py - Backtesting](#viz_app)

---

## main_app.py - Estrutura Geral {#main_app}

### ?? O arquivo tem ~1015 linhas e é organizado assim:

```
main_app.py
??? IMPORTS e CONFIGURAÇÕES (linhas 1-150)
??? INICIALIZAÇÃO DE ESTADO (linhas 151-300)
??? DEFINIÇÃO DE FUNÇÕES (linhas 301-700)
??? INTERFACE PRINCIPAL (linhas 701-900)
??? GRÁFICOS E VISUALIZAÇÕES (linhas 901-1015)
```

---

## Importações e Configurações {#importacoes}

### **Bloco 1: Importações**
```python
import streamlit as st                    # Framework web
import pandas as pd                       # Manipulação de dados
import numpy as np                        # Cálculos numéricos
import time                               # Controle de tempo
from datetime import datetime, timedelta  # Data/hora
import pytz                               # Fusos horários
import plotly.graph_objects as go         # Gráficos interativos
from binance.client import Client         # Cliente REST Binance
from binance import ThreadedWebsocketManager  # WebSocket Binance
import threading                          # Multi-threading
import os                                 # Sistema de arquivos
import json                               # JSON parsing
import tempfile                           # Arquivos temporários
from config.settings import BINANCE_API_KEY, BINANCE_API_SECRET  # Credenciais
```

**Para quê cada um serve:**
- `streamlit`: Renderiza a interface web
- `pandas/numpy`: Processamento de dados financeiros
- `plotly`: Gráficos em tempo real
- `binance`: Integração com a exchange
- `threading`: Receber dados WebSocket sem travar UI
- `tempfile`: Armazenar dados sem corromper JSON

---

### **Bloco 2: Lista de Pares**
```python
symbols = [
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    # ... mais 8 pares
]
```

**O que é:** Criptomoedas suportadas. Formato `XXX/USDT` é convertido para `XXXUSDT` ao comunicar com Binance.

---

### **Bloco 3: Configuração Streamlit**
```python
st.set_page_config(page_title="Bot Binance - Tempo Real", layout="wide")
st.title("?? Bot Binance - Monitoramento em Tempo Real")

BRAZIL_TZ = pytz.timezone('America/Sao_Paulo')
```

**Explicação:**
- `set_page_config()`: Configura a aba do navegador e layout (wide = 100% de largura)
- `title()`: Título principal da página
- `BRAZIL_TZ`: Define fuso horário para sincronizar com horário de Brasília

---

## Gerenciamento de Estado (Session State) {#session-state}

### **O que é Session State?**

Streamlit **reconstrói toda a página a cada interação**. Sem session_state, perderíamos dados. Ele funciona como um dicionário persistente:

```python
# ? ERRADO - Reseta a cada rerun
saldo = 1000
saldo += 100  # Perde valor

# ? CORRETO - Persiste entre reruns
st.session_state['saldo'] = 1000
st.session_state['saldo'] += 100  # Mantém valor
```

---

### **Função: ensure_bot_state()**

```python
def ensure_bot_state():
    """Garante que o dicionário bot_data exista e tenha todas as chaves padrão."""
    defaults = {
        'saldo_usdt': saldo_inicial,           # Saldo em USDT
        'saldo_inicial': saldo_inicial,        # Referência inicial
        'posicao_aberta': False,               # Tem criptomoeda em posse?
        'preco_compra': None,                  # Preço de entrada
        'quantidade': 0,                       # Qtd de criptomoeda
        'valor_investido': 0,                  # $ investido (com taxas)
        'trades': [],                          # Histórico de trades
        'inicio_operacao': None,               # Quando começou
        'ultimo_sinal': None,                  # Último sinal gerado
        'dados_mercado': {},                   # DataFrames de preço
        'conexao_websocket': None,             # Conexão Binance
        'client': None,                        # Cliente REST
        'ultima_atualizacao': None,            # Timestamp
        'eventos_ws': {}                       # Contador de eventos
    }

    if 'bot_data' not in st.session_state or not isinstance(st.session_state.get('bot_data'), dict):
        st.session_state['bot_data'] = defaults
        return

    # Preenche chaves faltantes
    for key, value in defaults.items():
        st.session_state.bot_data.setdefault(key, value)

    # Sincroniza se usuário mudou saldo inicial no sidebar
    if st.session_state.bot_data.get('saldo_inicial') != saldo_inicial:
        st.session_state.bot_data['saldo_inicial'] = saldo_inicial
        if not st.session_state.bot_data.get('posicao_aberta', False):
            st.session_state.bot_data['saldo_usdt'] = saldo_inicial
```

**Por que é importante:**
1. Garante que sempre existem todas as chaves necessárias
2. Evita erros `KeyError`
3. Permite resetar o saldo sem perder a sessão
4. Sincroniza mudanças do usuario no sidebar

---

## Funções Principais {#funcoes}

### **1. Função: now_brazil()**
```python
def now_brazil():
    return datetime.now(BRAZIL_TZ)
```

**Uso:** Obtém hora atual do Brasil (sincroniza com Binance em São Paulo/UTC-3)

---

### **2. Função: format_time(dt)**
```python
def format_time(dt):
    return dt.strftime("%d/%m/%Y %H:%M:%S")
```

**Uso:** Converte datetime em string formatada
```python
# Input: 2026-02-25 14:30:45 (datetime)
# Output: "25/02/2026 14:30:45" (string)
```

---

### **3. Função: calcular_posicao(saldo, preco, risco, stop_pct)**

```python
def calcular_posicao(saldo, preco, risco, stop_loss):
    return (saldo * risco) / (preco * stop_loss)
```

**Fórmula de Posição Sizing:**

$$
\text{Quantidade} = \frac{\text{Saldo} \times \text{Risco \%}}{\text{Preço} \times \text{Stop Loss \%}}
$$

**Exemplo prático:**
```
Saldo = 1000 USDT
Preço = 42500 USDT/BTC
Risco = 1% (0.01)
Stop Loss = 2% (0.02)

Quantidade = (1000 × 0.01) / (42500 × 0.02)
           = 10 / 850
           = 0.0118 BTC
```

**Interpretação:** "Compro 0.0118 BTC, de forma que se cair 2% perco exatamente 10 USDT"

---

### **4. Função: executar_ordem(tipo, preco, quantidade, usar_simulacao)**

Esta é a **função mais importante** do bot. Executa compras/vendas com simulação realista.

```python
def executar_ordem(tipo, preco, quantidade, usar_simulacao=None):
    """
    Executa uma ordem com simulação realista de execução.
    
    Args:
        tipo: 'COMPRA' ou 'VENDA'
        preco: Preço atual do mercado
        quantidade: Quantidade a negociar
        usar_simulacao: Se True, usa slippage/taxas. Se None, usa session_state
    """
```

#### **Passo 1: Determinar simulação**
```python
if usar_simulacao is None:
    usar_simulacao = st.session_state.get('usar_simulacao', True)
```

#### **Passo 2: Calcular volatilidade**
```python
volatilidade = None
volume_24h = None
if symbol in st.session_state.bot_data['dados_mercado']:
    df = st.session_state.bot_data['dados_mercado'][symbol]
    if len(df) >= 20:
        # Volatilidade = desvio padrão das mudanças de preço
        volatilidade = df['close'].pct_change().std()
        # Volume em USDT
        volume_24h = df['volume'].sum() * preco
```

#### **Passo 3: Simular ou executar simples**
```python
if usar_simulacao:
    # Chama função que simula slippage, taxas, execução parcial
    execucao = executar_ordem_simulada(
        lado=lado,  # 'buy' ou 'sell'
        quantidade=quantidade,
        preco_atual=preco,
        symbol=symbol,
        volume_24h=volume_24h,  # Affects slippage
        volatilidade=volatilidade  # Affects slippage
    )
    
    preco_exec = execucao['preco_execucao']  # Preço real
    quantidade_exec = execucao['quantidade_executada']
    taxas = execucao['taxas']
    slippage_pct = execucao['slippage_pct']
    valor_total = execucao['valor_total']
    valor_liquido = execucao['valor_liquido']
else:
    # Sem simulação
    preco_exec = preco
    quantidade_exec = quantidade
    taxas = preco * quantidade * 0.001  # Taxa fixa 0.1%
    slippage_pct = 0.0
    valor_total = preco * quantidade
    valor_liquido = valor_total - taxas
```

#### **Passo 4: Criar registro de trade**
```python
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
```

#### **Passo 5: Processar COMPRA**
```python
if tipo == 'COMPRA':
    # Subtrai do saldo USDT
    st.session_state.bot_data['saldo_usdt'] -= valor_liquido
    
    # Marca posição como aberta
    st.session_state.bot_data['posicao_aberta'] = True
    st.session_state.bot_data['preco_compra'] = preco_exec
    st.session_state.bot_data['quantidade'] = quantidade_exec
    st.session_state.bot_data['valor_investido'] = valor_liquido  # Com taxas
```

**Exemplo:**
```
Saldo USDT: 1000.00
Compra 0.0235 BTC a 42500 USDT

Valor = 42500 × 0.0235 = 998.75 USDT
Taxa = 998.75 × 0.001 = 0.99875 USDT
Valor Líquido = 998.75 - 0.99875 = 997.75 USDT

Novo Saldo USDT: 1000.00 - 997.75 = 2.25 USDT
```

#### **Passo 6: Processar VENDA**
```python
else:  # VENDA
    # Adiciona ao saldo USDT
    st.session_state.bot_data['saldo_usdt'] += valor_liquido
    st.session_state.bot_data['posicao_aberta'] = False
    
    # Calcula lucro do trade
    preco_compra = st.session_state.bot_data.get('preco_compra', preco_exec)
    valor_investido = st.session_state.bot_data.get('valor_investido', preco_compra * quantidade_exec)
    
    # Lucro = valor recebido - valor investido
    trade['lucro'] = valor_liquido - valor_investido
    trade['lucro_liquido'] = trade['lucro']  # Já deduzidas as taxas
    trade['retorno'] = (trade['lucro'] / valor_investido * 100) if valor_investido > 0 else 0
    
    # Resetar posição
    st.session_state.bot_data['valor_investido'] = 0
    st.session_state.bot_data['preco_compra'] = None
    st.session_state.bot_data['quantidade'] = 0
```

**Exemplo completo de round-trip:**
```
COMPRA (14:30)
?????????????
Preço: 42500 USDT
Quantidade: 0.0235 BTC
Investido: 997.75 USDT (com taxa)
Saldo após: 2.25 USDT

VENDA (14:45)
?????????????
Preço: 43000 USDT
Quantidade: 0.0235 BTC
Recebido: 1010.50 USDT (com taxa)
Saldo após: 1012.75 USDT

RESULTADO
?????????
Lucro Bruto: 1010.50 - 998.75 = 11.75 USDT
Lucro Líquido: 1010.50 - 997.75 - 1.01 = 11.74 USDT (desp. taxa venda)
Retorno: (11.74 / 997.75) × 100 = 1.18%
```

---

### **5. Função: atualizar_dados_mercado(symbol, novo_dado)**

```python
def atualizar_dados_mercado(symbol, novo_dado):
    """Atualiza o DataFrame de mercado para o símbolo informado."""
    if symbol not in st.session_state.bot_data['dados_mercado']:
        # Cria novo DataFrame
        st.session_state.bot_data['dados_mercado'][symbol] = pd.DataFrame([novo_dado])
    else:
        # Concatena novo dado
        st.session_state.bot_data['dados_mercado'][symbol] = pd.concat([
            st.session_state.bot_data['dados_mercado'][symbol],
            pd.DataFrame([novo_dado])
        ]).drop_duplicates().tail(500)  # Mantém últimos 500 candles
    
    # Incrementa contador de eventos
    if 'eventos_ws' in st.session_state.bot_data:
        st.session_state.bot_data['eventos_ws'][symbol] = \
            st.session_state.bot_data['eventos_ws'].get(symbol, 0) + 1
```

**O que faz:**
1. Se é o primeiro dado do par, cria DataFrame novo
2. Se já existe, concatena o novo dado
3. Remove duplicatas
4. Mantém apenas últimos 500 candles (para não sobrecarregar memória)
5. Incrementa contador de eventos

---

### **6. Função: iniciar_conexao(selected_symbols)**

Estabelece conexão com WebSocket da Binance:

```python
def iniciar_conexao(selected_symbols):
    _api_key = st.session_state.get('api_key', '')
    _api_secret = st.session_state.get('api_secret', '')
    
    if _api_key and _api_secret:
        try:
            # Cria cliente REST
            client = Client(_api_key, _api_secret)
            
            # Cria gerenciador de WebSocket (em thread separada)
            twm = ThreadedWebsocketManager(api_key=_api_key, api_secret=_api_secret)
            twm.start()
            
            # Define callback para processar mensagens
            def handle_socket_message(msg):
                if msg['e'] == 'kline':  # Apenas eventos de candle
                    kline = msg['k']
                    symbol_ws = msg['s'] if 's' in msg else symbol.replace("/", "")
                    symbol_fmt = symbol_ws[:-4] + "/USDT"
                    
                    novo_dado = {
                        'timestamp': pd.to_datetime(kline['t'], unit='ms')\
                            .tz_localize('UTC')\
                            .tz_convert(BRAZIL_TZ)\
                            .strftime('%Y-%m-%d %H:%M:%S'),
                        'open': float(kline['o']),
                        'high': float(kline['h']),
                        'low': float(kline['l']),
                        'close': float(kline['c']),
                        'volume': float(kline['v']),
                        'timeframe': timeframe
                    }
                    
                    # Salva em arquivo temporário com lock
                    tmpfile = os.path.join(tempfile.gettempdir(), 
                                         f"tmp_ws_{symbol_ws}.json")
                    with file_write_lock:
                        # Lê dados existentes
                        if os.path.exists(tmpfile):
                            with open(tmpfile, 'r') as f:
                                dados = json.load(f)
                        else:
                            dados = []
                        
                        # Adiciona novo
                        dados.append(novo_dado)
                        
                        # Salva
                        with open(tmpfile, 'w') as f:
                            json.dump(dados, f)
            
            # Inicia socket para cada par
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
            st.error(f"Erro na conexão: {str(e)}")
            return False
    return False
```

**Fluxo:**
```
??????????????????????????????
? Credenciais válidas?       ?
??????????????????????????????
             YES
              ?
??????????????????????????????
? Cria Client REST           ?
??????????????????????????????
              ?
??????????????????????????????
? Cria ThreadedWebsocket     ?
? (inicia thread separada)   ?
??????????????????????????????
              ?
??????????????????????????????
? Define callback para cada   ?
? novo candle recebido       ?
??????????????????????????????
              ?
??????????????????????????????
? Para cada par selecionado: ?
? start_kline_socket()       ?
??????????????????????????????
              ?
??????????????????????????????
? Salva client e twm em      ?
? session_state              ?
??????????????????????????????
```

---

### **7. Função: processar_sinais(symbol_proc, usar_estrategia_melhorada)**

**A função mais complexa** - gera sinais de compra/venda:

```python
def processar_sinais(symbol_proc=None, usar_estrategia_melhorada=None):
    if usar_estrategia_melhorada is None:
        usar_estrategia_melhorada = st.session_state.get('usar_estrategia_melhorada', True)
    
    symbol_proc = symbol_proc or symbol
    df_dict = st.session_state.bot_data['dados_mercado']
    
    if symbol_proc not in df_dict or df_dict[symbol_proc].empty:
        return
    
    df = df_dict[symbol_proc].copy()
    preco_atual = df.iloc[-1]['close']
```

#### **Seção 1: Verificar Stop Loss e Take Profit**

```python
if st.session_state.bot_data['posicao_aberta']:
    preco_compra = st.session_state.bot_data['preco_compra']
    
    # Stop Loss: se preço caiu 2%
    if preco_atual <= preco_compra * (1 - stop_loss):
        executar_ordem('VENDA', preco_atual, 
                      st.session_state.bot_data['quantidade'])
        st.toast(f"?? STOP LOSS ATIVADO: {preco_atual:.2f}", icon="??")
        return
    
    # Take Profit: se lucro é 50% maior que o configurado
    # (Se configurado 3%, vende em 4.5% para deixar lucros rodarem)
    elif preco_atual >= preco_compra * (1 + take_profit * 1.5):
        executar_ordem('VENDA', preco_atual, 
                      st.session_state.bot_data['quantidade'])
        lucro_pct = (preco_atual/preco_compra - 1)*100
        st.toast(f"?? TAKE PROFIT ATIVADO: {preco_atual:.2f} (Lucro: {lucro_pct:.2f}%)", 
                icon="??")
        return
```

**Lógica:**
- Stop Loss é **obrigatório** quando preço cai além do configurado
- Take Profit é **conservador** - vende apenas com lucro 50% maior para deixar ganhos rodarem

#### **Seção 2: Estratégia Melhorada de IA**

```python
if usar_estrategia_melhorada:
    try:
        from strategies.ai_strategy_melhorada import executar_estrategia_ai_melhorada
        
        config = {
            'min_confidence_buy': 0.60,      # Compra com 60% de confiança
            'min_confidence_sell': 0.50,     # Vende com 50% de confiança
            'min_rsi_buy': 30,               # Não compra se RSI < 30 (já vendido)
            'max_rsi_buy': 75,               # Não compra se RSI > 75 (já comprado)
            'min_rsi_sell': 40,              # Não vende se RSI < 40
            'max_rsi_sell': 80,              # Vende se RSI > 80
            'min_adx': 20,                   # Só opera se tendência clara (ADX > 20)
            'min_volume_ratio': 1.0,         # Volume mínimo: 1x a média
            'stop_loss_pct': stop_loss,
            'take_profit_pct': take_profit
        }
        
        resultado = executar_estrategia_ai_melhorada(
            df=df,
            posicao_aberta=st.session_state.bot_data['posicao_aberta'],
            preco_compra=st.session_state.bot_data.get('preco_compra'),
            config=config
        )
        
        sinal = resultado['sinal']        # 'buy', 'sell', 'hold'
        confianca = resultado['confianca'] # Percentual de confiança
        razao = resultado['razao']        # String explicando o sinal
        
        # Executar COMPRA se sinal for 'buy'
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
        
        # Executar VENDA se sinal for 'sell'
        elif sinal == 'sell' and st.session_state.bot_data['posicao_aberta']:
            trade = executar_ordem('VENDA', preco_atual, 
                                  st.session_state.bot_data['quantidade'])
            st.toast(
                f"?? VENDA: {preco_atual:.2f} | Confiança: {confianca:.1%} | {razao}",
                icon="??"
            )
        
        # Armazenar sinal para visualização
        st.session_state.bot_data['ultimo_sinal'] = {
            'sinal': sinal,
            'confianca': confianca,
            'razao': razao,
            'timestamp': now_brazil()
        }
        
    except Exception as e:
        st.warning(f"Erro na estratégia melhorada: {e}. Usando estratégia simples.")
        usar_estrategia_melhorada = False
```

#### **Seção 3: Fallback para Médias Móveis Simples**

Se a estratégia de IA falhar, usa crossover de médias móveis:

```python
if not usar_estrategia_melhorada:
    df['MA_5'] = df['close'].rolling(window=5).mean()
    df['MA_20'] = df['close'].rolling(window=20).mean()
    
    # COMPRA quando MA rápida > MA lenta
    if not st.session_state.bot_data['posicao_aberta'] and \
       df['MA_5'].iloc[-1] > df['MA_20'].iloc[-1]:
        quantidade = calcular_posicao(
            st.session_state.bot_data['saldo_usdt'],
            preco_atual,
            risco_por_trade,
            stop_loss
        )
        executar_ordem('COMPRA', preco_atual, quantidade)
        st.toast(f"?? COMPRA EXECUTADA: {preco_atual:.2f}", icon="?")
    
    # VENDA quando MA rápida < MA lenta
    elif st.session_state.bot_data['posicao_aberta'] and \
         df['MA_5'].iloc[-1] < df['MA_20'].iloc[-1]:
        executar_ordem('VENDA', preco_atual, 
                      st.session_state.bot_data['quantidade'])
        st.toast(f"?? VENDA EXECUTADA: {preco_atual:.2f}", icon="??")
```

**Lógica simples:**
```
Se MA 5 > MA 20 ? Tendência ALTA ? COMPRA
Se MA 5 < MA 20 ? Tendência BAIXA ? VENDA
```

---

### **8. Funções de Cálculo de Indicadores**

#### **calcular_macd(df, fast=12, slow=26, signal=9)**

MACD = Moving Average Convergence Divergence

```python
def calcular_macd(df, fast=12, slow=26, signal=9):
    # Calcula médias exponenciais rápida e lenta
    df['EMA_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
    df['EMA_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
    
    # MACD = diferença entre elas
    df['MACD'] = df['EMA_fast'] - df['EMA_slow']
    
    # Linha de sinal = média móvel do MACD
    df['MACD_signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
    
    # Histograma = diferença entre MACD e sinal
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']
    
    return df
```

**Interpretação:**
- MACD > 0 ? Tendência ALTA
- MACD < 0 ? Tendência BAIXA
- MACD_hist > 0 ? Momentum crescente
- Cruzamento de MACD e sinal = mudança de tendência

---

#### **calcular_bollinger(df, window=20, num_std=2)**

Bollinger Bands detecta sobrecompra/sobrevenda:

```python
def calcular_bollinger(df, window=20, num_std=2):
    # Média móvel simples
    df['BB_MA'] = df['close'].rolling(window=window).mean()
    
    # Desvio padrão
    df['BB_STD'] = df['close'].rolling(window=window).std()
    
    # Bandas superior e inferior (±2 desvios)
    df['BB_upper'] = df['BB_MA'] + num_std * df['BB_STD']
    df['BB_lower'] = df['BB_MA'] - num_std * df['BB_STD']
    
    return df
```

**Interpretação:**
```
Preço toca BB superior ? Pode estar sobrecomprado (vender?)
Preço toca BB inferior ? Pode estar sobrevendido (comprar?)
```

---

## Fluxo de Execução {#fluxo}

### **Fluxo Completo quando Bot está RODANDO:**

```
??????????????????????????????????????????????????????????????
? INÍCIO DO STREAMLIT RERUN                                  ?
????????????????????????????????????????????????????????????
                 ?
        ???????????????????
        ? Renderiza       ?
        ? Sidebar         ?
        ? (configurações) ?
        ???????????????????
                 ?
        ???????????????????
        ? ensure_bot_      ?
        ? state()          ?
        ? (init dados)     ?
        ???????????????????
                 ?
        ???????????????????
        ? Bot rodando?    ?
        ???????????????????
             ?       ?
            SIM      NÃO
             ?       ?
             ?   ??????????
             ?   ? Para   ?
             ?   ? conexão?
             ?   ??????????
             ?
        ?????????????????????????
        ? WebSocket já          ?
        ? iniciado?             ?
        ?????????????????????????
             ?              ?
            NÃO             SIM
             ?              ?
   ????????????????   ????????????????
   ? Inicia       ?   ? Info: já     ?
   ? conexão      ?   ? iniciado     ?
   ????????????????   ???????????????
             ?
   ??????????????????????????????
   ? Renderiza dashboard         ?
   ? (métricas, gráficos)        ?
   ??????????????????????????????
             ?
   ??????????????????????????????
   ? Lê dados WebSocket do       ?
   ? arquivo temporário          ?
   ??????????????????????????????
             ?
   ??????????????????????????????
   ? Atualiza DataFrame          ?
   ? atualizar_dados_mercado()   ?
   ??????????????????????????????
             ?
   ??????????????????????????????
   ? Processa sinais             ?
   ? processar_sinais()          ?
   ? • Stop Loss                 ?
   ? • Take Profit               ?
   ? • Estratégia IA/MA          ?
   ??????????????????????????????
             ?
   ??????????????????????????????
   ? Se sinal:                   ?
   ? executar_ordem()            ?
   ? • Simula execução           ?
   ? • Atualiza saldo            ?
   ? • Registra trade            ?
   ??????????????????????????????
             ?
   ??????????????????????????????
   ? Renderiza gráficos          ?
   ? (Preço, MACD, IA)           ?
   ??????????????????????????????
             ?
   ??????????????????????????????
   ? Renderiza histórico de      ?
   ? trades e estatísticas       ?
   ??????????????????????????????
             ?
   ??????????????????????????????
   ? Passou 5+ segundos ou       ?
   ? dados novos?                ?
   ???????????????????????????????
        ?                  ?
       SIM                 NÃO
        ?                  ?
   ???????????        ???????????
   ? st.rerun?        ? Aguarda ?
   ???????????        ???????????
```

---

### **Timing de Atualização (Otimizado)**

```python
# Lê arquivo temporário com novos candles
for symb in selected_symbols:
    symbol_socket = symb.replace("/", "")
    tmpfile = os.path.join(tempfile.gettempdir(), f"tmp_ws_{symbol_socket}.json")
    if os.path.exists(tmpfile):
        # ... atualiza DataFrame

# Processa sinais apenas se:
# 1. Há dados novos OU
# 2. Passaram 5 segundos desde última atualização
if dados_novos or tempo_desde_ultima_atualizacao >= 5:
    for symb in selected_symbols:
        processar_sinais(symbol_proc=symb)
    st.session_state['ultima_atualizacao_ui'] = now_brazil()

# Rerun completo apenas se:
# 1. Há dados novos OU
# 2. Passaram 10 segundos
if dados_novos or tempo_desde_ultima_atualizacao >= 10:
    st.rerun()
```

**Por que essa estratégia?**
- Evita piscar muito a interface
- Processa sinais frequentemente (5s)
- Atualiza UI menos frequentemente (10s)
- Economiza processamento

---

## viz_app.py - Backtesting {#viz_app}

Arquivo menor (~80 linhas), usado para testar sinais sem tradear:

```python
import streamlit as st
import pandas as pd
import os
from datetime import datetime
import time
import matplotlib.pyplot as plt

try:
    from strategies.ai_strategy import executar_estrategia_ai
    from exchanges.mock import MockExchange
except ModuleNotFoundError:
    import sys
    sys.path.append(os.path.abspath(os.path.dirname(__file__)))
    from strategies.ai_strategy import executar_estrategia_ai
    from exchanges.mock import MockExchange
```

### **Interface Simples**

```python
st.title('Visualização das Intenções da IA - Cripto')

par = st.selectbox('Escolha o par de criptomoeda:', ['BTC/USDT', 'PEPE/USDT'])
fonte = st.selectbox('Fonte de dados:', ['Mock', 'Binance'])

if st.button('Rodar análise agora'):
    with st.spinner('Analisando dados, por favor aguarde...'):
        try:
            if fonte == 'Binance':
                from exchanges.binance import BinanceExchange
                exchange = BinanceExchange()
                df = exchange.fetch_ohlcv(par)
            else:
                exchange = MockExchange()
                df = exchange.fetch_ohlcv(par)
```

### **Backtesting Loop**

```python
sinais = []
posicao_aberta = False

# Para cada candle a partir do 50º
for i in range(50, len(df)):
    janela = df.iloc[:i]  # Dados até este ponto
    sinal = executar_estrategia_ai(janela, posicao_aberta)
    sinais.append(sinal)
    
    # Atualiza posição simulada
    if sinal == 'buy':
        posicao_aberta = True
    elif sinal == 'sell':
        posicao_aberta = False

df = df.iloc[50:].copy()  # Remove primeiros 50 (aquecimento)
df['sinal'] = sinais
```

**O que faz:**
1. Pega histórico de 50+ candles
2. Para cada novo candle, simula a estratégia
3. Registra se seria COMPRA, VENDA ou HOLD
4. Não executa trades (apenas análise)

### **Visualização de Sinais**

```python
# Filtro interativo
filtro = st.selectbox('Filtrar por sinal:', ['Todos', 'buy', 'sell', 'hold'])
if filtro != 'Todos':
    df = df[df['sinal'] == filtro]

# Tabela
st.dataframe(df.tail(50))

# Gráfico
fig, ax = plt.subplots()
ax.plot(df['timestamp'], df['close'], label='Preço', color='gray')

buy_signals = df[df['sinal'] == 'buy']
sell_signals = df[df['sinal'] == 'sell']

ax.scatter(buy_signals['timestamp'], buy_signals['close'], 
          color='green', label='Buy', marker='^')
ax.scatter(sell_signals['timestamp'], sell_signals['close'], 
          color='red', label='Sell', marker='v')

ax.legend()
plt.xticks(rotation=45)
st.pyplot(fig)
```

---

## ?? Resumo de Fluxo Macro

```
user_interface
??? SIDEBAR (Configurações)
    ??? Credenciais API
    ??? Par de negociação
    ??? Timeframe
    ??? Parâmetros de risco
    ??? Configurações avançadas
    ??? [Iniciar/Parar Bot]
    
??? MAIN AREA (Dashboard)
    ??? Métricas (Saldo, Lucro)
    ??? Gráfico Principal
    ??? Análise da IA
    ??? MACD
    ??? Histórico de Trades
    ??? Estatísticas
    ??? Atualização em tempo real
    
??? BACKEND (Thread separada)
    ??? WebSocket recebe dados
    ??? Salva em arquivo temporário
    ??? Streamlit lê e atualiza DataFrame
    ??? Processa sinais
    ??? Executa ordens
    ??? Atualiza UI
```

---

## ?? Indicadores Técnicos Usados

| Indicador | Fórmula | Sinal |
|-----------|---------|-------|
| **MA 5** | `close.rolling(5).mean()` | Tendência rápida |
| **MA 20** | `close.rolling(20).mean()` | Tendência lenta |
| **MACD** | `EMA12 - EMA26` | Momentum |
| **MACD Signal** | `EMA9(MACD)` | Suavização |
| **Bollinger Bands** | `MA ± 2×STD` | Volatilidade |
| **RSI** | `100 - (100/(1+RS))` | Força (0-100) |
| **ADX** | Calcula força da tendência | Tendência (0-100) |
| **Volume Ratio** | `volume / avg_volume` | Confirmação |

---

## ?? Segurança Implementada

```python
# 1. Credenciais em arquivo local (não no código)
from config.settings import BINANCE_API_KEY, BINANCE_API_SECRET

# 2. Sub-conta recomendada (não use conta principal)
# 3. ThreadedWebsocket em thread separada (não bloqueia UI)
# 4. file_write_lock para evitar corrupção de arquivos
# 5. Drop_duplicates() para evitar trades duplicados
# 6. Sempre com Stop Loss obrigatório
# 7. Session State persiste entre reruns (não perde dados)
```

---

## ?? Performance Otimizações

```python
# 1. Limita DataFrame a 500 candles
df_market.tail(500)

# 2. Processa sinais cada 5 segundos (não a cada novo candle)
if tempo_desde_atualização >= 5:
    processar_sinais()

# 3. Rerun apenas cada 10 segundos
if tempo_desde_atualização >= 10:
    st.rerun()

# 4. uirevision='key' mantém zoom/pan do gráfico
fig.update_layout(uirevision='main-chart')

# 5. Cache de plotly charts
key='main_chart'
```

---

*Explicação completa do código - L-Trade-AI Bot*
*Última atualização: 25/02/2026*
