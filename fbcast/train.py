"""Train both models, report their backtests, save models/bundle.pkl.

  * Grid model (binding probability, and the grid-only spread forecast kept for comparison): history from --start, strict time split.
  * Fundamentals model (spread quantiles, sign, DE and FR price quantiles): all history since Core flow-based coupling started,
    monthly walk-forward backtest over the last twelve months; its out-of-sample errors also set the band-width calibration.

Usage: python -m fbcast.train [--start 2026-09-01] [--split 2026-10-18] [--no-fund]
"""
import argparse, json, os, sys
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


def main():
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
    summary = {"trained_at": full["trained_at"], "train_days": full["train_days"], "n_train": full["n_train"], "backtest": metrics}
    if not a.no_fund:
        from fbcast import fund
        fm = fund.train(a.end, log=lambda m: print(m, flush=True))
        full["fund"] = fm
        fb = fm["backtest"]
        summary["fund"] = {"train_days": fm["train_days"], "n_train": fm["n_train"], "n_features": len(fm["features"]), "gbm": fm["gbm"], "band_factors": fm["cal"], "backtest": fb}
        print("fundamentals backtest %s..%s: pinball %.2f (clim %.2f) | P50 MAE %.1f (clim %.1f, persistence %.1f) | sign Brier %.3f (clim %.3f) | coverage raw %.0f%%, calibrated %.0f%%" % (
            fb["days"][0], fb["days"][1], fb["pinball"], fb["pinball_clim"], fb["mae_p50"], fb["mae_clim"], fb["mae_persistence"], fb["sign_brier"], fb["sign_brier_clim"],
            100 * fb["coverage80_raw"], 100 * fb.get("coverage80_calibrated", float("nan"))))
    os.makedirs(os.path.join(ROOT, "models"), exist_ok=True)
    model.save(full, os.path.join(ROOT, "models", "bundle.pkl"))
    json.dump(summary, open(os.path.join(ROOT, "models", "bundle.json"), "w"), indent=1)
    print("saved models/bundle.pkl trained on %s..%s (%d hour-rows)" % (full["train_days"][0], full["train_days"][1], full["n_train"]))


if __name__ == "__main__":
    main()
