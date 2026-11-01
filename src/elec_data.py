"""Domain B step 2: pick the countries by a fixed rule and write the two clean tables.

    python -m src.elec_data

Eligibility rule: a country is eligible if its measured load has no gap longer
than 14 hours and under 0.1% missing hours since 2015, and its operator day-ahead forecast is under
0.2% missing. Gaps in the operator forecast are left as gaps: those hours are left out of scoring for every model, so all models are compared on identical hours. The 10 eligible countries with the largest average load are used. Small gaps are
filled by straight-line interpolation and counted. Nothing here touches a model.

Reads  data/opsd/load_hourly.parquet (from src.opsd_download)
Writes data/opsd/elec_actual.parquet  measured load, MW, UTC hourly index (no time zone attached), one column per country
       data/opsd/elec_tso.parquet     operator day-ahead forecast, same shape
       results/elec_data_report.json  the rule, the countries, how many hours were filled
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MAX_GAP, MAX_MISS_ACT, MAX_MISS_TSO, N_COUNTRIES = 14, 0.1, 0.2, 10
SINCE = "2015-01-01"


def longest_gap(s):
    isna = s.isna().astype(int)
    run = isna.groupby((isna != isna.shift()).cumsum()).cumsum()
    return int(run.max()) if len(run) else 0


def pick(df, n=N_COUNTRIES, since=SINCE):
    """Eligible countries, largest average load first. Returns (chosen list, table)."""
    d = df[df.index >= pd.Timestamp(since, tz="UTC")] if df.index.tz is not None else df[df.index >= pd.Timestamp(since)]
    rows = []
    for cc in sorted({c.split("_")[0] for c in d.columns}):
        if f"{cc}_actual" not in d.columns or f"{cc}_tso" not in d.columns:
            continue
        a, t = d[f"{cc}_actual"], d[f"{cc}_tso"]
        if a.dropna().empty:
            continue
        rows.append(dict(country=cc, mean_load_mw=float(a.mean()), missing_actual_pct=100 * float(a.isna().mean()),
                         longest_gap_h=longest_gap(a), missing_tso_pct=100 * float(t.isna().mean()), longest_gap_tso_h=longest_gap(t)))
    t = pd.DataFrame(rows)
    t["eligible"] = (t.longest_gap_h <= MAX_GAP) & (t.missing_actual_pct <= MAX_MISS_ACT) & (t.missing_tso_pct <= MAX_MISS_TSO)
    t = t.sort_values("mean_load_mw", ascending=False).reset_index(drop=True)
    chosen = t[t.eligible].head(n)["country"].tolist()
    t["chosen"] = t.country.isin(chosen)
    return chosen, t


def clean(df, chosen, since=SINCE):
    """Two tables for the chosen countries, gaps filled by interpolation. Returns (actual, tso, filled counts)."""
    idx = df.index.tz_convert("UTC").tz_localize(None) if df.index.tz is not None else df.index
    d = df.copy(); d.index = idx
    d = d[d.index >= pd.Timestamp(since)]
    full = pd.date_range(d.index.min(), d.index.max(), freq="h")
    d = d.reindex(full)
    act = d[[f"{c}_actual" for c in chosen]].rename(columns=lambda c: c.split("_")[0])
    tso = d[[f"{c}_tso" for c in chosen]].rename(columns=lambda c: c.split("_")[0])
    # trim to the span where every chosen country has data, so no column starts later than the rest
    cols = [act[c] for c in act.columns] + [tso[c] for c in tso.columns]   # every series, actual and operator
    start = max(x.first_valid_index() for x in cols); end = min(x.last_valid_index() for x in cols)
    act, tso = act.loc[start:end], tso.loc[start:end]
    filled = {"actual": int(act.isna().sum().sum()), "tso_left_missing": int(tso.isna().sum().sum())}
    act = act.interpolate(limit=MAX_GAP, limit_area="inside")      # operator forecast is NOT filled
    if act.isna().any().any():
        bad = {c: (int(act[c].isna().sum()), str(act[c][act[c].isna()].index[0])) for c in act.columns if act[c].isna().any()}
        raise SystemExit(f"Gaps remain after interpolation (column: count, first missing hour): {bad}. Paste this to me.")
    return act, tso, filled


def tso_quality(act, tso):
    """Data check, not a model: how far the operator forecast is from the measured load, per country and year.
    A series that is wildly off in every year is probably measuring something else (different scope or units)."""
    e = ((tso - act).abs() / act * 100)
    return e.groupby(e.index.year).mean().round(2).T


def main():
    src = ROOT / "data" / "opsd" / "load_hourly.parquet"
    df = pd.read_parquet(src)
    chosen, table = pick(df)
    act, tso, filled = clean(df, chosen)
    qc = tso_quality(act, tso)
    out = ROOT / "data" / "opsd"
    act.to_parquet(out / "elec_actual.parquet"); tso.to_parquet(out / "elec_tso.parquet")
    (ROOT / "results").mkdir(exist_ok=True)
    rep = dict(rule=dict(max_gap_hours=MAX_GAP, max_missing_actual_pct=MAX_MISS_ACT, max_missing_tso_pct=MAX_MISS_TSO, n_countries=N_COUNTRIES, since=SINCE),
               chosen=chosen, first_hour=str(act.index[0]), last_hour=str(act.index[-1]), hours=len(act), hours_filled=filled,
               table=table.round(3).to_dict(orient="records"), operator_forecast_mape_pct_by_year=qc.to_dict(orient="index"))
    (ROOT / "results" / "elec_data_report.json").write_text(json.dumps(rep, indent=2))
    pd.set_option("display.width", 200)
    print(table.round(2).to_string(index=False))
    print("\nOperator forecast vs measured load, mean % error by year (a data check, no model involved):"); print(qc.to_string())
    print(f"\nChosen ({len(chosen)}): {', '.join(chosen)}")
    print(f"Span {act.index[0]} to {act.index[-1]} UTC, {len(act):,} hours. Filled by interpolation: {filled}")
    print("Wrote data/opsd/elec_actual.parquet, data/opsd/elec_tso.parquet, results/elec_data_report.json")


if __name__ == "__main__":
    main()
