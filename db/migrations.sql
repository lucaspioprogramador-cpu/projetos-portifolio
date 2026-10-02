-- Criação inicial da tabela de trades
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    side TEXT,
    amount REAL,
    price REAL,
    timestamp TEXT
);

