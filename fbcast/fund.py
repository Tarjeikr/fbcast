"""Fundamentals model: quantiles of the DE−FR day-ahead spread, P(DE > FR) and quantiles of the DE and FR prices
for each hour of day D, from what is public at about 10:00 CET on D-1.

Information set
  * JAO pre-coupling publication for D, which arrives with the final flow-based domain on D-1 morning:
      - d2CF: the TSOs' D-2 congestion forecast, per hub: vertical load, generation and Core net position;
      - refprog: reference programmes on the non-Core borders (France–Switzerland, –Italy, –Spain, –Great Britain, ...);
      - maxNetPos and maxExchanges: the largest net positions and bilateral exchanges the domain allows.
  * Realized day-ahead results up to delivery day D-1, published on D-2: DE and FR prices and Core net positions.
Nothing from D's own auction is used, and no weather or TSO forecast that is published after gate closure.

The models are gradient-boosted trees fitted on all history since Core flow-based coupling started (June 2022).
Vertical load is load net of generation embedded in the distribution grids, so it carries the TSOs' own wind, solar and
temperature view; the forecast Core net positions say on which side of the domain the TSOs expect each hub to sit.
"""
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from . import data

START = "2022-06-09"
TZ = "Europe/Berlin"
HUBS = ("DE", "FR", "NL", "BE", "AT")
TSOS = ("50Hertz", "Amprion", "TennetGmbh", "Transnet")
REF = ["border_CH_FR", "border_FR_ES", "border_FR_IT", "border_FR_UK", "border_CH_DE", "border_NL_UK", "border_BE_UK", "border_CH_IT", "border_CH_AT"]
BEX = ["border_DE_FR", "border_FR_DE", "border_DE_NL", "border_NL_DE", "border_FR_BE", "border_BE_FR", "border_DE_BE", "border_BE_DE", "border_DE_AT", "border_AT_DE"]
KEEP = {"d2CF": ["dateTimeUtc"] + [f"{k}_{h}" for k in ("verticalLoad", "generation", "coreNetPosition") for h in HUBS] + [f"verticalLoad_{t}" for t in TSOS],
        "refprog": ["dateTimeUtc"] + REF,
        "maxNetPos": ["dateTimeUtc"] + [f"{m}{h}" for m in ("min", "max") for h in HUBS],
        "maxExchanges": ["dateTimeUtc"] + BEX,
        "netPos": ["dateTimeUtc", "hub_DE", "hub_FR"]}
PREFIX = {"d2CF": "", "refprog": "ref_", "maxNetPos": "", "maxExchanges": "bex_", "netPos": ""}
PUBLISHED_WITH_DOMAIN = ("d2CF", "refprog", "maxNetPos", "maxExchanges")
QS = (0.1, 0.5, 0.9)
TARGETS = ("spread", "DE", "FR")
# The spread is modelled relative to last week's price level (the higher of the two zones' mean prices) and multiplied back, so that
# what the trees learn about a decoupled France or Germany in one price regime carries over to another. Over the twelve-month
# walk-forward this was level with a raw target on average and clearly better when the price level shifted (November 2026).
# The two price levels are modelled raw: scaling them by their own weekly mean made them worse in the same test.
SCALE = {"spread": "lvl_m7", "DE": None, "FR": None}
GBM = dict(learning_rate=0.1, max_iter=120, max_leaf_nodes=16, min_samples_leaf=60, l2_regularization=1.0, early_stopping=False, random_state=0)
CAL_DAYS, CAL_DAYS_PRODUCT = 90, 180                                 # out-of-sample days used to calibrate the band widths
OUTCOMES = ["DE", "FR", "spread", "hub_DE", "hub_FR"]


# ---------------------------------------------------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------------------------------------------------
def _hourly(df, ds):
    """Hourly means per CET (day, hour) of the kept columns of one dataset."""
    cols = [c for c in KEEP[ds] if c != "dateTimeUtc"]
    if df is None or df.empty:
        return pd.DataFrame(columns=["day", "hour"] + [PREFIX[ds] + c.replace("border_", "") for c in cols])
    lt = df.t.dt.tz_convert(TZ)
    d = pd.DataFrame({c: pd.to_numeric(df[c], errors="coerce") if c in df else np.nan for c in cols})
    d["day"], d["hour"] = lt.dt.strftime("%Y-%m-%d").values, lt.dt.hour.values
    g = d.groupby(["day", "hour"])[cols].mean().reset_index()
    return g.rename(columns={c: PREFIX[ds] + c.replace("border_", "") for c in cols})


