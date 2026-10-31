"""Baseline forecasters. Each takes `hist` (wide frame, hourly index, one column per zone,
containing ONLY rows strictly before the origin) and returns a 24-row frame for the horizon.
Origin is midnight, so history ends at hour 23 of the previous day."""
import pandas as pd

H = 24


def _out(hist, values):
    idx = pd.date_range(hist.index[-1] + pd.Timedelta(hours=1), periods=H, freq="h")
    return pd.DataFrame(values, index=idx, columns=hist.columns)


def naive_last_hour(hist):
    """Last observed hour, held flat."""
    return _out(hist, [hist.iloc[-1].values] * H)


def same_hour_yesterday(hist):
    return _out(hist, hist.iloc[-24:].values)


def same_hour_last_week(hist):
    # forecast for origin+h is the value at origin+h-168, which is hist position -168+h
    return _out(hist, hist.iloc[-168:-144].values)


def mean_same_hour_4w(hist):
    # k=1: [-168:-144]; k=2: [-336:-312]; k=3: [-504:-480]; k=4: [-672:-648]
    parts = [hist.iloc[-168 * k : -168 * k + H].values for k in range(1, 5)]
    return _out(hist, sum(parts) / 4.0)


BASELINES = {
    "naive_last_hour": naive_last_hour,
    "same_hour_yesterday": same_hour_yesterday,
    "same_hour_last_week": same_hour_last_week,
    "mean_same_hour_4w": mean_same_hour_4w,
}
