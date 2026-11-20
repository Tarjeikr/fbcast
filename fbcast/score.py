"""Score every issued forecast whose day-ahead results are now published. Writes scorecard/<day>.json and scorecard/log.csv.

Usage: python -m fbcast.score
"""
import glob, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fbcast import data
from fbcast.features import realized, product_forecast, product_hours, PRODUCT_MIN_HOURS, daily_forecasts, previous_product_day

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _f(v):
    return None if v is None or pd.isna(v) else round(float(v), 2)


def _pinball(y, q, tau):
    d = np.asarray(y) - np.asarray(q)
    return float(np.mean(np.maximum(tau * d, (tau - 1) * d)))


def quantile_scores(H):
    """Pinball loss, coverage and median error of the spread quantiles, against the climatological quantiles the forecast was issued with."""
    if "spread_p50" not in H or H.spread_p50.isna().all():
        return None
    y = H.spread.values
    aft = H[H.hour.isin([15, 16, 17])]
    out = {"pinball": float(np.mean([_pinball(y, H.spread_p10, 0.1), _pinball(y, H.spread_p50, 0.5), _pinball(y, H.spread_p90, 0.9)])),
           "pinball_clim": float(np.mean([_pinball(y, H.clim_q10, 0.1), _pinball(y, H.clim_q50, 0.5), _pinball(y, H.clim_q90, 0.9)])),
           "coverage80": float(np.mean((y >= H.spread_p10) & (y <= H.spread_p90))), "coverage80_clim": float(np.mean((y >= H.clim_q10) & (y <= H.clim_q90))),
           "mae_p50": float(np.mean(np.abs(y - H.spread_p50))), "mae_clim_median": float(np.mean(np.abs(y - H.clim_q50))), "mae_zero": float(np.mean(np.abs(y))),
           "band_width": float(np.mean(H.spread_p90 - H.spread_p10)),
           "afternoon_p50": float(aft.spread_p50.mean()), "afternoon_p10": float(aft.spread_p10.mean()), "afternoon_p90": float(aft.spread_p90.mean())}
    if H.spread_prev.notna().any():
        out["mae_persistence"] = float(np.mean(np.abs(H.spread - H.spread_prev.fillna(0))))
    return out


def product_scores(H, day, cal=None):
    """Daily base and peak: the forecast issued (average of hourly quantiles, with the product band calibration the forecast was issued with),
    the climatological equivalent, the grid-only model's equivalent when the file carries one, yesterday's value and the outcome."""
    rows = H.to_dict("records")
    f = product_forecast(rows, day, cal=cal)
    c = product_forecast(rows, day, keys=("clim_q10", "clim_q50", "clim_q90"))
    g = product_forecast(rows, day, keys=("grid_p10", "grid_p50", "grid_p90")) if "grid_p50" in H else {}
    out = {}
    for name, v in f.items():
        X = H[H.hour.isin(product_hours(name))]
        if len(X) < PRODUCT_MIN_HOURS[name]:
            continue
        d = {k: round(x, 2) if isinstance(x, float) else x for k, x in v.items()}
        d.update({"actual": round(float(X.spread.mean()), 2), "n_actual": int(len(X)),
                  "clim_p50": round(c[name]["p50"], 2) if name in c else None, "clim_p_pos": round(c[name]["p_pos"], 3) if name in c else None,
                  "prev_actual": round(float(X.spread_prev.mean()), 2) if X.spread_prev.notna().sum() >= PRODUCT_MIN_HOURS[name] else None})
        if name in g:
            d.update({"grid_p10": round(g[name]["p10"], 2), "grid_p50": round(g[name]["p50"], 2), "grid_p90": round(g[name]["p90"], 2), "grid_p_pos": round(g[name]["p_pos"], 3)})
        out[name] = d
    return out


def daily_scores(H, day, cal, Rall):
    """Base and peak of the DE price, the FR price and the DE-FR spread: the forecast as issued (with its band calibration), the outcome,
    and the outcome on the product's previous delivery day, which a forecast has to beat to be worth anything."""
    out = {}
    for key, v in daily_forecasts(H.to_dict("records"), day, cal).items():
        target, name = key.split("_")
        X = H[H.hour.isin(product_hours(name))]
        if len(X) < PRODUCT_MIN_HOURS[name]:
            continue
        prev_day = previous_product_day(name, day)
        Y = Rall[(Rall.day == prev_day) & Rall.hour.isin(product_hours(name))][target].dropna()
        actual = float(X[target].mean())
        out[key] = {"p10": round(v["p10"], 2), "p50": round(v["p50"], 2), "p90": round(v["p90"], 2), "actual": round(actual, 2), "in_band": bool(v["p10"] <= actual <= v["p90"]),
                    "prev_day": prev_day, "prev_actual": round(float(Y.mean()), 2) if len(Y) >= PRODUCT_MIN_HOURS[name] else None}
    return out


