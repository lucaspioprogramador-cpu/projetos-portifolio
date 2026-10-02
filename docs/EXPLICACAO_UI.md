> **Nota de segurança/escopo:** esta documentação contém descrições históricas. A aplicação atual coleta dados e simula trades; ela não envia ordens reais. Credenciais digitadas na interface permanecem somente na sessão. Consulte [README.md](../README.md) e [GUIA_RAPIDO_RODAR.md](../GUIA_RAPIDO_RODAR.md) para instruções vigentes.
# ?? Explica��o Completa da UI - L-Trade-AI
# ?? Explica��o Completa da UI - L-Trade-AI

## ?? Vis�o Geral

A aplica��o possui **duas interfaces principais** constru�das com **Streamlit**, uma framework Python para criar dashboards web interativos.

---

## 1?? **main_app.py** - Bot de Trading em Tempo Real

### ?? Prop�sito
Interface principal para **monitoramento e execu��o de trading automatizado** na Binance com dados em tempo real via WebSocket.

### ??? Estrutura da Interface

#### **A. Sidebar (Painel Esquerdo)**
Controla todas as configura��es do bot:

```
???????????????????????????????????
?  CONFIGURA��ES DO BOT            ?
???????????????????????????????????
? ?? API Key (password)            ?
? ?? API Secret (password)         ?
?                                  ?
? ?? [Salvar Credenciais]          ?
? ?? [Carregar Credenciais]        ?
?                                  ?
? ? Status das Credenciais        ?
?                                  ?
? ?? Par de Negocia��o: BTC/USDT   ?
? ?? Timeframe: 5m                 ?
?                                  ?
? ?? Saldo Inicial: 1000 USDT      ?
? ?? Risco por Trade: 1.0%         ?
? ?? Stop Loss: 2.0%               ?
? ?? Take Profit: 3.0%             ?
?                                  ?
? ?? [Configura��es Avan�adas]     ?
?   ?? Usar Simula��o Realista     ?
?   ?? Usar Estrat�gia Melhorada   ?
?   ?? Mostrar Detalhes Execu��o   ?
?                                  ?
? ?? [Iniciar Bot]                 ?
? ?? [Parar Bot]                   ?
???????????????????????????????????
```

**Funcionalidades:**
- **Credenciais**: Carrega de `.env` ou arquivo local `binance_api.json`
- **Par�metros de Trading**: Configure o par, timeframe e estrat�gia
- **Gerenciamento de Risco**: Define saldo inicial, risco por trade, Stop Loss e Take Profit
- **Controles**: Inicia/para o bot
- **Modo Simula��o**: Testa estrat�gias sem risco real

---

#### **B. Se��o Principal**

##### **1. Status e M�tricas em Tempo Real**
Exibe indicadores-chave do bot:
- **Saldo Atual**: Montante em USDT dispon�vel
- **Saldo Inicial**: Refer�ncia para c�lculo de retorno
- **Posi��o Aberta**: Se h� uma compra ativa
- **Pre�o de Entrada**: Pre�o em que entrou na posi��o
- **Quantidade**: Quantidade de criptomoeda em posse

##### **2. Gr�fico Principal - An�lise T�cnica**
Mostra o pre�o com indicadores:
- **Pre�o (linha cinza)**: Cota��o em tempo real
- **M�dias M�veis** (MA 5 e MA 20): Sinais simples de compra/venda
- **Bollinger Bands**: Detec��o de sobrevenda/sobrecompra
- **Volume**: For�a das movimenta��es

##### **3. Gr�fico MACD**
Indicador de converg�ncia/diverg�ncia de m�dias m�veis para detectar mudan�as de tend�ncia

##### **4. Estrat�gia de IA**
An�lise avan�ada com m�ltiplos indicadores:
- RSI (Relative Strength Index)
- ADX (Average Directional Index)
- Volume Ratio
- Confian�a percentual do sinal

---

### ?? Fluxo de Funcionamento

