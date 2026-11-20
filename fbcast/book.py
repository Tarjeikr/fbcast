"""A public book of calls, priced against the market.

A scorecard shows whether a forecast has skill; a book shows what a view was worth. Each call here is a paper position with a
size, entered at a published market price, written to the repository by a GitHub Actions run (so GitHub signs and timestamps
it) and never edited afterwards. A call is closed by a second file, not by changing the first.

Kinds of call
  forward   A power forward for a delivery period: one zone ("DE", "FR") or a spread ("DE-FR" = long DE, short FR).
            Entered, marked and closed at exchange settlement prices typed in together with their source. Left open to the
            end of delivery it settles as the exchange contract does, against the average day-ahead price of the period,
            which the report computes from public prices (DE and FR only).
  lttr      A long-term transmission right bought at a JAO auction: an option on one direction of a border. "FR>DE" pays
            max(price DE − price FR, 0) in every hour of the period. Entered at the auction's clearing price. The report
            computes the payout from public day-ahead prices; nothing is typed in after the entry.

Usage (normally through the `call` workflow)
  python -m fbcast.book open  --kind forward --product DE-FR --period Q1-2027 --direction long --size 10 --price 12.4
                              --source "EEX settlement 19 Nov 2026" --rationale "..." [--profile peak] [--target 25] [--stop 5]
  python -m fbcast.book mark  --product DE-FR --period Q1-2027 --price 15.1 --source "EEX settlement 26 Nov 2026"
  python -m fbcast.book close --id 20261120-01 --price 18.0 --source "EEX settlement 3 Dec 2026" [--note "..."]
  python -m fbcast.book open  --kind lttr --product "FR>DE" --period Cal-2027 --size 10 --price 9.87
                              --source "JAO yearly auction, results 4 Dec 2026" --rationale "..."
  python -m fbcast.book report
"""
import argparse, glob, json, os, re, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = os.path.join(ROOT, "book")
TZ = "Europe/Berlin"
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
PRICED = ("DE", "FR")   # zones whose day-ahead prices the report can load for settlement


def period_days(period):
    """First and last CET delivery day of a period written as Cal-2027, Q1-2027, Dec-2026 (or M12-2026), W49-2026, or
    2026-12-01..2026-12-31."""
    p = period.strip()
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})", p)
    if m:
        a, b = pd.Timestamp(m.group(1)), pd.Timestamp(m.group(2))
    elif re.fullmatch(r"(?i)cal-\d{4}", p):
        y = int(p[-4:]); a, b = pd.Timestamp(y, 1, 1), pd.Timestamp(y, 12, 31)
    elif re.fullmatch(r"(?i)q[1-4]-\d{4}", p):
        q, y = int(p[1]), int(p[-4:]); a = pd.Timestamp(y, 3 * q - 2, 1); b = a + pd.offsets.QuarterEnd(0)
    elif re.fullmatch(r"(?i)(m\d{1,2}|[a-z]{3})-\d{4}", p):
        head, y = p.split("-")[0].lower(), int(p[-4:])
        mo = int(head[1:]) if head[0] == "m" and head[1:].isdigit() else (MONTHS.index(head) + 1 if head in MONTHS else 0)
        if not 1 <= mo <= 12:
            raise ValueError(f"cannot read the month in '{period}': use Dec-2026 or M12-2026")
        a = pd.Timestamp(y, mo, 1); b = a + pd.offsets.MonthEnd(0)
    elif re.fullmatch(r"(?i)w\d{1,2}-\d{4}", p):
        w, y = int(p.split("-")[0][1:]), int(p[-4:]); a = pd.Timestamp.fromisocalendar(y, w, 1); b = a + pd.Timedelta(days=6)
    else:
        raise ValueError(f"cannot read the period '{period}': use Cal-2027, Q1-2027, Dec-2026, W49-2026 or 2026-12-01..2026-12-31")
    if b < a:
        raise ValueError(f"period '{period}' ends before it starts")
    return a.strftime("%Y-%m-%d"), b.strftime("%Y-%m-%d")


