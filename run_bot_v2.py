# -*- coding: utf-8 -*-
"""
Script para rodar L-Trade-AI Bot
Configura o ambiente Python corretamente
"""
import sys
import os
from pathlib import Path

# Adiciona raiz do projeto ao path
project_root = str(Path(__file__).parent.absolute())
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configura variáveis de ambiente
os.environ['PYTHONPATH'] = project_root

print("=" * 50)
print("L-TRADE-AI BOT - INICIANDO")
print("=" * 50)
print("Raiz do projeto: " + project_root)
print("Python: " + sys.version.split()[0])
print()

# Testa imports
print("Testando imports...")
try:
    from config.settings import DEFAULT_TIMEFRAME
    print(f"OK - Config carregada (timeframe padrão: {DEFAULT_TIMEFRAME})")
except Exception as e:
    print("ERRO ao carregar config: " + str(e))
    sys.exit(1)

try:
    from core.execution import executar_ordem_simulada
    print("OK - Core carregado")
except Exception as e:
    print("ERRO ao carregar core: " + str(e))
    sys.exit(1)

try:
    import streamlit
    print("OK - Streamlit carregado")
except Exception as e:
    print("ERRO ao carregar streamlit: " + str(e))
    sys.exit(1)

print()
print("Iniciando aplicacao Streamlit...")
print("Acesse: http://localhost:8501")
print()

# Executa streamlit
import subprocess
cmd = [
    sys.executable, 
    "-m", 
    "streamlit", 
    "run", 
    os.path.join(project_root, "ui", "main_app.py"),
    "--client.showErrorDetails=true"
]

os.chdir(project_root)
subprocess.run(cmd)
