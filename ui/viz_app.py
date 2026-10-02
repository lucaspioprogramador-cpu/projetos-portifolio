import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

try:
    from exchanges.mock import MockExchange
    from strategies.ai_strategy import executar_estrategia_ai
except ModuleNotFoundError:
    import os
    import sys
    sys.path.append(os.path.abspath(os.path.dirname(__file__)))
    from exchanges.mock import MockExchange
    from strategies.ai_strategy import executar_estrategia_ai

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

        except Exception as e:  # noqa: BLE001 - converte falhas de rede/modelo em erro visível na UI
            st.error(f"Erro durante anÃ¡lise: {e}")

# Filtros interativos que nÃ£o reiniciam a anÃ¡lise
if st.session_state['resultado'] is not None:
    df = st.session_state['resultado']

    # Filtro por sinal
    filtro = st.selectbox('Filtrar por sinal:', ['Todos', 'buy', 'sell', 'hold'])
    tabela_df = df
    if filtro != 'Todos':
        tabela_df = df[df['sinal'] == filtro]

    st.dataframe(tabela_df.tail(50), use_container_width=True)

    # Gráfico interativo de preço, volume e sinais.
    st.subheader("Gráfico de preço e sinais")
    show_volume = st.toggle("Mostrar volume", value=True, key="viz_show_volume")
    show_average = st.toggle("Média móvel de 20 candles", value=True, key="viz_show_ma")

    if not df.empty:
        _change = (float(df['close'].iloc[-1]) / float(df['close'].iloc[0]) - 1) * 100
        _metrics = st.columns(4)
        _metrics[0].metric("Último preço", f"{df['close'].iloc[-1]:,.4f}")
        _metrics[1].metric("Variação", f"{_change:+.2f}%")
        _metrics[2].metric("Compras", int((df['sinal'] == 'buy').sum()))
        _metrics[3].metric("Vendas", int((df['sinal'] == 'sell').sum()))

        _volume_row = 2 if show_volume else None
        if _volume_row:
            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                row_heights=[0.75, 0.25], subplot_titles=("Preço OHLC", "Volume"),
            )
        else:
            fig = go.Figure()

        def _add_trace(trace, row=1):
            if show_volume:
                fig.add_trace(trace, row=row, col=1)
            else:
                fig.add_trace(trace)

        if {'open', 'high', 'low', 'close'}.issubset(df.columns):
            _add_trace(go.Candlestick(
                x=df['timestamp'], open=df['open'], high=df['high'],
                low=df['low'], close=df['close'], name='OHLC',
                increasing_line_color='#2dd4a7', decreasing_line_color='#ff647c',
                increasing_fillcolor='rgba(45,212,167,0.7)',
                decreasing_fillcolor='rgba(255,100,124,0.7)',
            ))
        else:
            _add_trace(go.Scatter(
                x=df['timestamp'], y=df['close'], name='Fechamento',
                mode='lines', line={'color': '#38d9c0', 'width': 2},
            ))

        if show_average:
            _add_trace(go.Scatter(
                x=df['timestamp'], y=df['close'].rolling(20, min_periods=1).mean(),
                name='MM 20', mode='lines', line={'color': '#ffd166', 'width': 1.5},
            ))

        buy_signals = df[df['sinal'] == 'buy']
        sell_signals = df[df['sinal'] == 'sell']
        if not buy_signals.empty:
            _add_trace(go.Scatter(
                x=buy_signals['timestamp'], y=buy_signals['close'], name='Compra',
                mode='markers', marker={'symbol': 'triangle-up', 'size': 13, 'color': '#2dd4a7', 'line': {'color': 'white', 'width': 1}},
                hovertemplate='COMPRA<br>%{x}<br>%{y:,.4f}<extra></extra>',
            ))
        if not sell_signals.empty:
            _add_trace(go.Scatter(
                x=sell_signals['timestamp'], y=sell_signals['close'], name='Venda',
                mode='markers', marker={'symbol': 'triangle-down', 'size': 13, 'color': '#ff647c', 'line': {'color': 'white', 'width': 1}},
                hovertemplate='VENDA<br>%{x}<br>%{y:,.4f}<extra></extra>',
            ))

        if show_volume and 'volume' in df.columns:
            colors = ['#2dd4a7' if c >= o else '#ff647c' for o, c in zip(df['open'], df['close'])]
            fig.add_trace(go.Bar(
                x=df['timestamp'], y=df['volume'], name='Volume', marker_color=colors,
                hovertemplate='Volume: %{y:,.4g}<extra></extra>',
            ), row=2, col=1)

        fig.update_layout(
            template='plotly_dark', height=620,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='#0b1220',
            hovermode='x unified',
            legend={'orientation': 'h', 'yanchor': 'bottom', 'y': 1.02, 'xanchor': 'left', 'x': 0},
            margin={'l': 12, 'r': 20, 't': 48, 'b': 16},
            xaxis_rangeslider_visible=False,
        )
        fig.update_xaxes(showgrid=True, gridcolor='rgba(148,163,184,0.10)', rangeslider_visible=False)
        fig.update_yaxes(showgrid=True, gridcolor='rgba(148,163,184,0.10)', side='right')
        st.plotly_chart(fig, use_container_width=True, config={'displaylogo': False, 'scrollZoom': True, 'responsive': True})
