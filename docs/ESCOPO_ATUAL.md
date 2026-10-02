# Escopo e segurança atuais

Leia este aviso antes dos guias antigos da pasta `docs/`: alguns descrevem versões anteriores do programa e podem mencionar gravação de credenciais ou execução real. Essas descrições não correspondem ao código atual.

- O aplicativo atual obtém dados públicos/mercado e simula operações; **não envia ordens reais**.
- Nenhuma credencial Binance é necessária ou solicitada; os dados usados são públicos. O token Telegram, se configurado, é mantido apenas na sessão. As opções do processo vêm de variáveis de ambiente ou `.env` local.
- O snapshot de saldo/posições é local e isolado por sessão Streamlit; não é fonte de verdade de uma exchange nem é compartilhado intencionalmente entre usuários.
- Não há autenticação gerenciada nem proteção contra força bruta na senha opcional `APP_PASSWORD`; não exponha o servidor diretamente à internet.
- Os saldos, ordens e lucros são simulações, não equivalem à carteira, execução ou rentabilidade numa exchange.
- Se scikit-learn não carregar, a interface pode usar um fallback determinístico de indicadores; não é ML treinado nem tem garantia de performance.
- Revogue credenciais que tenham sido publicadas ou compartilhadas anteriormente.

Use [README.md](../README.md) e [GUIA_RAPIDO_RODAR.md](../GUIA_RAPIDO_RODAR.md) como instruções atuais.
