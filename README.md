# Crypto AI Simulator

Sistema de trading automatizado com IA para criptomoedas, integrado com múltiplas exchanges.

##  Pré-requisitos

- Python 3.8 ou superior
- Conta na Binance com API Key e Secret (opcional para testes com Mock)

##  Instalação

1. **Clone ou navegue até o diretório do projeto:**
   ```bash
   cd F:\JornadaAcademica\workspace\L-TRADE AI
   ```

2. **Crie um ambiente virtual (recomendado):**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows PowerShell
   ```

3. **Instale as dependências:**
   ```bash
   python -m pip install -r requirements.txt
   ```

4. **Configure as credenciais:**

   **Opção 1 - Arquivo .env (recomendado):**
   - Crie um arquivo `.env` na raiz do projeto
   - Adicione suas credenciais:
     ```
     BINANCE_API_KEY=sua_api_key_aqui
     BINANCE_API_SECRET=sua_api_secret_aqui
     DEFAULT_TIMEFRAME=1m
     ```

   **Opção 2 - Via interface do Streamlit:**
   - As credenciais podem ser informadas diretamente na interface
   - Elas serão salvas em `binance_api.json`

##  Como Usar

### Aplicação Principal (Bot de Trading)

Execute o aplicativo principal:
```bash
streamlit run ui/main_app.py
```

**Funcionalidades:**
- Monitoramento em tempo real via WebSocket
- Trading automatizado com estratégias de IA
- Controle de risco (Stop Loss, Take Profit)
- Visualização de gráficos e métricas
- Relatórios de performance

### Visualização de Sinais

Execute o aplicativo de visualização:
```bash
streamlit run ui/viz_app.py
```

**Funcionalidades:**
- Análise histórica de estratégias
- Visualização de sinais de compra/venda
- Teste com dados Mock ou Binance

## 📁 Estrutura do Projeto

```
project/
├── core/              # Módulos principais
│   ├── engine.py      # Engine de execução
│   ├── risk.py        # Gestão de risco
│   ├── execution.py   # Execução de ordens
│   ├── state.py       # Gerenciamento de estado
│   ├── ws.py          # WebSocket manager
│   └── data.py        # Normalização de dados
├── exchanges/         # Integrações com exchanges
│   ├── base.py        # Classe abstrata Exchange
│   ├── binance.py     # Integração Binance
│   └── mock.py        # Exchange mock para testes
├── strategies/        # Estratégias de trading
│   ├── base.py        # Interface de estratégia
│   ├── ai_strategy.py
│   └── ai_strategy_corrigido.py
├── backtest/          # Sistema de backtesting
│   ├── runner.py
│   └── metrics.py
├── db/                # Banco de dados
│   ├── database.py
│   └── migrations.sql
├── ui/                # Interfaces Streamlit
│   ├── main_app.py    # App principal
│   └── viz_app.py     # Visualização
├── config/            # Configurações
│   └── settings.py
└── relatorios/        # Relatórios gerados
```

## ⚙️ Configuração

### Variáveis de Ambiente (.env)

- `BINANCE_API_KEY`: Sua API Key da Binance
- `BINANCE_API_SECRET`: Sua API Secret da Binance
- `DEFAULT_TIMEFRAME`: Timeframe padrão (1m, 5m, 15m, 30m, 1h, 4h)

### Parâmetros de Trading

Configure na interface do Streamlit:
- **Saldo Inicial**: Capital inicial em USDT
- **Risco por Trade**: Percentual de risco por operação (0.1% - 5%)
- **Stop Loss**: Percentual de stop loss (0.1% - 10%)
- **Take Profit**: Percentual de take profit (0.1% - 10%)

## 🔒 Segurança

⚠️ **IMPORTANTE:**
- Nunca compartilhe suas credenciais da API
- Use apenas permissões de leitura para testes
- O arquivo `.env` e `binance_api.json` estão no `.gitignore` (não são commitados)
- Para produção, considere usar variáveis de ambiente do sistema

## 📊 Estratégias Disponíveis

1. **AI Strategy (Básica)**: Random Forest com indicadores básicos
2. **AI Strategy Corrigida**: Versão avançada com Bollinger Bands, MACD, OBV

## 🐛 Troubleshooting

**Erro: "pip não é reconhecido"**
```bash
python -m pip install -r requirements.txt
```

**Erro: "streamlit não é reconhecido"**
```bash
python -m pip install streamlit
python -m streamlit run ui/main_app.py
```

**Erro de importação de módulos**
- Certifique-se de estar na raiz do projeto
- Verifique se todos os `__init__.py` existem nas pastas

## 📝 Notas

- O sistema usa WebSocket para dados em tempo real
- Dados históricos são armazenados localmente
- Relatórios são salvos em `relatorios/`
- O banco de dados SQLite é criado automaticamente em `simulacao.db`

## 🤝 Contribuindo

Este é um projeto em desenvolvimento. Sinta-se à vontade para sugerir melhorias!

## 📄 Licença

Este projeto é para fins educacionais e de pesquisa.

# projetos
