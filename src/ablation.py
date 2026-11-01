"""Paired comparison of two LightGBM variants on the same development backtest.
Applies the rule in DECISIONS D18.

    python -m src.run_models --no-ets --drop-features lag_24,roll24_l24 --tag nolag
    python -m src.ablation
"""
import argparse
from pathlib import Path

import pandas as pd

from src.analyze import abs_err, compare
from src.run_baselines import load_dev

ROOT = Path(__file__).resolve().parent.parent
KEYS = ["origin", "ts", "zone"]


def verdict(cmp: pd.DataFrame) -> str:
    """D18: switch to the ablated model only if its overall paired gain over the full model is
    positive with a 95% interval that excludes zero. Otherwise keep the full model."""
    row = cmp.set_index("scope").loc["all"]
    return "switch" if row["ci95_lo"] > 0 else "keep"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hourly", default=str(ROOT / "data" / "hourly.parquet"))
    ap.add_argument("--full", default=str(ROOT / "results" / "predictions.parquet"))
    ap.add_argument("--ablated", default=str(ROOT / "results" / "predictions_nolag.parquet"))
    ap.add_argument("--drop-features", default="lag_24,roll24_l24")
    a = ap.parse_args()

    full, abl = pd.read_parquet(a.full), pd.read_parquet(a.ablated)
    assert full[KEYS].equals(abl[KEYS]), "the two runs do not cover the same origins and zones"
    df = full[KEYS + ["y", "lgbm"]].copy()
    df["lgbm_ablated"] = abl["lgbm"].to_numpy()
    _, zones, _ = load_dev(a.hourly)
    tier = zones.set_index("zone")["tier"]

    cmp = compare(df, "lgbm_ablated", "lgbm", tier)
    cmp = cmp.rename(columns={"baseline_mae": "full_mae", "model_mae": "ablated_mae"})
    print("Ablated LightGBM versus full LightGBM. mae_gain is full minus ablated, so positive "
          "favours the ablated model. 95% interval from a weekly block bootstrap.")
    print(cmp.round(3).to_string(index=False))

    d = df.assign(date=df["origin"].dt.date, full=abs_err(df, "lgbm"), ablated=abs_err(df, "lgbm_ablated"))
    g = d.groupby("date")[["full", "ablated"]].sum()
    worst = g.sort_values("full", ascending=False).head(10)
    worst["ablated_minus_full"] = worst["ablated"] - worst["full"]
    print("\nThe ten days where the full model erred most, with both models' total absolute error:")
    print(worst.round(0).to_string())

    v = verdict(cmp)
    drop = a.drop_features
    print(f"\nRule D18 verdict: {v.upper()}.")
    if v == "switch":
        print(f"Freeze the model without {drop}. Held-out command:\n"
              f"  python -m src.final_eval --drop-features {drop}")
    else:
        print("Freeze the full model. Held-out command:\n  python -m src.final_eval")


if __name__ == "__main__":
    main()
