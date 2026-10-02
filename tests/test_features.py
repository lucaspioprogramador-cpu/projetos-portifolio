import unittest

import numpy as np
import pandas as pd

from strategies.features import calcular_rsi, gerar_features_melhorada


class FeatureTests(unittest.TestCase):
    def test_flat_market_has_neutral_finite_features(self):
        df = pd.DataFrame({
            "open": np.full(120, 100.0),
            "high": np.full(120, 100.0),
            "low": np.full(120, 100.0),
            "close": np.full(120, 100.0),
            "volume": np.zeros(120),
        })
        features = gerar_features_melhorada(df)
        self.assertFalse(features.empty)
        self.assertTrue(np.isfinite(features.select_dtypes(include=["number"]).to_numpy()).all())
        self.assertEqual(features.iloc[-1]["rsi"], 50)
        self.assertEqual(features.iloc[-1]["bb_position"], 0.5)
        self.assertEqual(features.iloc[-1]["volume_ratio"], 1)

    def test_rsi_marks_only_up_or_down_series(self):
        up = pd.DataFrame({"close": np.arange(1.0, 40.0)})
        down = pd.DataFrame({"close": np.arange(40.0, 1.0, -1.0)})
        self.assertEqual(calcular_rsi(up).iloc[-1], 100)
        self.assertEqual(calcular_rsi(down).iloc[-1], 0)


if __name__ == "__main__":
    unittest.main()
