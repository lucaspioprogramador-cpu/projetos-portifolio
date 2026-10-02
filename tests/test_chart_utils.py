import unittest

import pandas as pd

from ui.chart_utils import filter_events_to_window, padded_chart_range


class ChartWindowTests(unittest.TestCase):
    def test_filters_old_trade_markers_from_visible_candle_window(self):
        events = pd.DataFrame({
            "timestamp": [
                "2026-04-27T16:04:08-03:00",
                "2026-10-02T08:03:00",
                "2026-10-02T08:05:00-03:00",
            ],
            "side": ["old", "visible-naive", "visible-aware"],
        })
        visible = filter_events_to_window(
            events,
            pd.Timestamp("2026-10-02 08:00:00"),
            pd.Timestamp("2026-10-02 08:05:00"),
        )
        self.assertEqual(visible["side"].tolist(), ["visible-naive", "visible-aware"])

    def test_chart_range_uses_candle_bounds_not_overlay_dates(self):
        start, end = padded_chart_range(pd.date_range("2026-10-02 08:00", periods=3, freq="1min"))
        self.assertEqual(start, pd.Timestamp("2026-10-02 07:59:30"))
        self.assertEqual(end, pd.Timestamp("2026-10-02 08:02:30"))

    def test_empty_events_and_single_candle_are_supported(self):
        empty = filter_events_to_window(pd.DataFrame(), "2026-01-01", "2026-01-02")
        self.assertTrue(empty.empty)
        start, end = padded_chart_range([pd.Timestamp("2026-10-02 08:00")])
        self.assertLess(start, pd.Timestamp("2026-10-02 08:00"))
        self.assertGreater(end, pd.Timestamp("2026-10-02 08:00"))


if __name__ == "__main__":
    unittest.main()
