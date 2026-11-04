"""Write SCORECARD.md: cumulative and rolling skill of the issued forecasts against the hour-of-day climatology.

Usage: python -m fbcast.report
"""
import glob, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fbcast import model

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "scorecard", "*.json")))
    bundle = model.load(os.path.join(ROOT, "models", "bundle.pkl"))
    clim = bundle["clim"]
    hours, days = [], []
    for fn in files:
        sc = json.load(open(fn))
        if sc["status"] != "ex-ante":
            continue
        for h in sc["hours"]:
            hours.append({"day": sc["day"], **h})
        days.append({"day": sc["day"], "bind_brier": sc["bind"]["brier"], "bind_hit": sc["bind"]["hit"], "sign_brier": sc["sign"]["brier"], "sign_hit": sc["sign"]["hit"],
                     "aft_actual": sc["afternoon_15_17"]["actual_spread"], "aft_forecast": sc["afternoon_15_17"]["forecast_spread"], "aft_p_pos": sc["afternoon_15_17"]["p_pos"],
                     "bind_actual_hours": sc["bind"]["actual_hours"], "bind_expected_hours": sc["bind"]["expected_hours"]})
    lines = ["# Scorecard: Core binding-constraint forecast", "", "Forecasts are issued each morning for the next CET day from the published JAO domain, before the day-ahead auction closes; "
             "only forecasts whose issue time precedes the publication of the results count (status `ex-ante`). Metrics compare each forecast with the hour-of-day climatology of the training window.", ""]
    if not hours:
        lines += ["No ex-ante forecasts scored yet."]
    else:
        H = pd.DataFrame(hours); D = pd.DataFrame(days)
        H["clim_bind"] = H.hour.map(clim["bind"]); H["clim_pos"] = H.hour.map(clim["pos"])
        s = (H.spread > 0).astype(int)
        def block(X, label):
            y = X.bind.astype(int); sx = (X.spread > 0).astype(int)
            return [f"| {label} | {len(X)} | {X.day.nunique()} | {np.mean((X.p_bind - y) ** 2):.3f} | {np.mean((X.clim_bind - y) ** 2):.3f} | {((X.p_bind > 0.5) == y).mean():.0%} | {((X.clim_bind > 0.5) == y).mean():.0%} | "
                    f"{np.mean((X.p_de_above_fr - sx) ** 2):.3f} | {np.mean((X.clim_pos - sx) ** 2):.3f} | {((X.p_de_above_fr > 0.5) == sx).mean():.0%} | {((X.clim_pos > 0.5) == sx).mean():.0%} |"]
        lines += ["| Window | Hours | Days | Bind Brier | Bind Brier, climatology | Bind hit | Bind hit, climatology | Sign Brier | Sign Brier, climatology | Sign hit | Sign hit, climatology |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        lines += block(H, "All ex-ante forecasts")
        last = sorted(H.day.unique())[-14:]
        lines += block(H[H.day.isin(last)], "Last 14 days")
        lines += block(H[H.hour.isin([13, 14, 15, 16, 17, 18, 19])], "Afternoon hours 13–19 CET")
        lines += ["", "## Afternoon block 15–17 CET, by day", "", "| Day | P(DE > FR) | Actual spread, €/MWh | Forecast spread, €/MWh | Binding hours expected | Binding hours actual |", "| --- | --- | --- | --- | --- | --- |"]
        for r in D.sort_values("day", ascending=False).head(21).itertuples():
            lines.append(f"| {r.day} | {r.aft_p_pos:.2f} | {r.aft_actual:+.1f} | {r.aft_forecast:+.1f} | {r.bind_expected_hours:.1f} | {r.bind_actual_hours} |")
        hit_sign_days = (np.sign(D.aft_p_pos - 0.5) == np.sign(D.aft_actual)).mean()
        lines += ["", f"Afternoon-block sign hit rate: {hit_sign_days:.0%} over {len(D)} days; share of days with a positive afternoon spread: {(D.aft_actual > 0).mean():.0%}.", "",
                  "## Reliability of P(bind)", "", "| Forecast bin | Hours | Mean forecast | Observed frequency |", "| --- | --- | --- | --- |"]
        H["bin"] = pd.cut(H.p_bind, [0, .2, .4, .6, .8, 1.0])
        for b, g in H.groupby("bin", observed=True):
            lines.append(f"| {b} | {len(g)} | {g.p_bind.mean():.2f} | {g.bind.mean():.2f} |")
    bt = bundle.get("backtest", {})
    if bt:
        lines += ["", "## Model and backtest", "", f"Logistic models on the D-1 published Core domain (Creys–St-Vulbas RAM, loading and minRAM top-up, French max net positions) plus hour-of-day climatology; "
                  f"trained on {bundle['train_days'][0]} to {bundle['train_days'][1]} ({bundle['n_train']} hour-rows). Held-out backtest {bt['days'][0]} to {bt['days'][1]}: "
                  f"binding AUC {bt['bind']['auc']:.2f}, Brier {bt['bind']['brier']:.3f} vs {bt['bind']['brier_clim']:.3f} climatology; "
                  f"sign AUC {bt['sign']['auc']:.2f}, Brier {bt['sign']['brier']:.3f} vs {bt['sign']['brier_clim']:.3f}; spread level MAE {bt['level']['mae']:.1f} vs {bt['level']['mae_zero']:.1f} for a zero forecast (no level skill claimed)."]
    open(os.path.join(ROOT, "SCORECARD.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))


if __name__ == "__main__":
    main()