def _prices_hourly(P):
    lt = P.t.dt.tz_convert(TZ)
    return P.assign(day=lt.dt.strftime("%Y-%m-%d"), hour=lt.dt.hour).groupby(["day", "hour"])[["DE", "FR"]].mean().reset_index()


def raw_table(start, end, prices=None):
    """One row per CET (day, hour) between start and end: the forecast inputs published for that hour and its realized outcomes."""
    T = None
    for ds in KEEP:
        h = _hourly(data.load_windows(ds, start, end, keep=KEEP[ds]), ds)
        T = h if T is None else T.merge(h, on=["day", "hour"], how="outer")
    P = prices if prices is not None else data.load_prices_long(start, end)
    T = T.merge(_prices_hourly(P), on=["day", "hour"], how="outer")
    return T[(T.day >= start) & (T.day <= end)].sort_values(["day", "hour"]).reset_index(drop=True)


def _shift(T, cols, k, suffix):
    L = T[["day", "hour"] + cols].copy()
    L["day"] = (pd.to_datetime(L.day) + pd.Timedelta(days=k)).dt.strftime("%Y-%m-%d")
    return L.rename(columns={c: f"{c}{suffix}" for c in cols})


def make(T):
    """Feature table. Every feature of day D is either published for D on D-1 morning or realized on or before D-1."""
    T = T.sort_values(["day", "hour"]).drop_duplicates(["day", "hour"]).reset_index(drop=True)
    cur = {}
    for h in HUBS:
        cur[f"vl_{h}"] = T[f"verticalLoad_{h}"]; cur[f"gen_{h}"] = T[f"generation_{h}"]; cur[f"cnp_{h}"] = T[f"coreNetPosition_{h}"]
        cur[f"bal_{h}"] = T[f"generation_{h}"] - T[f"verticalLoad_{h}"]
        cur[f"max{h}"] = T[f"max{h}"]; cur[f"min{h}"] = T[f"min{h}"]
    for t in TSOS:
        cur[f"vl_{t}"] = T[f"verticalLoad_{t}"]
    for c in [PREFIX["refprog"] + c.replace("border_", "") for c in REF] + [PREFIX["maxExchanges"] + c.replace("border_", "") for c in BEX]:
        cur[c] = T[c]
    C = pd.DataFrame(cur)
    for h in ("DE", "FR"):  # where the forecast net position sits inside the domain: 1 at the export limit, 0 at the import limit
        C[f"cnp_pos_{h}"] = (C[f"cnp_{h}"] - C[f"min{h}"]) / (C[f"max{h}"] - C[f"min{h}"]).replace(0, np.nan)
    C["cnp_FR_minus_DE"] = C.cnp_FR - C.cnp_DE
    X = pd.concat([T[["day", "hour"]], C], axis=1)
    R = T[["day", "hour", "DE", "FR", "hub_DE", "hub_FR"]].copy()
    R["spread"] = R.DE - R.FR
    X = X.merge(_shift(R, ["DE", "FR", "spread", "hub_DE", "hub_FR"], 1, "_l1"), on=["day", "hour"], how="left")
    X = X.merge(_shift(R, ["DE", "FR", "spread"], 7, "_l7"), on=["day", "hour"], how="left")
    X = X.merge(_shift(R, ["DE", "FR", "spread"], 2, "_l2"), on=["day", "hour"], how="left")
    chg = ["vl_DE", "vl_FR", "gen_DE", "gen_FR", "cnp_DE", "cnp_FR", "maxFR", "minFR", "maxDE", "minDE", "bex_FR_DE", "bex_DE_FR", "vl_50Hertz", "vl_TennetGmbh"]
    X = X.merge(_shift(pd.concat([T[["day", "hour"]], C[chg]], axis=1), chg, 1, "_p1"), on=["day", "hour"], how="left")
    for c in chg:  # day-on-day change of the forecast inputs at the same hour
        X[f"d_{c}"] = X[c] - X[f"{c}_p1"]
    X["err_np_FR_l1"] = X.hub_FR_l1 - X.cnp_FR_p1   # how wrong yesterday's forecast net position was
    X["err_np_DE_l1"] = X.hub_DE_l1 - X.cnp_DE_p1
    X = X.drop(columns=[c for c in X.columns if c.endswith("_p1")])
    ctx = ["vl_DE", "vl_FR", "gen_DE", "gen_FR", "cnp_DE", "cnp_FR", "maxFR", "bex_FR_DE", "bex_DE_FR"]
    Dc = pd.concat([T[["day"]], C[ctx]], axis=1).groupby("day").agg(["mean", "min", "max"])
    Dc.columns = [f"{a}_day{b}" for a, b in Dc.columns]
    X = X.merge(Dc.reset_index(), on="day", how="left")
    Dr = R.groupby("day").agg(DE_mean=("DE", "mean"), FR_mean=("FR", "mean"), DE_max=("DE", "max"), FR_max=("FR", "max"), DE_min=("DE", "min"), FR_min=("FR", "min"),
                              spread_mean=("spread", "mean"), spread_abs=("spread", lambda s: s.abs().mean()), spread_max=("spread", "max"), spread_min=("spread", "min"),
                              spread_pos=("spread", lambda s: (s > 0).mean()), npFR_mean=("hub_FR", "mean"), npDE_mean=("hub_DE", "mean")).sort_index()
    Dr = Dr.reindex(pd.date_range(Dr.index.min(), Dr.index.max(), freq="D").strftime("%Y-%m-%d"))
    roll = pd.DataFrame({"DE_m7": Dr.DE_mean.rolling(7, min_periods=3).mean(), "FR_m7": Dr.FR_mean.rolling(7, min_periods=3).mean(),
                         "spread_abs_m7": Dr.spread_abs.rolling(7, min_periods=3).mean(), "spread_m7": Dr.spread_mean.rolling(7, min_periods=3).mean(),
                         "spread_sd7": Dr.spread_mean.rolling(7, min_periods=3).std(), "DE_m30": Dr.DE_mean.rolling(30, min_periods=10).mean(),
                         "FR_m30": Dr.FR_mean.rolling(30, min_periods=10).mean()})
    L1 = pd.concat([Dr.add_suffix("_d1"), roll], axis=1)
    L1.index = (pd.to_datetime(L1.index) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")   # everything here describes days up to D-1
    X = X.merge(L1.rename_axis("day").reset_index(), on="day", how="left")
    X["lvl_m7"] = np.maximum(X.DE_m7.abs(), X.FR_m7.abs())
    X["wd"] = pd.to_datetime(X.day).dt.weekday
    X["weekend"] = (X.wd >= 5).astype(int)
    return X.merge(R[["day", "hour"] + OUTCOMES], on=["day", "hour"], how="left")


def feature_names(X):
    return [c for c in X.columns if c not in ["day"] + OUTCOMES]


# ---------------------------------------------------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------------------------------------------------
def pinball(y, q, tau):
    d = np.asarray(y, float) - np.asarray(q, float)
    return float(np.nanmean(np.maximum(tau * d, (tau - 1) * d)))


def _scale(X, target):
    return X[SCALE[target]].abs().clip(lower=20).values if SCALE[target] else np.ones(len(X))


def fit(X, feats=None):
    """Quantile models for every target and a classifier for the sign of the spread, on all rows of X with known outcomes."""
    feats = feats or feature_names(X)
    feats = [c for c in feats if X[c].nunique() >= 2]
    out = {"features": feats, "q": {}, "train_days": [X.day.min(), X.day.max()]}
    for target in TARGETS:
        tr = X.dropna(subset=[target]); s = _scale(tr, target); ok = np.isfinite(s)
        tr, s = tr[ok], s[ok]
        out["q"][target] = {tau: HistGradientBoostingRegressor(loss="quantile", quantile=tau, **GBM).fit(tr[feats], tr[target].values / s) for tau in QS}
    tr = X.dropna(subset=["spread"])
    out["sign"] = HistGradientBoostingClassifier(**GBM).fit(tr[feats], (tr.spread > 0).astype(int))
    out["n_train"] = int(len(tr))
    return out


def predict_raw(m, X):
    """Uncalibrated predictions: q10/q50/q90 for the spread and both prices, and P(DE > FR)."""
    P = X[["day", "hour"]].copy()
    for target in TARGETS:
        s = _scale(X, target)
        s = np.where(np.isfinite(s), s, np.nan)
        Q = np.sort(np.vstack([m["q"][target][tau].predict(X[m["features"]]) * s for tau in QS]), axis=0)
        pre = "" if target == "spread" else target.lower() + "_"
        P[pre + "q10"], P[pre + "q50"], P[pre + "q90"] = Q[0], Q[1], Q[2]
    P["p_pos"] = m["sign"].predict_proba(X[m["features"]])[:, 1]
    return P


def band_factors(y, q10, q50, q90):
    """Width factors that would have made the band cover 80%: the 90th percentile of the outcome's distance from the median,
    measured in units of the half-band on its side."""
    y, q10, q50, q90 = (np.asarray(v, float) for v in (y, q10, q50, q90))
    ok = np.isfinite(y) & np.isfinite(q50)
    if ok.sum() < 30:
        return {"up": 1.0, "lo": 1.0}
    up = (y[ok] - q50[ok]) / np.maximum(q90[ok] - q50[ok], 0.5)
    lo = (q50[ok] - y[ok]) / np.maximum(q50[ok] - q10[ok], 0.5)
    return {"up": float(np.clip(np.quantile(up, 0.9), 0.6, 5.0)), "lo": float(np.clip(np.quantile(lo, 0.9), 0.6, 5.0))}


def widen(q10, q50, q90, k):
    """Scale the two halves of a band around its median by the calibration factors k."""
    if not k:
        return q10, q90
    return q50 - k["lo"] * (q50 - q10), q50 + k["up"] * (q90 - q50)


PRODUCT_TARGETS = (("spread", "", "y_spread", ""), ("DE", "de_", "y_DE", "DE_"), ("FR", "fr_", "y_FR", "FR_"))   # target, quantile prefix, outcome, calibration key prefix


def product_key(target, name):
    """Key of a daily product's band factors: "base" and "peak" for the spread, "DE_base", "FR_peak", ... for the prices."""
    return ("" if target == "spread" else target + "_") + name


def product_table(P):
    """Daily base and peak aggregates of hourly out-of-sample predictions: one row per target (spread, DE, FR), product and day on
    which the product is delivered, with the outcome, the averaged hourly quantiles and the outcome on the product's previous
    delivery day (yesterday for base, the previous weekday for peak), which is the benchmark a forecast has to beat."""
    from .features import product_hours, product_applies, previous_product_day, PRODUCT_MIN_HOURS
    rows = []
    for name in ("base", "peak"):
        ok_day = {d: product_applies(name, d) for d in P.day.unique()}
        X = P[P.hour.isin(product_hours(name)) & P.day.map(ok_day)]
        for target, pre, ycol, _ in PRODUCT_TARGETS:
            g = X.dropna(subset=[ycol, pre + "q50"]).groupby("day")
            D = pd.DataFrame({"y": g[ycol].mean(), "q10": g[pre + "q10"].mean(), "q50": g[pre + "q50"].mean(), "q90": g[pre + "q90"].mean(), "n": g[ycol].size()})
            D = D[D.n >= PRODUCT_MIN_HOURS[name]]
            if D.empty:
                continue
            D["prev"] = [D.y.get(previous_product_day(name, d), np.nan) for d in D.index]
            D["target"], D["product"] = target, name
            rows.append(D.reset_index())
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["day", "y", "q10", "q50", "q90", "n", "prev", "target", "product"])


