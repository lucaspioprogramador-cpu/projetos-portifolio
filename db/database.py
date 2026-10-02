import sqlite3
from datetime import datetime, timezone
from config.settings import BASE_DIR
import pandas as pd


def conectar():
    conn = sqlite3.connect(BASE_DIR / 'simulacao.db', timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")  # melhor performance com multiplas leituras
    conn.execute("PRAGMA busy_timeout=5000")

    # FIX: colunas da tabela trades alinhadas com o que registrar_trade() insere
    conn.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol               TEXT,
            tipo                 TEXT,
            preco_solicitado     REAL,
            preco_execucao       REAL,
            quantidade_solicitada REAL,
            quantidade_executada  REAL,
            valor_total          REAL,
            taxas                REAL,
            slippage_pct         REAL,
            valor_liquido        REAL,
            lucro                REAL,
            lucro_liquido        REAL,
            retorno              REAL,
            retorno_liquido      REAL,
            timestamp            TEXT
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS candles (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol    TEXT,
            timestamp TEXT,
            open      REAL,
            high      REAL,
            low       REAL,
            close     REAL,
            volume    REAL,
            timeframe TEXT,
            UNIQUE(symbol, timestamp, timeframe)  -- evita candles duplicados
        )
    ''')

    conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol_timestamp ON trades(symbol, timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_candles_symbol_timeframe_timestamp ON candles(symbol, timeframe, timestamp)")

    conn.commit()
    return conn


def registrar_trade(trade: dict):
    """Persiste um trade no banco. Campos de lucro sao opcionais (so existem em vendas)."""
    conn = conectar()
    try:
        conn.execute('''
            INSERT INTO trades (
                symbol, tipo,
                preco_solicitado, preco_execucao,
                quantidade_solicitada, quantidade_executada,
                valor_total, taxas, slippage_pct, valor_liquido,
                lucro, lucro_liquido, retorno, retorno_liquido,
                timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade.get('symbol'),
            trade.get('tipo'),
            trade.get('preco_solicitado'),
            trade.get('preco_execucao'),
            trade.get('quantidade_solicitada'),
            trade.get('quantidade_executada'),
            trade.get('valor_total'),
            trade.get('taxas'),
            trade.get('slippage_pct'),
            trade.get('valor_liquido'),
            trade.get('lucro'),           # None em compras — salvo como NULL
            trade.get('lucro_liquido'),
            trade.get('retorno'),
            trade.get('retorno_liquido'),
            str(trade.get('timestamp', datetime.now(timezone.utc).isoformat())),
        ))
        conn.commit()
    finally:
        conn.close()


def registrar_candle(symbol, timestamp, open, high, low, close, volume, timeframe):
    """Insere um candle ignorando duplicatas (mesmo symbol + timestamp + timeframe)."""
    conn = conectar()
    try:
        conn.execute('''
            INSERT OR IGNORE INTO candles
                (symbol, timestamp, open, high, low, close, volume, timeframe)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symbol.replace('/', ''), str(timestamp), open, high, low, close, volume, timeframe))
        conn.commit()
    finally:
        conn.close()


def registrar_candles(symbol: str, candles: list[dict]) -> None:
    """Persiste vários candles numa transação única, ignorando duplicatas."""
    if not candles:
        return
    sym = symbol.replace('/', '')
    rows = [
        (sym, str(candle['timestamp']), candle['open'], candle['high'],
         candle['low'], candle['close'], candle['volume'], candle['timeframe'])
        for candle in candles
    ]
    conn = conectar()
    try:
        conn.executemany(
            '''INSERT OR IGNORE INTO candles
               (symbol, timestamp, open, high, low, close, volume, timeframe)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def get_candles(symbol: str, limit: int = None, since: str = None, timeframe: str = None) -> pd.DataFrame:
    """
    Retorna candles do banco como DataFrame ordenado por timestamp ASC.

    symbol   : com ou sem slash (ex: 'BTCUSDT' ou 'BTC/USDT') — normalizado internamente.
    limit    : numero maximo de linhas (as mais recentes).
    since    : filtro de data minima, formato 'YYYY-MM-DD HH:MM:SS'.
    timeframe: filtro opcional de timeframe.
    """
    conn = conectar()
    try:
        sym = symbol.replace('/', '')
        params = [sym]
        q = "SELECT timestamp, open, high, low, close, volume, timeframe FROM candles WHERE symbol = ?"

        if timeframe:
            q += " AND timeframe = ?"
            params.append(timeframe)
        if since:
            q += " AND timestamp >= ?"
            params.append(since)

        # Se ha limite, pega os mais recentes via subquery e reordena ASC
        if limit:
            q = f"SELECT * FROM ({q} ORDER BY timestamp DESC LIMIT {int(limit)}) ORDER BY timestamp ASC"
        else:
            q += " ORDER BY timestamp ASC"

        cursor = conn.cursor()
        cursor.execute(q, tuple(params))
        rows = cursor.fetchall()
    finally:
        conn.close()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'timeframe'])
    try:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    except Exception:
        pass
    return df


def get_trades(symbol: str = None, since: str = None) -> pd.DataFrame:
    """
    Retorna trades do banco como DataFrame.
    symbol : filtro por par (ex: 'BTC/USDT'). None = todos os pares.
    since  : filtro de data minima 'YYYY-MM-DD HH:MM:SS'. None = todos.
    """
    conn = conectar()
    try:
        params = []
        q = (
            "SELECT symbol, tipo, preco_execucao, quantidade_executada, "
            "valor_liquido, lucro, retorno, timestamp "
            "FROM trades WHERE 1=1"
        )
        if symbol:
            q += " AND symbol = ?"
            params.append(symbol)
        if since:
            q += " AND timestamp >= ?"
            params.append(since)
        q += " ORDER BY timestamp ASC"

        cursor = conn.cursor()
        cursor.execute(q, tuple(params))
        rows = cursor.fetchall()
    finally:
        conn.close()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=[
        'symbol', 'tipo', 'preco_execucao', 'quantidade_executada',
        'valor_liquido', 'lucro', 'retorno', 'timestamp'
    ])
    try:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    except Exception:
        pass
    return df


def count_trades_e_candles() -> tuple:
    """Retorna (total_trades, total_candles)."""
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trades")
        trades_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM candles")
        candles_count = cursor.fetchone()[0]
    finally:
        conn.close()
    return trades_count, candles_count