# Estado atual do projeto

O repositório está preparado para instalação local e testes. O dashboard pode ser iniciado com `python -m streamlit run ui/main_app.py` depois de instalar `requirements-dev.txt` e configurar `.env`.

## Limites importantes

- A aplicação recebe dados Binance, calcula sinais e **simula** fills e trades.
- Não há envio de ordens reais. O modo sem custos realistas também é apenas simulação.
- Saldo, posições e lucro apresentados são dados de simulação, não saldo de exchange.
- Não use resultados de backtest ou simulação como promessa de rentabilidade.

## Verificações antes de usar

1. Configure o ambiente seguindo [GUIA_RAPIDO_RODAR.md](GUIA_RAPIDO_RODAR.md).
2. Rode `python -m pytest -q`.
3. Revogue credenciais que tenham sido expostas e use novas chaves com permissões mínimas.
4. Defina `APP_PASSWORD` antes de qualquer acesso remoto; para produção, use autenticação e HTTPS gerenciados.

Este arquivo não afirma que o bot está rodando: o estado do processo depende da máquina em que ele for iniciado.
