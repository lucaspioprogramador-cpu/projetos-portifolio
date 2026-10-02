"""
FunÃ§Ãµes de gerenciamento de risco e tamanho de posiÃ§Ã£o.
"""


def position_size(balance: float, risk_pct: float, stop_pct: float, price: float) -> float:
    """
    Calcula o tamanho da posiÃ§Ã£o baseado em risco percentual e distÃ¢ncia de stop.
    """
    if stop_pct <= 0 or price <= 0 or risk_pct <= 0:
        return 0.0
    return (balance * risk_pct) / (price * stop_pct)


def apply_stop_take(entry_price: float, stop_pct: float, take_pct: float):
    """
    Calcula nÃ­veis de stop loss e take profit.
    """
    stop = entry_price * (1 - stop_pct)
    take = entry_price * (1 + take_pct)
    return stop, take