def delivery_hours(first, last, profile="base"):
    """UTC timestamps of the delivery hours: every hour of the CET days (base), or Monday to Friday 08:00–20:00 (peak)."""
    h = pd.date_range(pd.Timestamp(first, tz=TZ), (pd.Timestamp(last) + pd.Timedelta(days=1)).tz_localize(TZ), freq="h", inclusive="left")
    if profile == "peak":
        h = h[(h.weekday < 5) & (h.hour >= 8) & (h.hour < 20)]
    return h.tz_convert("UTC")


def label(c):
    if c["kind"] == "lttr":
        return f"LTTR {c['product']} {c['period']}"
    return f"{c['direction'].capitalize()} {c['product']} {c['profile'].capitalize()} {c['period']}"


def _load(folder):
    return [json.load(open(f)) for f in sorted(glob.glob(os.path.join(BOOK, folder, "*.json")))]


def _marks():
    fn = os.path.join(BOOK, "marks.csv")
    return pd.read_csv(fn, dtype=str) if os.path.exists(fn) else pd.DataFrame(columns=["date", "product", "period", "profile", "price", "source", "recorded_at_utc"])


def _now():
    return pd.Timestamp.now("UTC")


def _require(cond, msg):
    if not cond:
        sys.exit("refused: " + msg)


def _clean(text):
    """Free text ends up in markdown tables and lists: one line, no cell separators."""
    return " ".join(str(text or "").replace("|", "/").split())


def open_call(a):
    kind = a.kind.lower()
    _require(kind in ("forward", "lttr"), "kind must be forward or lttr")
    product = a.product.strip().upper().replace(" ", "")
    if kind == "lttr":
        _require(re.fullmatch(r"[A-Z]{2}>[A-Z]{2}", product) is not None, "an LTTR product is a border direction such as FR>DE")
        direction, profile = "long", "base"
    else:
        _require(re.fullmatch(r"[A-Z]{2}(-[A-Z]{2})?", product) is not None, "a forward product is a zone (DE) or a spread of two zones (DE-FR)")
        direction, profile = a.direction.lower(), a.profile.lower()
        _require(direction in ("long", "short"), "direction must be long or short")
        _require(profile in ("base", "peak"), "profile must be base or peak")
    try:
        first, last = period_days(a.period)
        size, price = float(a.size), float(a.price)
    except ValueError as e:
        sys.exit("refused: " + str(e))
    _require(size > 0, "size must be positive (MW)")
    _require(kind != "lttr" or price >= 0, "an auction price cannot be negative")
    _require(len(a.source.strip()) >= 5, "say where the entry price comes from (exchange or auction, and the date)")
    _require(len(a.rationale.strip()) >= 20, "a call needs its reasoning: at least a sentence")
    now = _now()
    _require(pd.Timestamp(first, tz=TZ) > now, f"delivery of {a.period} has already started; a call is opened before delivery")
    os.makedirs(os.path.join(BOOK, "calls"), exist_ok=True)
    day = now.strftime("%Y%m%d")
    n = len(glob.glob(os.path.join(BOOK, "calls", f"{day}-*.json"))) + 1
    opt = lambda v: None if v is None or str(v).strip() == "" else float(v)
    c = {"id": f"{day}-{n:02d}", "opened_at_utc": now.isoformat(), "kind": kind, "product": product, "period": a.period.strip(), "profile": profile,
         "direction": direction, "size_mw": size, "entry_price": price, "entry_source": _clean(a.source), "delivery_first_day": first, "delivery_last_day": last,
         "hours": int(len(delivery_hours(first, last, profile))), "target": opt(a.target), "stop": opt(a.stop), "rationale": _clean(a.rationale)}
    json.dump(c, open(os.path.join(BOOK, "calls", c["id"] + ".json"), "w"), indent=1)
    print("opened", c["id"], label(c), f"{size:g} MW at {price:g}")


def close_call(a):
    calls = {c["id"]: c for c in _load("calls")}
    _require(a.id in calls, f"no call with id {a.id}")
    _require(calls[a.id]["kind"] == "forward", "an LTTR runs to the end of its period and settles by itself")
    fn = os.path.join(BOOK, "closes", a.id + ".json")
    _require(not os.path.exists(fn), f"call {a.id} is already closed")
    _require(len(a.source.strip()) >= 5, "say where the exit price comes from")
    os.makedirs(os.path.join(BOOK, "closes"), exist_ok=True)
    json.dump({"id": a.id, "closed_at_utc": _now().isoformat(), "exit_price": float(a.price), "exit_source": _clean(a.source), "note": _clean(a.note)}, open(fn, "w"), indent=1)
    print("closed", a.id, "at", a.price)


