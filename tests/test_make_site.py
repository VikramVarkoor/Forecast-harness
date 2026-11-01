"""The static site's data build: valid JSON, same numbers as the app, per-zone files that line up."""
import json
import sys

import numpy as np
import pandas as pd
import pytest

from src import make_site


def _pred(n_days, zones, start, seed):
    rng = np.random.default_rng(seed)
    rows = []
    for o in pd.date_range(start, periods=n_days):
        for z in zones:
            ts = pd.date_range(o, periods=24, freq="h")
            y = rng.poisson(20, 24).astype(float)
            rows.append(pd.DataFrame({"origin": o, "ts": ts, "zone": z, "y": y, "lgbm": y + rng.normal(0, 3, 24),
                                      "mean_same_hour_4w": y + rng.normal(0, 5, 24), "q10_int": y - 5, "q90_int": y + 5}))
    return pd.concat(rows, ignore_index=True)


@pytest.fixture
def built(tmp_path, monkeypatch):
    res, out = tmp_path / "res", tmp_path / "out"
    res.mkdir()
    _pred(14, (1, 2), "2026-01-01", 0).to_parquet(res / "predictions.parquet", index=False)
    _pred(7, (1, 2), "2026-02-01", 1).to_parquet(res / "heldout_predictions.parquet", index=False)
    monkeypatch.setattr(sys, "argv", ["make_site", "--results", str(res), "--out", str(out)])
    make_site.main()
    return out


def test_clean_makes_plain_json():
    got = make_site._clean({"a": np.float64(1.5), "b": [np.int64(2), float("nan")], "c": pd.Timestamp("2026-01-02 03:00")})
    assert got == {"a": 1.5, "b": [2, None], "c": "2026-01-02T03:00:00"}
    json.dumps(got)


def test_files_written_and_valid(built):
    for name in ("story.json", "theme.json", "dashboard.json", "heldout_forecasts.csv", "zones/1.json", "zones/2.json"):
        assert (built / name).exists(), name
    json.loads((built / "story.json").read_text())


def test_zone_file_is_columnar_and_lines_up(built):
    z = json.loads((built / "zones" / "1.json").read_text())
    n = len(z["ts"])
    assert n == 21 * 24
    for k in ("origin", "held", "y", "lgbm", "base", "q10", "q90"):
        assert len(z[k]) == n, k
    assert set(z["takeaway"]) == set(z["origin"]) and all(z["takeaway"].values())
    assert sum(z["held"]) == 7 * 24


def test_dashboard_matches_the_data(built):
    d = json.loads((built / "dashboard.json").read_text())
    assert [x["id"] for x in d["zones"]] == [1, 2]
    assert len(d["days"]) == 21 and d["held_start"] == "2026-02-01"
    assert 0 <= d["coverage"] <= 1
    assert d["spread"]["zones"] == 2 and len(d["heat"]) == 7 * 24
    text = (built / "dashboard.json").read_text()
    assert "NaN" not in text


def test_game_day_is_not_the_story_day_and_has_context(built):
    s = json.loads((built / "story.json").read_text())
    g = s["game"]
    assert g and len(g["rows"]) == 24 and len(g["yesterday"]) == 24
    assert g["date"] != s["up_close"]["date"]
    assert s["games"] and s["games"][0] == g
    assert all(len(x["rows"]) == 24 and len(x["yesterday"]) == 24 for x in s["games"])
    assert len({(x["place"], x["date"]) for x in s["games"]}) == len(s["games"])
    assert len(s["fleet"]["columns"]) == 3 and all(c["items"] for c in s["fleet"]["columns"])
    assert "—" not in json.dumps(s["fleet"])


def test_map_data_only_with_geojson(built):
    d = json.loads((built / "dashboard.json").read_text())
    assert d["map"] is False and not (built / "zones.geojson").exists()
    assert set(d["hourly"]) == {"1", "2"} and all(len(v) == 24 for v in d["hourly"].values())
