"""Issue the forecast for CET day D (default: tomorrow) from the domain JAO published this morning.

Usage: python -m fbcast.forecast [--day 2026-11-05] [--wait-minutes 90]

The script refuses to produce a countable forecast if the day-ahead results for D are already on JAO
(then the file is written with status "late" and is excluded from the scorecard). With --wait-minutes it polls
until the final domain appears or the time runs out, so a scheduled run at 10:00 UTC can wait for a late publication.
"""
import argparse, hashlib, json, os, sys, time
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fbcast import data, model
from fbcast.features import domain_features, maxnp_features

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def features_for_day(day):
    fc = data.load_days("finalComputation", [day])
    mx = data.load_days("maxNetPos", [day])
    if fc.empty or mx.empty:
        return None
    X = domain_features(fc).merge(maxnp_features(mx), on=["day", "hour"], how="left")
    X["wd"] = pd.to_datetime(X.day).dt.weekday
    X["weekend"] = (X.wd >= 5).astype(int)
    return X


def rebuild_log():
    """log.csv is derived from the forecast files, so it is rebuilt in full every run."""
    import glob
    rows = []
    for fn in sorted(glob.glob(os.path.join(ROOT, "forecasts", "*.json"))):
        f = json.load(open(fn))
        rows.append({"day": f["day"], "issued_at_utc": f["issued_at_utc"], "status": f["status"], **f["summary"]})
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
    try:
        published, res_mod = data.results_published(day)
        status = "late" if published else "ex-ante"
    except Exception as e:
        published, res_mod, status = None, None, "unverified"  # the scorer settles it from JAO's publication time of the results
        print("results check failed (%s); status left for the scorer to settle" % type(e).__name__, flush=True)
    issued_at = pd.Timestamp.now("UTC")
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
    hours = [{"hour": int(r.hour), "p_bind": round(float(r.p_bind), 3), "p_de_above_fr": round(float(r.p_pos), 3), "e_spread": round(float(r.e_spread), 1),
              "spread_p10": round(float(r.q10), 1), "spread_p50": round(float(r.q50), 1), "spread_p90": round(float(r.q90), 1),
              "clim_q10": round(float(r.clim_q10), 1), "clim_q50": round(float(r.clim_q50), 1), "clim_q90": round(float(r.clim_q90), 1),
              "creys_ram": None if pd.isna(r.c2_ram) else round(float(r.c2_ram)), "creys_fref": None if pd.isna(r.c2_fref) else round(float(r.c2_fref)),
              "maxFR": round(float(r.maxFR)), "minFR": round(float(r.minFR))} for r in P.itertuples()]
    aft = P[P.hour.isin([15, 16, 17])]
    night = P[P.hour.isin([21, 22, 23])]
    fc = {"day": day, "issued_at_utc": issued_at.isoformat(), "status": status,
          "domain_published_utc": dom_mod, "results_published_utc": res_mod,
          "model": {"trained_at": bundle.get("trained_at"), "train_days": bundle.get("train_days"), "bundle_sha256": model_sha},
          "summary": {"hours_expected_binding": round(float(P.p_bind.sum()), 1), "p_bind_afternoon_15_17": round(float(aft.p_bind.mean()), 3),
                      "p_de_above_fr_afternoon_15_17": round(float(aft.p_pos.mean()), 3),
                      "spread_p50_afternoon_15_17": round(float(aft.q50.mean()), 1), "spread_p10_afternoon_15_17": round(float(aft.q10.mean()), 1), "spread_p90_afternoon_15_17": round(float(aft.q90.mean()), 1),
                      "p_de_above_fr_night_21_23": round(float(night.p_pos.mean()), 3), "spread_p50_day": round(float(P.q50.mean()), 1),
                      "creys_min_ram": None if P.c2_ram.isna().all() else round(float(P.c2_ram.min())), "fr_max_export": round(float(P.maxFR.max()))},
          "hours": hours}
    os.makedirs(os.path.join(ROOT, "forecasts"), exist_ok=True)
    json.dump(fc, open(out_fn, "w"), indent=1)
    rebuild_log()
    print(json.dumps({k: v for k, v in fc.items() if k != "hours"}, indent=1))


if __name__ == "__main__":
    main()
