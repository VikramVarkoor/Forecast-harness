import json
from pathlib import Path

import numpy as np
import pytest
import pandas as pd

from src import make_readme


def _pred(n_days=14, zones=(1, 2), start="2026-01-01", seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for o in pd.date_range(start, periods=n_days):
        for z in zones:
            ts = pd.date_range(o, periods=24, freq="h")
            y = rng.poisson(20, 24).astype(float)
            rows.append(pd.DataFrame({"origin": o, "ts": ts, "zone": z, "y": y,
                                      "lgbm": y + rng.normal(0, 3, 24), "mean_same_hour_4w": y + rng.normal(0, 5, 24),
                                      "q10_int": y - 5, "q90_int": y + 5}))
    return pd.concat(rows, ignore_index=True)


def _apptest(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    _pred().to_parquet(tmp_path / "predictions.parquet", index=False)
    _pred(7, start="2026-02-01", seed=1).to_parquet(tmp_path / "heldout_predictions.parquet", index=False)
    monkeypatch.setenv("FORECAST_RESULTS", str(tmp_path))
    return AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app" / "app.py"), default_timeout=30)


def test_story_is_the_first_view_then_dashboard(tmp_path, monkeypatch):
    at = _apptest(tmp_path, monkeypatch)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any('class="meter"' in m.value for m in at.markdown), "hero number missing"
    assert any("How it was tested" in str(s.value) for s in at.subheader)
    at.button[0].click().run()                          # "Open the dashboard"
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["view"] == "Dashboard"
    assert len(at.tabs) == 7                            # no map tab without zones30.geojson
    assert at.selectbox[0].options == ["1", "2"]
    assert at.metric[2].value == "held-out"
    at.toggle[0].set_value(True).run()                  # dark mode
    assert not at.exception, [e.value for e in at.exception]


def test_md_table_and_pct():
    t = make_readme.md(pd.DataFrame({"a": ["x"], "b": [1.2345]}), 2)
    assert "| x | 1.23 |" in t and make_readme.pct(31.38, 36.374) == 100 * (36.374 - 31.38) / 36.374


def test_readme_numbers_come_from_files(tmp_path, monkeypatch):
    (tmp_path / "results" / "analysis").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    R = tmp_path / "results"

    def models(mae):
        rows = {}
        for n, m in mae.items():
            for suf in ("", "|top", "|mid", "|quiet"):
                rows[n + suf] = dict(MAE=m, RMSE=m * 2, bias=-1.0, MASE=m / 40, scale=1.0)
        return pd.DataFrame(rows).T
    m = {"naive_last_hour": 140.0, "same_hour_yesterday": 59.0, "same_hour_last_week": 39.0,
         "mean_same_hour_4w": 36.0, "ets_weekly": 49.0, "lgbm": 31.0, "lgbm_plus_mean_same_hour_4w": 33.0}
    models(m).to_csv(R / "models.csv"); models(m).to_csv(R / "heldout.csv"); models(m).to_csv(R / "models_nolag.csv")
    paired = pd.DataFrame({"scope": ["all"], "baseline_mae": [36.0], "model_mae": [31.0], "mae_gain": [5.0],
                           "ci95_lo": [3.0], "ci95_hi": [6.0], "win_rate": [0.9], "n_days": [28]})
    paired.to_csv(R / "heldout_paired.csv", index=False); paired.to_csv(R / "analysis" / "paired_comparison.csv", index=False)
    pd.DataFrame({"scope": ["all", "top", "mid", "quiet"], "coverage_raw": [.75] * 4, "coverage_rounded": [.82] * 4,
                  "width_raw": [1.0] * 4, "width_rounded": [1.0] * 4}).to_csv(R / "heldout_intervals.csv", index=False)
    (R / "heldout_run.json").write_text(json.dumps({"runs": [{"status": "done"}]}))
    _pred().to_parquet(R / "heldout_predictions.parquet", index=False)
    pd.DataFrame({"date": ["2026-01-25", "2026-03-01"], "model_abs_err": [900.0, 800.0], "baseline_abs_err": [1.0, 1.0],
                  "actual": [1.0, 1.0], "forecast": [1.0, 1.0], "forecast_minus_actual": [-5.0, 3.0],
                  "weekday": ["Sunday", "Sunday"], "reason": ["unexplained: check weather and events", "holiday: X"]}
                 ).to_csv(R / "analysis" / "worst_days.csv", index=False)
    (tmp_path / "docs" / "day_reasons.csv").write_text("date,reason,source\n2026-01-25,Snow,http://x\n")
    monkeypatch.setattr(make_readme, "ROOT", tmp_path); monkeypatch.setattr(make_readme, "R", R)
    make_readme.main()
    t = (tmp_path / "README.md").read_text()
    assert "13.9% lower" in t            # (36-31)/36
    assert "Snow ([source](http://x))" in t and "scored 1 time(s)" in t


def test_zone_names_labels_the_dropdown(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import app.app as a
    (tmp_path / "z.csv").write_text("LocationID,Borough,Zone,service_zone\n1,EWR,Newark Airport,EWR\n2,Queens,Jamaica Bay,Boro Zone\n")
    assert a.zone_names.__wrapped__(str(tmp_path / "z.csv")) == {1: "EWR, Newark Airport", 2: "Queens, Jamaica Bay"}
    assert a.zone_names.__wrapped__(str(tmp_path / "missing.csv")) == {}


def test_chart_data_helpers():
    import app.app as a
    df = _pred().assign(split="development")
    df["ts"] = pd.to_datetime(df["ts"])
    g = a.daily_error(df)
    assert len(g) == 14 and {"model", "base", "date"} <= set(g.columns)
    h = a.hour_weekday_gain(df)
    assert set(h["hour"]) == set(range(24)) and h["weekday"].nunique() <= 7
    chart = a.error_chart(g, pd.DataFrame(columns=["date", "reason", "source"]), a.THEMES["dark"])
    assert chart.to_dict()


def test_scoreboard_reads_all_zone_rows_only(tmp_path):
    import app.app as a
    pd.DataFrame({"MAE": [31.0, 3.0, 36.0], "MASE": [.8, .8, .9], "bias": [-8., -1., -13.]},
                 index=["lgbm", "lgbm|quiet", "mean_same_hour_4w"]).to_csv(tmp_path / "heldout.csv")
    sb = a.scoreboard.__wrapped__(str(tmp_path))
    assert list(sb["model"]) == ["LightGBM", "Mean of same hour, last 4 weeks"]
    assert a.scoreboard.__wrapped__(str(tmp_path / "nope")).empty
    assert a.score_chart(sb, a.THEMES["light"]).to_dict()


def test_storm_story_and_zone_gain():
    import app.app as a
    df = _pred().assign(split="development")
    df["ts"] = pd.to_datetime(df["ts"])
    df["lgbm"] = df["y"]
    df.loc[df["origin"] == pd.Timestamp("2026-01-05"), "lgbm"] += 50     # one terrible day
    reasons = pd.DataFrame({"date": [pd.Timestamp("2026-01-05")], "reason": ["Blizzard; travel ban"], "source": ["http://x"]})
    date, why, ratio = a.storm_story(df, reasons)
    assert date == pd.Timestamp("2026-01-05") and why == "Blizzard" and ratio > 5
    assert a.storm_story(df, reasons.iloc[0:0]) is None
    zg = a.zone_gain(df)
    assert set(zg["zone"]) == {1, 2} and (zg["gain_pct"] > 0).all()


def test_zone_geojson_cut_and_map(tmp_path):
    import app.app as a
    from src.make_zone_geojson import cut
    sq = lambda x: {"type": "Polygon", "coordinates": [[[x, 40.0], [x + .1, 40.0], [x + .1, 40.1], [x, 40.0]]]}
    geo = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"location_id": "1"}, "geometry": sq(-74.0)},
        {"type": "Feature", "properties": {"location_id": "2"}, "geometry": sq(-73.9)},
        {"type": "Feature", "properties": {"location_id": "99"}, "geometry": sq(-73.8)}]}
    out = cut(geo, {1, 2})
    assert [f["properties"]["zone"] for f in out["features"]] == [1, 2]
    df = _pred().assign(split="development")
    assert a.map_chart(out, a.zone_gain(df), {1: "A"}, a.THEMES["light"]).to_dict()
    bad = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"location_id": 1},
           "geometry": {"type": "Polygon", "coordinates": [[[990000.0, 200000.0], [990001.0, 200000.0], [990001.0, 200001.0]]]}}]}
    with pytest.raises(SystemExit):
        cut(bad, {1})


