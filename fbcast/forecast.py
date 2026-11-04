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
        return
    deadline = time.time() + 60 * a.wait_minutes
    while True:
        ok, dom_mod = data.domain_published(day)
        if ok:
            break
        if time.time() > deadline:
            print("domain for", day, "not published yet; giving up")
            sys.exit(2)
        time.sleep(600)
    published, res_mod = data.results_published(day)
    issued_at = pd.Timestamp.now("UTC")
    bundle_path = os.path.join(ROOT, "models", "bundle.pkl")
    bundle = model.load(bundle_path)
    model_sha = hashlib.sha256(open(bundle_path, "rb").read()).hexdigest()
    X = features_for_day(day)
    if X is None:
        print("domain data for", day, "incomplete")
        sys.exit(2)
    P = model.predict(bundle, X).sort_values("hour")
    hours = [{"hour": int(r.hour), "p_bind": round(float(r.p_bind), 3), "p_de_above_fr": round(float(r.p_pos), 3), "e_spread": round(float(r.e_spread), 1),
              "creys_ram": None if pd.isna(r.c2_ram) else round(float(r.c2_ram)), "creys_fref": None if pd.isna(r.c2_fref) else round(float(r.c2_fref)),
              "maxFR": round(float(r.maxFR)), "minFR": round(float(r.minFR))} for r in P.itertuples()]
    aft = P[P.hour.isin([15, 16, 17])]
    night = P[P.hour.isin([21, 22, 23])]
    fc = {"day": day, "issued_at_utc": issued_at.isoformat(), "status": "late" if published else "ex-ante",
          "domain_published_utc": dom_mod, "results_published_utc": res_mod,
          "model": {"trained_at": bundle.get("trained_at"), "train_days": bundle.get("train_days"), "bundle_sha256": model_sha},
          "summary": {"hours_expected_binding": round(float(P.p_bind.sum()), 1), "p_bind_afternoon_15_17": round(float(aft.p_bind.mean()), 3),
                      "p_de_above_fr_afternoon_15_17": round(float(aft.p_pos.mean()), 3), "e_spread_afternoon_15_17": round(float(aft.e_spread.mean()), 1),
                      "p_de_above_fr_night_21_23": round(float(night.p_pos.mean()), 3), "e_spread_day": round(float(P.e_spread.mean()), 1),
                      "creys_min_ram": None if P.c2_ram.isna().all() else round(float(P.c2_ram.min())), "fr_max_export": round(float(P.maxFR.max()))},
          "hours": hours}
    os.makedirs(os.path.join(ROOT, "forecasts"), exist_ok=True)
    json.dump(fc, open(out_fn, "w"), indent=1)
    log_fn = os.path.join(ROOT, "forecasts", "log.csv")
    row = {"day": day, "issued_at_utc": fc["issued_at_utc"], "status": fc["status"], **fc["summary"]}
    pd.DataFrame([row]).to_csv(log_fn, mode="a", header=not os.path.exists(log_fn), index=False)
    print(json.dumps({k: v for k, v in fc.items() if k != "hours"}, indent=1))


if __name__ == "__main__":
    main()
