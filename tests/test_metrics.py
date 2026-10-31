import numpy as np
import pytest

from src.metrics import bias, mae, mase, rmse, seasonal_naive_scale


def test_basic_metrics_hand_checked():
    y, yh = [1, 2, 3, 4], [2, 2, 5, 3]
    assert mae(y, yh) == pytest.approx(1.0)          # |1|,|0|,|2|,|1| -> 4/4
    assert rmse(y, yh) == pytest.approx(np.sqrt(6 / 4))  # 1+0+4+1 = 6
    assert bias(y, yh) == pytest.approx(0.5)         # (+1+0+2-1)/4 = 2/4


def test_mase_is_one_for_the_naive_forecast_itself():
    rng = np.random.default_rng(0)
    h = rng.normal(100, 10, 500)
    # forecast = lag-168 naive, scored on the same series the scale came from
    y = h[168:]
    yhat = h[:-168]
    assert mase(y, yhat, h, m=168) == pytest.approx(1.0)


def test_mase_below_one_for_a_better_forecast():
    h = np.tile(np.arange(168, dtype=float), 4)  # perfectly periodic, scale = 0 -> nan
    assert np.isnan(mase(h[:24], h[:24], h))
    rng = np.random.default_rng(0)
    h = np.tile(np.arange(168, dtype=float), 4) + rng.normal(0, 1, 672)
    assert seasonal_naive_scale(h) > 0
    assert mase(h[-24:], h[-24:] + 0.1, h) < 1


def test_scale_needs_enough_history():
    with pytest.raises(ValueError):
        seasonal_naive_scale(np.arange(100.0))
