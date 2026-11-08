"""Models: P(Creys–St-Vulbas binds in hour h), P(DE > FR in hour h) and E[DE−FR spread in hour h],
all from the D-1-morning information set (the published Core domain for D plus hour-of-day climatology).

Lagged realized values are deliberately NOT used: on the 2026 backtest they added noise, and leaving them out
means the forecast depends only on what JAO publishes for the target day, which makes the audit trail simple.
"""
import json, os
import numpy as np, pandas as pd, joblib
from sklearn.linear_model import LogisticRegression, Ridge, QuantileRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss, mean_absolute_error

BIND_FEATS = ["c2_pres", "c2_rf", "c2_load", "c2_amr_rel", "maxFR", "minFR", "clim_bind", "weekend"]
SIGN_FEATS = BIND_FEATS + ["clim_pos", "clim_spread", "p_bind"]
LEVEL_FEATS = SIGN_FEATS
QUANT_FEATS = SIGN_FEATS + ["clim_q10", "clim_q50", "clim_q90"]
QUANTILES = (0.1, 0.5, 0.9)
RULES = ["creys_absent_from_domain_caps_p_bind_at_0.01"]  # a CNEC outside the presolved domain cannot carry a shadow price (53/53 hours in training, 24/24 in backtests)


def derived(T, clim):
    """Add derived columns and the stored hour-of-day climatologies."""
    T = T.copy()
    T["c2_load"] = T.c2_fref / T.c2_fmax
    T["c2_amr_rel"] = T.c2_amr / T.c2_fmax
    T["clim_bind"] = T.hour.map(clim["bind"]).astype(float)
    T["clim_pos"] = T.hour.map(clim["pos"]).astype(float)
    T["clim_spread"] = T.hour.map(clim["spread"]).astype(float)
    for q, key in ((0.1, "q10"), (0.5, "q50"), (0.9, "q90")):
        T[f"clim_{key}"] = T.hour.map(clim.get(key, {})).astype(float)
    return T


def climatology(train):
    g = train.groupby("hour")
    return {"bind": g.bind.mean().to_dict(), "pos": g.spread.apply(lambda s: (s > 0).mean()).to_dict(), "spread": g.spread.mean().to_dict(),
            "q10": g.spread.quantile(0.1).to_dict(), "q50": g.spread.quantile(0.5).to_dict(), "q90": g.spread.quantile(0.9).to_dict()}


def _logit(C=0.3):
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=C, max_iter=5000))


def _ridge(alpha=30.0):
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=alpha))


def _qr(tau, alpha=0.01):
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), QuantileRegressor(quantile=tau, alpha=alpha, solver="highs"))


def pinball(y, q, tau):
    d = np.asarray(y) - np.asarray(q)
    return float(np.mean(np.maximum(tau * d, (tau - 1) * d)))


def fit(train):
    clim = climatology(train)
    Tr = derived(train, clim)
    m_bind = _logit().fit(Tr[BIND_FEATS], Tr.bind)
    Tr["p_bind"] = m_bind.predict_proba(Tr[BIND_FEATS])[:, 1]
    m_sign = _logit().fit(Tr[SIGN_FEATS], (Tr.spread > 0).astype(int))
    m_level = _ridge().fit(Tr[LEVEL_FEATS], Tr.spread)
    m_q = {tau: _qr(tau).fit(Tr[QUANT_FEATS], Tr.spread) for tau in QUANTILES}
    return {"clim": clim, "bind": m_bind, "sign": m_sign, "level": m_level, "quantiles": m_q, "train_days": [train.day.min(), train.day.max()], "n_train": int(len(train))}


def predict(bundle, X):
    Xd = derived(X, bundle["clim"])
    Xd["p_bind"] = bundle["bind"].predict_proba(Xd[BIND_FEATS])[:, 1]
    Xd["p_pos"] = bundle["sign"].predict_proba(Xd[SIGN_FEATS])[:, 1]
    Xd["e_spread"] = bundle["level"].predict(Xd[LEVEL_FEATS])
    if "quantiles" in bundle:
        Q = np.sort(np.vstack([bundle["quantiles"][tau].predict(Xd[QUANT_FEATS]) for tau in QUANTILES]), axis=0)
        Xd["q10"], Xd["q50"], Xd["q90"] = Q[0], Q[1], Q[2]
    # structural rule, applied last so the other models see the same inputs they were trained on
    absent = (Xd.c2_pres == 0) & (Xd.c1_pres == 0)
    Xd["p_bind"] = np.where(absent, np.minimum(Xd.p_bind, 0.01), Xd.p_bind)
    return Xd


def evaluate(bundle, test):
    P = predict(bundle, test)
    y, s = P.bind.astype(int), (P.spread > 0).astype(int)
    out = {"n": int(len(P)), "days": [P.day.min(), P.day.max()],
           "bind": {"auc": roc_auc_score(y, P.p_bind), "brier": brier_score_loss(y, P.p_bind), "brier_clim": brier_score_loss(y, P.clim_bind),
                    "hit": float(((P.p_bind > 0.5) == y).mean()), "hit_clim": float(((P.clim_bind > 0.5) == y).mean()), "base_rate": float(y.mean())},
           "sign": {"auc": roc_auc_score(s, P.p_pos), "brier": brier_score_loss(s, P.p_pos), "brier_clim": brier_score_loss(s, P.clim_pos),
                    "hit": float(((P.p_pos > 0.5) == s).mean()), "hit_clim": float(((P.clim_pos > 0.5) == s).mean()), "base_rate": float(s.mean())},
           "level": {"mae": mean_absolute_error(P.spread, P.e_spread), "mae_zero": mean_absolute_error(P.spread, np.zeros(len(P))),
                     "mae_clim": mean_absolute_error(P.spread, P.clim_spread), "corr": float(np.corrcoef(P.e_spread, P.spread)[0, 1])}}
    if "q50" in P:
        y = P.spread.values
        out["quantiles"] = {"pinball": float(np.mean([pinball(y, P.q10, 0.1), pinball(y, P.q50, 0.5), pinball(y, P.q90, 0.9)])),
                            "pinball_clim": float(np.mean([pinball(y, P.clim_q10, 0.1), pinball(y, P.clim_q50, 0.5), pinball(y, P.clim_q90, 0.9)])),
                            "coverage80": float(np.mean((y >= P.q10) & (y <= P.q90))), "coverage80_clim": float(np.mean((y >= P.clim_q10) & (y <= P.clim_q90))),
                            "mae_p50": float(np.mean(np.abs(y - P.q50))), "mae_clim_median": float(np.mean(np.abs(y - P.clim_q50))), "mae_zero": float(np.mean(np.abs(y))),
                            "band_width": float(np.mean(P.q90 - P.q10))}
    return {k: ({kk: float(vv) for kk, vv in v.items()} if isinstance(v, dict) else v) for k, v in out.items()}


def save(bundle, path):
    joblib.dump(bundle, path)


def load(path):
    return joblib.load(path)
