import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session")
def wide():
    """Hand-made hourly series: daily sine + weekend bump + noise. Deterministic."""
    rng = np.random.default_rng(1)
    idx = pd.date_range("2025-02-01", periods=24 * 70, freq="h")
    cols = {}
    for z, s in zip([10, 20, 30], [5, 50, 200]):
        daily = 1 + 0.6 * np.sin((idx.hour.values - 14) / 24 * 2 * np.pi)
        wk = np.where(idx.day_of_week.values >= 5, 1.3, 1.0)
        cols[z] = rng.poisson(s * daily * wk)
    return pd.DataFrame(cols, index=idx).astype(float)
