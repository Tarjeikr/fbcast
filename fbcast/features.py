"""Feature construction for the Core binding-constraint forecast.

Information set for day D is what a desk has at ~10:00 CET on D-1:
  * the final Core flow-based domain for D (JAO finalComputation, presolved CNECs) and max net positions for D,
    both published on D-1 morning;
  * realized day-ahead results for D-1 (shadow prices, net positions, prices), published on D-2 ~13:00 CET.
Nothing from D's own auction is used.
"""
import glob, json
import numpy as np, pandas as pd

BLOCKS = {"night 00–05": (0, 5), "morning 06–09": (6, 9), "midday 10–14": (10, 14), "afternoon 15–17": (15, 17), "evening 18–20": (18, 20), "late 21–23": (21, 23)}
# Daily products. Peak = delivery 08:00-21:00 CET (hours beginning 08 to 20) on all seven days; set PEAK_WEEKDAYS_ONLY = True for exchange-style Mon-Fri peak.
PEAK_HOURS = tuple(range(8, 21))
PEAK_WEEKDAYS_ONLY = False
PRODUCT_MIN_HOURS = {"base": 20, "peak": 11}  # fewer hours than this (partial days) and the product is not scored


def product_hours(name):
    return tuple(range(24)) if name == "base" else PEAK_HOURS


def product_applies(name, day):
    if name == "peak" and PEAK_WEEKDAYS_ONLY and day is not None:
        return pd.Timestamp(day).weekday() < 5
    return True


def _p_pos(p10, p50, p90):
    """P(daily mean > 0) from a normal approximation whose width is read off the P10-P90 band (floor 1 EUR/MWh)."""
    from math import erf, sqrt
    sigma = max((p90 - p10) / 2.5631, 1.0)
    return 0.5 * (1 + erf(p50 / (sigma * sqrt(2))))


def product_forecast(hours, day=None, keys=("spread_p10", "spread_p50", "spread_p90")):
    """Daily base (24 h) and peak spread forecast from hourly quantiles: the average of the hourly P10, P50 and P90 over the product's hours
    (exact if the hourly errors move together, which they largely do within a day), plus P(mean > 0)."""
    out = {}
    for name in ("base", "peak"):
        if not product_applies(name, day):
            continue
        vals = [[h.get(k) for k in keys] for h in hours if h["hour"] in product_hours(name)]
        vals = [v for v in vals if all(x is not None and x == x for x in v)]
        if len(vals) < PRODUCT_MIN_HOURS[name]:
            continue
        a = np.mean(vals, axis=0)
        out[name] = {"p10": float(a[0]), "p50": float(a[1]), "p90": float(a[2]), "p_pos": float(_p_pos(a[0], a[1], a[2])), "n_hours": len(vals)}
    return out


CREYS2 = ("L 400kV N0 2 CREYS-ST-VULBAS-OUEST", "OPPOSITE")
CREYS1 = ("L 400kV N0 1 CREYS-ST-VULBAS-OUEST", "OPPOSITE")
TZ = "Europe/Berlin"


def load_json_days(folder, prefix):
    frames = []
    for f in sorted(glob.glob(f"{folder}/{prefix}_*.json")):
        rows = json.load(open(f))
        if rows:
            frames.append(pd.DataFrame(rows))
    d = pd.concat(frames, ignore_index=True)
    d["t"] = pd.to_datetime(d.dateTimeUtc, utc=True)
    return d


def hour_index(t):
    """CET day and hour for UTC timestamps."""
    lt = t.dt.tz_convert(TZ)
    return pd.DataFrame({"day": lt.dt.strftime("%Y-%m-%d"), "hour": lt.dt.hour, "wd": lt.dt.weekday}, index=t.index)


def domain_features(fc):
    """Per CET hour: Creys circuits' RAM/Fref/AMR/F_uaf/Fmax, RTE domain stats, whole-domain stats."""
    fc = fc.copy()
    fc["tso"] = fc.tso.str.upper()
    hi = hour_index(fc.t)
    fc["day"], fc["hour"] = hi.day, hi.hour
    fc["rf"] = fc.ram / fc.fmax
    out = []
    for (day, hour), g in fc.groupby(["day", "hour"]):
        row = {"day": day, "hour": hour}
        for tag, (name, direction) in (("c2", CREYS2), ("c1", CREYS1)):
            c = g[(g.cneName.str.strip() == name) & (g.direction == direction)]
            if len(c):
                c = c.iloc[0]
                row.update({f"{tag}_pres": 1, f"{tag}_ram": c.ram, f"{tag}_rf": c.ram / c.fmax, f"{tag}_fref": c.fref,
                            f"{tag}_amr": c.amr, f"{tag}_fuaf": c.fuaf, f"{tag}_fmax": c.fmax, f"{tag}_headroom": c.fmax - c.frm - c.fref})
            else:
                row.update({f"{tag}_pres": 0, f"{tag}_ram": np.nan, f"{tag}_rf": np.nan, f"{tag}_fref": np.nan,
                            f"{tag}_amr": np.nan, f"{tag}_fuaf": np.nan, f"{tag}_fmax": np.nan, f"{tag}_headroom": np.nan})
        rte = g[(g.tso == "RTE") & ~g.cneName.str.contains("External", case=False)]
        phys = g[~g.cneName.str.contains("External", case=False)]
        row.update({"n_pres": len(phys), "n_rte": len(rte), "rte_min_rf": rte.rf.min() if len(rte) else np.nan,
                    "rte_mean_rf": rte.rf.mean() if len(rte) else np.nan, "all_min_rf": phys.rf.min(), "all_p10_rf": phys.rf.quantile(0.1)})
        out.append(row)
    return pd.DataFrame(out)


