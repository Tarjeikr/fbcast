"""Issue the forecast for CET day D (default: tomorrow) from what JAO published this morning.

Usage: python -m fbcast.forecast [--day 2026-11-05] [--wait-minutes 90]

Two models contribute to one forecast file:
  * the grid model (fbcast.model): P(Creys–St-Vulbas binds) from the published flow-based domain;
  * the fundamentals model (fbcast.fund): quantiles of the DE−FR spread, P(DE > FR) and quantiles of the DE and FR prices
    from the TSOs' D-2 congestion forecast, the reference programmes, the domain's limits and yesterday's market results.
The grid model's own spread and sign forecasts are kept in every file under `grid_*`, so both can be scored on the same days.
If the fundamentals inputs are not on JAO in time, the file is issued from the grid model alone and says so.

The script refuses to produce a countable forecast if the day-ahead results for D are already on JAO (then the file is
written with status "late" and is excluded from the scorecard). With --wait-minutes it polls until the final domain appears
or the time runs out, so a scheduled run can start before the publication and wait for it.
"""
import argparse, hashlib, json, os, sys, time
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fbcast import data, model, fund
from fbcast.features import domain_features, maxnp_features, BLOCKS, product_forecast, daily_forecasts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def gate_closure(day):
    """The day-ahead auction for delivery day D closes at 12:00 Central European time on D-1."""
    return (pd.Timestamp(day) - pd.Timedelta(hours=12)).tz_localize("Europe/Berlin").tz_convert("UTC")


def features_for_day(day):
    fc = data.load_days("finalComputation", [day])
    mx = data.load_days("maxNetPos", [day])
    if fc.empty or mx.empty:
        return None
    X = domain_features(fc).merge(maxnp_features(mx), on=["day", "hour"], how="left")
    X["wd"] = pd.to_datetime(X.day).dt.weekday
    X["weekend"] = (X.wd >= 5).astype(int)
    return X


def fundamentals_for_day(day, deadline):
    """Feature rows for the fundamentals model, waiting for JAO's pre-coupling datasets until `deadline` (epoch seconds) or
    20 minutes before gate closure, whichever comes first. Returns None if they cannot be had; the caller then falls back."""
    cutoff = min(deadline, (gate_closure(day) - pd.Timedelta(minutes=20)).timestamp())
    while True:
        try:
            if fund.published(day):
                X = fund.live_features(day)
                if X is not None:
                    return X
                print("fundamentals inputs for", day, "are incomplete", flush=True)
            else:
                print("d2CF / reference programmes for", day, "not on JAO yet", flush=True)
        except Exception as e:
            print("fundamentals inputs failed (%s: %s)" % (type(e).__name__, str(e)[:120]), flush=True)
        if time.time() > cutoff:
            return None
        time.sleep(120)


