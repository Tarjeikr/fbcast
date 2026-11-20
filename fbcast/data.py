"""Data access: JAO Core publication tool (public, no key) and energy-charts.info day-ahead prices (SMARD).

Everything is cached as one JSON file per dataset and day under DATA_DIR so re-runs are cheap and the
information set of a forecast can be reconstructed later. The long history used by the fundamentals model is
cached per dataset and two-day window (JAO serves at most two days per request) and per zone and year for prices.
"""
import json, os, time
import pandas as pd, requests

JAO = "https://publicationtool.jao.eu/core/api/data/"
PRICES = "https://api.energy-charts.info/price"
DATA_DIR = os.environ.get("FBCAST_DATA", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
FC_KEEP = ["dateTimeUtc", "tso", "cneName", "contName", "direction", "elementType", "presolved", "ram", "minRamFactor", "fmax", "frm",
           "fref", "fcore", "fall", "fuaf", "amr", "ptdf_DE", "ptdf_FR", "ptdf_NL", "ptdf_BE", "ptdf_AT"]
_S = requests.Session()


def _get(ds, f, t, extra=None, take=4000, retries=5, single=False, timeout=180):
    rows, skip, last_mod = [], 0, None
    while True:
        p = {"FromUtc": f.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "ToUtc": t.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "Skip": skip, "Take": take}
        if extra:
            p.update(extra)
        for a in range(retries):
            try:
                r = _S.get(JAO + ds, params=p, timeout=timeout)
                r.raise_for_status()
                j = r.json()
                break
            except Exception:
                if a == retries - 1:
                    raise
                time.sleep(10 * (a + 1))
        data = j.get("data", [])
        last_mod = j.get("lastModifiedOn") or last_mod
        rows.extend(data)
        total = j.get("totalRowsWithFilter")
        if single or total is None or skip + take >= total or len(data) < take:
            break
        skip += take
    return rows, last_mod


def day_bounds(day):
    """UTC bounds of a CET calendar day: 23 hours apart on the day summer time starts, 25 on the day it ends."""
    d0 = pd.Timestamp(day, tz="Europe/Berlin")
    d1 = (pd.Timestamp(day) + pd.Timedelta(days=1)).tz_localize("Europe/Berlin")
    return d0.tz_convert("UTC"), d1.tz_convert("UTC")


def fetch_day(ds, day, force=False):
    """Fetch one dataset for one CET day; returns (rows, lastModifiedOn). Cached unless force."""
    os.makedirs(DATA_DIR, exist_ok=True)
    fn = os.path.join(DATA_DIR, f"{ds}_{day}.json")
    if os.path.exists(fn) and not force:
        j = json.load(open(fn))
        return j["rows"], j.get("lastModifiedOn")
    f, t = day_bounds(day)
    extra = {"Filter": json.dumps({"Presolved": True})} if ds == "finalComputation" else None
    rows, last_mod = _get(ds, f, t, extra)
    if ds == "finalComputation":
        rows = [{k: r.get(k) for k in FC_KEEP} for r in rows]
    if rows:  # never cache an empty answer: the data may simply not be published yet
        json.dump({"rows": rows, "lastModifiedOn": last_mod}, open(fn, "w"))
    return rows, last_mod


def load_days(ds, days, workers=4):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fetched = list(ex.map(lambda d: fetch_day(ds, d)[0], days))
    frames = [pd.DataFrame(rows) for rows in fetched if rows]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["t"] = pd.to_datetime(df.dateTimeUtc, utc=True)
    return df


def fetch_prices(start, end, zones=("DE-LU", "FR")):
    """Day-ahead prices from energy-charts (SMARD), native resolution, as a DataFrame with columns t, DE, FR.
    The API rate-limits shared addresses (HTTP 429), so requests back off patiently and honour Retry-After."""
    out = None
    for bzn in zones:
        col = "DE" if bzn == "DE-LU" else bzn
        r = None
        for a in range(7):
            try:
                r = _S.get(PRICES, params={"bzn": bzn, "start": start, "end": end}, timeout=120)
                if r.status_code == 200:
                    break
                wait = int(r.headers.get("Retry-After", 0) or 0) or min(120, 20 * 2 ** a)
            except Exception:
                wait = min(120, 20 * 2 ** a)
            time.sleep(wait)
        r.raise_for_status()
        j = r.json()
        d = pd.DataFrame({"t": pd.to_datetime(j["unix_seconds"], unit="s", utc=True), col: j["price"]})
        out = d if out is None else out.merge(d, on="t", how="outer")
        time.sleep(5)
    return out.sort_values("t").dropna().reset_index(drop=True)


def results_published(day):
    """True if the day-ahead results (shadow prices) for CET day `day` are on JAO, with their publication time."""
    f, t = day_bounds(day)
    rows, last_mod = _get("shadowPrices", f, t, take=1, single=True, retries=2, timeout=60)
    return len(rows) > 0, last_mod


def domain_published(day):
    f, t = day_bounds(day)
    rows, last_mod = _get("finalComputation", f, f + pd.Timedelta(minutes=60), {"Filter": json.dumps({"Presolved": True})}, take=1, single=True, retries=2, timeout=60)
    return len(rows) > 0, last_mod


def day_complete(day, force=True):
    """True when JAO has published the final domain and max net positions for every hour of the CET day.
    Publication arrives over several minutes; a forecast issued on a partial day has NaN hours, so wait for the full set."""
    f, t = day_bounds(day)
    hours_expected = int((t - f) / pd.Timedelta(hours=1))
    fc_rows, _ = fetch_day("finalComputation", day, force=force)
    mx_rows, _ = fetch_day("maxNetPos", day, force=force)
    if not fc_rows or not mx_rows:
        return False
    fc_hours = {r["dateTimeUtc"][:13] for r in fc_rows}
    mx_hours = {r["dateTimeUtc"][:13] for r in mx_rows}
    return len(fc_hours) >= hours_expected and len(mx_hours) >= hours_expected


# ---------------------------------------------------------------------------------------------------------------------
# Long history for the fundamentals model
# ---------------------------------------------------------------------------------------------------------------------
EPOCH = pd.Timestamp("2022-06-08", tz="UTC")   # Core flow-based market coupling went live for delivery day 9 June 2022


def fetch_window(ds, k, keep=None):
    """Rows of dataset `ds` for the k-th two-day UTC window since EPOCH. Cached once the window is more than two days old."""
    os.makedirs(DATA_DIR, exist_ok=True)
    f = EPOCH + pd.Timedelta(days=2 * k); t = f + pd.Timedelta(days=2)
    fn = os.path.join(DATA_DIR, f"w2_{ds}_{f.strftime('%Y%m%d')}.json")
    if os.path.exists(fn):
        return json.load(open(fn))
    rows, _ = _get(ds, f, t, take=100000, single=True, retries=6, timeout=120)
    if keep:
        rows = [{c: r.get(c) for c in keep} for r in rows]
    if rows and t < pd.Timestamp.now("UTC") - pd.Timedelta(days=2):
        tmp = fn + ".tmp"
        json.dump(rows, open(tmp, "w"))
        os.replace(tmp, fn)
    return rows


def load_windows(ds, start, end, keep=None, workers=6):
    """All rows of `ds` between CET days start and end (inclusive), as a DataFrame with a UTC timestamp column t."""
    from concurrent.futures import ThreadPoolExecutor
    f, _ = day_bounds(start); _, t = day_bounds(end)
    k0 = int((f - EPOCH) / pd.Timedelta(days=2)); k1 = int((t - EPOCH) / pd.Timedelta(days=2))
    ks = list(range(max(k0, 0), k1 + 1))

    def safe(k):
        try:
            return fetch_window(ds, k, keep)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        parts = dict(zip(ks, ex.map(safe, ks)))
    failed = [k for k in ks if parts[k] is None]
    for k in failed:  # second pass, one at a time: JAO sometimes times out under parallel load
        time.sleep(2)
        parts[k] = safe(k)
    failed = [k for k in ks if parts[k] is None]
    if len(failed) > max(2, 0.02 * len(ks)):
        raise RuntimeError(f"JAO did not return {len(failed)} of {len(ks)} windows of {ds}")
    if failed:  # a few missing windows leave gaps that the models tolerate; they are downloaded again next time
        print(f"{ds}: {len(failed)} of {len(ks)} windows missing this run", flush=True)
    rows = [r for k in ks if parts[k] for r in parts[k]]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["t"] = pd.to_datetime(df.dateTimeUtc, utc=True)
    return df[(df.t >= f) & (df.t < t)].drop_duplicates("t").sort_values("t").reset_index(drop=True)


def _price_request(bzn, start, end):
    r = None
    for a in range(8):
        try:
            r = _S.get(PRICES, params={"bzn": bzn, "start": start, "end": end}, timeout=180)
            if r.status_code == 200:
                j = r.json()
                return {"unix_seconds": j["unix_seconds"], "price": j["price"]}
            wait = int(r.headers.get("Retry-After", 0) or 0) or min(180, 30 * (a + 1))
        except Exception:
            wait = min(180, 30 * (a + 1))
        time.sleep(wait)
    raise RuntimeError(f"energy-charts did not return prices for {bzn} {start}..{end}")


def load_prices_long(start, end, zones=("DE-LU", "FR")):
    """Day-ahead prices between two dates, native resolution, columns t, DE, FR. One request per zone and calendar year,
    spaced out because the API rate-limits; closed years are cached, the current year is downloaded each time."""
    os.makedirs(DATA_DIR, exist_ok=True)
    this_year = pd.Timestamp.now("UTC").year
    out = None
    for bzn in zones:
        col = "DE" if bzn == "DE-LU" else bzn
        frames = []
        for year in range(pd.Timestamp(start).year, pd.Timestamp(end).year + 1):
            fn = os.path.join(DATA_DIR, f"px_{bzn}_{year}.json")
            if year < this_year and os.path.exists(fn):
                j = json.load(open(fn))
            else:
                j = _price_request(bzn, f"{year}-01-01", f"{year}-12-31" if year < this_year else end)
                if year < this_year:
                    json.dump(j, open(fn, "w"))
                time.sleep(6)
            frames.append(pd.DataFrame({"t": pd.to_datetime(j["unix_seconds"], unit="s", utc=True), col: j["price"]}))
        d = pd.concat(frames).drop_duplicates("t")
        out = d if out is None else out.merge(d, on="t", how="outer")
    lo, _ = day_bounds(start); _, hi = day_bounds(end)
    out = out[(out.t >= lo) & (out.t < hi)]
    return out.sort_values("t").dropna().reset_index(drop=True)