def calibration(P):
    """Band-width factors from out-of-sample predictions P (columns y_spread, y_DE, y_FR and the raw quantiles): per target for the
    hourly bands from the last CAL_DAYS days, and per daily product (base and peak of the spread and of each price) from the last
    CAL_DAYS_PRODUCT days of daily errors."""
    days = sorted(P.day.unique())
    H = P[P.day.isin(days[-CAL_DAYS:])]
    cal = {"spread": band_factors(H.y_spread, H.q10, H.q50, H.q90), "DE": band_factors(H.y_DE, H.de_q10, H.de_q50, H.de_q90),
           "FR": band_factors(H.y_FR, H.fr_q10, H.fr_q50, H.fr_q90), "days": [days[-CAL_DAYS:][0], days[-1]]}
    T = product_table(apply_calibration(P[P.day.isin(days[-CAL_DAYS_PRODUCT:])], cal))
    for (target, name), D in T.groupby(["target", "product"]):
        cal[product_key(target, name)] = band_factors(D.y, D.q10, D.q50, D.q90)
    return cal


def apply_calibration(P, cal):
    P = P.copy()
    for target, pre in (("spread", ""), ("DE", "de_"), ("FR", "fr_")):
        k = cal.get(target)
        if k:
            P[pre + "q10"], P[pre + "q90"] = widen(P[pre + "q10"], P[pre + "q50"], P[pre + "q90"], k)
    return P


