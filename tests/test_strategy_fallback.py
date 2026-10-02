import unittest

import pandas as pd

from strategies.ai_strategy_melhorada import RuleBasedTrendModel


class RuleBasedFallbackTests(unittest.TestCase):
    def test_predict_and_probabilities_are_deterministic(self):
        features = pd.DataFrame({
            "retorno": [0.1, -0.1],
            "macd_hist": [1.0, -1.0],
            "price_vs_ma20": [0.1, -0.1],
            "volume_ratio": [1.2, 0.5],
        })
        model = RuleBasedTrendModel()
        probabilities = model.predict_proba(features)
        self.assertEqual(model.predict(features).tolist(), [1, 0])
        self.assertEqual(probabilities[0].tolist(), [0.0, 1.0])
        self.assertEqual(probabilities[1].tolist(), [1.0, 0.0])

    def test_neutral_indicators_produce_fifty_fifty(self):
        features = pd.DataFrame({
            "retorno": [0.0], "macd_hist": [0.0],
            "price_vs_ma20": [0.0], "volume_ratio": [1.0],
        })
        probabilities = RuleBasedTrendModel().predict_proba(features)
        self.assertEqual(probabilities[0].tolist(), [0.5, 0.5])


if __name__ == "__main__":
    unittest.main()