def test_plain_english_summary_uses_the_numbers():
    import app.app as a
    df = _pred(7, start="2026-02-01").assign(split="held-out")
    df["ts"] = pd.to_datetime(df["ts"])
    hl = a.headline(df)
    text = " ".join(a.plain_summary(df, hl, {1: "Queens, Astoria"}))
    assert f"{hl[0]:.0f} rides" in text and f"{hl[2]:.0f}% fewer misses" in text and "busiest zone" in text
    assert len(a.plain_summary(df, None, {})) == 2      # no held-out result yet: only the explanation
    assert "Held-out" in a.glossary() and "<details" in a.glossary()


def test_verdict_only_says_what_the_numbers_say():
    import app.app as a
    hl = (31.38, 36.37, 13.7, 28)
    assert a.verdict(hl, 2.4, (26, 28)) == "The model won on 26 of 28 days. A winter storm still broke it."
    assert "storm" not in a.verdict(hl, 1.1, (26, 28)) and "storm" not in a.verdict(hl, None)
    assert "13.7" not in a.verdict(hl, None, (26, 28))      # the hero already says the percentage
    assert "30 parts" in a.verdict(None)
    df = _pred(6).assign(split="held-out")
    df["ts"] = pd.to_datetime(df["ts"])
    w = a.day_wins(df)
    assert w is not None and w[1] == 6 and 0 <= w[0] <= 6
    assert a.day_wins(df.assign(split="development")) is None
    assert a.next_steps().count('class="card"') == len(a.NEXT_STEPS)


