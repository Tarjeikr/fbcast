"""Write SCORECARD.md: the forecast for tomorrow, the record so far and each day's forecast against the price that cleared, for the six
daily products (base and peak of the DE price, the FR price and the DE-FR spread).

The record starts with the first forecast issued by the fundamentals model. Forecasts of the earlier, grid-only version stay in
forecasts/ and scorecard/ and are not counted here.

Usage: python -m fbcast.report           # SCORECARD.md
       python -m fbcast.report --full    # scorecard/DIAGNOSTICS.md: hourly skill, binding probability, reliability (all versions)
"""
import glob, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fbcast import model
from fbcast.features import BLOCKS, product_forecast, daily_forecasts

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


def full():
    """The earlier, detailed report: hourly spread and binding skill against climatology, by block and by model. Not part of the daily run."""
    files = sorted(glob.glob(os.path.join(ROOT, "scorecard", "*.json")))
    bundle = model.load(os.path.join(ROOT, "models", "bundle.pkl"))
    clim = bundle["clim"]
    hours, days = [], []
    for fn in files:
        sc = json.load(open(fn))
        if sc["status"] != "ex-ante":
            continue
        for h in sc["hours"]:
            hours.append({"day": sc["day"], "sm": sc.get("spread_model", "grid"), **h})
        pre_gate = sc.get("issued_before_gate_closure")
        if pre_gate is None:  # scorecards written before the field existed: gate closure is 12:00 CET on the day before delivery
            pre_gate = bool(pd.Timestamp(sc["issued_at_utc"]) < (pd.Timestamp(sc["day"]) - pd.Timedelta(hours=12)).tz_localize("Europe/Berlin").tz_convert("UTC"))
        days.append({"day": sc["day"], "sm": sc.get("spread_model", "grid"), "levels": sc.get("levels"), "grid": sc.get("grid_only"), "pre_gate": pre_gate,
                     "bind_brier": sc["bind"]["brier"], "bind_hit": sc["bind"]["hit"], "sign_brier": sc["sign"]["brier"], "sign_hit": sc["sign"]["hit"],
                     "aft_actual": sc["afternoon_15_17"]["actual_spread"], "aft_p_pos": sc["afternoon_15_17"]["p_pos"],
                     "bind_actual_hours": sc["bind"]["actual_hours"], "bind_expected_hours": sc["bind"]["expected_hours"],
                     "fr_np": sc.get("fr_net_position_mean"), "q": sc.get("quantiles"), "prod": sc.get("products") or {}})
    H = pd.DataFrame()
    lines = ["# Scorecard: Core day-ahead forecast (DE–FR spread, DE and FR prices, Creys–St-Vulbas binding)", "",
             "Forecasts are issued each morning for the next CET day from what JAO has published by then, before the day-ahead auction closes; "
             "only forecasts whose issue time precedes the publication of the results count (status `ex-ante`). Metrics compare each forecast with the hour-of-day climatology of the training window.", ""]
    if days:
        n_pre = sum(1 for d in days if d["pre_gate"])
        lines += [f"Counted forecasts: {len(days)}, of which {n_pre} were issued before gate closure (12:00 CET) and {len(days) - n_pre} between gate closure and the publication of the results.", ""]
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
    if hours:
        # ---- which model produced the spread forecast, and how the two compare on the same days ----
        def mrow(key, label):
            """One row per model of record: day-level scores as stored in the scorecards, averaged over that model's counted days."""
            Dm = [d for d in days if d["sm"] == key]
            if not Dm:
                return None
            Q = [d["q"] for d in Dm if d.get("q")]
            mq = lambda k: f"{np.mean([q[k] for q in Q]):.2f}" if Q else "n/a"
            X = H[H.day.isin([d["day"] for d in Dm])]
            sx = (X.spread > 0).astype(int)
            cov = f"{np.mean([q['coverage80'] for q in Q]):.0%}" if Q else "n/a"
            return (f"| {label} | {len(Dm)} | {mq('pinball')} | {mq('pinball_clim')} | {mq('mae_p50')} | {mq('mae_clim_median')} | {cov} | "
                    f"{np.mean([d['sign_brier'] for d in Dm]):.3f} | {np.mean((X.clim_pos - sx) ** 2):.3f} | {np.mean([d['sign_hit'] for d in Dm]):.0%} |")
        rows_m = [r for r in (mrow(k, label) for k, label in (("fundamentals", "Fundamentals model"), ("grid", "Grid-only model"))) if r]
        if rows_m:
            lines += ["", "## Spread forecast by model", "",
                      "The spread and sign forecasts come from the fundamentals model on every day its inputs were on JAO in time, and from the grid-only model before it was introduced and on fallback days.", "",
                      "| Model of record | Days | Pinball loss | Pinball, climatology | P50 error, €/MWh | Climatology median error | 80% band coverage | Sign Brier | Sign Brier, climatology | Sign hit |",
                      "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"] + rows_m
        G = [d for d in days if d.get("grid") and d.get("q")]
        if G:
            m = lambda f: np.mean([f(d) for d in G])
            lines += ["", "### Both models on the same days", "",
                      "Every file issued from the fundamentals model also carries the grid-only model's spread forecast, so the two are scored on identical hours.", "",
                      "| Model | Days | Pinball loss | P50 error, €/MWh | 80% band coverage | Sign Brier | Sign hit |", "| --- | --- | --- | --- | --- | --- | --- |",
                      f"| Fundamentals | {len(G)} | {m(lambda d: d['q']['pinball']):.2f} | {m(lambda d: d['q']['mae_p50']):.1f} | {m(lambda d: d['q']['coverage80']):.0%} | {m(lambda d: d['sign_brier']):.3f} | {m(lambda d: d['sign_hit']):.0%} |",
                      f"| Grid only | {len(G)} | {m(lambda d: d['grid']['pinball']):.2f} | {m(lambda d: d['grid']['mae_p50']):.1f} | {m(lambda d: d['grid']['coverage80']):.0%} | {m(lambda d: d['grid']['sign_brier']):.3f} | {m(lambda d: d['grid']['sign_hit']):.0%} |"]
        L = [d for d in days if d.get("levels")]
        if L:
            lines += ["", "## DE and FR day-ahead prices", "", "Hourly price quantiles from the fundamentals model; the benchmark is yesterday's price at the same hour.", "",
                      "| Zone | Days | P50 error, €/MWh | Yesterday's price error | Pinball loss | 80% band coverage | Mean price, €/MWh |", "| --- | --- | --- | --- | --- | --- | --- |"]
            for z in ("DE", "FR"):
                V = [d["levels"][z] for d in L if z in d["levels"]]
                if not V:
                    continue
                pers = [v["mae_persistence"] for v in V if v.get("mae_persistence") is not None]
                lines.append(f"| {z} | {len(V)} | {np.mean([v['mae_p50'] for v in V]):.1f} | {np.mean(pers) if pers else float('nan'):.1f} | {np.mean([v['pinball'] for v in V]):.2f} | "
                             f"{np.mean([v['coverage80'] for v in V]):.0%} | {np.mean([v['actual_mean'] for v in V]):.1f} |")
    bt = bundle.get("backtest", {})
    fb = (bundle.get("fund") or {}).get("backtest")
    if fb:
        fm = bundle["fund"]
        lines += ["", "## Fundamentals model and its backtest", "",
                  f"Gradient-boosted quantile models on JAO's pre-coupling publication for the target day (the TSOs' D-2 congestion forecast of vertical load, generation and Core net positions; "
                  f"reference programmes on the non-Core borders; maximum net positions and bilateral exchanges) and on the day-ahead results up to the day before; "
                  f"trained on {fm['train_days'][0]} to {fm['train_days'][1]} ({fm['n_train']} hours). "
                  f"Walk-forward backtest with monthly refits, {fb['days'][0]} to {fb['days'][1]} ({fb['n_days']} days), every prediction made by a model that had seen nothing from its own month:", "",
                  "| Hourly DE−FR spread | Fundamentals model | Climatology, last 60 days | Yesterday's value | Zero |", "| --- | --- | --- | --- | --- |",
                  f"| Pinball loss (P10, P50, P90) | {fb['pinball']:.2f} | {fb['pinball_clim']:.2f} | | |",
                  f"| P50 absolute error, €/MWh | {fb['mae_p50']:.1f} | {fb['mae_clim']:.1f} | {fb['mae_persistence']:.1f} | {fb['mae_zero']:.1f} |",
                  f"| Sign Brier score | {fb['sign_brier']:.3f} | {fb['sign_brier_clim']:.3f} | | |",
                  f"| Sign hit rate | {fb['sign_hit']:.0%} | {fb['sign_hit_clim']:.0%} | | |", "",
                  f"Daily base spread: P50 error {fb['base']['mae_p50']:.1f} €/MWh against {fb['base']['mae_persistence']:.1f} for yesterday's value and {fb['base']['mae_clim']:.1f} for climatology; "
                  f"sign right on {fb['base']['sign_hit']:.0%} of days. Peak: {fb['peak']['mae_p50']:.1f} against {fb['peak']['mae_persistence']:.1f} and {fb['peak']['mae_clim']:.1f}. "
                  f"Prices: DE P50 error {fb['DE']['mae_p50']:.1f} €/MWh against {fb['DE']['mae_persistence']:.1f} for yesterday's price, FR {fb['FR']['mae_p50']:.1f} against {fb['FR']['mae_persistence']:.1f}. "
                  f"The raw 80% bands covered {fb['coverage80_raw']:.0%} of hours; with the band-width calibration a live forecast would have had at each date (factors from earlier days only), "
                  f"{fb.get('coverage80_calibrated', float('nan')):.0%} of hours, {fb['base'].get('coverage80_calibrated', float('nan')):.0%} of daily base and {fb['peak'].get('coverage80_calibrated', float('nan')):.0%} of daily peak outcomes."]
    if bt:
        lines += ["", "## Grid model and its backtest", "", f"Logistic models on the D-1 published Core domain (Creys–St-Vulbas RAM, loading and minRAM top-up, French max net positions) plus hour-of-day climatology; "
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
        pf = product_forecast(lf["hours"], lf["day"], cal=(lf.get("model") or {}).get("product_cal"))
        if pf:
            lines_top += ["| Product | P(spread > 0) | P50 (P10 to P90), €/MWh |", "| --- | --- | --- |"]
            for k, label in (("base", "Base (24 h)"), ("peak", "Peak (08–21)")):
                if k in pf:
                    lines_top.append(f"| {label} | {pf[k]['p_pos']:.2f} | {pf[k]['p50']:+.1f} ({pf[k]['p10']:+.1f} to {pf[k]['p90']:+.1f}) |")
            lines_top.append("")
        has_px = all(h.get("de_p50") is not None and h.get("fr_p50") is not None for h in lf["hours"])
        lines_top += ["| Block | Expected binding hours | P(DE > FR) | Spread P50 (P10 to P90), €/MWh |" + (" DE price P50 | FR price P50 |" if has_px else ""), "| --- | --- | --- | --- |" + (" --- | --- |" if has_px else "")]
        NH = _norm_hours(lf["hours"])
        for name, (a, b) in BLOCKS.items():
            B = [h for h in NH if a <= h["hour"] <= b]
            if not B:
                continue
            m = lambda k: float(np.mean([h[k] for h in B])) if all(h[k] is not None for h in B) else None
            band = "n/a" if m("p50") is None else f"{m('p50'):+.0f} ({m('p10'):+.0f} to {m('p90'):+.0f})"
            px = ""
            if has_px:
                R = [h for h in lf["hours"] if a <= h["hour"] <= b]
                px = f" {np.mean([h['de_p50'] for h in R]):.0f} | {np.mean([h['fr_p50'] for h in R]):.0f} |"
            lines_top.append(f"| {name} | {sum(h['p_bind'] or 0 for h in B):.1f} | {m('p_pos'):.2f} | {band} |" + px)
        if has_px:
            lines_top += ["", f"Spread, sign and prices from the fundamentals model; binding probability from the grid model. Day-ahead base price P50: DE {np.mean([h['de_p50'] for h in lf['hours']]):.0f} €/MWh, FR {np.mean([h['fr_p50'] for h in lf['hours']]):.0f} €/MWh."]
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
    open(os.path.join(ROOT, "scorecard", "DIAGNOSTICS.md"), "w").write("\n".join(lines).replace("](scorecard/", "](") + "\n")
    print("\n".join(lines[:12]))


PRODUCTS = (("DE_base", "DE base"), ("DE_peak", "DE peak"), ("FR_base", "FR base"), ("FR_peak", "FR peak"), ("spread_base", "DE−FR base"), ("spread_peak", "DE−FR peak"))


def _px(key, x):
    """Prices as whole euros, spreads with their sign."""
    return (f"{x:+.0f}" if key.startswith("spread") else f"{x:.0f}").replace("-", "−")


def _day(day, long=False):
    t = pd.Timestamp(day)
    return f"{t.strftime('%A')} {t.day} {t.strftime('%B %Y')}" if long else f"{t.strftime('%a')} {t.day} {t.strftime('%b')}"


def _issued(fc):
    """When a forecast was issued, in Central European time, and where that falls relative to gate closure and the results."""
    t = pd.Timestamp(fc["issued_at_utc"]).tz_convert("Europe/Berlin")
    when = f"{t.day} {t.strftime('%b')} at {t.strftime('%H:%M %Z')}"
    if fc.get("status") == "late":
        return f"Issued {when}, after the results were published: not counted."
    if fc.get("issued_before_gate_closure"):
        return f"Issued {when}, before the auction closed."
    return f"Issued {when}, after gate closure and before the results were published."


def main():
    if "--full" in sys.argv:
        return full()
    fcs, scs = {}, {}
    for fn in sorted(glob.glob(os.path.join(ROOT, "forecasts", "2*.json"))):
        f = json.load(open(fn)); fcs[f["day"]] = f
    for fn in sorted(glob.glob(os.path.join(ROOT, "scorecard", "2*.json"))):
        sc = json.load(open(fn)); scs[sc["day"]] = sc
    record = sorted(d for d, f in fcs.items() if (f.get("model") or {}).get("version", 1) >= 2)     # issued by the fundamentals model
    counted = [scs[d] for d in record if d in scs and scs[d]["status"] == "ex-ante" and (scs[d].get("daily") or {}).get("DE_base")]
    late = [d for d in record if (scs[d]["status"] if d in scs else fcs[d]["status"]) == "late"]
    lines = ["# Scorecard: German and French day-ahead prices, base and peak", "",
             "Forecasts of the German (DE-LU) and French day-ahead base and peak prices and of the DE−FR spread, issued every morning before the 12:00 CET auction "
             "and scored the next day against the prices that cleared. Base is all hours of the day; peak is Monday to Friday, 08:00 to 20:00 CET.", ""]
    st_fn = os.path.join(ROOT, "scorecard", "last_run.txt")
    if os.path.exists(st_fn):
        st = json.load(open(st_fn))
        lines += [f"Last scoring run: {st['run_utc']} UTC." + (f" Awaiting scoring: {', '.join(st['not_scored'])}." if st.get("not_scored") else ""), ""]
    # ---- the latest forecast ----
    lf = fcs[max(fcs)] if fcs else None
    if lf is not None and lf["day"] in record:
        d = daily_forecasts(lf["hours"], lf["day"], (lf.get("model") or {}).get("product_cal"))
        cell = lambda key: f"{_px(key, d[key]['p50'])} ({_px(key, d[key]['p10'])} to {_px(key, d[key]['p90'])})" if key in d else "–"
        lines += [f"## Forecast for {_day(lf['day'], long=True)}", "", _issued(lf) + " €/MWh: the P50, with the P10 to P90 band in brackets.", "",
                  "| | Base | Peak |", "| --- | --- | --- |"]
        lines += [f"| {name} | {cell(t + '_base')} | {cell(t + '_peak')} |" for t, name in (("DE", "DE"), ("FR", "FR"), ("spread", "DE−FR"))]
        if "DE_peak" not in d:
            lines += ["", f"There is no peak product on a {pd.Timestamp(lf['day']).strftime('%A')}."]
    elif lf is not None and record:
        lines += [f"## Latest forecast: {_day(lf['day'], long=True)}", "", "This forecast was issued from the grid model alone, because the inputs of the price model were not on JAO in time. "
                  "It carries no price forecast and is not part of the record."]
    else:
        lines += ["## Forecast", "", "The first forecast of this record has not been issued yet."]
    # ---- the record ----
    if record:
        lines += ["", f"## Record since {_day(record[0], long=True)}: {len(counted)} day{'' if len(counted) == 1 else 's'} counted", ""]
    if counted:
        lines += ["| | Days | Error, €/MWh | Error of yesterday's price | In band |", "| --- | --- | --- | --- | --- |"]
        for key, name in PRODUCTS:
            V = [sc["daily"][key] for sc in counted if key in sc["daily"]]
            if not V:
                lines.append(f"| {name} | 0 | | | |"); continue
            B = [abs(v["actual"] - v["prev_actual"]) for v in V if v.get("prev_actual") is not None]
            lines.append(f"| {name} | {len(V)} | {np.mean([abs(v['actual'] - v['p50']) for v in V]):.1f} | {np.mean(B) if B else float('nan'):.1f} | {sum(v['in_band'] for v in V)} of {len(V)} |")
        n_pre = sum(1 for sc in counted if sc.get("issued_before_gate_closure"))
        lines += ["", "Error is the average absolute difference between the P50 and the price that cleared. The benchmark is the same error for a forecast that repeats the product's last delivered price: "
                  "yesterday's for base, the previous weekday's for peak. In band counts the days on which the outcome fell inside the P10 to P90 band, which should be about four in five.", "",
                  f"A forecast counts only if it was issued before the results were published; {n_pre} of the {len(counted)} were issued before the auction closed."
                  + (f" Not counted, because issued late: {', '.join(_day(x) for x in late)}." if late else "")]
        lines += ["", "## Day by day: forecast → price that cleared, €/MWh", "", "| Day | " + " | ".join(n for _, n in PRODUCTS) + " |", "| --- |" + " --- |" * len(PRODUCTS)]
        out_of_band = False
        for sc in sorted(counted, key=lambda x: x["day"], reverse=True)[:60]:
            cells = []
            for key, _ in PRODUCTS:
                v = sc["daily"].get(key)
                if v is None:
                    cells.append("–"); continue
                out_of_band |= not v["in_band"]
                cells.append(f"{_px(key, v['p50'])} → {_px(key, v['actual'])}" + ("" if v["in_band"] else " *"))
            lines.append(f"| {_day(sc['day'])} | " + " | ".join(cells) + " |")
        if out_of_band:
            lines += ["", "\\* The price cleared outside the P10 to P90 band."]
        if len(counted) > 60:
            lines += ["", "The 60 most recent days are shown; every day is in `scorecard/log.csv`."]
    elif record:
        waiting = [d for d in record if d not in scs]
        lines += ["No day has been scored yet." + (f" The forecast for {_day(waiting[0])} is scored once its results are published." if waiting else "")
                  + (f" Not counted, because issued late: {', '.join(_day(x) for x in late)}." if late else "")]
    # ---- what to expect: the model's backtest ----
    bj_fn = os.path.join(ROOT, "models", "bundle.json")
    bt = (json.load(open(bj_fn)).get("fund") or {}).get("backtest") if os.path.exists(bj_fn) else None
    if bt and bt.get("products"):
        lines += ["", "## Backtest of the model", "",
                  f"The live record above is the test that counts. This is what to expect from it: a walk-forward backtest from {_day(bt['days'][0])} {bt['days'][0][:4]} to {_day(bt['days'][1])} {bt['days'][1][:4]}, "
                  "refitted every month, in which every forecast comes from a model that had seen nothing from its own month.", "",
                  "| | Days | Average price | Error, €/MWh | Error of yesterday's price | In band |", "| --- | --- | --- | --- | --- | --- |"]
        for key, name in PRODUCTS:
            v = bt["products"].get(key)
            if v:
                cov = v.get("coverage80_calibrated")
                lines.append(f"| {name} | {v['days']} | {_px(key, v['mean_actual'])} | {v['mae_p50']:.1f} | {v['mae_prev']:.1f} | {'n/a' if cov is None else format(cov, '.0%')} |")
    lines += ["", "## Where things are", "",
              "How the forecast is made: `README.md`. Each forecast as issued, hour by hour: `forecasts/`. Each day's score: `scorecard/`."
              + (f" Forecasts issued before {_day(record[0])} {record[0][:4]} came from the first, grid-only version of this project; they remain in the same folders and are not part of this record." if record else "")]
    open(os.path.join(ROOT, "SCORECARD.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines[:16]))


if __name__ == "__main__":
    main()
