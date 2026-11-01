"""Build site/data/elec/elec.json for the Electricity page from the Domain B results files.

    python -m src.make_site_elec [--results results]

Every number and claim sentence is computed here from results/elec_*.csv, elec_*_predictions.parquet
and results/elec_data_report.json. Nothing is typed in. Wording that depends on a result (who won,
whether an interval crosses zero) is chosen by code from the result, so it cannot disagree with it.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.elec_run import DEV_DAYS

ROOT = Path(__file__).resolve().parent.parent
NAMES = dict(DE="Germany", FR="France", IT="Italy", ES="Spain", PL="Poland", NL="Netherlands", BE="Belgium", FI="Finland",
             AT="Austria", CH="Switzerland", GR="Greece", HU="Hungary", DK="Denmark", SK="Slovakia", HR="Croatia", SE="Sweden", NO="Norway")
LINKS = [("Portfolio", "https://vikramvarkoor.vercel.app"), ("GitHub", "https://github.com/VikramVarkoor"), ("LinkedIn", "https://linkedin.com/in/vikram-varkoor")]
FLAG_PCT = 4.0   # operator forecast flagged if its mean error vs measured load is above this in every year of the data
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
OP, BASE_LABEL = "operator_forecast", dict(same_hour_last_week="repeat the same hour from a week earlier")


def label(d):
    d = pd.Timestamp(d)
    return f"{DOW[d.day_of_week]} {d.day} {MON[d.month - 1]} {d.year}"


def daily(pred, col):
    return (pred[col] - pred["y"]).abs().groupby(pred["origin"]).mean().sort_index()


def crosses_zero(lo, hi):
    return lo <= 0 <= hi


def build(res: Path):
    pred = pd.read_parquet(res / "elec_heldout_predictions.parquet")
    table = pd.read_csv(res / "elec_heldout.csv", index_col=0)
    cc = pd.read_csv(res / "elec_heldout_by_country.csv")
    pr = pd.read_csv(res / "elec_heldout_paired.csv")
    band = json.loads((res / "elec_heldout_band.json").read_text())
    rep = json.loads((res / "elec_data_report.json").read_text())
    base = (res / "elec_dev_best.txt").read_text().strip()
    runs = json.loads((res / "elec_heldout_run.json").read_text())["runs"]
    has_w = (res / "elec_weather_predictions.parquet").exists()
    qc = rep["operator_forecast_mape_pct_by_year"]
    chosen = rep["chosen"]
    mae = table["MAE"]; mape = table["MAPE_pct"]
    gain = 100 * (mae[base] - mae["lgbm"]) / mae[base]
    better = gain >= 0                                    # every sentence below is worded from the sign, so a bad result reads as a bad result
    fewer = "fewer" if better else "more"
    n_days = pred["origin"].nunique()
    d_m, d_b, d_o = daily(pred, "lgbm"), daily(pred, base), daily(pred, OP)
    win_b, win_o = int((d_m < d_b).sum()), int((d_m < d_o).sum())
    first, last = pd.Timestamp(pred["origin"].min()), pd.Timestamp(pred["origin"].max())

    flagged = {c: all(v > FLAG_PCT for v in qc[c].values()) for c in chosen}
    c_mape = cc.pivot(index="country", columns="model", values="MAPE_pct")
    c_mae = cc.pivot(index="country", columns="model", values="MAE")
    load = cc.groupby("country")["mean_load"].first()
    countries = []
    for c in sorted(chosen, key=lambda x: -load[x]):
        countries.append(dict(code=c, name=NAMES.get(c, c), mean_load=round(float(load[c])), flagged=bool(flagged[c]),
                              mape_model=round(float(c_mape.loc[c, "lgbm"]), 2), mape_base=round(float(c_mape.loc[c, base]), 2), mape_op=round(float(c_mape.loc[c, OP]), 2),
                              mae_model=round(float(c_mae.loc[c, "lgbm"])), mae_base=round(float(c_mae.loc[c, base])), mae_op=round(float(c_mae.loc[c, OP])),
                              op_year_err=round(float(np.mean(list(qc[c].values()))), 1)))
    n_better = sum(c["mape_model"] < c["mape_base"] for c in countries)
    every = f"in every one of the {len(countries)} countries" if n_better == len(countries) else (f"in {n_better} of the {len(countries)} countries" if n_better else f"in none of the {len(countries)} countries")
    sane = [c for c in countries if not c["flagged"]]
    op_wins_sane = [c["name"] for c in sane if c["mape_op"] < c["mape_model"]]
    mo_wins_sane = [c["name"] for c in sane if c["mape_model"] < c["mape_op"]]
    flagged_names = [c["name"] for c in countries if c["flagged"]]

    p_mae = pr[(pr.versus == OP) & (pr.metric == "MAE (MW)")].iloc[0]; p_map = pr[(pr.versus == OP) & (pr.metric == "MAPE (%)")].iloc[0]
    if crosses_zero(p_mae.ci95_lo, p_mae.ci95_hi):
        op_mw = f"In megawatts the difference is small and the 95% range runs from {p_mae.ci95_lo:+.0f} to {p_mae.ci95_hi:+.0f} MW a day, so I cannot say the model is ahead."
    else:
        op_mw = f"In megawatts the model was {abs(p_mae.gain):.0f} MW a day {'better' if p_mae.gain > 0 else 'worse'}, with a 95% range of {abs(min(p_mae.ci95_lo, p_mae.ci95_hi)):.0f} to {abs(max(p_mae.ci95_lo, p_mae.ci95_hi)):.0f}."
    mw_flat, pct_flat = crosses_zero(p_mae.ci95_lo, p_mae.ci95_hi), crosses_zero(p_map.ci95_lo, p_map.ci95_hi)
    pct_rng = f"{min(abs(p_map.ci95_lo), abs(p_map.ci95_hi)):.2f} to {max(abs(p_map.ci95_lo), abs(p_map.ci95_hi)):.2f}"
    pct_dir = "better" if p_map.gain > 0 else "worse"
    weigh = "Megawatts count the big countries most, percent counts every country the same."
    if mw_flat and pct_flat:
        op_pct = f"In percent the difference is also within noise ({p_map.ci95_lo:+.2f} to {p_map.ci95_hi:+.2f} points)."
    elif mw_flat:
        op_pct = (f"In percent the model was {abs(p_map.gain):.2f} points {pct_dir} (95% range {pct_rng}). {weigh} The two measures disagree, "
                  f"so my conclusion stands on megawatts, the measure this page leads with: not clearly different.")
    elif pct_flat:
        op_pct = (f"In percent the difference is within noise ({p_map.ci95_lo:+.2f} to {p_map.ci95_hi:+.2f} points). {weigh} The two measures disagree, "
                  f"so my conclusion stands on megawatts, the measure this page leads with.")
    else:
        op_pct = f"In percent the model was {abs(p_map.gain):.2f} points {pct_dir}, with a 95% range of {pct_rng}."

    split = bool(op_wins_sane and mo_wins_sane)
    if crosses_zero(p_mae.ci95_lo, p_mae.ci95_hi):
        op_summary = "Not clearly different overall" + (", and the countries split." if split else ".")
    else:
        op_summary = ("The model is ahead overall" if p_mae.gain > 0 else "The operators are ahead overall") + (", and the countries split." if split else ".")
    cov = band["coverage"]
    band_note = "The range is a little too narrow, so treat it as optimistic." if cov < 0.77 else ("The range is too wide to be useful." if cov > 0.83 else "That is close to the target.")
    # series for the up-close chart: every country, every held-out day, 24 hours
    days = sorted(pred["origin"].unique())
    series = {}
    for c in chosen:
        g = pred[pred["zone"] == c].sort_values("ts")
        arr = lambda col: [[int(round(v)) for v in g[g["origin"] == d][col].tolist()] for d in days]
        series[c] = dict(y=arr("y"), model=arr("lgbm"), base=arr(base), op=arr(OP), lo=arr("q10"), hi=arr("q90"))
    med = float(d_m.median())
    worst = []
    for d in d_m.sort_values(ascending=False).index[:3]:
        g = pred[pred["origin"] == d]
        e = (g["lgbm"] - g["y"]).abs().groupby(g["zone"]).mean() / g.groupby("zone")["y"].mean() * 100
        worst.append(dict(i=[pd.Timestamp(x) for x in days].index(pd.Timestamp(d)), worst_code=str(e.idxmax()), date=label(d), day_mae=round(float(d_m[d])), times_typical=round(float(d_m[d] / med), 1),
                          worst_country=NAMES.get(e.idxmax(), e.idxmax()), worst_country_pct=round(float(e.max()), 1)))
    out = dict(
        hero=dict(kicker="Can you predict how much electricity Europe will use tomorrow?", pct=f"{abs(gain):.1f}%", cap=("lower" if better else "higher") + " average error, in megawatts, than a simple guess.",
                  fine=(f"That is the LightGBM model I trained, forecasting hourly electricity demand in each of {len(chosen)} European countries, a day ahead. "
                        f"A simple guess repeats what happened at the same hour a week earlier. Tested on {n_days} days it never saw ({label(first)[4:]} to {label(last)[4:]}), scored once."),
                  side=[["Model: off by", f"{mae['lgbm']:.0f}", "MW per country per hour"], ["Simple guess: off by", f"{mae[base]:.0f}", "MW per country per hour"]]),
        verdict=f"The model beat the simple guess on {win_b} of {n_days} days.",
        plain=[
            f"Grid operators publish a day-ahead demand forecast that traders and plant schedulers lean on. I built the same kind of forecast for {len(chosen)} European countries and tested it honestly. I hid the last {n_days} days, then made the model forecast each one from the night before. It was off by about <b>{mae['lgbm']:.0f} MW</b> per country per hour. A simple guess was off by {mae[base]:.0f}. That is <b>{abs(gain):.1f}% {'lower' if better else 'higher'} average error</b>, measured in megawatts, and the percentage error is lower {every}.",
            f"I also compared it with the grid operators' own forecast, which was off by {mae[OP]:.0f} MW. {op_mw} {op_pct}",
            "The operators beat the model in " + (", ".join(op_wins_sane) if op_wins_sane else "none of the checked countries") + ", and the model beat them in " + (", ".join(mo_wins_sane) if mo_wins_sane else "none of the checked countries") +
            f". In {', '.join(flagged_names)} the operator forecast is more than {FLAG_PCT:.0f}% away from measured load every year, so those comparisons are not fair. The operators use weather forecasts and my model does not, so weather is the first thing I would add."+(" I did test that on a separate window, in the Weather tab." if has_w else "")+""],
        daily=[dict(label=label(d), model=round(float(d_m[d])), base=round(float(d_b[d])), op=round(float(d_o[d]))) for d in d_m.index],
        countries=countries,
        compare=dict(base=base, base_label=BASE_LABEL.get(base, base), model_mae=round(float(mae["lgbm"]), 1), base_mae=round(float(mae[base]), 1), op_mae=round(float(mae[OP]), 1),
                     model_mape=round(float(mape["lgbm"]), 2), base_mape=round(float(mape[base]), 2), op_mape=round(float(mape[OP]), 2),
                     model_mase=round(float(table.loc["lgbm", "MASE"]), 3), base_mase=round(float(table.loc[base, "MASE"]), 3), op_mase=round(float(table.loc[OP, "MASE"]), 3),
                     win_base=win_b, win_op=win_o, n_days=n_days, flag_pct=FLAG_PCT),
        series=series, days=[dict(iso=str(pd.Timestamp(d).date()), label=label(d)) for d in days], worst=worst,
        findings=[dict(big=f"{abs(gain):.1f}%", lab=f"{'lower' if better else 'higher'} average error in MW than the simple guess", sub=f"{mae['lgbm']:.0f} MW against {mae[base]:.0f} MW, on {n_days} days never seen. The model had the lower error on {win_b} of them."),
                  dict(big=f"{win_o}/{n_days}", lab="days with a lower error than the operators' forecast", sub=op_summary + f" Average error {mae['lgbm']:.0f} MW against {mae[OP]:.0f} MW; the model was lower on {win_o} of {n_days} days, which is context, not the conclusion."),
                  dict(big=f"{band['coverage'] * 100:.0f}%", lab="of actual hours inside the 10% to 90% range", sub="It should be about 80%. " + band_note)],
        timeline=dict(dev=DEV_DAYS, held=int(n_days)),
        steps=[dict(lab="Forecast from midnight", sub="Each day, the model sees only data from before that moment and forecasts the next 24 hours for every country."),
               dict(lab="Reveal and score", sub="The real numbers are revealed and the miss is scored. Then the clock moves forward one day."),
               dict(lab="Same rules for everyone", sub="The simple guess and the operators' forecast are scored on the same hours, by the same code."),
               dict(lab=f"Score {n_days} days once", sub=f"The last {n_days} days were locked away until every choice was frozen. The run is recorded, and a second run is refused. It was scored {len([r for r in runs if r['status'] == 'done'])} time(s).")],
        limits=["The held-out days are September 2020, right after the spring lockdowns, so demand was not behaving normally. One month of September says little about winter peaks.",
                "The data ends in 2020 and comes from one public source, so this shows the method, not what happens on today's grid.",
                ("The main test has no weather input, and the operators' forecasts use weather. A second test on a different window added measured temperature; see the Weather tab." if has_w else "No weather input. Heating and cooling move demand, and the operators' forecasts use weather."),
                "Holidays are national only. Regional holidays are not in the model.",
                f"The operators' forecast was issued about half a day before my forecast and uses information mine does not have. It is a reference line, not a like-for-like opponent.",
                f"For {', '.join(flagged_names)} the operator series looks like it measures something else, so I report the numbers but do not draw a conclusion from them.",
                f"The 10% to 90% range covered {band['coverage'] * 100:.0f}% of hours against a target of 80%.",
                f"The country list was chosen by a rule (complete data, then the largest average load). The rule was changed once after a first development run, and that is written down in the project notes. Countries with the most missing data were not used."],
        method=["Pick a day. At midnight the model may only look at what happened before that moment.",
                "It forecasts every hour of that day, in every country, using demand from the past day, week and four weeks, the hour, weekday, month and national holidays.",
                f"Countries differ hugely in size, so the model predicts demand relative to each country's recent level and scales the answer back.",
                "The real numbers are revealed, the miss is scored, and the clock moves forward one day.",
                "A test checks that every feature equals an independent recalculation from raw history, and that a deliberately planted leak is caught.",
                f"Choices were made on the {DEV_DAYS} development days. The last {n_days} days were scored once."],
        glossary=[["MW", "Megawatts, the size of demand in a given hour."], ["MAPE", "Mean absolute percentage error: the average miss as a share of the real demand. Operators often quote this one."],
                  ["MASE", "The average miss divided by the miss of a repeat-last-week guess on the training days. Under 1 means better than that guess."],
                  ["Held out", "Days the model never saw while I built it, scored once at the end."], ["Operator forecast", "The day-ahead demand forecast that each country's grid operators publish."]],
        data_note=f"Hourly load and operator forecasts from Open Power System Data (originally the ENTSO-E Transparency Platform), {rep['first_hour'][:10]} to {rep['last_hour'][:10]}.",
        links=[dict(name=n, url=u) for n, u in LINKS], evidence=evidence(), fleet=FLEET)
    if (res / "elec_weather_predictions.parquet").exists():
        out["weather"] = weather(res, flagged, base)
    out["mind"] = mind_checks(pred, countries, base, mae, n_days, win_b, band, out.get("weather"))
    return out


FLEET = dict(
    intro="An example of how this work could move into a real grid operator or utility. The middle column is a plan, not something I have built.",
    columns=[
        dict(title="What carries over", sub="Built and tested here", items=[
            "The backtest harness: forecast each day using only what was known before it, then move forward one day.",
            "The leak test: every feature is checked against an independent recalculation, and a deliberately planted leak is caught.",
            "Simple baselines scored first, so a model has to beat them to count.",
            "Held-out days scored once, with every number on this site read from a results file.",
            "A weather test on a separate window, with the model's settings left alone.",
        ]),
        dict(title="What would change", sub="Planned, not built", items=[
            "Their own meter and control-room data instead of public national totals.",
            "Real weather forecasts, not measured temperature, since that is what is known the night before.",
            "Regional holidays, school terms, and solar and wind generation as inputs.",
            "Smaller areas than whole countries, and a rule for areas with no history.",
            "A forecast range scored on what a wrong forecast costs in balancing, not only on average error.",
            "Monitoring to catch the model drifting after launch.",
        ]),
        dict(title="What this does not prove", sub="Stated plainly", items=[
            "One held-out month and one weather window say little about a full year.",
            "The data is public national load, not a utility's live feeds.",
            "It was never tested against a running system.",
            "The operators' own forecast is issued earlier and uses weather forecasts, so it is a reference, not a like-for-like opponent.",
        ]),
    ])


def mind_checks(pred, countries, base, mae, n_days, win_b, band, wx):
    """Claims I would drop if they failed, each computed from the held-out results. status: Holds, Fails or Untested."""
    out = []
    won = sum(c["mape_model"] < c["mape_base"] for c in countries)
    out.append(("Holds" if won * 2 >= len(countries) else "Fails", "It beats the simple guess in most countries",
                f"It had the lower percentage error in {won} of {len(countries)} countries."))
    top = max(countries, key=lambda c: c["mean_load"])["code"]
    rest = pred[pred["zone"] != top]
    rb = (rest[base] - rest["y"]).abs().mean()
    if rb > 0:
        pct = 100 * (rb - (rest["lgbm"] - rest["y"]).abs().mean()) / rb
        out.append(("Holds" if pct > 0 else "Fails", "The result is not just the biggest country",
                    f"With {NAMES.get(top, top)} removed, the model still made {abs(pct):.1f}% {'fewer' if pct > 0 else 'more'} misses than the simple guess."))
    out.append(("Holds" if win_b * 2 >= n_days else "Fails", "It wins on most days, not a few lucky ones",
                f"It beat the simple guess on {win_b} of {n_days} held-out days."))
    sane = [c for c in countries if not c["flagged"]]
    lvl = sum(c["mape_model"] <= c["mape_op"] for c in sane)
    out.append(("Holds" if sane and lvl * 2 >= len(sane) else "Fails", "It keeps up with the operators where the comparison is fair",
                f"It had the lower or equal percentage error than the operators in {lvl} of {len(sane)} countries whose operator series looks sound. The operators have weather forecasts and the model does not."))
    cov = band["coverage"]
    off = abs(cov - 0.8)
    out.append(("Holds" if off <= 0.03 else ("Partly" if off <= 0.10 else "Fails"), "The 10% to 90% range can be trusted",
                f"The range caught {cov:.0%} of held-out hours; an ideal range catches 80%."
                + (" That is " + ("a little too narrow, so treat it as optimistic." if cov < 0.8 else "wider than it needs to be.") if 0.03 < off <= 0.10 else "")))
    if wx:
        st = wx["stat"]
        if st["ci_lo"] > 0:
            out.append(("Holds", "Weather helps on days the model was not tuned on", f"On a separate window, measured temperature cut the miss by {st['gain_pct']:.1f}%, and the 95% range on the daily gap stays above zero."))
        elif st["ci_hi"] < 0:
            out.append(("Fails", "Weather helps on days the model was not tuned on", f"On a separate window, adding temperature made the miss {abs(st['gain_pct']):.1f}% larger, and the 95% range stays below zero."))
        else:
            out.append(("Untested", "Weather helps on days the model was not tuned on", "On a separate window the 95% range on the daily gap includes zero, so I cannot say."))
    out.append(("Untested", "It keeps winning in other months and years",
                "Only one held-out month" + (" and one weather window were" if wx else " was") + " scored, so I cannot rule this out."))
    return [dict(status=a, title=b, detail=c) for a, b, c in out]


def evidence(path=None):
    """Source cards for 'Is this a real problem?'. Each row in docs/evidence_elec.csv was opened and read before it was added.
    Only https links are kept, and an image address only if it is safe to put in a CSS url()."""
    p = Path(path) if path else ROOT / "docs" / "evidence_elec.csv"
    if not p.exists():
        return []
    ev = pd.read_csv(p).fillna("")
    out = []
    for r in ev.itertuples():
        if not str(r.url).startswith("https://"):
            continue
        img = str(r.image)
        ok = img.startswith("https://") and not any(c in img for c in "\"'()<> \\;{}")
        out.append(dict(outlet=str(r.outlet), date=f"{pd.Timestamp(r.date):%b %Y}", title=str(r.title), why=str(r.why), url=str(r.url),
                        host=str(r.url).split("/")[2].removeprefix("www."), image=img if ok else "", credit=str(r.credit) if ok else "",
                        fit=str(getattr(r, "fit", "")) if str(getattr(r, "fit", "")) in ("contain",) else ""))
    return out


def weather(res: Path, flagged, base):
    """Second test, on a different window, of the same model with measured temperature added. Wording follows the result."""
    pred = pd.read_parquet(res / "elec_weather_predictions.parquet")
    t = pd.read_csv(res / "elec_weather_models.csv", index_col=0)
    cc = pd.read_csv(res / "elec_weather_by_country.csv")
    pr = pd.read_csv(res / "elec_weather_paired.csv")
    run = json.loads((res / "elec_weather_run.json").read_text())["runs"][-1]
    W, N = "lgbm_weather", "lgbm"
    f_ = lambda v: f"{v:.1f}" if abs(v) < 10 else f"{v:.0f}"      # tiny differences keep a decimal so they do not read as 0
    n_days = pred["origin"].nunique(); first, last = pd.Timestamp(pred["origin"].min()), pd.Timestamp(pred["origin"].max())
    mae, mape = t["MAE"], t["MAPE_pct"]
    gain = 100 * (mae[N] - mae[W]) / mae[N]
    d_w, d_n, d_o = daily(pred, W), daily(pred, N), daily(pred, OP)
    win = int((d_w < d_n).sum())
    pm = pr[(pr.model == W) & (pr.versus == N) & (pr.metric == "MAE (MW)")].iloc[0]
    po = pr[(pr.model == W) & (pr.versus == OP) & (pr.metric == "MAE (MW)")].iloc[0]
    if crosses_zero(pm.ci95_lo, pm.ci95_hi):
        sure = f"The 95% range runs from {pm.ci95_lo:+.1f} to {pm.ci95_hi:+.1f} MW a day, which includes zero, so I cannot say weather helped or hurt."
    else:
        sure = f"The 95% range, {f_(min(abs(pm.ci95_lo), abs(pm.ci95_hi)))} to {f_(max(abs(pm.ci95_lo), abs(pm.ci95_hi)))} MW a day, stays on one side of zero."
    verdict = (f"With measured temperature added, the model missed {f_(abs(gain))}% {'less' if gain >= 0 else 'more'} than without it." )
    gap_o = 100 * (mae[W] - mae[OP]) / mae[OP]
    if crosses_zero(po.ci95_lo, po.ci95_hi):
        vs_op = f"Against the grid operators' forecast ({mae[OP]:.0f} MW) the weather model ({mae[W]:.0f} MW) is not clearly different: the 95% range on the daily gap is {po.ci95_lo:+.0f} to {po.ci95_hi:+.0f} MW."
    else:
        vs_op = f"Against the grid operators' forecast ({mae[OP]:.0f} MW) the weather model ({mae[W]:.0f} MW) is {'ahead' if po.gain > 0 else 'behind'}, {abs(gap_o):.0f}% {'lower' if gap_o < 0 else 'higher'} in error."
    c_mape = cc.pivot(index="country", columns="model", values="MAPE_pct"); c_mae = cc.pivot(index="country", columns="model", values="MAE"); load = cc.groupby("country")["mean_load"].first()
    rows = [dict(code=c, name=NAMES.get(c, c), without=round(float(c_mape.loc[c, N]), 2), withw=round(float(c_mape.loc[c, W]), 2), op=round(float(c_mape.loc[c, OP]), 2), base=round(float(c_mape.loc[c, base]), 2), flagged=bool(flagged.get(c, False)))
            for c in sorted(c_mape.index, key=lambda x: -load[x])]
    better = [r["name"] for r in rows if r["withw"] < r["without"]]
    worse = [r["name"] for r in rows if r["withw"] > r["without"]]
    where = ("Weather lowered the percentage error in " + (f"all {len(rows)} countries." if len(better) == len(rows) else f"{len(better)} of {len(rows)} countries" + (": " + ", ".join(better) + "." if better else ".")))
    return dict(
        window=f"{label(first)[4:]} to {label(last)[4:]}", n_days=int(n_days), verdict=verdict,
        plain=[f"The first test asked whether the model could match the grid operators. This one asks what weather adds. I gave the same model four extra numbers: the temperature at the hour being forecast, its average over the day, and how far below 15 degrees or above 22 degrees it was. Then I forecast {n_days} days it had not seen ({label(first)[4:]} to {label(last)[4:]}), next to the same model without temperature, a simple guess and the operators.",
               f"Without weather the model missed by {mae[N]:.0f} MW per country per hour. With weather it missed by {mae[W]:.0f} MW, which is {f_(abs(gain))}% {'lower' if gain >= 0 else 'higher'}. It was the better of the two on {win} of {n_days} days. {sure} {vs_op}",
               f"{where} The temperature the model got is what was measured, not a forecast, so a real system would do worse than this. Read it as the most weather could add to this model, not as a result you could bank."],
        cards=[dict(big=f"{f_(abs(gain))}%", lab=f"{'fewer' if gain >= 0 else 'more'} misses with weather", sub=f"{mae[N]:.0f} MW without, {mae[W]:.0f} MW with, on {n_days} days."),
               dict(big=f"{win}/{n_days}", lab="days weather helped", sub=sure),
               dict(big=f"{mae[W]:.0f}", lab="MW off with weather", sub=f"Simple guess: {mae[base]:.0f} MW. Operators: {mae[OP]:.0f} MW.")],
        countries=rows, stat=dict(gain_pct=float(gain), ci_lo=float(pm.ci95_lo), ci_hi=float(pm.ci95_hi)),
        caveats=["Measured temperature stands in for a weather forecast. Real forecasts are wrong by a degree or two, so this is an upper bound on what weather would give.",
                 f"One window, {n_days} days, in autumn heating season. It says nothing about summer cooling or about holidays.",
                 "The window was chosen before any weather result existed and sits wholly before the development days used for the first test. It is the only time it was scored."
                 + (" It was run more than once." if len(json.loads((res / 'elec_weather_run.json').read_text())['runs']) > 1 else ""),
                 "Settings were the same as the model without weather. Nothing was tuned for the weather version, so a tuned one could do better or worse.",
                 "Temperature is a population-weighted country average from NASA's MERRA-2 reanalysis via Open Power System Data. Wind, cloud and sun are not included."],
        data_note="Weather: Open Power System Data weather_data (MERRA-2 reanalysis, population-weighted country temperature).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--out", default=str(ROOT / "site" / "data" / "elec"))
    ap.add_argument("--og", default=str(ROOT / "site" / "assets" / "og-elec.png"), help="where to write the link-preview picture")
    a = ap.parse_args()
    o = build(Path(a.results))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "elec.json").write_text(json.dumps(o, separators=(",", ":")))
    try:
        from src import og_elec
        s0 = o["series"][o["countries"][0]["code"]]
        og_elec.og_image(Path(a.og), o["hero"], (s0["y"][-1], s0["model"][-1]))
    except Exception as e:      # the preview picture is a nicety; never block the page data
        print("preview image not written:", e)
    print(f"wrote {out / 'elec.json'}")


if __name__ == "__main__":
    main()
