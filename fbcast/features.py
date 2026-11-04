"""Feature construction for the Core binding-constraint forecast.

Information set for day D is what a desk has at ~10:00 CET on D-1:
  * the final Core flow-based domain for D (JAO finalComputation, presolved CNECs) and max net positions for D,
    both published on D-1 morning;
  * realized day-ahead results for D-1 (shadow prices, net positions, prices), published on D-2 ~13:00 CET.
Nothing from D's own auction is used.
"""
import glob, json
import numpy as np, pandas as pd

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
