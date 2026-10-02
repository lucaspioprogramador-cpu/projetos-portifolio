"""
Configurações do projeto.
Carrega variáveis de ambiente de um arquivo .env se existir.
Também tenta carregar de binance_api.json para compatibilidade com código legado.
"""
import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Tenta carregar python-dotenv se disponÃ­vel
try:
    from dotenv import load_dotenv
    env_path = BASE_DIR / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv nÃ£o instalado, usa apenas variÃ¡veis de ambiente do sistema

# Carrega credenciais de variÃ¡veis de ambiente ou binance_api.json
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Se nÃ£o encontrou nas variÃ¡veis de ambiente, tenta carregar de binance_api.json
if not BINANCE_API_KEY or not BINANCE_API_SECRET:
    binance_json_path = BASE_DIR / "binance_api.json"
    if binance_json_path.exists():
        try:
            with open(binance_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                BINANCE_API_KEY = BINANCE_API_KEY or data.get("api_key", "")
                BINANCE_API_SECRET = BINANCE_API_SECRET or data.get("api_secret", "")
        except Exception:
            pass

DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "1m")


