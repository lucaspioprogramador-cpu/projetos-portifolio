import unittest

import pandas as pd

from backtest.metrics import basic_metrics
from backtest.runner import run_backtest


class BacktestTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({
            "open": [100.0] * 50 + [100.0, 110.0, 105.0, 105.0],
            "close": [100.0] * 50 + [100.0, 110.0, 105.0, 105.0],
        })

    def test_executes_at_next_bar_and_charges_fees(self):
        observed_window_lengths = []

        def strategy(window, in_position):
            observed_window_lengths.append(len(window))
            if len(window) == 50:
                return "buy"
            if len(window) == 51 and in_position:
                return "sell"
            return "hold"

        result = run_backtest(self.df, strategy, initial_balance=1_000, slippage_rate=0)
        self.assertEqual(observed_window_lengths[:2], [50, 51])
        self.assertEqual(result.iloc[0]["signal"], "buy")
        self.assertEqual(result.iloc[1]["signal"], "sell")
        self.assertGreater(result.iloc[1]["portfolio_value"], 1_000)
        self.assertEqual(basic_metrics(result, periods_per_year=1)["num_trades"], 1)

    def test_metrics_report_return_drawdown_and_win_rate(self):
        def strategy(window, in_position):
            if len(window) == 50:
                return "buy"
            if len(window) == 51 and in_position:
                return "sell"
            return "hold"

        result = run_backtest(self.df, strategy, initial_balance=1_000, slippage_rate=0)
        metrics = basic_metrics(result, periods_per_year=1)
        self.assertGreater(metrics["total_return"], 0)
        self.assertEqual(metrics["win_rate"], 1.0)
        self.assertLessEqual(metrics["max_drawdown"], 0)

    def test_rejects_invalid_prices_and_parameters(self):
        bad = self.df.copy()
        bad.loc[0, "open"] = 0
        with self.assertRaises(ValueError):
            run_backtest(bad, lambda *_: "hold")
        with self.assertRaises(ValueError):
            run_backtest(self.df, lambda *_: "hold", position_fraction=2)


if __name__ == "__main__":
    unittest.main()
