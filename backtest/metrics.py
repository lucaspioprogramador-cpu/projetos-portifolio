"""
MÃ©tricas bÃ¡sicas de backtest.
"""
import pandas as pd


def basic_metrics(
    df: pd.DataFrame,
    initial_balance: float | None = None,
    periods_per_year: float = 365.0,
) -> dict[str, float | int]:
    """Calcula retorno, drawdown, Sharpe por período e taxa de acerto."""
    if "portfolio_value" not in df.columns:
        raise ValueError("O DataFrame deve ser produzido por run_backtest")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year deve ser positivo")
    if initial_balance is None:
        initial_balance = float(df.attrs.get("initial_balance", 10_000.0))
    if initial_balance <= 0:
        raise ValueError("initial_balance deve ser positivo")
    if df.empty:
        return {
            "num_trades": 0,
            "win_rate": 0.0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "final_equity": initial_balance,
        }

    equity = df["portfolio_value"].astype(float)
    returns = equity.pct_change().replace([float("inf"), float("-inf")], 0).fillna(0)
    returns.iloc[0] = equity.iloc[0] / initial_balance - 1
    peak = equity.cummax().clip(lower=initial_balance)
    drawdown = equity / peak - 1
    closed_returns = df.get("trade_return", pd.Series(dtype=float)).dropna().astype(float)
    volatility = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    sharpe = (
        float(returns.mean() / volatility * periods_per_year**0.5)
        if volatility > 0 else 0.0
    )
    return {
        "num_trades": len(closed_returns),
        "win_rate": float((closed_returns > 0).mean()) if len(closed_returns) else 0.0,
        "total_return": float(equity.iloc[-1] / initial_balance - 1),
        "max_drawdown": float(drawdown.min()),
        "sharpe_ratio": sharpe,
        "final_equity": float(equity.iloc[-1]),
    }