def level_scores(H):
    """DE and FR price quantiles against the outcome, with yesterday's price at the same hour as the benchmark."""
    out = {}
    for z, pre in (("DE", "de"), ("FR", "fr")):
        if f"{pre}_p50" not in H or H[f"{pre}_p50"].isna().all():
            continue
        y = H[z].values
        out[z] = {"mae_p50": float(np.mean(np.abs(y - H[f"{pre}_p50"]))), "coverage80": float(np.mean((y >= H[f"{pre}_p10"]) & (y <= H[f"{pre}_p90"]))),
                  "pinball": float(np.mean([_pinball(y, H[f"{pre}_p10"], 0.1), _pinball(y, H[f"{pre}_p50"], 0.5), _pinball(y, H[f"{pre}_p90"], 0.9)])),
                  "mae_persistence": float(np.mean(np.abs(H[z] - H[f"{z}_prev"]))) if H[f"{z}_prev"].notna().all() else None,
                  "actual_mean": float(np.mean(y)), "p50_mean": float(H[f"{pre}_p50"].mean())}
    return out or None


def grid_scores(H):
    """The grid-only model's spread and sign forecasts on the same hours, for a like-for-like comparison with the fundamentals model."""
    if "grid_p50" not in H or H.grid_p50.isna().all():
        return None
    y = H.spread.values; s = (H.spread > 0).astype(int)
    return {"pinball": float(np.mean([_pinball(y, H.grid_p10, 0.1), _pinball(y, H.grid_p50, 0.5), _pinball(y, H.grid_p90, 0.9)])),
            "mae_p50": float(np.mean(np.abs(y - H.grid_p50))), "coverage80": float(np.mean((y >= H.grid_p10) & (y <= H.grid_p90))),
            "sign_brier": float(np.mean((H.grid_p_de_above_fr - s) ** 2)), "sign_hit": float(((H.grid_p_de_above_fr > 0.5) == s).mean())}


