"""Models. Each forecaster is f(hist) -> 24-row frame, exactly like the baselines, so
run_backtest scores them unchanged. They only ever see `hist`, which the harness slices to
rows strictly before the origin. Features for the horizon are built from `hist` extended with
empty (NaN) horizon rows, so even a bug in a feature cannot read the future.
"""
import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from src.features import FEATURES, NUMERIC, build_features

H = 24


class ETSForecaster:
    """Additive Holt-Winters, weekly season (168 hours), no trend, one fit per zone on the last
    `weeks` weeks. Falls back to same-hour-last-week if a fit fails; the count is kept."""

    def __init__(self, weeks=6):
        self.weeks = weeks
        self.fallbacks = 0

    def __call__(self, hist):
        win = hist.iloc[-168 * self.weeks :]
        idx = pd.date_range(hist.index[-1] + pd.Timedelta(hours=1), periods=H, freq="h")
        out = {}
        for z in hist.columns:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fit = ExponentialSmoothing(
                        win[z].to_numpy(float), trend=None, seasonal="add",
                        seasonal_periods=168, initialization_method="heuristic",
                    ).fit()
                f = np.asarray(fit.forecast(H), float)
                if not np.all(np.isfinite(f)):
                    raise ValueError("non-finite forecast")
            except Exception:
                self.fallbacks += 1
                f = hist[z].to_numpy(float)[-168:-144]
            out[z] = np.clip(f, 0, None)
        return pd.DataFrame(out, index=idx)


class LGBMForecaster:
    """One global LightGBM across zones. Refit every `refit_days` days on all rows whose target
    is strictly before the origin (expanding window); between refits the model is reused and only
    the features move. objective='quantile' with alpha gives an interval edge instead of a mean.
    Parameters are fixed in advance, not tuned on the backtest."""

    def __init__(self, objective="poisson", alpha=None, refit_days=7, params=None, features=None):
        self.objective, self.alpha, self.refit_days = objective, alpha, refit_days
        self.features = list(features) if features else list(FEATURES)
        # native LightGBM names, so scikit-learn is not needed. n_estimators = boosting rounds.
        self.params = dict(
            n_estimators=300, learning_rate=0.05, num_leaves=63, min_data_in_leaf=50,
            bagging_fraction=0.8, bagging_freq=1, feature_fraction=0.9, seed=0,
            deterministic=True, force_row_wise=True, verbose=-1,
        )
        self.params.update(params or {})
        self.model = None
        self.last_fit = None
        self.n_fits = 0

    def _fit(self, hist):
        feats = build_features(hist)
        y = hist.stack(future_stack=True).to_numpy(float)
        assert len(y) == len(feats)
        feats["y"] = y
        df = feats.dropna(subset=NUMERIC + ["y"])
        kw = dict(self.params, objective=self.objective)
        rounds = kw.pop("n_estimators")
        if self.alpha is not None:
            kw["alpha"] = self.alpha
        self.model = lgb.train(kw, lgb.Dataset(df[self.features], label=df["y"]), num_boost_round=rounds)
        self.n_fits += 1

    def __call__(self, hist):
        origin = hist.index[-1] + pd.Timedelta(hours=1)
        if self.model is None or origin - self.last_fit >= pd.Timedelta(days=self.refit_days):
            self._fit(hist)
            self.last_fit = origin
        horizon = pd.date_range(origin, periods=H, freq="h")
        ext = hist.reindex(pd.date_range(hist.index[0], horizon[-1], freq="h"))
        feats = build_features(ext)
        sel = feats.loc[feats.index.get_level_values("ts").isin(horizon)]
        pred = pd.Series(self.model.predict(sel[self.features]), index=sel.index).unstack("zone")
        return pred.reindex(index=horizon, columns=hist.columns).clip(lower=0)
