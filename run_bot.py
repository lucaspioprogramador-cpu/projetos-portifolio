#!/usr/bin/env python
"""
Script para rodar o L-Trade-AI Bot
Adiciona a raiz do projeto ao sys.path
"""
import sys
import os
from pathlib import Path

# Adiciona raiz do projeto ao path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# Agora executa streamlit
import streamlit.web.cli as stcli

sys.argv = ["streamlit", "run", str(project_root / "ui" / "main_app.py"), "--logger.level=error"]

stcli.main()
