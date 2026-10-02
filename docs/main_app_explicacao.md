# Explicação detalhada de `ui/main_app.py`

Aplicação Streamlit que monitora pares da Binance em tempo real, calcula sinais (IA ou médias móveis), simula execuções e exibe dashboards. Abaixo um guia linha a linha (agrupado por blocos para legibilidade).

## Estrutura geral
- 1-14: Imports (Streamlit, pandas, numpy, time/datetime, pytz, plotly, binance SDK, threading, os/json/tempfile).
- 15-27: Lista de pares `symbols`.
- 29-35: Configuração de página/título Streamlit e fuso horário BR.

## Sidebar / Entrada de usuário
- 37-83: Sidebar com header; funções `salvar_credenciais`/`carregar_credenciais` e feedback visual.
- 84-97: Inputs de par (`symbol`), timeframe, saldo inicial, risco, SL/TP.
- 98-106: Expander “Configurações Avançadas” (flags de simulação/estratégia/detalhes execução).
- 107-110: Grava flags no `st.session_state`.
- 112-117: Botões Start/Stop que setam `st.session_state['bot_running']`.

## Estado da sessão
- 118-120: Inicializa `bot_running` se não existir.
- 122-157: `ensure_bot_state()` cria `bot_data` com defaults (saldos, posição, trades, dados de mercado, conexões, eventos) e sincroniza `saldo_inicial`/`saldo_usdt` quando o usuário altera o saldo na UI (sem sobrescrever posições abertas). Chamada em 157.
- 159-162: Estruturas globais para WebSocket (`websocket_data_global`, locks).

## Utilidades e cálculo
- 163-169: `now_brazil` e `format_time`.
- 170-171: `calcular_posicao` (tamanho da posição pelo risco e stop).

## Execução de ordens
- 173-248: `executar_ordem` recebe tipo/preço/quantidade, usa simulação (`core.execution.executar_ordem_simulada`) ou execução simples, aplica taxas/slippage, atualiza `bot_data` (saldos, posição, valor investido), calcula lucro em vendas e registra trade no histórico.

## Atualização de mercado
- 250-262: `atualizar_dados_mercado` concatena novo kline no DataFrame do símbolo e incrementa contador de eventos.

## Conexão Binance
- 263-325: `iniciar_conexao` cria `Client` e `ThreadedWebsocketManager`, abre sockets de kline para cada par selecionado e salva mensagens em arquivos temporários (proteção com lock). Em caso de erro, loga e mostra erro no UI.
- 327-331: `parar_conexao` encerra websockets.

## Indicadores
- 332-345: `calcular_macd`.
- 347-456: `processar_sinais`:
  - Verifica stop loss/take profit.
  - Se IA ativada: importa `strategies.ai_strategy_melhorada.executar_estrategia_ai_melhorada`, monta config, chama estratégia e toma decisão de compra/venda com toasts; salva último sinal.
  - Fallback: cruzamento de médias móveis simples (MA 5/20) para comprar/vender.

## UI principal e status
- 457-465: Cria placeholders de gráficos para evitar flicker.
- 467-480: Monta colunas de status; calcula `saldo_usdt`, valor da posição aberta e `saldo_total`.
- 481-486: Coluna 1: métricas de saldo e posição.
- 487-505: Coluna 2: lucro/prejuízo total (realizado + não realizado) vs saldo inicial.
- 506-513: Coluna 3: tempo operando desde início da conexão.
- 514-516: Coluna 4: status do bot (operando/parado).

## Gráfico principal
- 518-704: Gráfico de preço principal do par selecionado:
  - Prepara DataFrame, garante timestamp, remove NaN.
  - Desenha linha/área do preço; inclui MAs se existirem.
  - Depois (mais abaixo) também renderiza gráficos IA/MACD e mostra indicadores atuais.
  - Se não há dados, mostra expander com tutorial de interpretação.

## Tabs de trades e estatísticas
- 724-779: Tab “Histórico de Trades”: tabela com colunas configuráveis (preço exec, qty, valor, slippage/taxas se habilitado, lucro/retorno/duração). Resumo de custos se detalhado.
- 780-823: Tab “Estatísticas”: métricas agregadas de trades fechados (total, win rate, maior lucro/prejuízo, lucro total, duração média) e gráfico de lucro acumulado.
- 824-827: Tab “Configurações Avançadas” placeholder.

## Múltiplos pares e mini-painéis
- 828-833: `multiselect` de pares para monitorar.
- 835-856: Controle de conexão: inicia websocket ao apertar Start (garantindo uma vez), mostra status; para conexão ao parar o bot.

## Loop de atualização e sinais
- 857-965: Rotina que:
  - Inicializa controles de atualização.
  - Lê arquivos temporários por par, transforma timestamps, injeta em `bot_data['dados_mercado']`, zera arquivo.
  - Se bot rodando, processa sinais a cada 5s ou quando há novos dados, atualiza timestamp e mostra próximo ciclo; faz `st.rerun()` se dados novos ou >10s.
  - Para cada par selecionado: painel de debug (json + DataFrame), status visual, mini-gráfico com preço recente e últimas leituras.

## Alertas
- 971-976: Se bot rodando e nenhum evento WebSocket após 10s desde início, mostra erro de conexão/formato/credenciais.

## Notas adicionais
- A aplicação usa arquivos temporários para desacoplar o callback do WebSocket da UI Streamlit.
- Diversos avisos do Streamlit sobre `use_container_width=True` (deprecated); trocar por `width='stretch'` quando desejar.
- Dependências externas: `core.execution.executar_ordem_simulada` (simulação realista) e `strategies.ai_strategy_melhorada.executar_estrategia_ai_melhorada` (sinais IA).

## Como ler junto com o código
Use o mapa de faixas acima para navegar no arquivo. Cada bloco do código está comentado ou autoexplicativo; combine esta referência com o editor para localizar rapidamente a lógica desejada.

