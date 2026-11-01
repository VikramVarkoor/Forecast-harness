"""Build the static site's data from the results folder.

    python -m src.make_site                      # reads results/, writes site/data/
    python -m src.make_site --results DIR --out DIR

Every number and sentence on the site is produced here by the same functions the Streamlit app uses,
so the two cannot disagree. The browser only draws what this script writes.
"""
import argparse
import json
import os
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def _clean(o):
    """Plain JSON types only: numpy numbers become Python numbers, timestamps become ISO strings, NaN becomes null."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return None if o != o else float(o)
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return o


def game_day(A, df, zone, day):
    """The day for the "your turn" exercise: the same zone a week before the up-close day (else the day before),
    plus the day before that, which is all a forecaster would know at midnight. Never the day the page already shows."""
    z = df[df["zone"] == zone]
    for off in (7, 1):
        gd = pd.Timestamp(day).normalize() - pd.Timedelta(days=off)
        out = _game_for(A, z, zone, gd)
        if out:
            return out
    return None


# Plain text for the "Taking this into a real fleet" section. It is a plan, and says so. No numbers, so it cannot go stale.
FLEET = dict(
    intro="An example of how this work could move into a real ride-hail company. The middle column is a plan, not something I have built.",
    columns=[
        dict(title="What carries over", sub="Built and tested here", items=[
            "The backtest harness: forecast each day using only what was known before it, then move forward one day.",
            "The leak test, shown to fail on three deliberately planted leaks.",
            "Simple baselines scored first, so a model has to beat them to count.",
            "A held-out period scored once, with every number on this site read from a results file.",
        ]),
        dict(title="What would change", sub="Planned, not built", items=[
            "Their own demand and supply data instead of public trip records.",
            "Weather, events and prices as inputs. Storm days were the largest errors here.",
            "Finer zones, and a rule for brand-new zones with no history.",
            "A forecast with a range, scored on what a wrong forecast costs dispatch, not only on average error.",
            "Monitoring to catch the model drifting after launch.",
        ]),
        dict(title="What this does not prove", sub="Stated plainly", items=[
            "Only one month was held out, from one year of history.",
            "There is no weather or event input.",
            "The data is public trip records, not a company's live requests.",
            "It was never tested against a running system.",
        ]),
    ])


def _game_for(A, z, zone, gd):
    g = z[z["origin"].dt.normalize() == gd].sort_values("ts")
    prev = z[z["origin"].dt.normalize() == gd - pd.Timedelta(days=1)].sort_values("ts")
    if len(g) != 24 or len(prev) != 24:
        return None
    return dict(place=A.zone_names().get(int(zone)) or f"zone {int(zone)}", date=f"{gd:%A %d %B}", yesterday_label=f"{gd - pd.Timedelta(days=1):%A}",
                rows=[dict(hour=int(r.ts.hour), y=round(float(r.y), 1), lgbm=round(float(r.lgbm), 1), base=round(float(getattr(r, A.BASE)), 1)) for r in g.itertuples()],
                yesterday=[round(float(v), 1) for v in prev["y"]])


def game_rounds(A, df, zone, day, n=5):
    """Up to n rounds for the exercise: the first is game_day, the rest spread over zones (busiest to quiet) and held-out days by a fixed rule.
    Never the zone and day the page already shows."""
    first = game_day(A, df, zone, day)
    rounds = [first] if first else []
    held = sorted(df.loc[df["split"] == "held-out", "origin"].dt.normalize().unique())
    zones = list(df.groupby("zone")["y"].sum().sort_values(ascending=False).index)
    shown = (int(zone), pd.Timestamp(day).normalize())
    for k in range(1, n * 3):
        if len(rounds) >= n or not held or not zones:
            break
        zn, gd = zones[(k * len(zones)) // n % len(zones)], pd.Timestamp(held[(k * 5 + 2) % len(held)])
        if (int(zn), gd) == shown:
            continue
        g = _game_for(A, df[df["zone"] == zn], zn, gd)
        if g and all(g["date"] != r["date"] or g["place"] != r["place"] for r in rounds):
            rounds.append(g)
    return rounds


def story(A):
    """Everything the Story page shows, as one dict."""
    df = A.load()
    hl = A.headline(df)
    sb, reasons, names = A.scoreboard(), A.day_reasons(), A.zone_names()
    storm = A.storm_story(df, reasons)
    zone, day, d = A.story_day(df)
    n_dev = int(df.loc[df["split"] == "development", "origin"].nunique())
    n_held = int(df.loc[df["split"] == "held-out", "origin"].nunique())
    rows = [dict(ts=r.ts.isoformat(), y=round(float(r.y), 1), lgbm=round(float(r.lgbm), 1), base=round(float(getattr(r, A.BASE)), 1))
            for r in d.itertuples()] if len(d) else []
    return dict(
        game=game_day(A, df, zone, day), games=game_rounds(A, df, zone, day),
        hero=A.hero_copy(hl), hero_compact=A.hero_copy(hl, compact=True),
        verdict=A.verdict(hl, storm[2] if storm else None, A.day_wins(df)),
        plain=A.plain_summary(df, hl, names, reasons),
        up_close=dict(zone=int(zone), place=names.get(int(zone)) or f"zone {int(zone)}", date=f"{day:%A %d %B}", rows=rows,
                      takeaway=A.day_takeaway(d, day),
                      note="This day was picked by rule, not because it looks good: the busiest zone, on the last day tested."),
        glossary=A.GLOSSARY,
        findings=[dict(big=b, lab=lab, sub=sub) for b, lab, sub in A.finding_cards(df, hl, sb, reasons)],
        mind=[dict(status=s, title=t, detail=x) for s, t, x in A.mind_checks(df)],
        evidence=A.evidence_items(A.evidence()),
        timeline=dict(dev=n_dev, held=n_held),
        steps=[dict(lab=h, sub=b) for h, b in A.test_steps(A.heldout_runs())],
        next_steps=[dict(big=k, lab=h, sub=b) for k, h, b in A.NEXT_STEPS],
        fleet=FLEET,
        links=[dict(name=n, url=u) for n, u in A.LINKS],
    )


def zone_files(A, df, out):
    """One small JSON per zone, loaded only when a visitor picks that zone. Columnar to keep files small."""
    zdir = Path(out) / "zones"
    if zdir.exists():
        shutil.rmtree(zdir)
    zdir.mkdir(parents=True)
    r1 = lambda s: [None if v != v else round(float(v), 1) for v in s]
    for z, g in df.groupby("zone"):
        g = g.sort_values("ts")
        days, mae = {}, {}
        for day, d in g.groupby(g["origin"].dt.normalize()):
            d = d.sort_values("ts")
            days[f"{day:%Y-%m-%d}"] = A.day_takeaway(d, day)
            mae[f"{day:%Y-%m-%d}"] = [float((d["lgbm"] - d["y"]).abs().mean()), float((d[A.BASE] - d["y"]).abs().mean())]   # full precision, so the page agrees with the app
        doc = dict(zone=int(z), ts=[t.isoformat() for t in g["ts"]], origin=[f"{o:%Y-%m-%d}" for o in g["origin"]],
                   held=[int(s == "held-out") for s in g["split"]],
                   y=r1(g["y"]), lgbm=r1(g["lgbm"]), base=r1(g[A.BASE]), q10=r1(g["q10_int"]), q90=r1(g["q90_int"]), takeaway=days, mae=mae)
        (zdir / f"{int(z)}.json").write_text(json.dumps(_clean(doc), separators=(",", ":")))


def dashboard(A):
    """Everything the Dashboard shows apart from the per-zone hourly files."""
    df = A.load()
    names, sb, reasons = A.zone_names(), A.scoreboard(), A.day_reasons()
    held = df[df["split"] == "held-out"]
    cov = float(((held["y"] >= held["q10_int"]) & (held["y"] <= held["q90_int"])).mean()) if len(held) else None
    zt = A.zone_table(df, names)
    sp = A.zone_spread(zt)
    g = A.daily_error(df)
    med = float(g["model"].median()) if len(g) else None
    notes = A.method_notes(sb) if not sb.empty else {}
    storm = []
    if not reasons.empty:
        for r in reasons.merge(g, on="date").itertuples():
            d = df[df["origin"].dt.normalize() == r.date].groupby("ts")[["y", "lgbm", A.BASE]].sum().reset_index()
            storm.append(dict(date=f"{r.date:%Y-%m-%d}", label=f"{r.date:%a %d %b %Y}", reason=str(r.reason), cause=str(r.reason).split(";")[0],
                              source=str(r.source), model=float(r.model), base=float(r.base),
                              rows=[dict(ts=x.ts.isoformat(), y=round(float(x.y), 1), lgbm=round(float(x.lgbm), 1), base=round(float(getattr(x, A.BASE)), 1))
                                    for x in d.itertuples()]))
    best, worst = A.best_worst_days(df)
    pool = held if len(held) else df
    hourly = {str(int(z)): [round(float(v), 1) for v in g.groupby(g["ts"].dt.hour)["y"].mean().reindex(range(24), fill_value=0)] for z, g in pool.groupby("zone")}
    unexplained = [f"{d:%d %b}" for d in A.unexplained_days(df, reasons)]
    return dict(
        zones=[dict(id=int(z), name=names.get(int(z)) or f"Zone {int(z)}") for z in sorted(df["zone"].unique())],
        days=sorted({f"{d:%Y-%m-%d}" for d in df["origin"].dt.date.unique()}),
        held_start=f"{held['origin'].min():%Y-%m-%d}" if len(held) else None,
        median_daily_miss=med, coverage=cov,
        scoreboard=[dict(key=r.key, model=r.model, MAE=float(r.MAE), MASE=float(r.MASE), bias=float(r.bias),
                         what=notes.get(r.key, ("", ""))[0], why=notes.get(r.key, ("", ""))[1]) for r in sb.itertuples()],
        zone_table=[dict(zone=int(r.zone), name=r.name, rides=float(r.rides), model_miss=float(r.model_miss), rule_miss=float(r.rule_miss),
                         gain_pct=None if r.gain_pct != r.gain_pct else float(r.gain_pct)) for r in zt.itertuples()],
        spread=dict(beaten=sp[0], zones=sp[1], top_rides=sp[2], top_saving=sp[3]) if sp else None,
        daily=[dict(date=f"{r.date:%Y-%m-%d}", split=r.split, model=float(r.model), base=float(r.base)) for r in g.itertuples()],
        reasons=[dict(date=f"{r.date:%Y-%m-%d}", reason=str(r.reason)) for r in reasons.itertuples()],
        unexplained=unexplained,
        heat=[dict(weekday=r.weekday, hour=int(r.hour), gain=float(r.gain)) for r in A.hour_weekday_gain(df).itertuples()],
        best=best.to_dict("records"), worst=worst.to_dict("records"),
        storm=storm, hourly=hourly, map=bool(A.zone_geo()),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--out", default=str(ROOT / "site" / "data"))
    ap.add_argument("--site-url", default="", help="public address of the site, e.g. https://forecast.vercel.app, so link previews find their image")
    args = ap.parse_args()
    os.environ["FORECAST_RESULTS"] = args.results      # app.app reads this when imported
    import importlib
    import sys
    mod = sys.modules.get("app.app")                    # reload so a module imported earlier re-reads FORECAST_RESULTS
    A = importlib.reload(mod) if mod else importlib.import_module("app.app")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "story.json").write_text(json.dumps(_clean(story(A)), ensure_ascii=False, separators=(",", ":")))
    df = A.load()
    zone_files(A, df, out)
    (out / "dashboard.json").write_text(json.dumps(_clean(dashboard(A)), ensure_ascii=False, separators=(",", ":")))
    (out / "heldout_forecasts.csv").write_bytes(A.heldout_csv(df))
    sb = A.scoreboard()
    if not sb.empty:
        (out / "heldout_scoreboard.csv").write_text(sb.drop(columns="key").to_csv(index=False))
    geo = A.zone_geo()
    if geo:
        keep = {"type": "FeatureCollection", "features": [dict(type="Feature", properties=dict(zone=int(f["properties"]["zone"])), geometry=f["geometry"]) for f in geo["features"]]}
        (out / "zones.geojson").write_text(json.dumps(keep, separators=(",", ":")))
    if args.site_url:
        idx = ROOT / "site" / "index.html"
        base = args.site_url.rstrip("/") + "/"
        txt = idx.read_text()
        import re
        txt = re.sub(r'(<meta property="og:image" content=")[^"]*(")', rf"\g<1>{base}assets/og.png\g<2>", txt)
        txt = re.sub(r'(<meta property="og:url" content=")[^"]*(")', rf"\g<1>{base}\g<2>", txt)
        idx.write_text(txt)
    (out / "theme.json").write_text(json.dumps(dict(themes=A.THEMES, taxi=A.TAXI)))
    print(f"wrote {out}/story.json and theme.json")
    if (Path(args.results) / "elec_heldout_predictions.parquet").exists():     # Domain B results present: build the Electricity page data too
        from src import make_site_elec
        (out / "elec").mkdir(exist_ok=True)
        (out / "elec" / "elec.json").write_text(json.dumps(make_site_elec.build(Path(args.results)), separators=(",", ":")))
        print(f"wrote {out}/elec/elec.json")


if __name__ == "__main__":
    main()
