# Guia rápido

## Requisitos

- Python 3.10 ou superior.
- O app usa endpoints públicos Binance; não precisa de API key e **não envia ordens reais**.

## Instalar e configurar

```powershell
git clone https://github.com/lucaspioprogramador-cpu/projetos-portifolio.git
cd projetos-portifolio
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edite `.env` localmente. Nunca comite esse arquivo. Configure `APP_PASSWORD` com uma senha forte antes de disponibilizar o dashboard fora do computador local. As credenciais Binance podem ser fornecidas por variáveis de ambiente/`.env` ou digitadas na interface para uso somente durante a sessão.

## Iniciar o dashboard

```powershell
python -m streamlit run ui/main_app.py
```

Abra `http://localhost:8501`. O dashboard opera em modo simulado; seus saldos e trades são valores locais de simulação, não representam carteira nem ordens executadas na Binance. O controle de custos pode incluir taxas, spread, slippage e fills parciais.

A opção de custos simples também continua sendo simulação. Não há execução real de ordens implementada.

## Testes

```powershell
python -m pytest -q
```

## Segurança

- Revogue qualquer chave/token que tenha sido exposto anteriormente e crie credenciais novas com permissões mínimas.
- Nunca habilite permissão de saque.
- `APP_PASSWORD` é uma barreira básica para uma única senha; em hospedagem pública, prefira autenticação gerenciada por provedor/proxy e HTTPS.
- Não exponha o servidor Streamlit diretamente na internet.
- Veja [README.md](README.md) para detalhes e limitações.