def mark(a):
    _require(len(a.source.strip()) >= 5, "say where the mark comes from")
    try:
        period_days(a.period); float(a.price)
    except ValueError as e:
        sys.exit("refused: " + str(e))
    M = _marks()
    M.loc[len(M)] = {"date": _now().strftime("%Y-%m-%d"), "product": a.product.strip().upper().replace(" ", ""), "period": a.period.strip(), "profile": a.profile.lower(),
                     "price": f"{float(a.price):g}", "source": _clean(a.source), "recorded_at_utc": _now().isoformat()}
    os.makedirs(BOOK, exist_ok=True)
    M.to_csv(os.path.join(BOOK, "marks.csv"), index=False)
    print("marked", a.product, a.period, "at", a.price)


def _hourly_prices(first, last):
    from fbcast import data
    P = data.load_prices_long(first, last)
    return P.set_index("t")[["DE", "FR"]].resample("1h").mean()


def value(c, close, marks, prices, now):
    """Reference price, state and P&L of one call. P&L in €/MWh is per MWh of the whole period; P&L in € is that times MW and hours."""
    sign = 1 if c["direction"] == "long" else -1
    H = delivery_hours(c["delivery_first_day"], c["delivery_last_day"], c["profile"])
    out = {"state": "open", "ref": None, "ref_note": "no mark yet", "pnl_mwh": None, "pnl_eur": None, "closed_at": None}
    if c["kind"] == "lttr":
        src, snk = c["product"].split(">")
        done = H[H < now.floor("h")]
        if src not in PRICED or snk not in PRICED or prices is None or len(done) == 0:
            out["ref_note"] = "delivery not started" if len(done) == 0 else "prices for this border are not loaded"
            return out
        p = prices.reindex(done).dropna()
        payout = (p[snk] - p[src]).clip(lower=0)
        out.update({"ref": float(payout.mean()) if len(p) else None, "ref_note": f"average payout over {len(p)} of {len(H)} hours",
                    "pnl_mwh": float((payout - c["entry_price"]).sum() / len(H)), "pnl_eur": float((payout - c["entry_price"]).sum() * c["size_mw"]),
                    "state": "settled" if len(done) == len(H) and len(p) >= 0.98 * len(H) else "in delivery"})
        return out
    if close:
        ref, out["state"], out["ref_note"], out["closed_at"] = close["exit_price"], "closed", close["exit_source"], close["closed_at_utc"]
    elif H[-1] < now.floor("h") and prices is not None and all(z in PRICED for z in c["product"].split("-")):
        p = prices.reindex(H).dropna()
        if len(p) < 0.98 * len(H):
            return out
        z = c["product"].split("-")
        ref = float(p[z[0]].mean() - (p[z[1]].mean() if len(z) == 2 else 0.0))
        out["state"], out["ref_note"] = "settled", "average day-ahead price of the period"
    else:
        m = marks[(marks["product"] == c["product"]) & (marks["period"] == c["period"]) & (marks["profile"] == c["profile"]) & (marks["recorded_at_utc"] > c["opened_at_utc"])]
        if m.empty:
            return out
        last = m.sort_values("recorded_at_utc").iloc[-1]
        ref, out["ref_note"] = float(last["price"]), f"{last['source']}"
    out.update({"ref": ref, "pnl_mwh": sign * (ref - c["entry_price"]), "pnl_eur": sign * (ref - c["entry_price"]) * c["size_mw"] * c["hours"]})
    return out


