"""Train both models, report their backtests, save models/bundle.pkl.

  * Grid model (binding probability, and the grid-only spread forecast kept for comparison): history from --start, strict time split.
  * Fundamentals model (spread quantiles, sign, DE and FR price quantiles): all history since Core flow-based coupling started,
    monthly walk-forward backtest over the last twelve months; its out-of-sample errors also set the band-width calibration.

Usage: python -m fbcast.train [--start 2026-09-01] [--split 2026-10-18] [--no-fund]
       python -m fbcast.train --due      prints why a retrain is due now, or nothing if none is (used by the retrain workflow)
"""
import argparse, json, os, platform, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fbcast import data, model
from fbcast.features import build

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def history_table(start, end):
    days = [d.strftime("%Y-%m-%d") for d in pd.date_range(start, end, freq="D")]
    fc = data.load_days("finalComputation", days)
    mx = data.load_days("maxNetPos", days)
    sp = data.load_days("shadowPrices", days)
    npos = data.load_days("netPos", days)
    pr = data.fetch_prices(start, (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    T = build(fc, mx, sp, npos, pr)
    T = T[(T.day >= start) & (T.day <= end)].dropna(subset=["bind", "spread"]).reset_index(drop=True)
    return T


def requirements():
    """The pinned libraries, as listed in requirements.txt. A saved model is only read back reliably by the library versions
    that wrote it, so the model summary records them and a change of pins makes a retrain due."""
    fn = os.path.join(ROOT, "requirements.txt")
    if not os.path.exists(fn):
        return []
    return sorted(ln.split("#")[0].strip() for ln in open(fn) if ln.split("#")[0].strip())


def due(max_age_days=6.5):
    """Why a retrain is due, or None: no price model yet, a model a week old, or libraries pinned differently than at training."""
    try:
        b = json.load(open(os.path.join(ROOT, "models", "bundle.json")))
    except Exception:
        return "there is no model summary (models/bundle.json)"
    if not b.get("fund"):
        return "there is no price model yet"
    try:
        age = (pd.Timestamp.now("UTC") - pd.Timestamp(b["trained_at"])) / pd.Timedelta(days=1)
    except Exception:
        return "the model summary does not say when the model was trained"
    if age >= max_age_days:
        return "the model is %.0f days old" % age
    pins = (b.get("environment") or {}).get("requirements")
    if pins and pins != requirements():
        return "requirements.txt has changed since the model was trained"
    return None


def main():
    if "--due" in sys.argv:
        why = due()
        if why:
            print(why)
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-09-01")
    ap.add_argument("--end", default=(pd.Timestamp.now(tz="Europe/Berlin") - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    ap.add_argument("--split", default=None, help="first day of the backtest window; default: last 18 days")
    ap.add_argument("--no-fund", action="store_true", help="skip the fundamentals model (the forecast then comes from the grid model alone)")
    a = ap.parse_args()
    T = history_table(a.start, a.end)
    days = sorted(T.day.unique())
    split = a.split or days[-18]
    tr, te = T[T.day < split], T[T.day >= split]
    bt = model.fit(tr)
    metrics = model.evaluate(bt, te)
    print("backtest %s..%s: bind AUC %.3f Brier %.3f (clim %.3f) | sign AUC %.3f Brier %.3f (clim %.3f) | level MAE %.1f (zero %.1f)" % (
        metrics["days"][0], metrics["days"][1], metrics["bind"]["auc"], metrics["bind"]["brier"], metrics["bind"]["brier_clim"],
        metrics["sign"]["auc"], metrics["sign"]["brier"], metrics["sign"]["brier_clim"], metrics["level"]["mae"], metrics["level"]["mae_zero"]))
    full = model.fit(T)
    full["backtest"] = metrics
    full["trained_at"] = pd.Timestamp.now("UTC").isoformat()
    import numpy, sklearn
    summary = {"trained_at": full["trained_at"], "train_days": full["train_days"], "n_train": full["n_train"], "backtest": metrics,
               "environment": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": numpy.__version__, "scikit-learn": sklearn.__version__,
                               "requirements": requirements()}}
    if not a.no_fund:
        from fbcast import fund
        fm = fund.train(a.end, log=lambda m: print(m, flush=True))
        full["fund"] = fm
        fb = fm["backtest"]
        summary["fund"] = {"train_days": fm["train_days"], "n_train": fm["n_train"], "n_features": len(fm["features"]), "gbm": fm["gbm"], "anchors": fm.get("anchors"), "band_factors": fm["cal"], "backtest": fb}
        print("fundamentals backtest %s..%s: pinball %.2f (clim %.2f) | P50 MAE %.1f (clim %.1f, persistence %.1f) | sign Brier %.3f (clim %.3f) | coverage raw %.0f%%, calibrated %.0f%%" % (
            fb["days"][0], fb["days"][1], fb["pinball"], fb["pinball_clim"], fb["mae_p50"], fb["mae_clim"], fb["mae_persistence"], fb["sign_brier"], fb["sign_brier_clim"],
            100 * fb["coverage80_raw"], 100 * fb.get("coverage80_calibrated", float("nan"))))
    os.makedirs(os.path.join(ROOT, "models"), exist_ok=True)
    model.save(full, os.path.join(ROOT, "models", "bundle.pkl"))
    with open(os.path.join(ROOT, "models", "bundle.json"), "w") as fh:
        json.dump(summary, fh, indent=1)
    print("saved models/bundle.pkl trained on %s..%s (%d hour-rows)" % (full["train_days"][0], full["train_days"][1], full["n_train"]))


if __name__ == "__main__":
    main()
