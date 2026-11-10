"""Write SCORECARD.md: cumulative and rolling skill of the issued forecasts against the hour-of-day climatology.

Usage: python -m fbcast.report
"""
import glob, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fbcast import model
from fbcast.features import BLOCKS, product_forecast

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _norm_hours(hours):
    """Forecast files and scorecards name the quantile fields differently; return one common shape."""
    out = []
    for h in hours:
        g = lambda *ks: next((h[k] for k in ks if h.get(k) is not None), None)
        out.append({"hour": h["hour"], "p_bind": g("p_bind"), "p_pos": g("p_de_above_fr"), "p10": g("spread_p10", "p10"), "p50": g("spread_p50", "p50"), "p90": g("spread_p90", "p90"),
                    "actual": h.get("spread"), "bound": h.get("bind")})
    return sorted(out, key=lambda x: x["hour"])


def _chart(path, title, hours):
    """Hour-by-hour chart: P10–P90 band and P50 of the DE−FR spread, binding probability as bars, realized spread as dots when known."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        H = _norm_hours(hours)
        x = [h["hour"] for h in H]
        fig, ax = plt.subplots(figsize=(9.5, 4.0), dpi=110)
        ax2 = ax.twinx()
        ax2.bar(x, [h["p_bind"] or 0 for h in H], width=0.7, color="#c9c9c9", alpha=0.55, label="P(Creys–St-Vulbas binds), right axis")
        ax2.set_ylim(0, 2.2); ax2.set_yticks([0, 0.5, 1]); ax2.set_ylabel("binding probability")
        ax.set_zorder(ax2.get_zorder() + 1); ax.patch.set_visible(False)
        if all(h["p10"] is not None for h in H):
            ax.fill_between(x, [h["p10"] for h in H], [h["p90"] for h in H], color="#2a78d6", alpha=0.18, label="P10–P90")
            ax.plot(x, [h["p50"] for h in H], color="#2a78d6", lw=2, label="P50")
        act = [(h["hour"], h["actual"]) for h in H if h["actual"] is not None]
        if act:
            ax.scatter([a for a, _ in act], [b for _, b in act], color="#d6402a", s=22, zorder=5, label="realized spread")
        ax.axhline(0, color="#555", lw=0.8)
        ax.set_xlim(-0.6, 23.6); ax.set_xticks(range(0, 24, 3)); ax.set_xlabel("hour of day, CET"); ax.set_ylabel("DE−FR day-ahead spread, €/MWh")
        ax.set_title(title, fontsize=11, loc="left")
        h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8, frameon=False, ncol=2)
        fig.tight_layout(); fig.savefig(path); plt.close(fig)
        return True
    except Exception as e:
        print("chart skipped (%s)" % type(e).__name__)
        return False


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
                     "aft_actual": sc["afternoon_15_17"]["actual_spread"], "aft_p_pos": sc["afternoon_15_17"]["p_pos"],
                     "bind_actual_hours": sc["bind"]["actual_hours"], "bind_expected_hours": sc["bind"]["expected_hours"],
                     "fr_np": sc.get("fr_net_position_mean"), "q": sc.get("quantiles"), "prod": sc.get("products") or {}})
    H = pd.DataFrame()
    lines = ["# Scorecard: Core binding-constraint forecast", "", "Forecasts are issued each morning for the next CET day from the published JAO domain, before the day-ahead auction closes; "
             "only forecasts whose issue time precedes the publication of the results count (status `ex-ante`). Metrics compare each forecast with the hour-of-day climatology of the training window.", ""]
    if not hours:
        lines += ["No ex-ante forecasts scored yet."]
    else:
        H = pd.DataFrame(hours); D = pd.DataFrame(days)
        H["clim_bind"] = H.hour.map(clim["bind"]); H["clim_pos"] = H.hour.map(clim["pos"])
        for c in ("p10", "p50", "p90", "clim_q10", "clim_q50", "clim_q90"):
            if c not in H:
                H[c] = np.nan
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
        lines += ["", "## By day: afternoon block 15–17 CET and binding hours", "",
                  "| Day | P(DE > FR), 15–17 | Spread P50 (P10–P90), 15–17, €/MWh | Actual spread 15–17, €/MWh | Binding hours expected | Binding hours actual | French net position, GW (realized, day mean) |",
                  "| --- | --- | --- | --- | --- | --- | --- |"]
        for r in D.sort_values("day", ascending=False).head(21).itertuples():
            frnp = "n/a" if r.fr_np is None or pd.isna(r.fr_np) else f"{r.fr_np / 1000:+.1f}"
            band = "n/a" if not r.q or pd.isna(r.q.get("afternoon_p50", np.nan)) else f"{r.q['afternoon_p50']:+.0f} ({r.q['afternoon_p10']:+.0f} to {r.q['afternoon_p90']:+.0f})"
            ppos = "n/a" if pd.isna(r.aft_p_pos) else f"{r.aft_p_pos:.2f}"
            lines.append(f"| {r.day} | {ppos} | {band} | {r.aft_actual:+.1f} | {r.bind_expected_hours:.1f} | {r.bind_actual_hours} | {frnp} |")
        Q = [d["q"] for d in days if d.get("q")]
        if Q:
            n = len(Q)
            m = lambda k: np.mean([q[k] for q in Q if q.get(k) is not None])
            lines += ["", "## Spread quantiles (DE−FR, €/MWh)", "", "| Days | Pinball loss | Pinball, climatology | 80% band coverage | Coverage, climatology | P50 MAE | Climatology median MAE | Zero MAE | Persistence D-1 MAE | Band width |",
                      "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                      f"| {n} | {m('pinball'):.2f} | {m('pinball_clim'):.2f} | {m('coverage80'):.0%} | {m('coverage80_clim'):.0%} | {m('mae_p50'):.1f} | {m('mae_clim_median'):.1f} | {m('mae_zero'):.1f} | {m('mae_persistence'):.1f} | {m('band_width'):.0f} |",
                      "", "Pinball loss is averaged over the 10th, 50th and 90th percentiles; lower is better. Coverage is the share of hours whose realized spread fell inside the P10–P90 band (target 80%)."]
        lines += ["", "A positive French net position means France exported into Core; Creys–St-Vulbas is France's export path and cannot bind on days when France imports."]
        Dv = D.dropna(subset=["aft_p_pos", "aft_actual"])
        hit_sign_days = (np.sign(Dv.aft_p_pos - 0.5) == np.sign(Dv.aft_actual)).mean() if len(Dv) else float("nan")
        lines += ["", f"Afternoon-block sign hit rate: {hit_sign_days:.0%} over {len(Dv)} days; share of days with a positive afternoon spread: {(Dv.aft_actual > 0).mean():.0%}.", "",
                  "## Reliability of P(bind)", "", "| Forecast bin | Hours | Mean forecast | Observed frequency |", "| --- | --- | --- | --- |"]
        H["bin"] = pd.cut(H.p_bind, [0, .2, .4, .6, .8, 1.0])
        for b, g in H.groupby("bin", observed=True):
            lines.append(f"| {b} | {len(g)} | {g.p_bind.mean():.2f} | {g.bind.mean():.2f} |")
    bt = bundle.get("backtest", {})
    if bt:
        lines += ["", "## Model and backtest", "", f"Logistic models on the D-1 published Core domain (Creys–St-Vulbas RAM, loading and minRAM top-up, French max net positions) plus hour-of-day climatology; "
                  f"trained on {bundle['train_days'][0]} to {bundle['train_days'][1]} ({bundle['n_train']} hour-rows). Held-out backtest {bt['days'][0]} to {bt['days'][1]}: "
                  f"binding AUC {bt['bind']['auc']:.2f}, Brier {bt['bind']['brier']:.3f} vs {bt['bind']['brier_clim']:.3f} climatology; "
                  f"sign AUC {bt['sign']['auc']:.2f}, Brier {bt['sign']['brier']:.3f} vs {bt['sign']['brier_clim']:.3f}"
                  + (f"; spread quantiles pinball {bt['quantiles']['pinball']:.2f} vs {bt['quantiles']['pinball_clim']:.2f} climatology, P50 MAE {bt['quantiles']['mae_p50']:.1f} vs {bt['quantiles']['mae_zero']:.1f} for a zero forecast." if bt.get("quantiles") else ".")]
    # ---- through the day ----
    lines_extra, lines_top = [], []
    fcs = sorted(glob.glob(os.path.join(ROOT, "forecasts", "*.json")))
    if fcs:
        lf = json.load(open(fcs[-1]))
        ok = _chart(os.path.join(ROOT, "scorecard", "chart_forecast.png"), f"Forecast for {lf['day']} (issued {lf['issued_at_utc'][:16]} UTC, status {lf['status']})", lf["hours"])
        lines_top += ["", f"## Latest forecast: {lf['day']}", ""]
        if ok:
            lines_top += ["![Latest forecast, hour by hour](scorecard/chart_forecast.png)", ""]
        pf = product_forecast(lf["hours"], lf["day"])
        if pf:
            lines_top += ["| Product | P(spread > 0) | P50 (P10 to P90), €/MWh |", "| --- | --- | --- |"]
            for k, label in (("base", "Base (24 h)"), ("peak", "Peak (08–21)")):
                if k in pf:
                    lines_top.append(f"| {label} | {pf[k]['p_pos']:.2f} | {pf[k]['p50']:+.1f} ({pf[k]['p10']:+.1f} to {pf[k]['p90']:+.1f}) |")
            lines_top.append("")
        lines_top += ["| Block | Expected binding hours | P(DE > FR) | Spread P50 (P10 to P90), €/MWh |", "| --- | --- | --- | --- |"]
        NH = _norm_hours(lf["hours"])
        for name, (a, b) in BLOCKS.items():
            B = [h for h in NH if a <= h["hour"] <= b]
            if not B:
                continue
            m = lambda k: float(np.mean([h[k] for h in B])) if all(h[k] is not None for h in B) else None
            band = "n/a" if m("p50") is None else f"{m('p50'):+.0f} ({m('p10'):+.0f} to {m('p90'):+.0f})"
            lines_top.append(f"| {name} | {sum(h['p_bind'] or 0 for h in B):.1f} | {m('p_pos'):.2f} | {band} |")
        lines_top += ["", "<details><summary>Hour by hour</summary>", "", "| Hour (CET) | P(bind) | P(DE > FR) | P10 | P50 | P90 |", "| --- | --- | --- | --- | --- | --- |"]
        for h in _norm_hours(lf["hours"]):
            q = lambda v: "n/a" if v is None else f"{v:+.0f}"
            lines_top.append(f"| {h['hour']:02d} | {h['p_bind']:.2f} | {h['p_pos']:.2f} | {q(h['p10'])} | {q(h['p50'])} | {q(h['p90'])} |")
        lines_top += ["", "</details>"]
    D_prod = [d for d in days if d.get("prod")]
    if D_prod:
        lines_top += ["", "## Base and peak spread, day by day", "",
                      "Base is the 24-hour average DE−FR day-ahead spread; peak is the average over delivery 08:00–21:00 CET. The forecast is the average of the hourly P10, P50 and P90; P(> 0) is read off that band with a normal approximation.", "",
                      "| Day | Base P50 (P10 to P90) | Base actual | P(base > 0) | Peak P50 (P10 to P90) | Peak actual | P(peak > 0) |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for d in sorted(D_prod, key=lambda x: x["day"], reverse=True)[:21]:
            cells = []
            for k in ("base", "peak"):
                v = d["prod"].get(k)
                cells += ["n/a", "n/a", "n/a"] if not v else [f"{v['p50']:+.1f} ({v['p10']:+.1f} to {v['p90']:+.1f})", f"{v['actual']:+.1f}", f"{v['p_pos']:.2f}"]
            lines_top.append(f"| {d['day']} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | {cells[4]} | {cells[5]} |")
        lines_top += ["", "### Base and peak skill (all counted days)", "",
                      "| Product | Days | P50 error, €/MWh | Climatology level error | Yesterday's value error | 80% band coverage | Sign hit | Sign Brier | Sign Brier, climatology |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for k, label in (("base", "Base"), ("peak", "Peak")):
            V = [d["prod"][k] for d in D_prod if k in d["prod"]]
            if not V:
                continue
            act = np.array([v["actual"] for v in V]); p50 = np.array([v["p50"] for v in V]); pp = np.array([v["p_pos"] for v in V]); y = (act > 0).astype(int)
            cl = [(v["actual"], v["clim_p50"], v["clim_p_pos"]) for v in V if v.get("clim_p50") is not None and v.get("clim_p_pos") is not None]
            pr = [abs(v["actual"] - v["prev_actual"]) for v in V if v.get("prev_actual") is not None]
            cover = np.mean([(v["p10"] <= v["actual"] <= v["p90"]) for v in V])
            clim_err = np.mean([abs(a - c) for a, c, _ in cl]) if cl else float("nan")
            clim_br = np.mean([(cp - (a > 0)) ** 2 for a, _, cp in cl]) if cl else float("nan")
            lines_top.append(f"| {label} | {len(V)} | {np.mean(np.abs(act - p50)):.1f} | {clim_err:.1f} | {np.mean(pr) if pr else float('nan'):.1f} | {cover:.0%} | {np.mean((pp > .5) == y):.0%} | {np.mean((pp - y) ** 2):.3f} | {clim_br:.3f} |")
        lines_top += ["", "Error columns are mean absolute differences between the forecast level and the outcome (lower is better). The climatology level is the hour-of-day climatology aggregated the same way, and yesterday's value is the previous day's realized product. Few days are counted so far, so read these figures as provisional."]
    if hours:
        last_day = sorted(H.day.unique())[-1]
        sc_last = json.load(open(os.path.join(ROOT, "scorecard", f"{last_day}.json")))
        if _chart(os.path.join(ROOT, "scorecard", "chart_scored.png"), f"{last_day}: forecast against outcome", sc_last["hours"]):
            lines_extra += ["", f"## Last scored day: {last_day}", "", "![Last scored day](scorecard/chart_scored.png)"]
        lines_extra += ["", "## Skill through the day (all counted days)", "",
                        "| Block | Hours | Sign skill | Binding skill | Quantile skill | 80% band coverage | Mean realized spread, €/MWh |", "| --- | --- | --- | --- | --- | --- | --- |"]
        Hq = H.copy()
        for name, (a, b) in BLOCKS.items():
            X = Hq[(Hq.hour >= a) & (Hq.hour <= b)]
            if X.empty:
                continue
            if X.day.nunique() < 7:  # percentages from a handful of days are noise
                lines_extra.append(f"| {name} | {len(X)} | building up: {X.day.nunique()} of 7 days | | | | {X.spread.mean():+.1f} |")
                continue
            sx = (X.spread > 0).astype(int)
            sign = 1 - np.mean((X.p_de_above_fr - sx) ** 2) / max(np.mean((X.clim_pos - sx) ** 2), 1e-9)
            bind = 1 - np.mean((X.p_bind - X.bind) ** 2) / max(np.mean((X.clim_bind - X.bind) ** 2), 1e-9)
            Q = X.dropna(subset=["p10", "p50", "p90", "clim_q10", "clim_q50", "clim_q90"]) if "p10" in X else X.iloc[0:0]
            if len(Q) >= 6:
                y = Q.spread.values
                pm = np.mean([model.pinball(y, Q.p10, .1), model.pinball(y, Q.p50, .5), model.pinball(y, Q.p90, .9)])
                pc = np.mean([model.pinball(y, Q.clim_q10, .1), model.pinball(y, Q.clim_q50, .5), model.pinball(y, Q.clim_q90, .9)])
                qs, cov = f"{1 - pm / pc:+.0%}", f"{np.mean((y >= Q.p10) & (y <= Q.p90)):.0%}"
            else:
                qs, cov = "n/a", "n/a"
            lines_extra.append(f"| {name} | {len(X)} | {sign:+.0%} | {bind:+.0%} | {qs} | {cov} | {X.spread.mean():+.1f} |")
        lines_extra += ["", "Skill is 1 minus the model's squared (or pinball) error divided by that of the hour-of-day climatology: positive means better than climatology, zero equal, negative worse. Coverage should be near 80%. A block shows figures once it has 7 counted days."]
    lines += lines_extra
    k = 2
    st_fn = os.path.join(ROOT, "scorecard", "last_run.txt")
    if os.path.exists(st_fn):
        st = json.load(open(st_fn))
        note = f"Last scoring run: {st['run_utc']} UTC." + (f" Awaiting scoring (retried each run): {', '.join(st['not_scored'])}." if st.get("not_scored") else " All published days scored.")
        lines.insert(2, note); lines.insert(3, ""); k = 4
    lines[k:k] = lines_top
    open(os.path.join(ROOT, "SCORECARD.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))


if __name__ == "__main__":
    main()
