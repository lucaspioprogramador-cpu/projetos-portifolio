import math
import unittest

from core.risk import (
    affordable_quantity,
    apply_stop_take,
    exposure_budget,
    position_size,
)


class RiskTests(unittest.TestCase):
    def test_position_size_uses_fractional_risk_and_stop(self):
        self.assertAlmostEqual(position_size(1_000, 0.01, 0.02, 100), 5)

    def test_rejects_invalid_position_inputs(self):
        for args in ((-1, 0.01, 0.02, 100), (1_000, 1.1, 0.02, 100), (1_000, 0.01, 0, 100), (1_000, 0.01, 0.02, math.inf)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                position_size(*args)

    def test_affordable_quantity_includes_cost_buffer(self):
        qty = affordable_quantity(1_000, 100, 0.001, 0.001, 0.0002)
        self.assertLessEqual(qty * 100 * (1 + 0.0001) * (1 + 0.001) * 1.001, 1_000)

    def test_affordable_quantity_rejects_unbounded_cost_inputs(self):
        for args in ((-1, 100, 0.001, 0.05), (100, 0, 0.001, 0.05), (100, 100, -0.01, 0.05)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                affordable_quantity(*args)

    def test_exposure_budget_respects_total_and_symbol_caps(self):
        self.assertEqual(exposure_budget(1_000, 300, 100, 0.5, 0.25), 150)
        self.assertEqual(exposure_budget(1_000, 490, 100, 0.5, 0.25), 10)
        self.assertEqual(exposure_budget(1_000, 500, 250, 0.5, 0.25), 0)

    def test_stop_and_take_levels_validate_inputs(self):
        self.assertEqual(apply_stop_take(100, 0.02, 0.03), (98, 103))
        with self.assertRaises(ValueError):
            apply_stop_take(100, 1, 0.03)


if __name__ == "__main__":
    unittest.main()