def report():
    calls, closes, marks = _load("calls"), {c["id"]: c for c in _load("closes")}, _marks()
    now = _now()
    lines = ["# Book: calls priced against the market", "",
             "Paper positions with a size, each entered at a published market price and committed by a GitHub Actions run, so the entry carries GitHub's signature and timestamp. "
             "A call is never edited: it is marked, closed by a second file, or settled against published day-ahead prices. "
             "P&L in €/MWh is per MWh of the delivery period; P&L in € is that times the size and the hours of the period. No transaction costs are deducted.", ""]
    if not calls:
        lines += ["No calls yet. A call is opened from the Actions tab with the `call (open)` workflow."]
        open(os.path.join(ROOT, "BOOK.md"), "w").write("\n".join(lines) + "\n")
        return
    prices = None
    started = [c for c in calls if pd.Timestamp(c["delivery_first_day"], tz=TZ) < now and c["id"] not in closes]
    if started:
        try:
            prices = _hourly_prices(min(c["delivery_first_day"] for c in started), min(max(c["delivery_last_day"] for c in started), now.strftime("%Y-%m-%d")))
        except Exception as e:
            print("prices not loaded (%s); calls in delivery keep their last state" % type(e).__name__)
    V = [(c, value(c, closes.get(c["id"]), marks, prices, now)) for c in calls]
    done = [(c, v) for c, v in V if v["state"] in ("closed", "settled")]
    live = [(c, v) for c, v in V if v["state"] not in ("closed", "settled")]
    eur = lambda x: "n/a" if x is None else f"{x:+,.0f}"
    mwh = lambda x: "n/a" if x is None else f"{x:+.2f}"
    wins = [v["pnl_eur"] for _, v in done if v["pnl_eur"] is not None and v["pnl_eur"] > 0]
    losses = [v["pnl_eur"] for _, v in done if v["pnl_eur"] is not None and v["pnl_eur"] <= 0]
    lines += ["## Summary", "", "| Calls | Open | Closed or settled | Winners | Realized P&L, € | Average win, € | Average loss, € | Open P&L at last mark, € |", "| --- | --- | --- | --- | --- | --- | --- | --- |",
              f"| {len(calls)} | {len(live)} | {len(done)} | {len(wins)} of {len(done)} | {eur(sum(wins) + sum(losses)) if done else 'n/a'} | {eur(np.mean(wins)) if wins else 'n/a'} | {eur(np.mean(losses)) if losses else 'n/a'} | "
              f"{eur(sum(v['pnl_eur'] for _, v in live if v['pnl_eur'] is not None)) if any(v['pnl_eur'] is not None for _, v in live) else 'n/a'} |"]
    if live:
        lines += ["", "## Open calls", "", "| Id | Opened (UTC) | Call | MW | Entry, €/MWh | Reference, €/MWh | Reference is | P&L, €/MWh | P&L, € | Target | Stop |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for c, v in live:
            f = lambda x: "" if x is None else f"{x:g}"
            lines.append(f"| {c['id']} | {c['opened_at_utc'][:16].replace('T', ' ')} | {label(c)} | {c['size_mw']:g} | {c['entry_price']:.2f} | {'n/a' if v['ref'] is None else format(v['ref'], '.2f')} | {v['ref_note']} | "
                         f"{mwh(v['pnl_mwh'])} | {eur(v['pnl_eur'])} | {f(c.get('target'))} | {f(c.get('stop'))} |")
    if done:
        lines += ["", "## Closed and settled calls", "", "| Id | Opened (UTC) | Closed | Call | MW | Entry, €/MWh | Exit, €/MWh | Exit is | P&L, €/MWh | P&L, € |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for c, v in done:
            when = v["closed_at"][:10] if v["closed_at"] else c["delivery_last_day"]
            lines.append(f"| {c['id']} | {c['opened_at_utc'][:16].replace('T', ' ')} | {when} | {label(c)} | {c['size_mw']:g} | {c['entry_price']:.2f} | {v['ref']:.2f} | {v['ref_note']} | {mwh(v['pnl_mwh'])} | {eur(v['pnl_eur'])} |")
    lines += ["", "## Reasoning, as written when each call was opened", ""]
    for c in calls:
        lines.append(f"* **{c['id']}, {label(c)}** ({c['size_mw']:g} MW at {c['entry_price']:.2f}, {c['entry_source']}): {c['rationale']}")
    open(os.path.join(ROOT, "BOOK.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines[:14]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["open", "close", "mark", "report"])
    for k in ("kind", "product", "period", "direction", "profile", "size", "price", "source", "rationale", "target", "stop", "id", "note"):
        ap.add_argument("--" + k, default={"kind": "forward", "direction": "long", "profile": "base"}.get(k, ""))
    a = ap.parse_args()
    {"open": open_call, "close": close_call, "mark": mark}.get(a.action, lambda _: None)(a)
    report()


if __name__ == "__main__":
    main()