def predict(m, X):
    """Calibrated predictions for the rows of X (one day, 24 hours)."""
    return apply_calibration(predict_raw(m, X), m.get("cal", {}))


def walk_forward(X, first, last, freq="MS", feats=None, log=None):
    """Out-of-sample predictions between first and last: the models are refitted at each period start on everything before it."""
    out = []
    starts = pd.date_range(first, last, freq=freq)
    for a in starts:
        b = a + pd.tseries.frequencies.to_offset(freq)
        lo, hi = a.strftime("%Y-%m-%d"), min(b - pd.Timedelta(days=1), pd.Timestamp(last)).strftime("%Y-%m-%d")
        te = X[(X.day >= lo) & (X.day <= hi)]
        if te.empty:
            continue
        m = fit(X[X.day < lo], feats)
        P = predict_raw(m, te)
        for t in TARGETS:
            P["y_" + t] = te[t].values
        out.append(P)
        if log:
            log(f"walk-forward {lo}..{hi}: trained on {m['n_train']} hours")
    return pd.concat(out, ignore_index=True)


def summary(P, cal_rolling=True):
    """Skill of out-of-sample predictions P against a 60-day hour-of-day climatology, persistence and a zero forecast.
    Band coverage is reported raw and after the rolling calibration a live forecast would have had (factors from earlier days only).
    "products" holds the six daily products (base and peak of the spread and of each price) against the previous delivery day's value."""
    S = P.dropna(subset=["y_spread", "q50"]).copy()
    y = S.y_spread.values
    out = {"days": [S.day.min(), S.day.max()], "n_days": int(S.day.nunique()), "n_hours": int(len(S)),
           "pinball": float(np.mean([pinball(y, S.q10, .1), pinball(y, S.q50, .5), pinball(y, S.q90, .9)])),
           "mae_p50": float(np.mean(np.abs(y - S.q50))), "coverage80_raw": float(np.mean((y >= S.q10) & (y <= S.q90))),
           "sign_brier": float(np.mean((S.p_pos - (y > 0)) ** 2)), "sign_hit": float(np.mean((S.p_pos > 0.5) == (y > 0)))}
    for k in ("c10", "c50", "c90", "c_pos", "l1"):
        if k not in S:
            return out
    out.update({"pinball_clim": float(np.mean([pinball(y, S.c10, .1), pinball(y, S.c50, .5), pinball(y, S.c90, .9)])), "mae_clim": float(np.nanmean(np.abs(y - S.c50))),
                "mae_zero": float(np.mean(np.abs(y))), "mae_persistence": float(np.nanmean(np.abs(y - S.l1))),
                "sign_brier_clim": float(np.nanmean((S.c_pos - (y > 0)) ** 2)), "sign_hit_clim": float(np.nanmean((S.c_pos > 0.5) == (y > 0)))})
    for t, pre in (("DE", "de_"), ("FR", "fr_")):
        L = P.dropna(subset=["y_" + t, pre + "q50"])
        out[t] = {"mae_p50": float(np.mean(np.abs(L["y_" + t] - L[pre + "q50"]))), "mae_persistence": float(np.nanmean(np.abs(L["y_" + t] - L[t + "_l1"]))) if t + "_l1" in L else None,
                  "coverage80_raw": float(np.mean((L["y_" + t] >= L[pre + "q10"]) & (L["y_" + t] <= L[pre + "q90"]))), "mean_abs_price": float(np.mean(np.abs(L["y_" + t])))}
    T = product_table(S)
    out["products"] = {}
    for (target, name), D in T.groupby(["target", "product"]):
        e = {"days": int(len(D)), "mean_actual": float(D.y.mean()), "mae_p50": float(np.mean(np.abs(D.y - D.q50))), "mae_prev": float(np.nanmean(np.abs(D.y - D.prev))),
             "coverage80_raw": float(np.mean((D.y >= D.q10) & (D.y <= D.q90)))}
        if target == "spread":
            e["sign_hit"] = float(np.mean((D.q50 > 0) == (D.y > 0)))
        out["products"][f"{target}_{name}"] = e
    if cal_rolling:
        days = sorted(S.day.unique()); cov, covp = [], {}
        for i in range(CAL_DAYS, len(days), 7):                      # recalibrate weekly, as the live retrain does
            past, week = S[S.day.isin(days[max(0, i - CAL_DAYS_PRODUCT):i])], S[S.day.isin(days[i:i + 7])]
            cal = calibration(past)
            W = apply_calibration(week, cal)
            cov.append(((W.y_spread >= W.q10) & (W.y_spread <= W.q90)).values)
            for (target, name), D in product_table(W).groupby(["target", "product"]):
                lo, hi = widen(D.q10, D.q50, D.q90, cal.get(product_key(target, name)))
                covp.setdefault(f"{target}_{name}", []).append(((D.y >= lo) & (D.y <= hi)).values)
        if cov:
            out["coverage80_calibrated"] = float(np.mean(np.concatenate(cov)))
            for key, v in covp.items():
                out["products"][key]["coverage80_calibrated"] = float(np.mean(np.concatenate(v)))
    return out