```
???????????????????????????????????????????????????????
?              CICLO DE OPERA��O                       ?
???????????????????????????????????????????????????????
?                                                      ?
?  1??  Usuario clica "Iniciar Bot"                   ?
?      ?                                               ?
?  2??  Conecta ao WebSocket da Binance               ?
?      ?                                               ?
?  3??  Recebe dados de pre�o em tempo real (1m, 5m)  ?
?      ?                                               ?
?  4??  Armazena em DataFrame com 500 candles         ?
?      ?                                               ?
?  5??  Processa sinais de compra/venda               ?
?      ?? Estrat�gia Melhorada (IA): Alta confian�a  ?
?      ?? Fallback (M�dias M�veis): Simples          ?
?      ?                                               ?
?  6??  Verifica Stop Loss e Take Profit              ?
?      ?                                               ?
?  7??  Executa ordem (com simula��o de slippage)     ?
?      ?                                               ?
?  8??  Atualiza saldo e hist�rico de trades          ?
?      ?                                               ?
?  9??  Dashboard atualiza em tempo real               ?
?      ?                                               ?
?  ??  Repete a cada novo candle                      ?
?                                                      ?
???????????????????????????????????????????????????????
```

---

### ?? Hist�rico de Trades

Tabela mostrando cada trade executado:

| Timestamp | Par | Tipo | Pre�o | Quantidade | Valor | Taxas | Slippage | Lucro |
|-----------|-----|------|-------|-----------|-------|-------|----------|-------|
| 25/02/2026 14:30 | BTC/USDT | COMPRA | 42500.00 | 0.0235 | 1000.00 | 1.00 | 0.05% | - |
| 25/02/2026 14:45 | BTC/USDT | VENDA | 43000.00 | 0.0235 | 1010.50 | 1.01 | 0.08% | +8.49 |

---

### ?? Principais Fun��es

#### **executar_ordem(tipo, preco, quantidade)**
```python
- Tipo: 'COMPRA' ou 'VENDA'
- Executa com simula��o realista de:
  ? Slippage (desvio de pre�o)
  ? Taxas (comiss�o Binance: 0.1%)
  ? Execu��o parcial
  ? Volatilidade do ativo
```

#### **processar_sinais()**
```python
L�gica de decis�o:
1. Se posi��o aberta:
   - Verifica Stop Loss ? VENDE se pre�o cai 2%
   - Verifica Take Profit ? VENDE se lucra 4.5%

2. Se sem posi��o:
   - Usa IA melhorada para detectar setup de compra
   - Confian�a m�nima: 60%
   - RSI entre 30-75
   - ADX > 20 (tend�ncia clara)
   - Volume adequado

3. Fallback para M�dias M�veis se erro
```

#### **iniciar_conexao()**
```python
- Estabelece conex�o ThreadedWebsocketManager
- Inicia socket para cada par selecionado
- Callback processa cada novo candle
- Salva dados em arquivo tempor�rio JSON
```

---

### ?? Configura��es Avan�adas

```
???????????????????????????????????????????????????????
?           CONFIGURA��ES AVAN�ADAS                    ?
???????????????????????????????????????????????????????
?                                                      ?
? ?? Usar Simula��o Realista                          ?
?    ?? Ativa: slippage baseado em volatilidade       ?
?                                                      ?
? ?? Usar Estrat�gia Melhorada (IA)                   ?
?    ?? Desativa: cai para m�dias m�veis simples      ?
?                                                      ?
? ?? Mostrar Detalhes de Execu��o                     ?
?    ?? Exibe: slippage, taxas, execu��o parcial    ?
?                                                      ?
???????????????????????????????????????????????????????
```

---

## 2?? **viz_app.py** - Visualiza��o de Sinais da IA

### ?? Prop�sito
Interface de **backtesting e an�lise** de sinais gerados pela estrat�gia de IA.

### ??? Estrutura

```
???????????????????????????????????????
? Visualiza��o das Inten��es da IA    ?
???????????????????????????????????????
?                                      ?
? ?? Escolha o par:                   ?
?    [BTC/USDT] ?                    ?
?                                      ?
? ?? Fonte de dados:                  ?
?    [Mock] ?                        ?
?    ? Mock: Simula dados             ?
?    ? Binance: Dados reais           ?
?                                      ?
? ?? [Rodar an�lise agora]            ?
?                                      ?
? Aguardando an�lise...               ?
?                                      ?
???????????????????????????????????????
```

---

### ?? Resultados da An�lise

Ap�s clicar "Rodar an�lise":

