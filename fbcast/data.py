"""Data access: JAO Core publication tool (public, no key) and energy-charts.info day-ahead prices (SMARD).

Everything is cached as one JSON file per dataset and day under DATA_DIR so re-runs are cheap and the
information set of a forecast can be reconstructed later.
"""
import json, os, time
import pandas as pd, requests

JAO = "https://publicationtool.jao.eu/core/api/data/"
PRICES = "https://api.energy-charts.info/price"
DATA_DIR = os.environ.get("FBCAST_DATA", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
FC_KEEP = ["dateTimeUtc", "tso", "cneName", "contName", "direction", "elementType", "presolved", "ram", "minRamFactor", "fmax", "frm",
           "fref", "fcore", "fall", "fuaf", "amr", "ptdf_DE", "ptdf_FR", "ptdf_NL", "ptdf_BE", "ptdf_AT"]
_S = requests.Session()


def _get(ds, f, t, extra=None, take=4000, retries=5, single=False):
    rows, skip, last_mod = [], 0, None
    while True:
        p = {"FromUtc": f.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "ToUtc": t.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "Skip": skip, "Take": take}
        if extra:
            p.update(extra)
        for a in range(retries):
            try:
                r = _S.get(JAO + ds, params=p, timeout=180)
                r.raise_for_status()
                j = r.json()
                break
            except Exception:
                if a == retries - 1:
                    raise
                time.sleep(5 * (a + 1))
        data = j.get("data", [])
        last_mod = j.get("lastModifiedOn") or last_mod
        rows.extend(data)
        total = j.get("totalRowsWithFilter")
        if single or total is None or skip + take >= total or len(data) < take:
            break
        skip += take
    return rows, last_mod


def day_bounds(day):
    """UTC bounds of a CET calendar day."""
    d0 = pd.Timestamp(day, tz="Europe/Berlin")
    return d0.tz_convert("UTC"), (d0 + pd.Timedelta(days=1)).tz_convert("UTC")


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
    """Day-ahead prices from energy-charts (SMARD), native resolution, as a DataFrame with columns t, DE, FR."""
    out = None
    for bzn in zones:
        col = "DE" if bzn == "DE-LU" else bzn
        for a in range(4):
            r = _S.get(PRICES, params={"bzn": bzn, "start": start, "end": end}, timeout=120)
            if r.status_code == 200:
                break
            time.sleep(20)
        r.raise_for_status()
        j = r.json()
        d = pd.DataFrame({"t": pd.to_datetime(j["unix_seconds"], unit="s", utc=True), col: j["price"]})
        out = d if out is None else out.merge(d, on="t", how="outer")
        time.sleep(3)
    return out.sort_values("t").dropna().reset_index(drop=True)


def results_published(day):
    """True if the day-ahead results (shadow prices) for CET day `day` are on JAO, with their publication time."""
    f, t = day_bounds(day)
    rows, last_mod = _get("shadowPrices", f, t, take=1, single=True)
    return len(rows) > 0, last_mod


def domain_published(day):
    f, t = day_bounds(day)
    rows, last_mod = _get("finalComputation", f, f + pd.Timedelta(minutes=60), {"Filter": json.dumps({"Presolved": True})}, take=1, single=True)
    return len(rows) > 0, last_mod
