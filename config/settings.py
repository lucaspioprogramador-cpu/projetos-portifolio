"""
Configurações do projeto.
Carrega variáveis de ambiente de um arquivo .env se existir.
"""
import os
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

DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "1m")