def rebuild_log():
    """log.csv is derived from the forecast files, so it is rebuilt in full every run."""
    import glob
    rows = []
    for fn in sorted(glob.glob(os.path.join(ROOT, "forecasts", "*.json"))):
        f = json.load(open(fn))
        rows.append({"day": f["day"], "issued_at_utc": f["issued_at_utc"], "status": f["status"], **{k: v for k, v in f["summary"].items() if k not in ("blocks", "products", "daily")}})
    if rows:
        pd.DataFrame(rows).to_csv(os.path.join(ROOT, "forecasts", "log.csv"), index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=(pd.Timestamp.now(tz="Europe/Berlin") + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    ap.add_argument("--wait-minutes", type=int, default=0)
    ap.add_argument("--force", action="store_true", help="overwrite an existing forecast file")
    a = ap.parse_args()
    day = a.day
    out_fn = os.path.join(ROOT, "forecasts", f"{day}.json")
    if os.path.exists(out_fn) and not a.force:
        print("forecast for", day, "already issued; nothing to do")
        rebuild_log()
        return
    deadline = time.time() + 60 * a.wait_minutes
    while True:
        try:
            ok, dom_mod = data.domain_published(day)
            if ok and not data.day_complete(day):
                print("domain for", day, "is still being published (not all hours yet); waiting", flush=True)
                ok = False
        except Exception as e:  # JAO slow or unreachable: treat as not yet published and keep waiting
            ok, dom_mod = False, None
            print("JAO not answering (%s); will retry" % type(e).__name__, flush=True)
        if ok:
            break
        if time.time() > deadline:
            print("domain for", day, "not published yet; giving up")
            sys.exit(2)
        time.sleep(300)
    bundle_path = os.path.join(ROOT, "models", "bundle.pkl")
    bundle = model.load(bundle_path)
    model_sha = hashlib.sha256(open(bundle_path, "rb").read()).hexdigest()
    X = None
    for attempt in range(4):
        try:
            X = features_for_day(day)
            if X is not None:
                break
        except Exception as e:
            print("data pull failed (%s), attempt %d" % (type(e).__name__, attempt + 1), flush=True)
        time.sleep(60 * (attempt + 1))
    if X is None:
        print("domain data for", day, "incomplete")
        sys.exit(2)
    P = model.predict(bundle, X).sort_values("hour")
    if P[["p_bind", "p_pos", "q50"]].isna().any().any() or len(P) < 23:
        print("features incomplete for", day, "(NaN hours); not issuing", flush=True)
        sys.exit(2)
    # fundamentals model: the forecast of record for the spread, its sign and the two prices whenever its inputs are available
    F = None
    fm = bundle.get("fund")
    if fm:
        Xf = fundamentals_for_day(day, deadline)
        if Xf is not None:
            F = fund.predict(fm, Xf).set_index("hour")
            if F[["q10", "q50", "q90", "p_pos"]].isna().any().any() or not set(P.hour).issubset(F.index):
                print("fundamentals forecast incomplete for", day, "; issuing from the grid model alone", flush=True)
                F = None
        else:
            print("fundamentals inputs not available in time for", day, "; issuing from the grid model alone", flush=True)
    # status is settled as late as possible: it compares the moment of issue with the publication of the results
    try:
        published, res_mod = data.results_published(day)
        status = "late" if published else "ex-ante"
    except Exception as e:
        published, res_mod, status = None, None, "unverified"  # the scorer settles it from JAO's publication time of the results
        print("results check failed (%s); status left for the scorer to settle" % type(e).__name__, flush=True)
    issued_at = pd.Timestamp.now("UTC")
    gate = gate_closure(day)
    r1 = lambda v: round(float(v), 1)
    hours = []
    for r in P.itertuples():
        h = {"hour": int(r.hour), "p_bind": round(float(r.p_bind), 3)}
        g = {"p_de_above_fr": round(float(r.p_pos), 3), "spread_p10": r1(r.q10), "spread_p50": r1(r.q50), "spread_p90": r1(r.q90)}
        if F is not None:
            f = F.loc[r.hour]
            h.update({"p_de_above_fr": round(float(f.p_pos), 3), "spread_p10": r1(f.q10), "spread_p50": r1(f.q50), "spread_p90": r1(f.q90),
                      "de_p10": r1(f.de_q10), "de_p50": r1(f.de_q50), "de_p90": r1(f.de_q90), "fr_p10": r1(f.fr_q10), "fr_p50": r1(f.fr_q50), "fr_p90": r1(f.fr_q90),
                      "grid_p_de_above_fr": g["p_de_above_fr"], "grid_p10": g["spread_p10"], "grid_p50": g["spread_p50"], "grid_p90": g["spread_p90"]})
        else:
            h.update(g)
        h.update({"e_spread": r1(r.e_spread), "clim_q10": r1(r.clim_q10), "clim_q50": r1(r.clim_q50), "clim_q90": r1(r.clim_q90),
                  "creys_ram": None if pd.isna(r.c2_ram) else round(float(r.c2_ram)), "creys_fref": None if pd.isna(r.c2_fref) else round(float(r.c2_fref)),
                  "maxFR": round(float(r.maxFR)), "minFR": round(float(r.minFR))})
        hours.append(h)
    H = pd.DataFrame(hours)
    aft, night = H[H.hour.isin([15, 16, 17])], H[H.hour.isin([21, 22, 23])]
    blocks = {}
    for name, (a_, b_) in BLOCKS.items():
        B = H[(H.hour >= a_) & (H.hour <= b_)]
        blocks[name] = {"expected_binding_hours": r1(B.p_bind.sum()), "p_de_above_fr": round(float(B.p_de_above_fr.mean()), 3),
                        "spread_p10": r1(B.spread_p10.mean()), "spread_p50": r1(B.spread_p50.mean()), "spread_p90": r1(B.spread_p90.mean())}
        if F is not None:
            blocks[name].update({"de_p50": r1(B.de_p50.mean()), "fr_p50": r1(B.fr_p50.mean())})
    # band factors of the daily products: "base" and "peak" for the spread, "DE_base", "FR_peak", ... for the prices
    product_cal = {k: v for k, v in fm.get("cal", {}).items() if k.endswith(("base", "peak"))} if F is not None else {}
    meta = {"version": 2 if F is not None else 1, "trained_at": bundle.get("trained_at"), "train_days": bundle.get("train_days"), "bundle_sha256": model_sha, "rules": model.RULES,
            "spread_model": "fundamentals" if F is not None else "grid", "product_cal": product_cal}
    if F is not None:
        meta["fund"] = {"train_days": fm.get("train_days"), "n_train": fm.get("n_train"), "band_factors": {k: fm["cal"][k] for k in ("spread", "DE", "FR") if k in fm.get("cal", {})}}
    fc = {"day": day, "issued_at_utc": issued_at.isoformat(), "status": status,
          "gate_closure_utc": gate.isoformat(), "issued_before_gate_closure": bool(issued_at < gate),
          "domain_published_utc": dom_mod, "results_published_utc": res_mod, "model": meta,
          "summary": {"hours_expected_binding": r1(H.p_bind.sum()), "p_bind_afternoon_15_17": round(float(aft.p_bind.mean()), 3),
                      "p_de_above_fr_afternoon_15_17": round(float(aft.p_de_above_fr.mean()), 3),
                      "spread_p50_afternoon_15_17": r1(aft.spread_p50.mean()), "spread_p10_afternoon_15_17": r1(aft.spread_p10.mean()), "spread_p90_afternoon_15_17": r1(aft.spread_p90.mean()),
                      "p_de_above_fr_night_21_23": round(float(night.p_de_above_fr.mean()), 3), "spread_p50_day": r1(H.spread_p50.mean()),
                      "creys_min_ram": None if P.c2_ram.isna().all() else round(float(P.c2_ram.min())), "fr_max_export": round(float(P.maxFR.max())), "blocks": blocks},
          "hours": hours}
    if F is not None:
        fc["summary"].update({"de_base_p50": r1(H.de_p50.mean()), "fr_base_p50": r1(H.fr_p50.mean())})
    prod = product_forecast(hours, day, cal=product_cal)
    fc["summary"]["products"] = {k: {kk: (round(vv, 3) if kk == "p_pos" else round(vv, 1) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in prod.items()}
    for k in ("base", "peak"):
        fc["summary"][f"{k}_spread_p50"] = round(prod[k]["p50"], 1) if k in prod else None
        fc["summary"][f"p_{k}_above_zero"] = round(prod[k]["p_pos"], 3) if k in prod else None
    # the headline: base and peak of the DE price, the FR price and the DE-FR spread, each with its P10-P90 band
    fc["summary"]["daily"] = {k: {kk: (round(vv, 1) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in daily_forecasts(hours, day, product_cal).items()}
    os.makedirs(os.path.join(ROOT, "forecasts"), exist_ok=True)
    json.dump(fc, open(out_fn, "w"), indent=1)
    rebuild_log()
    print(json.dumps({k: v for k, v in fc.items() if k != "hours"}, indent=1))


if __name__ == "__main__":
    main()
