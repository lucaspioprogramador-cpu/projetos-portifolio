# ?? Guia Prático para Rodar o Bot L-Trade-AI

## ? Pré-requisitos Verificados
- ? Python 3.11.9 instalado
- ? Dependências instaladas (pandas, numpy, streamlit, plotly, etc)

## ?? Configuração

### Opção 1: Com Credenciais Reais (Recomendado para Produção)

#### Passo 1: Criar arquivo .env
```bash
# Copie o arquivo .env.example
cp .env.example .env

# Edite o arquivo .env com suas credenciais:
# BINANCE_API_KEY=sua_chave_aqui
# BINANCE_API_SECRET=seu_secret_aqui
```

#### Passo 2: Obter Credenciais Binance
1. Acesse: https://www.binance.com/en/account/api-management
2. Clique em "Create API"
3. Digite um nome (ex: "L-Trade-Bot")
4. Copie a API Key e API Secret
5. **Recomendado:** Crie uma sub-conta com permissões limitadas apenas para trading

#### Passo 3: Rodar o Bot
```bash
streamlit run ui/main_app.py
```

---

### Opção 2: Sem Credenciais (Modo Simulação/Mock)

Se não quiser configurar credenciais reais, você pode usar dados simulados:

```bash
# Roda direto sem credenciais
streamlit run ui/main_app.py
```

**Na interface:**
1. Não preencha credenciais
2. Ative "Usar Simulação Realista"
3. O bot usará dados históricos simulados

---

## ?? Executando o Bot

### Bot Principal (Trading em Tempo Real)
```bash
streamlit run ui/main_app.py
```

**Abre em:** http://localhost:8501

**Funcionalidades:**
- Monitoramento em tempo real
- Trading automatizado
- Dashboard com gráficos
- Histórico de trades
- Estatísticas de performance

---

### Visualização de Sinais (Backtesting)
```bash
streamlit run ui/viz_app.py
```

**Abre em:** http://localhost:8502

**Funcionalidades:**
- Análise de sinais históricos
- Teste de estratégias
- Sem risco (não executa trades)

---

## ?? Fluxo Completo de Uso

### 1?? **Primeira Execução**

```bash
# Abrir terminal
cd d:\L-Trade-AI

# Rodar o bot principal
streamlit run ui/main_app.py
```

A interface vai abrir em: **http://localhost:8501**

---

### 2?? **Configurar Credenciais**

**Opção A: Via Interface Streamlit (Fácil)**

```
???????????????????????????????????????
?  SIDEBAR - Configurações do Bot     ?
???????????????????????????????????????
?                                      ?
? ?? API Key Binance: [________________]?
? ?? API Secret: [___________________]?
?                                      ?
? ?? [Salvar Credenciais]             ?
? ?? [Carregar Credenciais]           ?
?                                      ?
? ? Credenciais carregadas do .env   ?
?                                      ?
???????????????????????????????????????
```

Passos:
1. Copie sua API Key da Binance
2. Cole no campo "API Key Binance"
3. Copie seu API Secret
4. Cole no campo "API Secret Binance"
5. Clique "?? Salvar Credenciais"
6. Credenciais são salvas em `binance_api.json`

**Opção B: Via Arquivo .env (Seguro)**

```bash
# 1. Crie arquivo .env na raiz
# 2. Adicione:
BINANCE_API_KEY=sua_chave_aqui
BINANCE_API_SECRET=seu_secret_aqui

# 3. Reinicie o bot
streamlit run ui/main_app.py

# Interface mostrará: ? Credenciais carregadas do arquivo .env
```

---

### 3?? **Configurar Parâmetros de Trading**

```
???????????????????????????????????????
?  SIDEBAR - Parâmetros               ?
???????????????????????????????????????
?                                      ?
? ?? Par de Negociação: [BTC/USDT ?] ?
? ?? Timeframe: [5m ?]                ?
?                                      ?
? ?? Saldo Inicial: [1000 USDT]      ?
? ?? Risco por Trade: [1.0 %]        ?
? ?? Stop Loss: [2.0 %]              ?
? ?? Take Profit: [3.0 %]            ?
?                                      ?
???????????????????????????????????????
```

**Valores Recomendados:**

| Parâmetro | Iniciante | Conservador | Agressivo |
|-----------|-----------|-------------|-----------|
| Saldo | 1,000 | 5,000 | 10,000+ |
| Risco/Trade | 0.5% | 1.0% | 2-3% |
| Stop Loss | 3% | 2% | 1.5% |
| Take Profit | 5% | 3% | 2% |

---

### 4?? **Configurações Avançadas**

```
?? [Configurações Avançadas] (expandir)

?? Usar Simulação Realista
   ?? Simula slippage, taxas, execução parcial
   
?? Usar Estratégia Melhorada (IA)
   ?? Usa múltiplos indicadores (RSI, ADX, Volume)
   
?? Mostrar Detalhes de Execução
   ?? Exibe slippage, taxas em cada trade
```

---

### 5?? **Iniciar o Bot**

```
SIDEBAR - Controles

?? [Iniciar Bot]  ? Clique para começar

Bot vai:
1. Conectar ao WebSocket da Binance
2. Receber preços em tempo real
3. Processar sinais da IA
4. Executar trades automaticamente
```

