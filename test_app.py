import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

import streamlit as st

st.set_page_config(page_title="Bot Binance - Teste", layout="wide")
st.title("?? Bot Binance - Teste de Conexão")

st.write("? Aplicação está rodando!")
st.write(f"Python: {sys.version}")

try:
    from config.settings import BINANCE_API_KEY, BINANCE_API_SECRET
    st.success("? Config importada")
except Exception as e:
    st.error(f"Erro ao importar config: {e}")

try:
    from core.execution import executar_ordem_simulada
    st.success("? Core importado")
except Exception as e:
    st.error(f"Erro ao importar core: {e}")

try:
    from strategies.ai_strategy_melhorada import executar_estrategia_ai_melhorada
    st.success("? Estratégia IA importada")
except Exception as e:
    st.error(f"Erro ao importar estratégia: {e}")

st.info("Se todos os ? aparecerem, o ambiente está OK!")
st.info("Agora pode rodar: streamlit run ui/main_app.py")