#### **Tabela de Sinais**
```
timestamp       | close    | sinal
2026-02-25 10:30| 42500.50 | hold
2026-02-25 10:35| 42510.20 | buy  ? COMPRAR
2026-02-25 10:40| 42540.80 | hold
2026-02-25 10:45| 42580.10 | sell ? VENDER
...
```

#### **Gr�fico Interativo**
- **Linha cinza**: Pre�o do ativo
- **Tri�ngulo verde ?**: Sinal de COMPRA
- **Tri�ngulo vermelho ?**: Sinal de VENDA

---

### ?? Fluxo de An�lise

```
1?? User seleciona par e fonte
2?? Clica "Rodar an�lise"
3?? Loop: Para cada candle (50 em diante)
   ?? Passa janela de dados para IA
   ?? IA gera sinal: BUY, SELL ou HOLD
   ?? Armazena sinal no hist�rico
4?? Exibe tabela com �ltimos 50 sinais
5?? Plota gr�fico com pre�o e sinais
```

---

### ?? Filtros Interativos

```
Filtrar por sinal: [Todos ?]
                   ?? Todos
                   ?? buy
                   ?? sell
                   ?? hold
```

Permite analisar apenas um tipo de sinal sem refazer a an�lise.

---

## ?? Integra��o Entre as UIs

### **main_app.py** (Bot Ativo)
```
Tempo Real ? WebSocket Binance ? Estrat�gia IA ? Execu��o Automatizada
   ?                                                      ?
Dados ao vivo                                    Trades reais com $
```

### **viz_app.py** (Backtesting)
```
Dados Hist�ricos ? Estrat�gia IA ? An�lise de Sinais ? Gr�ficos
                                        ?
                              Testa sem executar trades
```

---

## ?? Detalhes T�cnicos

### **Estado da Sess�o (Session State)**
Persiste dados durante a sess�o do Streamlit:
```python
st.session_state = {
    'bot_data': {
        'saldo_usdt': 950.50,
        'saldo_inicial': 1000.00,
        'posicao_aberta': True,
        'preco_compra': 42500.00,
        'quantidade': 0.0235,
        'trades': [lista de trades],
        'dados_mercado': {BTC/USDT: DataFrame, ETH/USDT: DataFrame},
        'conexao_websocket': ThreadedWebsocketManager,
        'api_key': 'xxxxxxxxxxxx',
        'api_secret': 'xxxxxxxxxxxx'
    }
}
```

### **WebSocket Threading**
```python
ThreadedWebsocketManager executa em thread separada:
????????????????????????
?  Thread Principal    ?  (Streamlit UI)
?  st.rerun()          ?  
????????????????????????
           ?
           ? Callback
           ?
????????????????????????
?  WebSocket Thread    ?  (Recebe dados)
?  handle_socket_msg() ?
????????????????????????
```

### **Indicadores T�cnicos Calculados**

| Indicador | Fun��o | Sinal |
|-----------|--------|-------|
| **MA 5 / MA 20** | M�dias M�veis | MA 5 > MA 20 = COMPRA |
| **Bollinger Bands** | Volatilidade | Pre�o < banda inf = Sobrevenda |
| **MACD** | Momentum | Histograma positivo = COMPRA |
| **RSI** | For�a | RSI < 30 = Sobrevenda / RSI > 70 = Sobrecompra |
| **ADX** | Tend�ncia | ADX > 20 = Tend�ncia clara |
| **Volume** | Confirma��o | Volume alto = Confian�a |

---

## ?? Fluxo de Decis�o de Compra/Venda

### **Decis�o de COMPRA**
```
1. Sem posi��o aberta? ?
2. Confian�a IA > 60%? ?
3. RSI entre 30-75? ?
4. ADX > 20? ?
5. Volume > 1.0x m�dia? ?
   ?
   ? COMPRA: Calcula quantidade baseada em risco
```

### **Decis�o de VENDA**
```
Cen�rio 1: Stop Loss
?????????????????????
Pre�o < (Pre�o Compra � 0.98)?
   ? ? VENDA: "STOP LOSS ATIVADO"

Cen�rio 2: Take Profit
??????????????????????
Pre�o > (Pre�o Compra � 1.045)?
   ? ? VENDA: "TAKE PROFIT ATIVADO + Lucro %"

Cen�rio 3: Sinal IA
??????????????????
IA gera SELL + Confian�a > 50%?
   ? ? VENDA: "Sinal IA gerado"
```

---

