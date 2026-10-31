"""End to end on SYNTHETIC trips: SQL aggregation -> hourly table -> audit -> baselines."""
import pandas as pd

from src.build_hourly import build
from src.synth import make_month_files


def test_sql_aggregation_matches_pandas(tmp_path):
    make_month_files(tmp_path, days=40, n_zones=6)
    glob = str(tmp_path / "*.parquet")
    h = build(glob, "2025-02-01", "2025-03-11")
    raw = pd.concat(pd.read_parquet(p) for p in tmp_path.glob("*.parquet"))
    raw = raw[(raw.pickup_datetime >= "2025-02-01") & (raw.pickup_datetime < "2025-03-11")]
    ref = raw.groupby([raw.pickup_datetime.dt.floor("h"), "PULocationID"]).size()
    got = h.set_index(["ts", "zone"])["trips"]
    assert (got.loc[ref.index].values == ref.values).all()   # every non-empty cell matches pandas
    assert got.sum() == len(raw)                     # nothing lost, nothing invented
    assert len(h) == 38 * 24 * 6                     # 1 Feb to 11 Mar exclusive = 38 days, complete grid