def test_day_takeaway_says_who_won():
    import pandas as pd, datetime as dt
    import app.app as a
    ts = pd.date_range("2026-03-18", periods=3, freq="h")
    d = pd.DataFrame({"ts": ts, "y": [100, 100, 100], "lgbm": [90, 100, 100], a.BASE: [150, 150, 150]})
    assert "model beat" in a.day_takeaway(d, dt.date(2026, 3, 18)) and "00:00" in a.day_takeaway(d, dt.date(2026, 3, 18))
    d2 = d.assign(lgbm=[150, 150, 150], **{a.BASE: [100, 100, 100]})
    assert "simple rule won" in a.day_takeaway(d2, dt.date(2026, 3, 18))
    assert a.day_takeaway(d.iloc[0:0], dt.date(2026, 3, 18)) == ""


def test_story_day_best_worst_and_csv():
    import pandas as pd
    import app.app as a
    ts = pd.date_range("2026-03-01", periods=48, freq="h")
    rows = []
    for z, scale in ((1, 10), (2, 100)):
        for i, t_ in enumerate(ts):
            rows.append(dict(origin=t_.normalize(), ts=t_, zone=z, y=scale, lgbm=scale + (1 if i < 24 else 9), **{a.BASE: scale + 5},
                             q10_int=scale - 3, q90_int=scale + 3, split="development" if i < 24 else "held-out"))
    df = pd.DataFrame(rows)
    zone, day, d = a.story_day(df)
    assert zone == 2 and str(day.date()) == "2026-03-02" and len(d) == 24     # busiest zone, last held-out day
    best, worst = a.best_worst_days(df, n=1)
    assert best.loc[0, "Day"].startswith("Sun 01 Mar") and worst.loc[0, "Day"].startswith("Mon 02 Mar")
    assert worst.loc[0, "Rule minus model"] < 0
    csv = a.heldout_csv(df).decode().splitlines()
    assert csv[0] == "forecast_made_at,hour,zone,actual,model_forecast,rule_of_thumb_forecast,model_low_10pct,model_high_90pct"
    assert len(csv) == 1 + 48                                                 # held-out rows only: 2 zones x 24h


