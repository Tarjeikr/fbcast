"""Wait for JAO to publish the flow-based domain of a delivery day. Used by the forecast workflow.

Usage: python -m fbcast.wait --day 2026-11-23 [--minutes 285] [--every 120]

Ends with one of three outcomes, printed and, inside a GitHub workflow, written to the step's outputs as `outcome`:
  issue      the domain is on JAO: go on and issue the forecast
  handover   not yet, and this run has used its time: a fresh run has to keep waiting (a GitHub job may run six hours)
  giveup     not yet, and it is past 14:00 CET on the day before delivery: the auction has cleared without the domain

GitHub starts scheduled runs hours late, so a run cannot be made to start shortly before the publication. Instead a run
starts whenever GitHub lets it and waits here.
"""
import argparse, os, sys, time
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fbcast import data


def cutoff(day):
    """14:00 CET on the day before delivery, as epoch seconds. The day-ahead results are out at about 13:05 CET."""
    return (pd.Timestamp(day) - pd.Timedelta(hours=10)).tz_localize("Europe/Berlin").timestamp()


def wait(day, minutes, every, published=None, now=time.time, sleep=time.sleep):
    published = published or data.domain_published
    end = now() + 60 * minutes
    while True:
        try:
            ok, when = published(day)
        except Exception as e:  # JAO slow or unreachable: the same as not published yet
            ok, when = False, None
            print("JAO not answering (%s); will ask again" % type(e).__name__, flush=True)
        if ok:
            print("domain for", day, "is on JAO, published", when, flush=True)
            return "issue"
        if now() >= end:
            break
        print(pd.Timestamp(now(), unit="s", tz="UTC").tz_convert("Europe/Berlin").strftime("%H:%M CET"), "domain for", day, "not on JAO yet", flush=True)
        sleep(every)
    if now() < cutoff(day):
        print("domain for", day, "not on JAO after", minutes, "minutes; a fresh run has to keep waiting", flush=True)
        return "handover"
    print("domain for", day, "not on JAO, and it is past 14:00 CET on the day before delivery; giving up", flush=True)
    return "giveup"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=(pd.Timestamp.now(tz="Europe/Berlin") + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    ap.add_argument("--minutes", type=float, default=285)
    ap.add_argument("--every", type=float, default=120, help="seconds between two looks at JAO")
    a = ap.parse_args()
    out = wait(a.day, a.minutes, a.every)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write("outcome=%s\n" % out)
    sys.exit(1 if out == "giveup" else 0)


if __name__ == "__main__":
    main()
