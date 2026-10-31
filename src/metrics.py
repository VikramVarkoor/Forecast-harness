"""Forecast metrics. Small pure functions so they can be tested on hand-made series."""
import numpy as np


def mae(y, yhat):
    return float(np.mean(np.abs(np.asarray(y, float) - np.asarray(yhat, float))))


def rmse(y, yhat):
    return float(np.sqrt(np.mean((np.asarray(y, float) - np.asarray(yhat, float)) ** 2)))


def bias(y, yhat):
    """Mean of forecast minus actual. Positive means over-forecasting."""
    return float(np.mean(np.asarray(yhat, float) - np.asarray(y, float)))


def seasonal_naive_scale(history, m=168):
    """Mean absolute in-sample error of the lag-m naive forecast. The MASE denominator."""
    h = np.asarray(history, float)
    if len(h) <= m:
        raise ValueError("history shorter than the seasonal period")
    return float(np.mean(np.abs(h[m:] - h[:-m])))


def mase(y, yhat, history, m=168):
    """Below 1 means better than the seasonal naive forecast on the training history."""
    scale = seasonal_naive_scale(history, m)
    if scale == 0:
        return float("nan")
    return mae(y, yhat) / scale


def interval_coverage(y, lo, hi):
    """Share of actuals inside [lo, hi]. A 10% to 90% band should cover about 80%."""
    y, lo, hi = (np.asarray(a, float) for a in (y, lo, hi))
    return float(np.mean((y >= lo) & (y <= hi)))


def interval_width(lo, hi):
    return float(np.mean(np.asarray(hi, float) - np.asarray(lo, float)))


def round_interval_outward(lo, hi):
    """Counts are integers, so a real-valued lower edge of 0.4 wrongly excludes an actual of 0.
    Round the lower edge down and the upper edge up. Never narrows a band."""
    return np.floor(np.asarray(lo, float)), np.ceil(np.asarray(hi, float))