def test_hero_states_units_and_the_rule():
    import app.app as a
    h = a.hero((31.38, 36.37, 13.7, 28))
    assert "rides per zone per hour" in h and "last 4 weeks" in h and "28 days it never saw" in h and "lower error than a simple guess" in h and "Can you predict" in h and "LightGBM" in h
    assert "28 days" not in a.hero((31.38, 36.37, 13.7, 28), compact=True)


def test_unexplained_days_excludes_verified_ones():
    import pandas as pd
    import app.app as a
    rows = []
    for k, miss in enumerate([10, 10, 10, 10, 40, 40]):          # days 4 and 5 are big misses
        t_ = pd.Timestamp("2026-03-01") + pd.Timedelta(days=k)
        rows.append(dict(origin=t_, ts=t_, zone=1, y=100, lgbm=100 + miss, **{a.BASE: 100}, q10_int=0, q90_int=0, split="development"))
    df = pd.DataFrame(rows)
    reasons = pd.DataFrame({"date": [pd.Timestamp("2026-03-05")]})
    assert a.unexplained_days(df, reasons) == [pd.Timestamp("2026-03-06")]
    assert len(a.unexplained_days(df, reasons.iloc[0:0])) == 2


def test_evidence_file_is_complete_and_safe():
    import pandas as pd
    import app.app as a
    ev = a.evidence()
    assert len(ev) >= 3
    assert not ev[["outlet", "date", "title", "url", "why"]].isna().any().any()
    assert all(u.startswith("https://") for u in ev["url"])
    pd.to_datetime(ev["date"])                                      # every date parses
    html_ = a.evidence_cards(ev)
    assert html_.count('class="news"') == len(ev) and 'rel="noopener noreferrer"' in html_
    bad = pd.DataFrame([dict(outlet="X<script>", date="2026-01-01", title="a & b", url="http://insecure", why="w"),
                        dict(outlet="Y", date="2026-01-01", title="<b>t</b>", url="https://example.com/a", why="w")])
    out = a.evidence_cards(bad)
    assert out.count('class="news"') == 1 and "<script>" not in out and "&lt;b&gt;" in out   # http dropped, text escaped


def test_evidence_images_are_strictly_filtered():
    import pandas as pd
    import app.app as a
    rows = [dict(outlet="A", date="2026-01-01", title="t", url="https://example.com/a", why="w",
                 image=img, credit="Image: A") for img in
            ("https://img.example.com/ok.png", "https://x.com/a.png); background:url(https://evil", 'https://x.com/"onerror=1', "http://x.com/a.png", "")]
    out = a.evidence_cards(pd.DataFrame(rows))
    assert out.count('class="news-img" style=') == 1 and "ok.png" in out and "evil" not in out and "onerror" not in out
    assert out.count('news-img none') == 4                       # rejected or missing images fall back to the checker band
    assert out.count("Image: A") == 1                            # credit only shown with a real image
    real = a.evidence()
    assert all(str(i).startswith("https://") for i in real["image"].dropna())


def test_fonts_are_embedded_not_served():
    import app.app as a
    css = a.font_faces()
    for fam in ("Fraunces", "Figtree", "Newsreader"):
        assert f"font-family: '{fam}'" in css
    assert "data:font/woff2;base64," in css and "/app/static" not in css