def score_day(day, fc, prices=None):
    _, results_pub = data.results_published(day)
    status = fc["status"]
    if status == "unverified":
        status = "ex-ante" if results_pub and fc["issued_at_utc"] < results_pub else "late"
    sp = data.load_days("shadowPrices", [day])
    npos = data.load_days("netPos", [day])
    if sp.empty:
        return None
    prev = (pd.Timestamp(day) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    # four days back: the benchmark for a Monday peak is the Friday before
    pr = prices if prices is not None else data.fetch_prices((pd.Timestamp(day) - pd.Timedelta(days=4)).strftime("%Y-%m-%d"), (pd.Timestamp(day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    Rall = realized(sp, npos, pr)
    R = Rall[Rall.day == day]
    Rprev = Rall[Rall.day == prev][["hour", "spread", "DE", "FR"]].rename(columns={"spread": "spread_prev", "DE": "DE_prev", "FR": "FR_prev"})
    if len(R) < 20:
        return None
    H = pd.DataFrame(fc["hours"]).merge(R[["hour", "bind", "spread", "hub_FR", "DE", "FR"]], on="hour", how="inner").merge(Rprev, on="hour", how="left")
    H = H.dropna(subset=["p_bind", "p_de_above_fr"])
    if len(H) < 20:
        status = "incomplete"  # issued on a partially published domain; kept but not counted
    y, s = H.bind.astype(int), (H.spread > 0).astype(int)
    mdl = fc.get("model") or {}
    gate = fc.get("gate_closure_utc") or (pd.Timestamp(day) - pd.Timedelta(hours=12)).tz_localize("Europe/Berlin").tz_convert("UTC").isoformat()   # 12:00 CET on D-1
    out = {"day": day, "status": status, "issued_at_utc": fc["issued_at_utc"], "results_published_utc": results_pub, "n_hours": int(len(H)),
           "issued_before_gate_closure": bool(pd.Timestamp(fc["issued_at_utc"]) < pd.Timestamp(gate)),
           "model_version": mdl.get("version", 1), "spread_model": mdl.get("spread_model", "grid"),
           "bind": {"actual_hours": int(y.sum()), "expected_hours": round(float(H.p_bind.sum()), 1), "brier": float(np.mean((H.p_bind - y) ** 2)),
                    "hit": float(((H.p_bind > 0.5) == y).mean()), "logloss": float(-np.mean(y * np.log(H.p_bind.clip(1e-3, 1 - 1e-3)) + (1 - y) * np.log(1 - H.p_bind.clip(1e-3, 1 - 1e-3))))},
           "sign": {"actual_pos_hours": int(s.sum()), "brier": float(np.mean((H.p_de_above_fr - s) ** 2)), "hit": float(((H.p_de_above_fr > 0.5) == s).mean())},
           "level": {"mae": float((H.e_spread - H.spread).abs().mean()), "mae_zero": float(H.spread.abs().mean()), "actual_mean": float(H.spread.mean()), "forecast_mean": float(H.e_spread.mean())},
           "afternoon_15_17": {"actual_spread": float(H[H.hour.isin([15, 16, 17])].spread.mean()), "forecast_spread": float(H[H.hour.isin([15, 16, 17])].e_spread.mean()),
                               "p_pos": float(H[H.hour.isin([15, 16, 17])].p_de_above_fr.mean()), "actual_pos": int(H[H.hour.isin([15, 16, 17])].spread.mean() > 0),
                               "p_bind": float(H[H.hour.isin([15, 16, 17])].p_bind.mean()), "actual_bind": float(H[H.hour.isin([15, 16, 17])].bind.mean())},
           "fr_net_position_mean": float(H.hub_FR.mean()) if H.hub_FR.notna().any() else None,
           "quantiles": quantile_scores(H),
           "levels": level_scores(H), "grid_only": grid_scores(H),
           "products": product_scores(H, day, mdl.get("product_cal")) if status != "incomplete" else {},
           "daily": daily_scores(H, day, mdl.get("product_cal"), Rall) if status != "incomplete" else {},
           "hours": [{"hour": int(r.hour), "p_bind": r.p_bind, "bind": int(r.bind), "p_de_above_fr": r.p_de_above_fr, "spread": round(float(r.spread), 1), "e_spread": r.e_spread,
                      "p10": _f(getattr(r, "spread_p10", None)), "p50": _f(getattr(r, "spread_p50", None)), "p90": _f(getattr(r, "spread_p90", None)),
                      "clim_q10": _f(getattr(r, "clim_q10", None)), "clim_q50": _f(getattr(r, "clim_q50", None)), "clim_q90": _f(getattr(r, "clim_q90", None)),
                      "de": _f(r.DE), "fr": _f(r.FR), "de_p50": _f(getattr(r, "de_p50", None)), "fr_p50": _f(getattr(r, "fr_p50", None))} for r in H.itertuples()]}
    return out


def verify():
    """Recompute every committed scorecard from freshly downloaded JAO and SMARD data and report any difference."""
    bad = 0
    files = sorted(glob.glob(os.path.join(ROOT, "scorecard", "2*.json")))
    days = [os.path.basename(f)[:-5] for f in files]
    # one price download for the whole record: a request per day runs into the API's rate limit as the record grows
    prices = data.fetch_prices((pd.Timestamp(min(days)) - pd.Timedelta(days=4)).strftime("%Y-%m-%d"), (pd.Timestamp(max(days)) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")) if days else None
    for fn in files:
        old = json.load(open(fn)); day = old["day"]
        fc = json.load(open(os.path.join(ROOT, "forecasts", f"{day}.json")))
        for ds in ("shadowPrices", "netPos"):
            data.fetch_day(ds, day, force=True)
        new = score_day(day, fc, prices)
        same = new is not None and abs(new["bind"]["brier"] - old["bind"]["brier"]) < 1e-6 and abs(new["sign"]["brier"] - old["sign"]["brier"]) < 1e-6 and new["bind"]["actual_hours"] == old["bind"]["actual_hours"]
        ok_time = (new is None) or (new["status"] != "ex-ante") or (new.get("results_published_utc") is None) or (fc["issued_at_utc"] < new["results_published_utc"])
        print(f"{day}: scorecard {'reproduced' if same else 'DIFFERS'}; issued {fc['issued_at_utc'][:16]} status {new['status'] if new else fc['status']}; results published {new['results_published_utc'] if new else 'n/a'}")
        bad += (not same) or (not ok_time)
    print("verification", "PASSED" if bad == 0 else f"FAILED on {bad} day(s)")
    return bad


def main():
    if "--verify" in sys.argv:
        sys.exit(1 if verify() else 0)
    os.makedirs(os.path.join(ROOT, "scorecard"), exist_ok=True)
    done = {os.path.basename(f)[:-5] for f in glob.glob(os.path.join(ROOT, "scorecard", "*.json"))}
    pending, failed = [], []
    for fn in sorted(glob.glob(os.path.join(ROOT, "forecasts", "*.json"))):
        fc = json.load(open(fn)); day = fc["day"]
        if day in done:
            continue
        try:
            published, _ = data.results_published(day)
        except Exception as e:
            print("could not check results for", day, "(%s)" % type(e).__name__, flush=True); failed.append(day); continue
        if published:
            pending.append((day, fc))
    prices = None
    if pending:  # one price download for the whole backlog: energy-charts rate-limits repeated requests
        lo, hi = min(d for d, _ in pending), max(d for d, _ in pending)
        try:
            prices = data.fetch_prices((pd.Timestamp(lo) - pd.Timedelta(days=4)).strftime("%Y-%m-%d"), (pd.Timestamp(hi) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
        except Exception as e:
            print("could not download prices (%s); nothing scored this run" % type(e).__name__, flush=True)
            failed += [d for d, _ in pending]; pending = []
    for day, fc in pending:
        try:
            sc = score_day(day, fc, prices)
        except Exception as e:
            print("could not score", day, "this run (%s: %s)" % (type(e).__name__, str(e)[:120]), flush=True); failed.append(day); continue
        if sc is None:
            failed.append(day); continue
        json.dump(sc, open(os.path.join(ROOT, "scorecard", f"{day}.json"), "w"), indent=1)
        print("scored", day, sc["status"], "| bind Brier %.3f hit %.2f | sign Brier %.3f hit %.2f | afternoon spread %.1f" % (
            sc["bind"]["brier"], sc["bind"]["hit"], sc["sign"]["brier"], sc["sign"]["hit"], sc["afternoon_15_17"]["actual_spread"]), flush=True)
    rebuild_log()
    json.dump({"run_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%d %H:%M"), "not_scored": sorted(set(failed))}, open(os.path.join(ROOT, "scorecard", "last_run.txt"), "w"))
    if failed:
        print("NOT SCORED this run:", sorted(set(failed)), "- they stay pending and are retried next run", flush=True)


def rebuild_log():
    """scorecard/log.csv is derived from the scorecard files, so it is rebuilt in full every run (columns may grow over time)."""
    rows = []
    for fn in sorted(glob.glob(os.path.join(ROOT, "scorecard", "*.json"))):
        sc = json.load(open(fn)); q = sc.get("quantiles") or {}
        rows.append({"day": sc["day"], "status": sc["status"], "issued_at_utc": sc.get("issued_at_utc"), "results_published_utc": sc.get("results_published_utc"),
                     "bind_brier": sc["bind"]["brier"], "bind_hit": sc["bind"]["hit"], "bind_actual_hours": sc["bind"]["actual_hours"], "bind_expected_hours": sc["bind"]["expected_hours"],
                     "sign_brier": sc["sign"]["brier"], "sign_hit": sc["sign"]["hit"], "aft_actual_spread": sc["afternoon_15_17"]["actual_spread"], "aft_p_pos": sc["afternoon_15_17"]["p_pos"],
                     "pinball": q.get("pinball"), "pinball_clim": q.get("pinball_clim"), "coverage80": q.get("coverage80"), "mae_p50": q.get("mae_p50"), "mae_persistence": q.get("mae_persistence"),
                     "fr_net_position_mean": sc.get("fr_net_position_mean"),
                     "model_version": sc.get("model_version", 1), "before_gate_closure": sc.get("issued_before_gate_closure"),
                     "de_mae_p50": ((sc.get("levels") or {}).get("DE") or {}).get("mae_p50"), "fr_mae_p50": ((sc.get("levels") or {}).get("FR") or {}).get("mae_p50"),
                     "grid_pinball": (sc.get("grid_only") or {}).get("pinball"),
                     **{f"{k}_{f}": v.get(f) for k, v in (sc.get("daily") or {}).items() for f in ("p50", "actual")},
                     **{f"{k}_{f}": (sc.get("products") or {}).get(k, {}).get(f) for k in ("base", "peak") for f in ("p50", "p_pos", "actual")}})
    if rows:
        pd.DataFrame(rows).to_csv(os.path.join(ROOT, "scorecard", "log.csv"), index=False)


if __name__ == "__main__":
    main()
