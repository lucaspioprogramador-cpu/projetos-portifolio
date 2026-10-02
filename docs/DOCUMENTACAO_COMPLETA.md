# Documentação Completa — L-Trade AI

> Sistema de trading automatizado com IA para criptomoedas, integrado com múltiplas exchanges.

Última atualização: Dezembro 11, 2025

---

##  Índice

1. [Visão Geral](#visão-geral)
2. [Estrutura do Projeto](#estrutura-do-projeto)
3. [Módulos Principais](#módulos-principais)
   - [core/](#core)
   - [exchanges/](#exchanges)
   - [strategies/](#strategies)
   - [ui/](#ui)
   - [backtest/](#backtest)
   - [db/](#db)
   - [config/](#config)
4. [Fluxo de Operação](#fluxo-de-operação)
5. [Instalação e Uso](#instalação-e-uso)
6. [Configurações](#configurações)

---

## Visão Geral

O **L-Trade AI** é um protótipo para análise de mercado e trading simulado que:

- **Coleta dados** em tempo real via WebSocket (Binance)
- **Analisa sinais** usando IA (Random Forest com indicadores técnicos)
- **Simula fills** de compra/venda (spread, slippage, taxas e fills parciais)
- **Gerencia risco** (stop loss, take profit, sizing de posição)
- **Gera relatórios** e métricas de performance
- **Permite backtesting** em dados históricos

Pode coletar dados públicos da Binance ou usar dados mock. A execução de ordens reais **não está implementada**; saldos e resultados no dashboard são simulações.

---

## Estrutura do Projeto

```
L-Trade AI/
├── core/                    # Camada de lógica principal
│   ├── engine.py            # Orquestração (Strategy + Exchange + State)
│   ├── state.py             # Estruturas de posições e portfólio
│   ├── data.py              # Normalização de candles (OHLCV)
│   ├── risk.py              # Cálculos de risco e posição sizing
│   ├── execution.py         # Construção e simulação de ordens
│   ├── simulator.py         # Simulador realista de execução
│   └── ws.py                # Gerenciador abstrato de WebSocket
│
├── exchanges/               # Integrações com exchanges
│   ├── base.py              # Interface abstrata
│   ├── binance.py           # Implementação Binance (via ccxt)
│   └── mock.py              # Exchange mockado para testes
│
├── strategies/              # Estratégias de trading (IA)
│   ├── base.py              # Interface de estratégia
│   ├── ai_strategy.py       # Estratégia básica (Random Forest)
│   └── ai_strategy_corrigido.py  # Versão melhorada com mais indicadores
│
├── ui/                      # Interfaces Streamlit
│   ├── main_app.py          # Dashboard principal e bot
│   └── viz_app.py           # Visualização de sinais históricos
│
├── backtest/                # Sistema de backtesting
│   ├── runner.py            # Executor de backtest
│   └── metrics.py           # Cálculo de métricas
│
├── db/                      # Persistência de dados
│   ├── database.py          # Funções SQLite
│   └── migrations.sql       # Schema do banco
│
├── config/                  # Configurações
│   └── settings.py          # Carregamento de ENV/.env
│
├── relatorios/              # Saída de relatórios (CSV)
│
├── requirements.txt         # Dependências Python
└── README.md                # Documentação de setup

```

---

## Módulos Principais

### **core/**

#### `engine.py`
**O que faz:** Orquestra a execução de uma estratégia + interação com exchange + atualização de estado.
- Classe `TradingEngine`: recebe dados, chama estratégia, delega execução
- Conecta Strategy (sinais) → Exchange (ordens) → PortfolioState (posições)

#### `state.py`
**O que faz:** Define estruturas de dados para posições e portfólio.
- `Position`: armazena símbolo, quantidade, preço de entrada, stop/take profit
- `PortfolioState`: saldo USDT, lista de posições abertas, metadados

#### `data.py`
**O que faz:** Normaliza DataFrames de candles.
- Valida colunas obrigatórias: `timestamp`, `open`, `high`, `low`, `close`, `volume`
- Converte timestamps para UTC/timezone

#### `risk.py`
**O que faz:** Cálculos de gerenciamento de risco.
- `position_size()`: calcula tamanho da posição baseado em % risco e distância de stop
- `apply_stop_take()`: gera níveis de stop loss e take profit

#### `execution.py`
**O que faz:** Constrói ordens e simula execução realista.
- `build_order()`: cria dict de ordem simples
- `executar_ordem_simulada()`: usa `OrderSimulator` para simular slippage/taxas/execução parcial

#### `simulator.py`
**O que faz:** Simula execução realista de ordens.
- Classe `OrderSimulator`: calcula slippage, spread bid/ask, taxas, execução parcial
- Baseado em volatilidade, tamanho da ordem, volume de mercado
- Configurável (taxa, spread, volatility multiplier)

#### `ws.py`
**O que faz:** Abstração simples para WebSocket (pub/sub).
- `WebSocketService`: registra callbacks por chave, emite mensagens
- Permite desacoplamento entre conexão real e lógica de processamento

---

### **exchanges/**

#### `base.py`
**O que faz:** Interface abstrata de exchange.
- Define métodos que toda exchange deve implementar:
  - `fetch_ohlcv()`: baixa candles históricos
  - `stream_candles()`: streaming em tempo real
  - `place_order()`, `cancel_order()`, `get_balance()`

#### `binance.py`
**O que faz:** Implementação Binance usando `ccxt`.
- `BinanceExchange`: conecta via CCXT
- Implementado: `fetch_ohlcv()` (dados históricos)
- Não implementado: streaming e ordens reais (placeholders)

#### `mock.py`
**O que faz:** Exchange fake com dados sintéticos para testes.
- `MockExchange`: gera OHLCV aleatório baseado em random walk
- Útil para testar UI/estratégia sem credenciais reais

---

### **strategies/**

#### `base.py`
**O que faz:** Interface de estratégia.
- Define método abstrato `on_bar(df)` que retorna sinal ('buy', 'sell', 'hold', etc.)

#### `ai_strategy.py`
**O que faz:** Estratégia de IA com Random Forest e indicadores.
- Gera features: retorno, médias móveis (5, 10, 20, 50), RSI, Bollinger Bands, MACD, OBV
- Treina Random Forest para prever próximo candle
- Compra se probabilidade > 65% e RSI < 65 e volume spike
- Vende se probabilidade < 35% ou stop loss (1%) ou take profit (2%)

#### `ai_strategy_corrigido.py`
**O que faz:** Versão simplificada (5 indicadores apenas).
- Usa: retorno, médias 5/10, RSI, média_diff
- Mesma lógica Random Forest mas com menos features
- Mais leve/rápido que a versão expandida

---

### **ui/**

#### `main_app.py`
**O que faz:** Dashboard principal do bot em Streamlit.
- **Sidebar:** entrada de credenciais Binance, parâmetros (symbol, timeframe, saldo, risco, SL/TP)
- **Seções:**
  - Monitoramento em tempo real via WebSocket
  - Execução de ordens (compra/venda) com simulação
  - Histórico de trades com lucro/prejuízo
  - Gráficos Plotly de preço + indicadores
  - Relatórios em CSV
- **Funcionalidades:** carregar/salvar credenciais em `binance_api.json`, simulação realista de execução

#### `viz_app.py`
**O que faz:** Visualizador de sinais históricos.
- Baixa dados (Mock ou Binance)
- Roda estratégia no histórico (loop de 50 a len(df))
- Plota gráfico com sinais buy/sell sobrepostos no preço
- Permite filtrar por sinal e ver tabela de eventos

---

### **backtest/**

#### `runner.py`
**O que faz:** Executa backtest de estratégia em dados históricos.
- `run_backtest()`: loop sobre janela de dados, chama estratégia, coleta sinais
- Retorna DataFrame com coluna `signal` adicionada

#### `metrics.py`
**O que faz:** Calcula métricas de performance.
- `basic_metrics()`: conta sinais gerados
- Placeholder para expansão (drawdown, Sharpe, Win Rate, etc.)

---

### **db/**

#### `database.py`
**O que faz:** Persistência de trades em SQLite.
- `conectar()`: cria tabela `trades` se não existir
- `registrar_trade()`: insere compra/venda no banco

#### `migrations.sql`
**O que faz:** Schema do banco de dados.
- Tabela `trades`: id, symbol, side, amount, price, timestamp

---

### **config/**

#### `settings.py`
**O que faz:** Carregamento de configurações e credenciais.
- Lê variáveis de ambiente (`.env`)
- Não lê credenciais de JSON legado; segredos digitados na UI valem apenas para a sessão
- Exporta: `BINANCE_API_KEY`, `BINANCE_API_SECRET`, `DEFAULT_TIMEFRAME`

---

## Fluxo de Operação

### Fluxo de Trading em Tempo Real (main_app.py)

```
Sidebar (Configurações)
    ↓
Credenciais → ENV/.env ou entrada temporária na sessão
    ↓
Iniciar WebSocket (Binance ThreadedWebsocketManager)
    ↓
Receber candle (kline event)
    ↓
Atualizar DataFrame local
    ↓
Estratégia (ai_strategy.executar_estrategia_ai)
    ↓
Sinal: 'buy' / 'sell' / 'hold'
    ↓
Se 'buy' → executar_ordem_simulada() → atualizar_saldo() → registrar trade
Se 'sell' → executar_ordem_simulada() → calcular lucro → registrar trade
    ↓
Atualizar UI (gráficos, histórico, saldo)
```

### Fluxo de Backtest (viz_app.py)

```
Selecionar par + fonte (Mock/Binance)
    ↓
Baixar OHLCV histórico (fetch_ohlcv)
    ↓
Loop: para cada candle, rodar estratégia com janela histórica
    ↓
Coletar sinais ('buy', 'sell', 'hold')
    ↓
Plotar sinais no gráfico de preço
    ↓
Exibir tabela + análise
```

---

## Instalação e Uso

### Setup

```powershell
# 1. Ambiente virtual
python -m venv .venv
.venv\Scripts\activate

# 2. Dependências
python -m pip install -r requirements.txt

# 3. Credenciais (opcional)
# Crie .env na raiz:
# BINANCE_API_KEY=xxx
# BINANCE_API_SECRET=yyy
# DEFAULT_TIMEFRAME=1m
```

### Executar

```powershell
# Bot principal (tempo real)
streamlit run ui/main_app.py

# Visualização de sinais (backtest)
streamlit run ui/viz_app.py
```

---

## Configurações

### Variáveis de Ambiente (.env)

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `BINANCE_API_KEY` | API Key Binance | "" |
| `BINANCE_API_SECRET` | API Secret Binance | "" |
| `DEFAULT_TIMEFRAME` | Timeframe padrão | "1m" |

### Parâmetros de Trading (UI Streamlit)

| Parâmetro | Tipo | Range | Padrão |
|-----------|------|-------|--------|
| Saldo Inicial | float | ≥ 100 | 1000 USDT |
| Risco por Trade | % | 0.1 – 5.0 | 1.0 |
| Stop Loss | % | 0.1 – 10.0 | 2.0 |
| Take Profit | % | 0.1 – 10.0 | 3.0 |

### Parâmetros do Simulador (core/simulator.py)

| Parâmetro | Descrição | Valor Padrão |
|-----------|-----------|--------------|
| `fee_rate` | Taxa de exchange | 0.1% (Binance) |
| `slippage_base` | Slippage base | 0.05% |
| `spread_pct` | Spread bid/ask | 0.02% |
| `volatility_multiplier` | Multiplicador de volatilidade | 2.0 |

---

## Guias Detalhados

### Como a Estratégia de IA Funciona (ai_strategy.py)

#### 1. Geração de Features
```python
def gerar_features(df):
    # Calcula indicadores técnicos a partir dos candles
    df['retorno'] = df['close'].pct_change()  # Retorno percentual
    df['media_5'] = df['close'].rolling(5).mean()  # Média móvel 5
    df['media_10'] = df['close'].rolling(10).mean()  # Média móvel 10
    df['rsi'] = calcular_rsi(df)  # Índice de Força Relativa
    df['bollinger_upper'], df['bollinger_lower'] = calcular_bollinger_bands(df)
    # ... mais 6 indicadores
    return df
```
**Propósito:** Transformar dados brutos de preço em features que a IA pode aprender.

#### 2. Treinamento do Modelo
```python
X = df[['retorno', 'media_5', 'media_10', ..., 'volume_spike']]
y = df['target']  # 1 se próximo candle subiu, 0 se caiu

modelo = RandomForestClassifier(n_estimators=200, random_state=42, max_depth=10)
modelo.fit(X[:-1], y[:-1])  # Treina no histórico
```
**Propósito:** Random Forest aprende padrões entre indicadores e movimento futuro.

#### 3. Geração de Sinal
```python
previsao_proba = modelo.predict_proba(X.iloc[[-1]])[0][1]  # Probabilidade de alta

if not posicao_aberta and previsao_proba > 0.65 and ultimo['rsi'] < 65:
    return 'buy'  # Compra se alta probabilidade e RSI baixo
elif posicao_aberta and previsao_proba < 0.35:
    return 'sell'  # Venda se baixa probabilidade
else:
    return 'hold'
```
**Propósito:** Combina predição de IA com filtros de indicadores para decisão robusta.

#### Indicadores Utilizados

| Indicador | Fórmula | Uso |
|-----------|---------|-----|
| **RSI (14)** | 100 - (100 / (1 + RS)) | Identifica overbought (>70) e oversold (<30) |
| **Bollinger Bands** | Media ± 2*StdDev | Identifica volatilidade extrema |
| **MACD** | EMA(12) - EMA(26) | Momentum e crossovers |
| **OBV** | Cumsum(sign(delta) × volume) | Volume on Balance |
| **Volume Spike** | Volume > 1.5 × MA(10) | Movimento anormal |

---

### Simulador de Execução (core/simulator.py)

#### Entendendo Slippage

**Slippage** é a diferença entre o preço esperado e o preço real de execução de uma ordem. É causado por:

1. **Spread Bid/Ask**: diferença entre o melhor preço de compra (bid) e venda (ask) no order book
2. **Movimento de mercado**: entre o momento da ordem e execução, o preço pode se mover contra você
3. **Tamanho da ordem**: ordens grandes impactam o order book mais que ordens pequenas
4. **Volatilidade**: em mercados voláteis, o slippage tende a ser maior
5. **Liquidez**: pares menos líquidos têm slippage maior

#### Como o Slippage é Calculado

O `OrderSimulator` calcula slippage em 4 etapas:

**1. Slippage Base (0.05%)**
```python
slippage = 0.0005  # 0.05% - componente fixa mínima
```
Representa o spread típico e frição mínima do mercado.

**2. Ajuste por Volatilidade**
```python
slippage += volatilidade * 2.0
```
- Volatilidade de 2% → adiciona 4% de slippage
- Volatilidade de 5% → adiciona 10% de slippage
- Maior volatilidade = preços mais impredizíveis = mais slippage

**3. Ajuste por Tamanho da Ordem**
```python
if ordem_pct_volume > 0.001:  # Se ordem > 0.1% do volume 24h
    slippage += min(ordem_pct * 10, 0.01)  # Máximo 1%
```
- Ordem de 0.2% do volume → adiciona 0.2% de slippage
- Ordem de 0.5% do volume → adiciona 0.5% de slippage
- Ordem de 1%+ do volume → tapa em 1% de slippage
- **Por quê?** Ordens grandes consomem partes do order book com preços piores

**4. Ajuste por Lado da Ordem**
```python
if lado == 'buy':
    slippage *= 1.2  # Compra tem 20% mais slippage
```
- **Compra**: você quer comprar AGORA, está disposto a pagar um pouco mais
- **Venda**: você quer vender AGORA, disposto a receber um pouco menos
- Compra tem **20% mais slippage** que venda

**5. Componente Aleatória**
```python
slippage += random(-0.01%, 0.01%)  # Simula variação natural
```
Simula flutuações pequenas do mercado durante a execução.

#### Cálculo do Preço de Execução

Após calcular o slippage, o preço é ajustado:

**Para Compra (BUY):**
```python
# 1. Primeiro aplica spread (você paga mais)
preco_exec = preco_atual * (1 + spread/2)  # Spread 0.02% = +0.01%

# 2. Depois aplica slippage (paga ainda mais pelo impacto)
preco_exec *= (1 + slippage)

# 3. Calcula valor total e taxas
valor_total = preco_exec * quantidade
taxas = valor_total * 0.001  # 0.1% taxa Binance
```

**Para Venda (SELL):**
```python
# 1. Primeiro aplica spread (você recebe menos)
preco_exec = preco_atual * (1 - spread/2)  # Spread 0.02% = -0.01%

# 2. Depois aplica slippage (recebe ainda menos)
preco_exec *= (1 - slippage)

# 3. Calcula valor total e taxas
valor_total = preco_exec * quantidade
taxas = valor_total * 0.001
```

#### Execução Parcial (Fill Partial)

Para ordens **muito grandes** (>1% do volume 24h), a simulação permite:
```python
if ordem_valor > volume_24h * 0.01:
    fill_rate = random(70%, 100%)  # 70-100% da ordem é executada
    quantidade_executada = quantidade * fill_rate
```
- Se você quer comprar 10 BTC mas é >1% do volume, pode executar apenas 70-100% da quantidade
- Simula a realidade: seu broker segue fazendo slices da ordem, mas nem tudo executa imediatamente

#### Exemplo Detalhado de Execução

**Cenário:** 
- Comprar **1 BTC**
- Preço atual: **$40.000**
- Volatilidade: **2%**
- Volume 24h: **$2B**
- Lado: **BUY**

**Passo 1: Calcular Slippage**
```
slippage = 0.05%                           # Base
slippage += 2% * 2.0 = 4%                 # Volatilidade
ordem_pct_volume = (40000 * 1) / 2B = 0.002% < 0.1%  # Sem ajuste por tamanho
slippage *= 1.2 = 4.8%                    # Compra = 20% mais
slippage += random(-0.01%, 0.01%) ≈ 4.8% # Aleatório mínimo

RESULTADO: slippage ≈ 0.048 ou 4.8%
```

**Passo 2: Calcular Preço de Execução**
```
preco_exec = 40000 * (1 + 0.0002/2)      # Spread bid/ask
preco_exec = 40000 * 1.0001 = 40004

preco_exec *= (1 + 0.048)                 # Slippage
preco_exec = 40004 * 1.048 = 41924.19

PREÇO FINAL: $41.924,19 (vs $40.000 esperado)
```

**Passo 3: Calcular Valores**
```
valor_total = 41924.19 * 1 = $41.924,19
taxas = 41924.19 * 0.001 = $41,92  (0.1% taxa Binance)
slippage_valor = (41924.19 - 40000) * 1 = $1.924,19
slippage_pct = 1924.19 / 40000 = 0.0481 (4.81%)
```

**Resposta da API:**
```python
{
    'lado': 'buy',
    'preco_solicitado': 40000.00,
    'preco_execucao': 41924.19,              # Preço real
    'quantidade_solicitada': 1.0,
    'quantidade_executada': 1.0,             # 100% executado (ordem pequena)
    'valor_total': 41924.19,
    'taxas': 41.92,                          # Taxa Binance
    'valor_liquido': 41882.27,               # valor_total - taxas
    'slippage_pct': 0.0481,                  # 4.81%
    'slippage_valor': 1924.19,               # Quanto perdeu em reais
    'executada_completa': True,
    'timestamp': '2025-12-10T14:32:15'
}
```

#### Exemplo Realista (Menor Slippage)

**Cenário mais típico:**
- Comprar **0.1 BTC**
- Preço: **$45.000**
- Volatilidade: **1.5%** (normal)
- Volume 24h: **$2.5B**
- Lado: **BUY**

**Cálculo:**
```
slippage = 0.05%                              # Base
slippage += 1.5% * 2.0 = 3%                  # Volatilidade
ordem_pct_volume = (45000 * 0.1) / 2.5B = 0.00018% < 0.1%  # Sem ajuste
slippage *= 1.2 = 3.6%                       # Compra
slippage += aleatório ≈ 3.6%

preco_exec = 45000 * (1 + 0.0002/2) = 45004.50
preco_exec *= (1 + 0.036) = 45004.50 * 1.036 = 46624.66

slippage_valor = (46624.66 - 45000) * 0.1 = $162.47
slippage_pct = 162.47 / 4500 = 0.0361 (3.61%)
```

**Resultado:**
```python
{
    'preco_solicitado': 45000.00,
    'preco_execucao': 46624.66,
    'slippage_pct': 0.0361,  # 3.61%
    'slippage_valor': 162.47,  # Perdeu ~$162 por slippage
    'taxas': 46.62,  # Taxa Binance 0.1%
    'valor_total': 4662.47,  # Custo total
    'executada_completa': True
}
```

#### Ordem de Venda (Menos Slippage)

**Mesmo cenário, mas VENDA:**
```
slippage = 0.05%
slippage += 1.5% * 2.0 = 3%
slippage *= 1.0 (sem multiplicador 1.2 para venda)
slippage ≈ 3%

preco_exec = 45000 * (1 - 0.0002/2) = 44995.50
preco_exec *= (1 - 0.03) = 44995.50 * 0.97 = 43645.64

slippage_valor = (45000 - 43645.64) * 0.1 = $135.44
slippage_pct = 135.44 / 4500 = 0.0301 (3.01%)
```
**Note:** Venda tem ~0.6% menos slippage (3.01% vs 3.61%)

#### Parâmetros Configuráveis

| Parâmetro | Padrão | Intervalo Típico | Descrição |
|-----------|--------|------------------|-----------|
| `fee_rate` | 0.001 | 0.001-0.002 | Taxa exchange (0.1%-0.2%) |
| `slippage_base` | 0.0005 | 0.0001-0.001 | Slippage mínimo (0.01%-0.1%) |
| `spread_pct` | 0.0002 | 0.0001-0.0005 | Spread bid/ask (0.01%-0.05%) |
| `volatility_multiplier` | 2.0 | 1.0-3.0 | Quantos % de slippage por % de volatilidade |

Para criar um simulador customizado:
```python
from core.simulator import OrderSimulator

# Mais agressivo (mais slippage)
sim_agressivo = OrderSimulator(
    fee_rate=0.002,           # 0.2% taxa
    slippage_base=0.001,      # 0.1% base
    spread_pct=0.0005,        # 0.05% spread
    volatility_multiplier=3.0 # Volatilidade conta mais
)

# Mais conservador (menos slippage)
sim_conservador = OrderSimulator(
    fee_rate=0.0005,          # 0.05% taxa (maker)
    slippage_base=0.0002,     # 0.02% base
    spread_pct=0.0001,        # 0.01% spread
    volatility_multiplier=1.5
)
```

---

### Fluxo Detalhado de Trading em Tempo Real

```
┌─────────────────────────────────────────────────────────┐
│ 1. Iniciar bot (streamlit run ui/main_app.py)          │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│ 2. Carregar configurações                               │
│    - API Key/Secret (env ou binance_api.json)          │
│    - Symbol, Timeframe, Saldo, Risco, SL/TP            │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│ 3. Conectar WebSocket (ThreadedWebsocketManager)        │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│ 4. Receber candle (kline event) a cada período          │
│    Exemplo: BTC/USDT 1m candle às 10:15:30             │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│ 5. Atualizar DataFrame local (últimos 500 candles)      │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────┐
│ 6. Chamar estratégia: executar_estrategia_ai(df)        │
│    - Gera features (RSI, MACD, OBV, etc.)              │
│    - Treina Random Forest                               │
│    - Retorna: 'buy', 'sell', ou 'hold'                 │
└──────────────────┬──────────────────────────────────────┘
                   │
           ┌───────┴────────┬────────────────┐
           │                │                │
      ┌────▼─────┐    ┌─────▼──────┐   ┌────▼─────┐
      │ Sinal    │    │ Sinal      │   │ Sinal    │
      │ 'buy'    │    │ 'sell'     │   │ 'hold'   │
      └────┬─────┘    └─────┬──────┘   └────┬─────┘
           │                │               │
           │                │         (sem ação)
           │                │
    ┌──────▼────────────────▼──────────────┐
    │ 7a. Executar Ordem (buy ou sell)     │
    │ - executar_ordem_simulada()          │
    │ - calcula preco_exec, quantidade_exec│
    │ - calcula slippage e taxas           │
    └──────┬─────────────────────────────────┘
           │
    ┌──────▼──────────────────────────────┐
    │ 7b. Atualizar estado                │
    │ - saldo_usdt                        │
    │ - posicao_aberta                    │
    │ - registrar trade                   │
    └──────┬───────────────────────────────┘
           │
    ┌──────▼──────────────────────────────┐
    │ 8. Atualizar UI                     │
    │ - gráfico (preço + sinais)          │
    │ - histórico de trades               │
    │ - saldo e lucro/prejuízo            │
    └──────┬───────────────────────────────┘
           │
    ┌──────▼──────────────────────────────┐
    │ 9. Aguardar próximo candle          │
    │    (volta ao passo 4)               │
    └───────────────────────────────────────┘
```

---

### Exemplo: Ciclo Completo de um Trade

**Condições iniciais:**
- Saldo: 1000 USDT
- BTC/USDT = 45.000
- Risco por trade: 1%
- Stop Loss: 2%
- Take Profit: 3%

**Passo 1: Calcula tamanho de posição**
```python
from core.risk import position_size

tamanho = position_size(
    balance=1000,
    risk_pct=0.01,      # 1% = 10 USDT de risco
    stop_pct=0.02,      # 2% de distância
    price=45000
)
# tamanho ≈ 0.0011 BTC (investimento ≈ 50 USDT)
```

**Passo 2: Estratégia retorna 'buy'**
```python
sinal = executar_estrategia_ai(df)  # Retorna 'buy'
```

**Passo 3: Executa compra simulada**
```python
trade = executar_ordem(
    tipo='COMPRA',
    preco=45000,
    quantidade=0.0011,
    usar_simulacao=True
)
# Resultado:
# - preco_execucao: 45045 (slippage de ~0.1%)
# - quantidade_executada: 0.0011
# - valor_total: 49.5495
# - taxas: 0.05
# - valor_liquido: 49.50 USDT debitado
# - novo_saldo: 950.50 USDT
```

**Passo 4: Monitora posição aberta**
- Preço sobe para 46.500: lucro de 3.25% → **Estratégia retorna 'sell' (take profit)**
- OU preço cai para 44.100: prejuízo de 2% → **Estratégia retorna 'sell' (stop loss)**

**Passo 5: Executa venda simulada**
```python
trade = executar_ordem(
    tipo='VENDA',
    preco=46500,
    quantidade=0.0011,
    usar_simulacao=True
)
# Resultado (cenário take profit):
# - preco_execucao: 46447 (slippage menor na venda)
# - quantidade_executada: 0.0011
# - valor_total: 51.09
# - taxas: 0.051
# - valor_liquido: 51.04 USDT creditado
# - lucro_liquido: 51.04 - 49.50 = 1.54 USDT
# - retorno: 3.1%
# - novo_saldo: 1001.54 USDT
```

**Histórico do trade:**
```
[
  {
    'timestamp': '10/12/2025 14:30:15',
    'symbol': 'BTC/USDT',
    'tipo': 'COMPRA',
    'preco_solicitado': 45000,
    'preco_execucao': 45045,
    'quantidade_executada': 0.0011,
    'valor_total': 49.55,
    'taxas': 0.05,
    'slippage_pct': 0.001
  },
  {
    'timestamp': '10/12/2025 14:35:20',
    'tipo': 'VENDA',
    'preco_solicitado': 46500,
    'preco_execucao': 46447,
    'quantidade_executada': 0.0011,
    'valor_total': 51.09,
    'taxas': 0.051,
    'lucro': 1.54,
    'retorno': 3.1%
  }
]
```

---

## Troubleshooting Expandido

### Problema: "ModuleNotFoundError: No module named 'streamlit'"
**Solução:**
```powershell
python -m pip install streamlit
```

### Problema: "ConnectionError: No such file or directory: 'binance_api.json'"
**Solução:** O arquivo é criado automaticamente na primeira vez que você salva credenciais via UI.
Se quiser pré-configurar:
```json
{
  "api_key": "sua_chave_aqui",
  "api_secret": "seu_secret_aqui"
}
```

### Problema: "The Binance API returned an error: [1015] 429 Too Much Request Weight Used"
**Causa:** Muitas requisições em pouco tempo (rate limiting).
**Solução:**
- Aumentar intervalo entre requisições
- Usar WebSocket em vez de HTTP polling
- Reduzir número de símbolos monitorados

### Problema: WebSocket desconecta frequentemente
**Causa:** Conexão instável com internet ou firewall.
**Solução:**
- Implementar reconexão automática em `core/ws.py`
- Aumentar timeout (`ws.timeout = 30`)
- Usar VPN se estiver em região bloqueada

### Problema: "Sinal nunca muda de 'hold'"
**Causa:** Estratégia muito conservadora ou mercado sem padrão.
**Solução:**
```python
# Reduzir threshold de confiança (em ai_strategy.py):
if previsao_proba > 0.55:  # era 0.65
    return 'buy'
```

### Problema: "Saldo fica negativo"
**Causa:** Erro no cálculo de taxas ou execução parcial mal tratada.
**Solução:**
- Verificar simulação realista está ativa
- Aumentar stop loss mínimo (2% → 5%)
- Reduzir risco por trade (1% → 0.5%)

---

## Estendendo o Projeto

### Adicionar Nova Estratégia

1. **Criar arquivo em `strategies/minha_estrategia.py`:**
```python
from strategies.base import Strategy

class MinhaEstrategia(Strategy):
    def on_bar(self, df):
        # Sua lógica aqui
        # Retorna: 'buy', 'sell', 'hold', etc.
        return 'hold'
```

2. **Importar em `ui/main_app.py`:**
```python
from strategies.minha_estrategia import MinhaEstrategia

# No sidebar, adicionar seletor:
estrategia = st.selectbox("Estratégia", ["IA", "Minha Estratégia"])

if estrategia == "IA":
    sinal = executar_estrategia_ai(df)
else:
    minha = MinhaEstrategia()
    sinal = minha.on_bar(df)
```

### Adicionar Nova Exchange

1. **Criar `exchanges/nova_exchange.py`:**
```python
from exchanges.base import Exchange

class NovaExchange(Exchange):
    def fetch_ohlcv(self, symbol, timeframe='1d', limit=500):
        # Buscar dados de NovaExchange
        pass
    
    def place_order(self, symbol, side, amount, price=None):
        # Colocar ordem
        pass
```

2. **Usar em engine:**
```python
from exchanges.nova_exchange import NovaExchange

exchange = NovaExchange()
engine = TradingEngine(strategy, exchange, state)
```

### Adicionar Indicador Customizado

```python
# Em strategies/ai_strategy.py, na função gerar_features():

def calcular_stochastic(df, k=14, d=3):
    """Stochastic oscillator"""
    low_min = df['low'].rolling(k).min()
    high_max = df['high'].rolling(k).max()
    k_line = 100 * (df['close'] - low_min) / (high_max - low_min)
    d_line = k_line.rolling(d).mean()
    return k_line, d_line

# Adicionar em gerar_features():
df['stochastic_k'], df['stochastic_d'] = calcular_stochastic(df)
df['stochastic_signal'] = (df['stochastic_k'] > df['stochastic_d']).astype(int)

# Adicionar em X = df[[...]]:
X = df[..., 'stochastic_signal']  # Adicionar feature
```

---

## Métricas de Performance

Métricas recomendadas a implementar em `backtest/metrics.py`:

| Métrica | Fórmula | Interpretação |
|---------|---------|----------------|
| **Win Rate** | trades_vencedores / total_trades | % de trades com lucro |
| **Profit Factor** | lucro_bruto / prejuízo_bruto | Relação ganho/perda |
| **Sharpe Ratio** | (retorno_médio - rf) / σ(retornos) | Retorno ajustado ao risco (≥1.0 é bom) |
| **Max Drawdown** | (pico - vale) / pico | Maior queda da curva (menor é melhor) |
| **Expectancy** | (WR × lucro_médio) - ((1-WR) × perda_média) | Ganho esperado por trade |

---

## Próximos Passos Recomendados

1. **Implementar ordens reais** em `exchanges/binance.py`
   - Usar `ccxt.binance().create_order()`
   - Adicionar validação de saldo

2. **Melhorar métricas** em `backtest/metrics.py`
   - Calcular Sharpe Ratio, Max Drawdown, Win Rate
   - Gerar relatório HTML exportável

3. **Adicionar logging** 
   - Usar `logging` padrão do Python
   - Registrar trades, erros, alertas

4. **Testes automatizados**
   - `pytest` para testes unitários
   - Testar estratégia, simulador, risk manager

5. **Dashboard de monitoramento**
   - Adicionar alertas (email/Telegram) ao atingir SL/TP
   - Exibir análise em tempo real (vol, volatility, etc.)

6. **Persistência e análise**
   - Salvar todos os trades em banco de dados
   - Gerar relatórios diários/semanais

---

## Análise de Código

Esta seção sumariza uma revisão técnica do código-fonte existente, destacando problemas potenciais, inconsistências e recomendações por módulo.

Observação: A análise se baseia no código presente na árvore do repositório (arquivos lidos). Recomenda-se rodar testes adicionais e uma revisão dinâmica (execução) para validar comportamentos em runtime.

### `core/`
- engine.py:
    - Observação: orquestração está mínima — `TradingEngine.on_new_data` chama a estratégia e retorna sinal. Falta: integração automática com exchange/state (execução de ordens, tratamento de exceções).
    - Recomendação: adicionar logging, tratamento de exceções e método `run_tick` que atualize `PortfolioState` automaticamente quando houver sinal.

- state.py:
    - Observação: uso correto de dataclasses para `Position` e `PortfolioState`.
    - Recomendação: adicionar métodos utilitários (ex.: `open_position`, `close_position`, `get_unrealized_pnl`) e tipos/validações.

- data.py:
    - Observação: `normalize_candles` valida colunas e converte timestamp; porém retorna somente `REQUIRED_COLUMNS` o que pode eliminar colunas auxiliares (ex.: indicadores já calculados).
    - Recomendação: manter colunas extras quando possível ou documentar que elas serão descartadas.

- risk.py:
    - Observação: funções `position_size` e `apply_stop_take` estão corretas mas sem validação de input (e.g. tipos, zeros/None).
    - Recomendação: adicionar checagens e testes unitários para casos limites.

- execution.py / simulator.py:
    - Observação: simulador (`OrderSimulator`) é robusto e realista; `execution` delega para o simulador. Bom isolamento.
    - Pontos a melhorar: simulação e execução real usam APIs diferentes; ao integrar ordens reais, controlar idempotência, tratar fills parciais e reconciliar saldo com `PortfolioState`.

- ws.py:
    - Observação: `WebSocketService` é um pub/sub simples, útil como abstraction. Falta reconexão automática e backoff.
    - Recomendação: adicionar reconexão, heartbeats e logs de conectividade.

### `exchanges/`
- base.py:
    - Observação: interface clara e aceitável.
    - Recomendação: documentar formatos esperados (ex.: DataFrame colunas, formato de símbolo).

- binance.py:
    - Observações encontradas:
        - `fetch_ohlcv` mapeia símbolos e converte timestamp (ms) — OK.
        - `stream_candles`, `place_order`, `cancel_order`, `get_balance` são placeholders (NotImplementedError) — portanto não há execução real.
    - Riscos: tentar usar métodos não implementados vai lançar erro em runtime.
    - Recomendação: implementar ordens com `ccxt` (create_order, cancel_order) ou usar python-binance para WebSocket/ordens reais; adicionar validação de saldo/erros e retry.

- mock.py:
    - Observação: útil para testes. Nota: assinatura `fetch_ohlcv(self, symbol)` não segue totalmente a assinatura do `base.Exchange` (timeframe/limit opcional). Pode causar incompatibilidade se o código pressupõe os parâmetros.
    - Recomendação: alinhar assinatura com `base.py` e documentar seeds/aleatoriedade para testes determinísticos.

### `strategies/`
- base.py:
    - Observação: interface clara (`on_bar`).

- ai_strategy.py / ai_strategy_corrigido.py:
    - Observações técnicas:
        - O código treina um RandomForest a cada chamada (cada candle) o que é muito custoso e instável para execução em tempo real.
        - Uso de `X[:-1]` e `y[:-1]` evita vazamento de label imediato, mas é preciso garantir janelas temporais corretas para evitar lookahead.
        - Falta persistência do modelo (joblib), validação e escalonamento de features (StandardScaler) antes do treino/predict.
    - Riscos: alto uso de CPU e latência; possíveis flutuações de performance e decisões inconsistentes.
    - Recomendações:
        - Treinar modelo em background (offline) e carregar modelo em memória para inferência em tempo real.
        - Atualizar modelo periodicamente (ex.: a cada N candles ou com agendamento), não a cada tick.
        - Salvar pipeline (scaler + modelo) com `joblib`.
        - Adicionar testes unitários e validação cruzada para evitar overfitting.

### `ui/`
- main_app.py:
    - Observações:
        - UI é rica e prática, porém contém lógica de execução (business logic) junto com apresentação: ideal separar responsabilidades.
        - Salvamento de credenciais em `binance_api.json` é conveniente, mas representa risco de segurança (arquivo legível no disco). Documentado no README, mas considerar criptografia ou storage seguro em produção.
        - Código do WebSocket mostrado contém prints/`experimental_rerun()` chamadas; lidar com thread-safety (manipulação de `st.session_state` dentro de threads requer cuidado).
    - Recomendações:
        - Mover lógica de execução/estado para `core/engine.py` e manter `ui` responsável só pela apresentação.
        - Proteger credenciais: recomendar `.env` ou variáveis de ambiente externas em produção.
        - Revisar thread-safety ao atualizar `st.session_state` a partir de callbacks do WebSocket (usar `st.session_state` apenas na thread principal ou usar filas/locks como já existe parcialmente).

- viz_app.py:
    - Observação: utilitário de visualização adequado para backtest rápido. Usa Mock e Binance.
    - Recomendação: adicionar botão para exportar CSV/relatório das métricas do backtest.

### `backtest/` e `db/`
- runner.py / metrics.py:
    - Observação: backtester simples funciona; `metrics.py` é placeholder com poucas métricas.
    - Recomendação: implementar métricas de risco (Sharpe, Max Drawdown), persistentar resultados de backtest para reprodutibilidade.

- database.py / migrations.sql:
    - Observação: SQLite simples, tabela `trades` criada — útil para POC.
    - Recomendação: adicionar índices, transações atômicas e abstração para trocar de DB (ex.: SQLAlchemy) se escala desejar.

### `config/` e `requirements.txt`
- settings.py:
    - Observação: carrega `.env` e faz fallback para `binance_api.json` — conveniente para desenvolvimento.
    - Recomendação: evitar fallback automático em produção; preferir variável de ambiente ou secret manager.

- requirements.txt:
    - Observação: atualmente lista pacotes sem pins de versão. Isso pode causar incompatibilidades futuras.
    - Recomendação: fixar versões mínimas/compatíveis (ex.: `pandas==1.5.3`, `scikit-learn==1.2.2`, etc.) e incluir `dev` extras (`pytest`, `flake8`).

### Riscos e Pontos Críticos
- Segurança: armazenamento de keys em `binance_api.json` em texto plano. Evitar em ambientes produtivos.
- Rate limiting: `exchanges/binance.py` e `ui/main_app.py` podem exceder limites da API; usar WebSocket quando possível e lembrar de backoff.
- Performance: retrain do modelo a cada bar é custoso — mover para pipeline offline/assíncrono.
- Confiabilidade: falta de testes automatizados e de tratamento robusto de exceções em integração com exchange.

### Status das recomendações
- Há testes unitários em `tests/` para risco, fills, features, dados, persistência e backtest; o GitHub Actions executa a suíte.
- As dependências têm faixas de versão e `streamlit-autorefresh` está declarada.
- A UI limita decisões a candles encerrados, mantém a fila WebSocket por sessão e persiste o snapshot local atomicamente.
- A execução real continua não implementada. Reconciliação com exchange, autenticação gerenciada, auditoria da estratégia e testes extensivos de reconexão seguem necessários antes de qualquer uso financeiro.


**Última atualização:** Dezembro 10, 2025
**Próxima revisão prevista:** Conforme novas funcionalidades sejam implementadas

Dúvidas ou sugestões? Atualize este documento conforme o projeto evolui.


---

## O Que Foi Implementado

Esta seção documenta as evoluções realizadas após a versão inicial (dezembro 2025).

### Arquitetura e qualidade

- Migração do `ai_strategy.py` deprecated para `ai_strategy_melhorada.py` com 19 features
- Remoção da duplicação de funções de indicadores em `ai_strategy_melhorada.py` — agora importa de `features.py`
- Cache do RandomForest no `session_state` — sem retreino a cada candle; retreina apenas quando chegam 10+ candles novos
- `build_strategy_config()` — stop loss e take profit dos sliders do sidebar chegam à estratégia (antes eram hardcoded em 1% e 2%)
- Logging estruturado com `logging` em todo o `main_app.py` — sem `print()` solto
- `registrar_trade` isolado em try/except — erro no banco não cancela a notificação Telegram nem o retorno do trade
- f-string corrigida na notificação Telegram de ordem executada (bug que enviava `{tipo}` literal)
- SSL habilitado em todas as chamadas ao Telegram (`verify=False` removido)
- Encoding UTF-8 com LF em todos os arquivos gerados

### Multi-par e multi-ordem

- `analisar_e_executar_trades()` itera sobre todos os pares com dados suficientes (≥100 candles) em vez de só o par ativo no sidebar
- `get_ordens(sym)` — lista de ordens por par substitui estado global único (`posicao_aberta/preco_compra/quantidade`)
- `executar_ordem()` recebe `sym` e `ordem_ref` — suporta múltiplas ordens abertas por par
- Verificação de saldo antes de cada compra — múltiplos pares competem pelo mesmo saldo disponível
- Venda em FIFO quando `ordem_ref` não é fornecida
- Status UI exibe contagem de ordens abertas por par (ex: `BTC/USDT (3)`)
- Saldo total soma o valor de mercado de todas as ordens abertas de todos os pares

### WebSocket e dados

- `_WS_CANDLE_QUEUE` (`queue.Queue`) thread-safe substitui arquivos temporários JSON no callback do websocket
- `carregar_historico_par()` — busca 500 candles via REST na inicialização, antes de ligar o websocket
- Carga histórica em paralelo com `ThreadPoolExecutor` (até 5 threads simultâneas)
- Websocket sobe apenas após o histórico estar carregado — bot analisa sinais imediatamente ao ligar
- `get_candles` corrigido — com `limit`, retorna os N mais **recentes** (não os N mais antigos)
- `registrar_candle` com `INSERT OR IGNORE` — sem duplicatas no banco
- Escrita atômica de arquivos via `os.replace()` — sem JSON corrompido em caso de interrupção

### Persistência

- `salvar_estado_bot()` / `carregar_estado_bot()` — saldo e ordens abertas persistem em `estado_bot.json` entre sessões
- `get_trades()` adicionado ao `database.py` — busca trades por par e período para o gráfico
- Schema da tabela `trades` corrigido — alinhado com os campos que `registrar_trade` insere (eram incompatíveis)
- `UNIQUE(symbol, timestamp, timeframe)` adicionado na tabela `candles`

### Interface e visualização

- `st_autorefresh` (10s) substitui `time.sleep() + st.rerun()` — a UI não congela mais durante o ciclo de atualização
- Gráfico: linha de preço com escala dinâmica (eixo Y próximo dos preços reais do período)
- Gráfico: triângulos de compra/venda dos trades reais do banco com tooltip detalhado (preço, quantidade, valor, lucro)
- Gráfico: linha tracejada conectando cada compra à venda correspondente (verde = lucro, vermelho = prejuízo)
- Gráfico: filtros de período (Agora / Última hora / Últimas 6h / Último dia / 7 dias / Tudo) com busca direta do banco
- Gráfico: toggle para mostrar/ocultar sinais da estratégia
- Painel de indicadores: 12 cards HTML com ponto colorido por threshold (verde/amarelo/vermelho) e tooltip explicativo ao passar o mouse
- Tooltip dos indicadores: `position: fixed` + JS de rastreamento do cursor — não é cortado pelas bordas do iframe

---

## Próximos Passos

Ordenados por prioridade.

### 1. Migrar banco existente (imediato)
Se `simulacao.db` foi criado antes da correção do schema, a tabela `trades` tem colunas incompatíveis (`side/amount/price` em vez das atuais). O `CREATE TABLE IF NOT EXISTS` não altera tabelas existentes. Apague o arquivo e reinicie:

```powershell
del simulacao.db
```

### 2. Pinar dependências no `requirements.txt`
Adicionar versões mínimas para garantir reprodutibilidade:

```
streamlit>=1.32.0
pandas>=2.0.0
numpy>=1.24.0
scikit-learn>=1.3.0
python-binance>=1.0.19
plotly>=5.18.0
pytz>=2024.1
requests>=2.31.0
streamlit-autorefresh>=1.0.0
```

E criar `requirements-dev.txt`:
```
pytest>=7.4.0
pytest-cov>=4.1.0
black>=23.0.0
flake8>=6.0.0
```

### 3. Testes unitários para módulos críticos
Prioridade: `core/simulator.py`, `core/risk.py`, `db/database.py`, `strategies/ai_strategy_melhorada.py`.

```python
# Exemplo — test_simulator.py
def test_slippage_compra_maior_que_venda():
    sim = OrderSimulator()
    r_buy  = sim.simulate('buy',  1.0, 45000, volatilidade=0.02)
    r_sell = sim.simulate('sell', 1.0, 45000, volatilidade=0.02)
    assert r_buy['slippage_pct'] > r_sell['slippage_pct']
```

### 4. Reconexão automática do WebSocket
O `ThreadedWebsocketManager` pode cair silenciosamente. Detectar e reconectar no loop principal:

```python
if st.session_state.get('ws_iniciado'):
    twm = st.session_state.bot_data.get('conexao_websocket')
    if twm and not twm.is_alive():
        logger.warning("WebSocket caiu — reconectando...")
        iniciar_conexao(selected_symbols)
```

### 5. Implementar `backtest/metrics.py`
As métricas listadas na seção anterior ainda são placeholder. Implementar Win Rate, Profit Factor, Sharpe Ratio e Max Drawdown com base nos trades do banco.

---

## Melhorias Futuras Recomendadas

### Estratégia e modelo

**Treinamento offline** — treinar o modelo com dados históricos completos, salvar com `joblib` e carregar na inicialização. Atualizar periodicamente em background, não online:

```python
import joblib
joblib.dump(modelo, 'models/rf_BTCUSDT_1m.pkl')
modelo = joblib.load('models/rf_BTCUSDT_1m.pkl')
```

**Validação cruzada temporal** — usar `TimeSeriesSplit` para validar sem lookahead bias:

```python
from sklearn.model_selection import TimeSeriesSplit
tscv = TimeSeriesSplit(n_splits=5)
for train_idx, test_idx in tscv.split(X):
    modelo.fit(X.iloc[train_idx], y.iloc[train_idx])
```

**Modelos alternativos** — XGBoost ou LightGBM tendem a superar RandomForest em dados financeiros com menos overfitting.

### Gestão de risco

**Exposição máxima por par** — limitar o percentual do saldo que pode estar investido em um único par (ex: máximo 30%).

**Exposição total** — limitar o saldo total investido em todas as posições abertas (ex: máximo 80%).

**Trailing stop** — stop loss dinâmico que sobe conforme o preço sobe, protegendo lucros acumulados.

### Infraestrutura

**Execução real na Binance** — implementar `place_order` em `exchanges/binance.py` usando `ccxt`:

```python
def place_order(self, symbol, side, amount, price=None):
    return self.exchange.create_order(
        symbol=symbol.replace('/', ''),
        type='market' if price is None else 'limit',
        side=side,
        amount=amount,
        price=price,
    )
```

**Dashboard de performance** — página dedicada com curva de capital, drawdown, win rate por par e comparação com buy-and-hold.

**Relatórios automáticos via Telegram** — envio diário com resumo: trades do dia, saldo atual, variação, pares mais lucrativos.

**SQLAlchemy** — abstração do banco para facilitar migração futura para PostgreSQL se o volume de dados crescer.

---

*Dúvidas ou sugestões? Atualize este documento conforme o projeto evolui.*