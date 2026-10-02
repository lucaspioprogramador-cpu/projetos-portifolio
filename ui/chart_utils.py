"""Helpers for keeping chart overlays inside the visible candle window."""

from collections.abc import Sequence

import pandas as pd

_LOCAL_TIMEZONE = "America/Sao_Paulo"


def _local_naive(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp
    return timestamp.tz_convert(_LOCAL_TIMEZONE).tz_localize(None)


def filter_events_to_window(
    events: pd.DataFrame,
    start: object,
    end: object,
    timestamp_column: str = "timestamp",
) -> pd.DataFrame:
    """Keep only overlay events between the first and last visible candle."""
    if events.empty or timestamp_column not in events.columns:
        return events.iloc[0:0].copy()
    start_time = _local_naive(start)
    end_time = _local_naive(end)
    event_times = events[timestamp_column].map(_local_naive)
    mask = event_times.between(start_time, end_time, inclusive="both")
    return events.loc[mask].copy()


def padded_chart_range(timestamps: Sequence[object]) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return candle bounds plus half a typical interval for clear edge candles."""
    values = pd.Series(timestamps).dropna().map(_local_naive).sort_values().drop_duplicates()
    if values.empty:
        raise ValueError("É necessário ao menos um timestamp válido para delimitar o gráfico")
    start = values.iloc[0]
    end = values.iloc[-1]
    interval = values.diff().dropna().median()
    if pd.isna(interval) or interval <= pd.Timedelta(0):
        interval = pd.Timedelta(minutes=1)
    padding = interval / 2
    return start - padding, end + padding
