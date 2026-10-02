# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import os
from datetime import datetime
import time
import matplotlib.pyplot as plt

try:
    from strategies.ai_strategy import executar_estrategia_ai
    from exchanges.mock import MockExchange
except ModuleNotFoundError:
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.dirname(__file__)))
    from strategies.ai_strategy import executar_estrategia_ai
    from exchanges.mock import MockExchange

st.title('VisualizaÃ§Ã£o das IntenÃ§Ãµes da IA - Cripto')

par = st.selectbox('Escolha o par de criptomoeda:', ['BTC/USDT', 'PEPE/USDT'])
fonte = st.selectbox('Fonte de dados:', ['Mock', 'Binance'])

if 'resultado' not in st.session_state:
    st.session_state['resultado'] = None
    st.session_state['raw_df'] = None

if st.button('Rodar anÃ¡lise agora'):
    with st.spinner('Analisando dados, por favor aguarde...'):
        try:
            if fonte == 'Binance':
                from exchanges.binance import BinanceExchange
                exchange = BinanceExchange()
                df = exchange.fetch_ohlcv(par)
            else:
                exchange = MockExchange()
                df = exchange.fetch_ohlcv(par)

            sinais = []
            posicao_aberta = False
            posicao_aberta = False
            sinais = []

            for i in range(50, len(df)):
                janela = df.iloc[:i]
                sinal = executar_estrategia_ai(janela, posicao_aberta)
                sinais.append(sinal)
                
                if sinal == 'buy':
                    posicao_aberta = True
                elif sinal == 'sell':
                    posicao_aberta = False
                else:
                    pass

            df = df.iloc[50:].copy()
            df['sinal'] = sinais

            # Armazena o resultado em cache de sessÃ£o
            st.session_state['resultado'] = df
            st.session_state['raw_df'] = df.copy()

            st.success("AnÃ¡lise concluÃ­da com sucesso!")

        except Exception as e:
            st.error(f"Erro durante anÃ¡lise: {e}")

# Filtros interativos que nÃ£o reiniciam a anÃ¡lise
if st.session_state['resultado'] is not None:
    df = st.session_state['resultado']

    # Filtro por sinal
    filtro = st.selectbox('Filtrar por sinal:', ['Todos', 'buy', 'sell', 'hold'])
    if filtro != 'Todos':
        df = df[df['sinal'] == filtro]

    st.dataframe(df.tail(50))

    # GrÃ¡fico de sinais
    st.subheader("GrÃ¡fico de PreÃ§o com Sinais")
    fig, ax = plt.subplots()
    ax.plot(df['timestamp'], df['close'], label='PreÃ§o', color='gray')

    buy_signals = df[df['sinal'] == 'buy']
    sell_signals = df[df['sinal'] == 'sell']
    ax.scatter(buy_signals['timestamp'], buy_signals['close'], color='green', label='Buy', marker='^')
    ax.scatter(sell_signals['timestamp'], sell_signals['close'], color='red', label='Sell', marker='v')

    ax.legend()
    plt.xticks(rotation=45)
    st.pyplot(fig)
