# Crypto Market Simulator

Sistema de trading automatizado com IA para criptomoedas, integrado com múltiplas exchanges.

##  Pré-requisitos

- Python 3.10 ou superior
- Acesso à internet para consultar candles públicos da Binance

##  Instalação

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/lucaspioprogramador-cpu/projetos-portifolio.git
   cd projetos-portifolio
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

4. **Configure as opções locais (opcional):**

   **Opção 1 - Arquivo .env (recomendado):**
    - Copie `.env.example` para `.env` e defina senha/timeframe localmente:
       ```dotenv
       DEFAULT_TIMEFRAME=1m
       APP_PASSWORD=uma_senha_forte_para_o_dashboard
       BOT_STATE_DIR=.bot_state
       ```

    Não são necessárias API keys Binance; a aplicação usa dados públicos. O token Telegram, se usado, vale apenas para a sessão.

5. **Execute os testes:**
   ```bash
   python -m pip install -r requirements-dev.txt
   python -m pytest -q
   ```

##  Como Usar

Para ressalvas sobre guias históricos da pasta `docs/`, consulte [docs/ESCOPO_ATUAL.md](docs/ESCOPO_ATUAL.md).

### Aplicação Principal (Bot de Trading)

Execute o aplicativo principal:
```bash
streamlit run ui/main_app.py
```

**Funcionalidades em modo de simulação:**
- Monitoramento em tempo real via WebSocket
- Simulação de sinais e operações com estratégia de IA
- Controle de risco (Stop Loss, Take Profit)
- Visualização de gráficos e métricas
- Relatórios de performance

Se o binário do scikit-learn não puder carregar no sistema, a interface informa e usa uma regra determinística de indicadores como fallback. Esse fallback não é um modelo de IA treinado nem foi validado como estratégia rentável.

### Visualização de Sinais

Execute o aplicativo de visualização:
```bash
streamlit run ui/viz_app.py
```

**Funcionalidades em modo de simulação:**
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

### Variáveis locais (.env)

- `DEFAULT_TIMEFRAME`: timeframe padrão (1m, 5m, 15m, 30m, 1h, 4h)
- `APP_PASSWORD`: senha básica opcional para proteger o dashboard local
- `BOT_STATE_DIR`: diretório gravável para snapshots locais de simulação (padrão `.bot_state`)

### Parâmetros de Trading

Configure na interface do Streamlit:
- **Saldo Inicial**: Capital inicial em USDT
- **Risco por Trade**: Percentual de risco por operação (0.1% - 5%)
- **Stop Loss**: Percentual de stop loss (0.1% - 10%)
- **Take Profit**: Percentual de take profit (0.1% - 10%)

## 🔒 Segurança

⚠️ **IMPORTANTE:**
- Não insira credenciais Binance: este protótipo não precisa delas
- Este projeto **não envia ordens reais** para a Binance; o dashboard deve permanecer em modo simulado
- Não crie API keys Binance para este protótipo; ele usa apenas dados públicos
- O arquivo `.env`, os arquivos JSON legados e os dados locais estão no `.gitignore` (não são commitados)
- O dashboard não está protegido por padrão. Configure `APP_PASSWORD` para a barreira de acesso básica ou use autenticação gerenciada por proxy/identidade antes de expor a aplicação na internet
- `APP_PASSWORD` protege o acesso à UI, mas não substitui um provedor de identidade, rate limiting ou HTTPS
- Nunca execute o bot com dinheiro real sem uma implementação auditada de ordens, reconciliação de saldo e testes em testnet

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