## ?? Exemplo Pr�tico de Trade

```
? 14:30 - COMPRA
???????????????????????????????????????????
? Pre�o: 42500.00 USDT/BTC                ?
? Saldo: 1000.00 USDT                     ?
? Risco: 1.0%                             ?
? Stop Loss: 2%                           ?
?                                          ?
? C�lculo:                                 ?
? Risco = 1000 � 1% = 10 USDT             ?
? SL = 42500 � 2% = 850 USDT              ?
? Quantidade = 10 / (42500 � 2%) = 0.0235 BTC ?
?                                          ?
? ?? Investido: 1000 USDT                 ?
? ?? Taxa Binance: -1 USDT                ?
? ?? Slippage: -0.05%                     ?
???????????????????????????????????????????
? Saldo restante: 0.00 USDT               ?
? Posi��o: 0.0235 BTC                     ?
???????????????????????????????????????????

? 14:45 - VENDA (Take Profit)
???????????????????????????????????????????
? Pre�o: 43000.00 USDT/BTC                ?
? Quantidade: 0.0235 BTC                  ?
?                                          ?
? Recebido: 43000 � 0.0235 = 1010.50 USDT?
? Taxa Binance: -1.01 USDT                ?
? Slippage: -0.08%                        ?
???????????????????????????????????????????
? ?? Lucro L�quido: +8.49 USDT            ?
? ?? Retorno: +0.849%                     ?
? Saldo Final: 1008.49 USDT               ?
???????????????????????????????????????????
```

---

## ?? Como Usar

### **Iniciar o Bot**
```bash
# Terminal
streamlit run ui/main_app.py
```

### **Analisar Sinais da IA**
```bash
# Terminal (outra aba)
streamlit run ui/viz_app.py --logger.level=debug
```

### **Configura��o Recomendada**
1. ? Configure credenciais Binance
2. ? Ative "Usar Simula��o Realista"
3. ? Ative "Usar Estrat�gia Melhorada (IA)"
4. ? Defina saldo inicial conservador (1000-5000 USDT)
5. ? Risco por trade: 0.5-1.5%
6. ? Stop Loss: 2-3%
7. ? Take Profit: 3-5%
8. ? Teste primeiro em visualiza��o (viz_app.py)
9. ? Ap�s validar, execute em tempo real

---

## ?? Avisos Importantes

```
?? MODO SIMULA��O
?? N�o executa trades reais
?? Simula slippage, taxas, execu��o parcial
?? Ideal para validar estrat�gia

?? MODO REAL
?? Executa trades com dinheiro real
?? Use credenciais de sub-conta (seguran�a)
?? Comece com saldo pequeno
?? Monitore sempre o bot

?? RISCOS
?? Volatilidade pode gerar perdas
?? WebSocket pode cair (reconecta autom�tico)
?? Slippage reduz lucros
?? Sempre tenha stop loss ativo
```

---

## ?? M�tricas Monitoradas

```
Dashboard em tempo real mostra:

1. PERFORMANCE
   ?? Saldo Atual vs Saldo Inicial
   ?? Retorno Total (%)
   ?? Win Rate (% trades lucrativos)

2. POSI��O ATUAL
   ?? Status (Aberta/Fechada)
   ?? Pre�o de Entrada
   ?? Pre�o Atual
   ?? Lucro/Preju�zo (P&L)
   ?? Quantidade em Posse

3. EVENTOS
   ?? �ltimo sinal da IA
   ?? Confian�a do sinal
   ?? Raz�o do sinal
   ?? Timestamp

4. TRADES
   ?? N�mero total
   ?? �ltimos 10 trades
   ?? Lucro por trade
   ?? Hist�rico completo (CSV export)
```

---

## ?? Conclus�o

A UI do L-Trade-AI oferece:

? **main_app.py**: Trading automatizado em tempo real com IA
? **viz_app.py**: An�lise e backtesting de sinais
? **Risco Controlado**: Stop loss e take profit autom�ticos
? **Simula��o**: Teste sem risco real antes de operar
? **Indicadores Avan�ados**: MACD, Bollinger, RSI, ADX, Volume
? **Execu��o Realista**: Slippage, taxas e execu��o parcial simulados
? **Interface Intuitiva**: Streamlit para f�cil uso

---

*�ltima atualiza��o: 25/02/2026*
