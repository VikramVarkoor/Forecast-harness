import json
import sys

import numpy as np
import pandas as pd
import pytest

from src import elec_data, elec_features, elec_run, elec_weather_run, make_site_elec

CC = ["DE", "FR", "IT", "ES", "PL", "NL", "BE", "FI", "AT", "CH"]


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    root = tmp_path_factory.mktemp("proj")
    rng = np.random.default_rng(3)
    idx = pd.date_range("2017-01-01", periods=24 * 1095, freq="h", tz="UTC")
    d = {}
    for i, c in enumerate(CC):
        h = idx.hour.values; dw = idx.day_of_week.values; doy = idx.day_of_year.values
        base = (10 - i) * 5000 * (1 + 0.25 * np.sin((h - 6) / 24 * 2 * np.pi) + 0.2 * np.cos(doy / 365 * 2 * np.pi) - 0.1 * (dw >= 5))
        d[f"{c}_actual"] = base + rng.normal(0, 150, len(idx))
        d[f"{c}_tso"] = base * (1.10 if c == "NL" else 1.0) + rng.normal(0, 400, len(idx))
    (root / "data" / "opsd").mkdir(parents=True)
    pd.DataFrame(d, index=idx).rename_axis("ts").to_parquet(root / "data" / "opsd" / "load_hourly.parquet")
    class Fast(elec_features.ElecLGBM):
        def __init__(self, *a, **k):
            super().__init__(*a, **k); self.rounds = 20
    saved = (elec_data.ROOT, elec_run.ROOT, elec_run.ElecLGBM, elec_weather_run.ROOT, elec_weather_run.ElecLGBM, elec_weather_run.WINDOW_DAYS, sys.argv)
    elec_data.ROOT = elec_run.ROOT = elec_weather_run.ROOT = root; elec_run.ElecLGBM = elec_weather_run.ElecLGBM = Fast; elec_weather_run.WINDOW_DAYS = 4
    try:
        sys.argv = ["x"]; elec_data.main()
        (root / "results" / "elec_dev_best.txt").write_text("same_hour_last_week")
        sys.argv = ["x", "final"]; elec_run.main()
        wx = pd.DataFrame({c: 10 + 12 * np.cos((idx.day_of_year.values - 200) / 365 * 2 * np.pi) + rng.normal(0, 3, len(idx)) for c in CC}, index=idx.tz_localize(None))
        wx.rename_axis("ts").to_parquet(root / "data" / "opsd" / "weather_temp.parquet")
        sys.argv = ["x"]; elec_weather_run.main()
    finally:
        elec_data.ROOT, elec_run.ROOT, elec_run.ElecLGBM, elec_weather_run.ROOT, elec_weather_run.ElecLGBM, elec_weather_run.WINDOW_DAYS, sys.argv = saved
    return root / "results"


def test_numbers_come_from_the_results_files(results):
    o = make_site_elec.build(results)
    t = pd.read_csv(results / "elec_heldout.csv", index_col=0)
    gain = 100 * (t.loc["same_hour_last_week", "MAE"] - t.loc["lgbm", "MAE"]) / t.loc["same_hour_last_week", "MAE"]
    assert o["hero"]["pct"] == f"{abs(gain):.1f}%"
    assert o["hero"]["side"][0][1] == f"{t.loc['lgbm', 'MAE']:.0f}"
    assert len(o["days"]) == 28 and all(len(v["y"]) == 28 and len(v["y"][0]) == 24 for v in o["series"].values())
    assert [c["code"] for c in o["countries"]][0] == "DE"                      # largest average load first


def test_odd_operator_series_is_flagged_and_text_is_clean(results):
    o = make_site_elec.build(results)
    flagged = {c["code"] for c in o["countries"] if c["flagged"]}
    assert "NL" in flagged and "DE" not in flagged
    blob = json.dumps(o, ensure_ascii=False)
    assert "—" not in blob and "–" not in blob


def test_writes_json(results, tmp_path):
    sys.argv = ["x", "--results", str(results), "--out", str(tmp_path)]
    make_site_elec.main()
    assert json.loads((tmp_path / "elec.json").read_text())["verdict"].startswith("The model beat the simple guess on")


def test_wording_follows_the_sign_of_the_result(results):
    o = make_site_elec.build(results)
    t = pd.read_csv(results / "elec_heldout.csv", index_col=0)
    better = t.loc["lgbm", "MAE"] <= t.loc["same_hour_last_week", "MAE"]
    assert o["hero"]["cap"].startswith("lower" if better else "higher")
    assert ("lower" if better else "higher") in o["findings"][0]["lab"]