def test_zone_table_spread_and_mind_checks():
    import app.app as a
    df = _pred(14, zones=(1, 2, 3)).assign(split="held-out")
    df["ts"] = pd.to_datetime(df["ts"])
    zt = a.zone_table(df, {1: "Alpha"})
    assert len(zt) == 3 and zt.iloc[0]["rides"] >= zt.iloc[-1]["rides"] and zt["name"].tolist().count("Alpha") == 1
    won, n, share_rides, share_saving = a.zone_spread(zt, top=1)
    assert n == 3 and 0 <= won <= 3 and 0 < share_rides <= 1
    # a model that is exactly right everywhere beats the rule everywhere, and the checks say so
    perfect = df.assign(lgbm=df["y"], **{a.BASE: df["y"] + 5})
    checks = a.mind_checks(perfect)
    assert [c[0] for c in checks[:3]] == ["holds"] * 3 and checks[-1][0] == "untested"
    # a model far worse than the rule makes the checks fail instead of passing
    awful = df.assign(lgbm=df["y"] + 50, **{a.BASE: df["y"]})
    assert [c[0] for c in a.mind_checks(awful)[:3]] == ["fails"] * 3
    assert a.mind_checks(df.assign(split="development")) == []
    assert "Holds" in a.mind_box(checks) and "Untested" in a.mind_box(checks)


def test_compare_takeaway_names_the_winner():
    import datetime as dt
    import app.app as a
    def frame(m, b):
        return pd.DataFrame({"y": [100.0, 100.0], "lgbm": [100 + m, 100 + m], a.BASE: [100 + b, 100 + b]})
    day = dt.date(2026, 3, 18)
    both = a.compare_takeaway([("A", frame(2, 10)), ("B", frame(5, 10))], day)
    assert "both zones" in both and both.index("A (80%") < both.index("B (50%")
    split = a.compare_takeaway([("A", frame(2, 10)), ("B", frame(12, 10))], day)
    assert "lost in B" in split and "rule missed by 10.0" in split and "model by 12.0" in split
    assert "rule beat the model in both" in a.compare_takeaway([("A", frame(12, 10)), ("B", frame(11, 10))], day)
    assert a.compare_takeaway([("A", frame(2, 10)), ("A", frame(5, 10))], day) == ""


def test_method_notes_cover_every_method_and_report_outcomes():
    import app.app as a
    sb = pd.DataFrame({"key": list(a.METHODS), "MAE": [31.0, 33.0, 36.0, 39.0, 58.0, 140.0, 49.0], "MASE": 1.0, "bias": 0.0})
    sb["model"] = sb["key"]
    notes = a.method_notes(sb)
    assert set(notes) == set(a.METHODS) and all(w and y for w, y in notes.values())
    assert "worse than the 4-week mean" in notes["ets_weekly"][1] and "worse than LightGBM alone" in notes["lgbm_plus_mean_same_hour_4w"][1]
    assert "what" in a.score_chart(sb, a.THEMES["light"]).to_json()


def test_hover_tip_is_escaped():
    import app.app as a
    assert "<script" not in a.hover_tip("<script>x</script>") and "Hover" in a.hover_tip()


def test_meter_keeps_the_real_number_for_readers():
    import app.app as a
    m = a.meter("13.7%")
    assert 'aria-label="13.7%"' in m and m.count('class="d"') == 3 and "--end:11" in m and "--end:13" in m and "--end:17" in m


def test_story_text_backs_up_the_storm_headline():
    import app.app as a
    df = _pred(10, start="2026-02-01").assign(split="held-out")
    df["ts"] = pd.to_datetime(df["ts"])
    df["lgbm"] = df["y"]
    df.loc[df["origin"] == pd.Timestamp("2026-02-05"), "lgbm"] += 60
    reasons = pd.DataFrame({"date": [pd.Timestamp("2026-02-05")], "reason": ["Major winter storm; travel ban"], "source": ["https://x"]})
    hl = a.headline(df)
    text = " ".join(a.plain_summary(df, hl, {}, reasons))
    assert "blind spot" in text and "05 February" in text and "Major winter storm" in text and "last four Tuesdays" in text
    assert "blind spot" not in " ".join(a.plain_summary(df, hl, {}, reasons.iloc[0:0]))