def with_benchmarks(P, X):
    """Add the benchmarks to out-of-sample predictions: yesterday's value at the same hour and the hour-of-day climatology of the
    60 days before each day (both known when the forecast is issued)."""
    R = X[["day", "hour", "spread"]].dropna().copy(); R["d"] = pd.to_datetime(R.day)
    rows = []
    for day in sorted(P.day.unique()):
        d = pd.Timestamp(day)
        g = R[(R.d < d) & (R.d >= d - pd.Timedelta(days=60))].groupby("hour").spread
        rows.append(pd.DataFrame({"day": day, "hour": g.median().index, "c10": g.quantile(0.1).values, "c50": g.median().values, "c90": g.quantile(0.9).values,
                                  "c_pos": g.apply(lambda s: (s > 0).mean()).values}))
    P = P.merge(pd.concat(rows, ignore_index=True), on=["day", "hour"], how="left")
    return P.merge(X[["day", "hour", "spread_l1", "DE_l1", "FR_l1"]].rename(columns={"spread_l1": "l1"}), on=["day", "hour"], how="left")


def train(end, start=START, backtest_months=12, log=print):
    """Fit on all history to `end`, with a monthly walk-forward backtest over the last `backtest_months` months whose out-of-sample
    predictions also set the band-width calibration. Returns the model dictionary stored in the bundle under "fund"."""
    X = make(raw_table(start, end))
    X = X[X.day >= (pd.Timestamp(start) + pd.Timedelta(days=10)).strftime("%Y-%m-%d")].reset_index(drop=True)
    first = (pd.Timestamp(end) - pd.DateOffset(months=backtest_months)).replace(day=1).strftime("%Y-%m-%d")
    P = with_benchmarks(walk_forward(X, first, end, log=log), X)
    m = fit(X)
    m["cal"] = calibration(P)
    m["backtest"] = summary(P)
    m["gbm"] = GBM
    return m


