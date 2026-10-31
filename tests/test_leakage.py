"""The leak test. It must pass on the real pipeline and FAIL on planted leaks."""
import pandas as pd

from src.features import FEATURES, build_features, features_from_raw
from src.leakcheck import matches_raw, truncation_invariance

NUM = ["lag_24", "lag_168", "roll24_l24", "roll4w_sh"]


def _origins(wide):
    return [wide.index[0].normalize() + pd.Timedelta(days=d) for d in (30, 41, 55, 62)]


def _pairs(wide):
    ts = [o + pd.Timedelta(hours=h) for o in _origins(wide) for h in (0, 11, 23)]
    return [(t, z) for t in ts for z in wide.columns]


def test_real_pipeline_is_clean(wide):
    assert truncation_invariance(build_features, wide, _origins(wide), NUM) == []
    assert matches_raw(build_features, features_from_raw, wide, _pairs(wide), NUM) == []


def test_planted_shift_leak_is_caught(wide):
    """lag 23 instead of 24: for the last hours of the origin day it reads the origin day itself."""
    def leaky(w):
        out = build_features(w)
        out["lag_24"] = w.shift(23).stack(future_stack=True).values
        return out

    assert truncation_invariance(leaky, wide, _origins(wide), NUM), "truncation test missed a lag leak"
    assert matches_raw(leaky, features_from_raw, wide, _pairs(wide), NUM), "raw recompute missed a lag leak"


def test_planted_centered_rolling_leak_is_caught(wide):
    """A centered rolling window sees the future."""
    def leaky(w):
        out = build_features(w)
        out["roll24_l24"] = w.shift(24).rolling(24, center=True).mean().stack(future_stack=True).values
        return out

    assert truncation_invariance(leaky, wide, _origins(wide), NUM)


def test_planted_target_leak_is_caught(wide):
    """The target itself used as a feature."""
    def leaky(w):
        out = build_features(w)
        out["lag_168"] = w.stack(future_stack=True).values
        return out

    assert truncation_invariance(leaky, wide, _origins(wide), NUM)
    assert matches_raw(leaky, features_from_raw, wide, _pairs(wide), NUM)