**Status esperado:**

```
Conexão com Binance estabelecida!
?? OPERANDO (status indicador)
?? Última atualização: 25/02/2026 14:30:45
```

---

### 6?? **Monitorar Dashboard**

```
MAIN AREA

???????????????? ???????????????? ???????????????? ????????????????
? ?? Saldo     ? ? ?? Saldo     ? ? ?? Lucro     ? ? ?? Tempo     ?
? USDT         ? ? Total        ? ? Total        ? ? Operando     ?
? US$ 1000.00  ? ? US$ 1000.50  ? ? US$ 0.50     ? ? 00:45:30     ?
???????????????? ???????????????? ???????????????? ????????????????

[Gráfico Principal - Preço em tempo real com MA 5 e MA 20]

[Gráfico IA - Análise técnica com indicadores]

[Gráfico MACD - Momentum do mercado]

?? Histórico de Trades | ?? Estatísticas | ?? Configurações Avançadas
```

---

## ?? Testando Antes de Usar Dinheiro Real

### Opção 1: Modo Simulação (Recomendado)

1. **Ative "Usar Simulação Realista"** no sidebar
2. **Defina um saldo pequeno** (500-1000 USDT)
3. **Deixe rodar por 1-2 horas** em modo simulado
4. **Analise os resultados** na aba "Estatísticas"
5. **Se performance for boa**, pode usar dinheiro real

---

### Opção 2: Backtesting Histórico

```bash
# Terminal novo
streamlit run ui/viz_app.py
```

**Interface:**
```
Escolha o par: [BTC/USDT ?]
Fonte de dados: [Mock ?]

?? [Rodar análise agora]

Aguardando análise...
?
Exibe tabela com sinais (buy/sell/hold)
Mostra gráfico com preços e marcadores
```

---

## ?? Troubleshooting

### Erro: "ModuleNotFoundError: No module named 'streamlit'"

```bash
# Reinstale as dependências
python -m pip install -r requirements.txt
```

---

### Erro: "Credenciais não informadas ou incompletas"

```bash
# Opção 1: Configure .env
echo BINANCE_API_KEY=sua_chave > .env
echo BINANCE_API_SECRET=seu_secret >> .env

# Opção 2: Use a interface
# Preencha os campos no sidebar e clique "Salvar Credenciais"
```

---

### Erro: "Nenhum evento WebSocket recebido após 10 segundos"

**Causa:** Conexão com Binance falhou

**Soluções:**
1. ? Verifique credenciais
2. ? Verifique conexão internet
3. ? Verifique se API está habilitada na Binance
4. ? Use VPN (alguns ISPs bloqueiam Binance)

---

### Erro: "AttributeError: 'NoneType' object has no attribute..."

**Causa:** Faltam dados históricos

**Solução:**
1. Aguarde alguns minutos para dados chegarem
2. Se o WebSocket estiver rodando, vai melhorar

---

## ?? Analisando Resultados

### Aba: Histórico de Trades

```
Timestamp          ? Operação ? Preço   ? Qtd      ? Valor   ? Lucro
??????????????????????????????????????????????????????????????????????
25/02 14:30:45     ? COMPRA   ? 42500.0 ? 0.0235   ? 997.75  ? -
25/02 14:45:12     ? VENDA    ? 43000.0 ? 0.0235   ? 1010.50 ? +11.74
```

---

### Aba: Estatísticas

```
?? Total de Trades: 15
? Trades Lucrativos: 10 (66.7%)
?? Maior Lucro: US$ 45.20
?? Maior Prejuízo: US$ -12.50
?? Lucro Total: US$ 128.45
?? Duração Média: 15.3 min

[Gráfico de Lucro Acumulado]
```

---

## ?? Próximos Passos

1. **Estude a documentação:**
   - [EXPLICACAO_UI.md](docs/EXPLICACAO_UI.md) - Interface completa
   - [EXPLICACAO_CODIGO_DETALHADA.md](docs/EXPLICACAO_CODIGO_DETALHADA.md) - Código linha por linha

2. **Teste em modo simulação:**
   - Deixe rodando por 24 horas
   - Analise estatísticas
   - Ajuste parâmetros se necessário

3. **Use dinheiro real (pequeno):**
   - Comece com 100-500 USDT
   - Acompanhe diariamente
   - Aumente o saldo conforme ganha confiança

4. **Customize a estratégia:**
   - Modifique parâmetros no sidebar
   - Teste diferentes pares
   - Combine indicadores

---

## ?? Precisa de Ajuda?

**Verificar status do bot:**
```bash
# Terminal
ps | grep streamlit

# Se não aparecer, restart
streamlit run ui/main_app.py
```

**Ver logs de erro:**
```bash
# Terminal mostra logs em tempo real
# Procure por [DEBUG] ou [ERROR]
```

**Parar o bot:**
```bash
# No terminal: Ctrl + C
```

---

## ?? Iniciando Agora!

### Comando Rápido:

```bash
cd d:\L-Trade-AI
streamlit run ui/main_app.py
```

Acesse: **http://localhost:8501**

**Boa sorte! ????**

---

*Último update: 25/02/2026*
*L-Trade-AI Bot - Trading Automatizado com IA*
