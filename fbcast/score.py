"""Score every issued forecast whose day-ahead results are now published. Writes scorecard/<day>.json and scorecard/log.csv.

Usage: python -m fbcast.score
"""
import glob, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fbcast import data
from fbcast.features import realized

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def score_day(day, fc):
    sp = data.load_days("shadowPrices", [day])
    npos = data.load_days("netPos", [day])
    if sp.empty:
        return None
    pr = data.fetch_prices(day, (pd.Timestamp(day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    R = realized(sp, npos, pr)
    R = R[R.day == day]
    if len(R) < 20:
        return None
    H = pd.DataFrame(fc["hours"]).merge(R[["hour", "bind", "spread", "hub_FR"]], on="hour", how="inner")
    y, s = H.bind.astype(int), (H.spread > 0).astype(int)
    out = {"day": day, "status": fc["status"], "issued_at_utc": fc["issued_at_utc"], "n_hours": int(len(H)),
           "bind": {"actual_hours": int(y.sum()), "expected_hours": round(float(H.p_bind.sum()), 1), "brier": float(np.mean((H.p_bind - y) ** 2)),
                    "hit": float(((H.p_bind > 0.5) == y).mean()), "logloss": float(-np.mean(y * np.log(H.p_bind.clip(1e-3, 1 - 1e-3)) + (1 - y) * np.log(1 - H.p_bind.clip(1e-3, 1 - 1e-3))))},
           "sign": {"actual_pos_hours": int(s.sum()), "brier": float(np.mean((H.p_de_above_fr - s) ** 2)), "hit": float(((H.p_de_above_fr > 0.5) == s).mean())},
           "level": {"mae": float((H.e_spread - H.spread).abs().mean()), "mae_zero": float(H.spread.abs().mean()), "actual_mean": float(H.spread.mean()), "forecast_mean": float(H.e_spread.mean())},
           "afternoon_15_17": {"actual_spread": float(H[H.hour.isin([15, 16, 17])].spread.mean()), "forecast_spread": float(H[H.hour.isin([15, 16, 17])].e_spread.mean()),
                               "p_pos": float(H[H.hour.isin([15, 16, 17])].p_de_above_fr.mean()), "actual_pos": int(H[H.hour.isin([15, 16, 17])].spread.mean() > 0),
                               "p_bind": float(H[H.hour.isin([15, 16, 17])].p_bind.mean()), "actual_bind": float(H[H.hour.isin([15, 16, 17])].bind.mean())},
           "fr_net_position_mean": float(H.hub_FR.mean()) if H.hub_FR.notna().any() else None,
           "hours": [{"hour": int(r.hour), "p_bind": r.p_bind, "bind": int(r.bind), "p_de_above_fr": r.p_de_above_fr, "spread": round(float(r.spread), 1), "e_spread": r.e_spread} for r in H.itertuples()]}
    return out


def verify():
    """Recompute every committed scorecard from freshly downloaded JAO and SMARD data and report any difference."""
    bad = 0
    for fn in sorted(glob.glob(os.path.join(ROOT, "scorecard", "*.json"))):
        old = json.load(open(fn)); day = old["day"]
        fc = json.load(open(os.path.join(ROOT, "forecasts", f"{day}.json")))
        for ds in ("shadowPrices", "netPos"):
            data.fetch_day(ds, day, force=True)
        new = score_day(day, fc)
        same = new is not None and abs(new["bind"]["brier"] - old["bind"]["brier"]) < 1e-6 and abs(new["sign"]["brier"] - old["sign"]["brier"]) < 1e-6 and new["bind"]["actual_hours"] == old["bind"]["actual_hours"]
        ok_time = (fc["status"] != "ex-ante") or (fc.get("results_published_utc") is None) or (fc["issued_at_utc"] < fc["results_published_utc"])
        print(f"{day}: scorecard {'reproduced' if same else 'DIFFERS'}; issued {fc['issued_at_utc'][:16]} status {fc['status']}; results published {new['results_published_utc'] if new and 'results_published_utc' in new else data.results_published(day)[1]}")
        bad += (not same) or (not ok_time)
    print("verification", "PASSED" if bad == 0 else f"FAILED on {bad} day(s)")
    return bad


def main():
    if "--verify" in sys.argv:
        sys.exit(1 if verify() else 0)
    os.makedirs(os.path.join(ROOT, "scorecard"), exist_ok=True)
    log_fn = os.path.join(ROOT, "scorecard", "log.csv")
    done = set(pd.read_csv(log_fn).day) if os.path.exists(log_fn) else set()
    rows = []
    for fn in sorted(glob.glob(os.path.join(ROOT, "forecasts", "*.json"))):
        fc = json.load(open(fn))
        day = fc["day"]
        if day in done:
            continue
        published, _ = data.results_published(day)
        if not published:
            continue
        sc = score_day(day, fc)
        if sc is None:
            continue
        json.dump(sc, open(os.path.join(ROOT, "scorecard", f"{day}.json"), "w"), indent=1)
        rows.append({"day": day, "status": sc["status"], "bind_brier": sc["bind"]["brier"], "bind_hit": sc["bind"]["hit"], "bind_actual_hours": sc["bind"]["actual_hours"],
                     "bind_expected_hours": sc["bind"]["expected_hours"], "sign_brier": sc["sign"]["brier"], "sign_hit": sc["sign"]["hit"], "level_mae": sc["level"]["mae"],
                     "level_mae_zero": sc["level"]["mae_zero"], "aft_actual_spread": sc["afternoon_15_17"]["actual_spread"], "aft_forecast_spread": sc["afternoon_15_17"]["forecast_spread"],
                     "aft_p_pos": sc["afternoon_15_17"]["p_pos"], "aft_actual_pos": sc["afternoon_15_17"]["actual_pos"]})
        print("scored", day, "bind Brier %.3f hit %.2f | sign Brier %.3f hit %.2f | afternoon spread %.1f vs forecast %.1f" % (
            sc["bind"]["brier"], sc["bind"]["hit"], sc["sign"]["brier"], sc["sign"]["hit"], sc["afternoon_15_17"]["actual_spread"], sc["afternoon_15_17"]["forecast_spread"]))
    if rows:
        pd.DataFrame(rows).to_csv(log_fn, mode="a", header=not os.path.exists(log_fn), index=False)


if __name__ == "__main__":
    main()