# ---------------------------------------------------------------------------------------------------------------------
# Live
# ---------------------------------------------------------------------------------------------------------------------
def published(day):
    """True once JAO has every hour of the four pre-coupling datasets for CET day `day`."""
    f, t = data.day_bounds(day)
    hours = int((t - f) / pd.Timedelta(hours=1))
    for ds in PUBLISHED_WITH_DOMAIN:
        rows, _ = data.fetch_day(ds, day, force=True)
        if len({r["dateTimeUtc"][:13] for r in rows}) < hours:
            return False
    return True


def live_features(day):
    """Feature rows for the hours of `day` from fresh downloads: JAO for D and D-1, net positions of D-1, prices of the last 31 days."""
    d = pd.Timestamp(day)
    prev = (d - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    T = None
    for ds in PUBLISHED_WITH_DOMAIN:
        h = _hourly(data.load_days(ds, [prev, day]), ds)
        T = h if T is None else T.merge(h, on=["day", "hour"], how="outer")
    T = T.merge(_hourly(data.load_days("netPos", [prev]), "netPos"), on=["day", "hour"], how="outer")
    P = data.fetch_prices((d - pd.Timedelta(days=32)).strftime("%Y-%m-%d"), day)
    T = T.merge(_prices_hourly(P), on=["day", "hour"], how="outer")
    T.loc[T.day >= day, ["DE", "FR"]] = np.nan          # the target day's own prices, if already published, are never an input
    X = make(T)
    X = X[X.day == day].sort_values("hour").reset_index(drop=True)
    return X if len(X) >= 23 and X.vl_DE.notna().sum() >= 23 else None