def maxnp_features(mx):
    hi = hour_index(mx.t)
    d = mx.assign(day=hi.day, hour=hi.hour)
    keep = ["maxFR", "minFR", "maxDE", "minDE", "maxNL", "minNL"]
    return d.groupby(["day", "hour"])[keep].mean().reset_index()


def realized(sp, npos, prices):
    """Realized hourly outcomes: Creys binding (any circuit, any MTU), FR/DE net positions, DE-FR spread."""
    sp = sp.copy()
    sp["creys"] = sp.cnecName.str.contains("CREYS-ST-VULBAS", case=False) & (sp.shadowPrice > 0)
    hi = hour_index(sp.t)
    sp["day"], sp["hour"] = hi.day, hi.hour
    bind = sp.groupby(["day", "hour"]).creys.max().rename("bind").reset_index()
    spc = sp[sp.creys].groupby(["day", "hour"]).shadowPrice.mean().rename("creys_sp").reset_index()
    hn = hour_index(npos.t)
    np_h = npos.assign(day=hn.day, hour=hn.hour).groupby(["day", "hour"])[["hub_FR", "hub_DE", "hub_NL"]].mean().reset_index()
    hp = hour_index(prices.t)
    pr_h = prices.assign(day=hp.day, hour=hp.hour).groupby(["day", "hour"])[["DE", "FR"]].mean().reset_index()
    pr_h["spread"] = pr_h.DE - pr_h.FR
    r = pr_h.merge(np_h, on=["day", "hour"], how="left").merge(bind, on=["day", "hour"], how="left").merge(spc, on=["day", "hour"], how="left")
    r["bind"] = r.bind.fillna(False).astype(int)
    return r


def build(fc, mx, sp, npos, prices):
    """Assemble the (day, hour) table: features known on D-1 morning + realized targets for D."""
    dom = domain_features(fc)
    mxf = maxnp_features(mx)
    real = realized(sp, npos, prices)
    X = dom.merge(mxf, on=["day", "hour"], how="left")
    # lags: realized values of D-1 and D-7 at the same hour, and D-1 daily means
    lag = real[["day", "hour", "bind", "hub_FR", "hub_DE", "spread"]].copy()
    lag["day"] = (pd.to_datetime(lag.day) + pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d")
    lag = lag.rename(columns={"bind": "bind_l1", "hub_FR": "fr_np_l1", "hub_DE": "de_np_l1", "spread": "spread_l1"})
    lag7 = real[["day", "hour", "bind", "spread"]].copy()
    lag7["day"] = (pd.to_datetime(lag7.day) + pd.Timedelta(days=7)).dt.strftime("%Y-%m-%d")
    lag7 = lag7.rename(columns={"bind": "bind_l7", "spread": "spread_l7"})
    dm = real.groupby("day").agg(spread_l1_day=("spread", "mean"), bind_l1_day=("bind", "mean"), fr_np_l1_day=("hub_FR", "mean")).reset_index()
    dm["day"] = (pd.to_datetime(dm.day) + pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d")
    X = X.merge(lag, on=["day", "hour"], how="left").merge(lag7, on=["day", "hour"], how="left").merge(dm, on="day", how="left")
    X["wd"] = pd.to_datetime(X.day).dt.weekday
    X["weekend"] = (X.wd >= 5).astype(int)
    X["afternoon"] = X.hour.between(13, 19).astype(int)
    X["night"] = X.hour.isin([21, 22, 23, 0, 1, 2]).astype(int)
    y = real[["day", "hour", "bind", "spread", "creys_sp", "hub_FR"]]
    return X.merge(y, on=["day", "hour"], how="left")


FEATURES = ["c2_pres", "c2_rf", "c2_fref", "c2_amr", "c2_fuaf", "c2_headroom", "c1_pres", "c1_rf", "n_rte", "rte_min_rf", "rte_mean_rf",
            "all_min_rf", "all_p10_rf", "maxFR", "minFR", "maxDE", "minDE", "bind_l1", "fr_np_l1", "de_np_l1", "spread_l1", "bind_l7",
            "spread_l7", "spread_l1_day", "bind_l1_day", "fr_np_l1_day", "weekend", "afternoon", "night", "hour"]
