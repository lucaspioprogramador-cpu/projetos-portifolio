import unittest
from datetime import datetime, timezone

import numpy as np

from core.execution import apply_simulated_fill, build_order
from core.simulator import OrderSimulator


class ExecutionTests(unittest.TestCase):
    def test_build_order_validates_inputs_and_zero_price_is_limit(self):
        self.assertEqual(build_order("BTC/USDT", "buy", 1, 0.5)["type"], "limit")
        with self.assertRaises(ValueError):
            build_order("BTC/USDT", "buy", 0)
        with self.assertRaises(ValueError):
            build_order("BTC/USDT", "hold", 1)

    def test_buy_debits_gross_plus_fee(self):
        positions = []
        result = apply_simulated_fill(
            1_000, positions, "buy",
            {"preco_execucao": 100, "quantidade_executada": 2, "valor_total": 200, "taxas": 0.2},
        )
        self.assertAlmostEqual(result["balance"], 799.8)
        self.assertEqual(result["position"]["quantidade"], 2)
        self.assertAlmostEqual(result["position"]["valor_investido"], 200.2)

    def test_partial_sell_reduces_quantity_and_cost_basis_proportionally(self):
        position = {"quantidade": 4.0, "valor_investido": 404.0}
        positions = [position]
        result = apply_simulated_fill(
            500, positions, "sell",
            {"quantidade_executada": 1.0, "valor_total": 120.0, "taxas": 0.12},
            order_ref=position,
        )
        self.assertEqual(len(positions), 1)
        self.assertAlmostEqual(position["quantidade"], 3.0)
        self.assertAlmostEqual(position["valor_investido"], 303.0)
        self.assertAlmostEqual(result["cost_basis"], 101.0)
        self.assertAlmostEqual(result["pnl"], 18.88)
        self.assertAlmostEqual(result["balance"], 619.88)

    def test_full_sell_removes_position_and_realizes_remaining_pnl(self):
        position = {"quantidade": 2.0, "valor_investido": 200.2}
        positions = [position]
        result = apply_simulated_fill(
            799.8, positions, "sell",
            {"quantidade_executada": 2.0, "valor_total": 220.0, "taxas": 0.22},
            order_ref=position,
        )
        self.assertEqual(positions, [])
        self.assertIsNone(result["position"])
        self.assertAlmostEqual(result["pnl"], 19.58)
        self.assertAlmostEqual(result["balance"], 1_019.58)

    def test_buy_cannot_spend_more_than_balance(self):
        with self.assertRaises(ValueError):
            apply_simulated_fill(
                10, [], "buy",
                {"quantidade_executada": 1, "valor_total": 10, "taxas": 0.1},
            )

    def test_simulator_fee_and_randomness_are_reproducible(self):
        def make_simulator():
            return OrderSimulator(rng=np.random.default_rng(7))

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        buy = make_simulator().simular_execucao("buy", 1, 100, timestamp=now)
        buy_again = make_simulator().simular_execucao("buy", 1, 100, timestamp=now)
        sell = make_simulator().simular_execucao("sell", 1, 100, timestamp=now)
        self.assertEqual(buy, buy_again)
        self.assertAlmostEqual(buy["valor_liquido"], buy["valor_total"] + buy["taxas"])
        self.assertAlmostEqual(sell["valor_liquido"], sell["valor_total"] - sell["taxas"])
        self.assertLessEqual(buy["slippage_pct"], 0.05)

    def test_limit_order_does_not_fill_when_price_is_unfavorable(self):
        simulator = OrderSimulator(rng=np.random.default_rng(1))
        result = simulator.simular_ordem_limit("buy", 1, 99, 100)
        self.assertFalse(result["executada"])
        self.assertEqual(result["quantidade_executada"], 0)

    def test_large_order_partial_fill_is_seeded_and_reported(self):
        simulator = OrderSimulator(rng=np.random.default_rng(5))
        result = simulator.simular_execucao(
            "buy", 2, 100, volume_24h=10_000,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        self.assertTrue(result["executada"])
        self.assertFalse(result["executada_completa"])
        self.assertLess(result["quantidade_executada"], result["quantidade_solicitada"])


if __name__ == "__main__":
    unittest.main()
