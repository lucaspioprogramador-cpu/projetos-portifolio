from binance import ThreadedWebsocketManager
import time

API_KEY = ''  # Coloque sua API Key se necessÃ¡rio
API_SECRET = ''  # Coloque sua API Secret se necessÃ¡rio

symbol = 'BTCUSDT'
timeframe = '1m'

def handle_socket_message(msg):
    print('[TESTE] Mensagem recebida:', msg)

if __name__ == '__main__':
    print('[TESTE] Iniciando ThreadedWebsocketManager')
    twm = ThreadedWebsocketManager(api_key=API_KEY, api_secret=API_SECRET)
    twm.start()
    twm.start_kline_socket(symbol=symbol, interval=timeframe, callback=handle_socket_message)
    print('[TESTE] Socket iniciado para', symbol)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('[TESTE] Encerrando...')
        twm.stop()
