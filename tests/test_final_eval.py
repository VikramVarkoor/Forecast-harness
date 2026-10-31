import json

import pandas as pd
import pytest

from src.ablation import verdict
from src.final_eval import MARKER, finish, guard
from src.models import LGBMForecaster
from src.features import FEATURES


def test_guard_allows_one_run_then_refuses_then_records_a_forced_rerun(tmp_path):
    m = guard(tmp_path, False, {"x": 1})
    finish(m)
    with pytest.raises(SystemExit):
        guard(tmp_path, False, {"x": 1})
    guard(tmp_path, True, {"x": 1})
    runs = json.loads((tmp_path / MARKER).read_text())["runs"]
    assert len(runs) == 2 and runs[0]["status"] == "done" and runs[1]["forced"] is True


def test_guard_blocks_even_after_a_crash(tmp_path):
    guard(tmp_path, False, {})            # started, never finished
    with pytest.raises(SystemExit):
        guard(tmp_path, False, {})


def _cmp(lo):
    return pd.DataFrame({"scope": ["all", "top"], "ci95_lo": [lo, 9.0]})


def test_verdict_follows_the_preregistered_rule():
    assert verdict(_cmp(0.3)) == "switch"
    assert verdict(_cmp(-0.1)) == "keep"
    assert verdict(_cmp(0.0)) == "keep"   # touching zero is not excluding it


def test_feature_subset_is_used_and_changes_the_model(wide):
    o = wide.index[0].normalize() + pd.Timedelta(days=50)
    hist = wide.loc[wide.index < o]
    fast = dict(n_estimators=20, num_leaves=15, min_data_in_leaf=10, num_threads=1)
    full = LGBMForecaster(params=fast)
    sub = LGBMForecaster(params=fast, features=[f for f in FEATURES if f not in ("lag_24", "roll24_l24")])
    a, b = full(hist), sub(hist)
    assert full.model.num_feature() == len(FEATURES)
    assert sub.model.num_feature() == len(FEATURES) - 2
    assert not a.equals(b)