def test_weather_numbers_come_from_the_files_and_wording_follows_the_sign(results):
    o = make_site_elec.build(results)
    w = o["weather"]
    t = pd.read_csv(results / "elec_weather_models.csv", index_col=0)
    gain = 100 * (t.loc["lgbm", "MAE"] - t.loc["lgbm_weather", "MAE"]) / t.loc["lgbm", "MAE"]
    assert w["cards"][0]["big"] == (f"{abs(gain):.1f}%" if abs(gain) < 10 else f"{abs(gain):.0f}%")
    assert ("less" if gain >= 0 else "more") in w["verdict"] and w["n_days"] == 4
    assert len(w["countries"]) == len(CC) and any("measured" in x.lower() for x in w["caveats"])
    blob = json.dumps(o, ensure_ascii=False)
    assert "—" not in blob and "–" not in blob
    assert "Weather tab" in " ".join(o["limits"])


def test_weather_run_is_refused_a_second_time(results):
    saved = (elec_weather_run.ROOT, elec_run.ROOT, sys.argv)
    elec_weather_run.ROOT = elec_run.ROOT = results.parent
    try:
        sys.argv = ["x"]
        with pytest.raises(SystemExit):
            elec_weather_run.main()
    finally:
        elec_weather_run.ROOT, elec_run.ROOT, sys.argv = saved


def test_evidence_cards_are_safe_and_complete(tmp_path):
    real = make_site_elec.evidence()
    assert len(real) == 3 and all(e["url"].startswith("https://") and e["why"] and e["title"] and e["date"] for e in real)
    assert not any(ch in json.dumps(real, ensure_ascii=False) for ch in "—–")
    bad = tmp_path / "e.csv"
    bad.write_text('outlet,date,title,url,why,image,credit\nA,2025-01-01,t,http://x.com/a,w,,\n'
                   'B,2025-01-01,t,https://x.com/b,w,https://x.com/i.png"onload=1,cr\n'
                   'C,2025-01-01,t,https://www.x.com/c,w,https://x.com/ok.png,cr\n')
    got = make_site_elec.evidence(bad)
    assert [g["outlet"] for g in got] == ["B", "C"]               # the http link is dropped
    assert got[0]["image"] == "" and got[0]["credit"] == ""        # unsafe image address is dropped with its credit
    assert got[1]["image"] == "https://x.com/ok.png" and got[1]["host"] == "x.com"


def test_mind_checks_are_computed_from_the_results_and_fleet_text_is_clean(results):
    o = make_site_elec.build(results)
    m = {c["title"]: c for c in o["mind"]}
    pred = pd.read_parquet(results / "elec_heldout_predictions.parquet")
    t = pd.read_csv(results / "elec_heldout.csv", index_col=0)
    n_days = pred["origin"].nunique()
    d_m = (pred["lgbm"] - pred["y"]).abs().groupby(pred["origin"]).mean(); d_b = (pred["same_hour_last_week"] - pred["y"]).abs().groupby(pred["origin"]).mean()
    wins = int((d_m < d_b).sum())
    c = m["It wins on most days, not a few lucky ones"]
    assert c["status"] == ("Holds" if wins * 2 >= n_days else "Fails") and f"{wins} of {n_days}" in c["detail"]
    assert all(x["status"] in ("Holds", "Fails", "Untested") for x in o["mind"]) and o["mind"][-1]["status"] == "Untested"
    assert any(x["title"].startswith("Weather helps") for x in o["mind"])
    blob = json.dumps([o["mind"], o["fleet"]], ensure_ascii=False)
    assert "—" not in blob and "–" not in blob and len(o["fleet"]["columns"]) == 3


def test_operator_text_stands_on_megawatts_when_the_two_measures_disagree(results, tmp_path):
    import shutil
    r2 = tmp_path / "results"; shutil.copytree(results, r2)
    pr = pd.read_csv(r2 / "elec_heldout_paired.csv")
    op = pr["versus"] == "operator_forecast"
    pr.loc[op & (pr.metric == "MAE (MW)"), ["gain", "ci95_lo", "ci95_hi"]] = [10.0, -40.0, 60.0]
    pr.loc[op & (pr.metric == "MAPE (%)"), ["gain", "ci95_lo", "ci95_hi"]] = [0.45, 0.11, 0.74]
    pr.to_csv(r2 / "elec_heldout_paired.csv", index=False)
    o = make_site_elec.build(r2)
    o = o[0] if isinstance(o, tuple) else o
    text = o["plain"][1]
    assert "cannot say the model is ahead" in text
    assert "disagree" in text and "stands on megawatts" in text
    assert "Not clearly different" in o["findings"][1]["sub"]
