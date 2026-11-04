# fbcast: a daily, public forecast of Core flow-based binding constraints

Every morning this repository forecasts, for the next CET day, which hours the Core domain's most price-relevant
French constraint (RTE's Creys–St-Vulbas Ouest 400 kV line) will bind in the day-ahead auction, and in which hours
Germany will price above France. The forecast is issued before the 12:00 CET auction closes and committed to this
repository; the next afternoon it is scored against the published results. The commit history is the track record.

## Information set and timing

| When (CET, winter) | What JAO publishes | What this repo does |
| --- | --- | --- |
| D-1, ~09:00–10:30 | Final flow-based domain for D (`finalComputation`) and max net positions (`maxNetPos`) | `fbcast.forecast` builds features and issues `forecasts/D.json` (Actions: 11:05, retry 12:05) |
| D-1, 12:00 | Day-ahead auction closes | — |
| D-1, ~13:00 | Results for D: shadow prices (`shadowPrices`), net positions, prices | `fbcast.score` scores the forecast for D (Actions: 14:30), `fbcast.report` rebuilds `SCORECARD.md` |

A forecast counts only if its issue time precedes the publication of the results it predicts; `fbcast.forecast`
records both timestamps and marks a forecast `late` if the results already exist. Late forecasts are kept but
excluded from the scorecard.

## What is forecast, per hour of day D

* `p_bind`: probability that Creys–St-Vulbas Ouest (either circuit) carries a positive shadow price in the hour.
* `p_de_above_fr`: probability that the DE–LU day-ahead price exceeds the FR price in the hour.
* `e_spread`: expected DE−FR spread in €/MWh (reported for completeness; the backtest shows no level skill).

Daily summaries: expected number of binding hours, the 15–17 CET block (where the German premium is made) and the
21–23 CET block.

## Model

Two logistic regressions and one ridge regression, all on the D-1 published domain plus hour-of-day climatology:

* Creys–St-Vulbas: presolved flag, RAM/Fmax, loading (Fref/Fmax), minRAM top-up (AMR/Fmax);
* French max export and max import net positions for the hour;
* hour-of-day climatology from the training window, weekend flag;
* for the spread models, additionally the binding probability and the hour's climatological sign and level.

No lagged realized values are used. On the 2026 data they added noise, and leaving them out means a forecast
depends only on what JAO publishes for the target day, which keeps the audit trail simple. Models are refit weekly
(`fbcast.train`, Mondays) on all history; the backtest is stored with the model in `models/bundle.json`.

## Backtest (strict time split, trained to 16 Oct, tested 17 Oct–3 Nov 2026, 432 hours)

| Target | AUC | Brier | Brier, climatology | Hit rate | Hit rate, climatology |
| --- | --- | --- | --- | --- | --- |
| Creys–St-Vulbas binds | 0.83 | 0.157 | 0.215 | 77% | 66% |
| DE price above FR | 0.86 | 0.144 | 0.220 | 78% | 64% |
| DE−FR level (MAE, €/MWh) | — | 23.5 | 23.8 (zero forecast) | — | — |

The binding model's skill comes from the published loading of the line (Fref/Fmax) and the size of its minRAM
top-up; the sign model's skill comes from the same variables plus the French export room. The level of the spread
is not forecastable from this information set: the hourly distribution is dominated by spikes.

## Running it

```
pip install -r requirements.txt
python -m fbcast.train                      # pulls history from 1 Sep 2026 (JAO, energy-charts), ~5 min, saves models/
python -m fbcast.forecast --wait-minutes 45 # issues tomorrow's forecast once the domain is on JAO
python -m fbcast.score                      # scores every issued forecast whose results are published
python -m fbcast.report                     # rewrites SCORECARD.md
```

For the public track record: push to a public GitHub repository, enable Actions, and the three workflows in
`.github/workflows` run the forecast (11:05 CET), the scoring (14:30 CET) and the weekly retrain (Monday 07:00 CET)
and commit the results. Cron times are UTC and set for winter time; move them one hour when CEST starts.

## How a third party can verify the track record

1. **The forecast existed before the result did.** Every forecast is committed by the GitHub Actions run through the
   GitHub API, so the commit carries GitHub's own signature (the *Verified* badge) and GitHub's server timestamp; the
   public Actions log of the run shows the same time. Each forecast file also records the JAO publication times of the
   domain it used and of the results (`domain_published_utc`, `results_published_utc`), which can be checked directly
   against the JAO publication tool. Forecasts issued after the results are marked `late` and never counted.
2. **Independent of GitHub.** Each forecast is additionally stamped with OpenTimestamps: the file's SHA-256 is anchored
   in a Bitcoin block. `pip install opentimestamps-client` and `ots verify forecasts/<day>.json.ots` prints the block
   that proves the file existed before that block's time.
3. **The scores are reproducible from public data.** `python -m fbcast.score --verify` re-downloads the JAO results
   and SMARD prices for every scored day, recomputes each scorecard and reports any difference; the `verify` workflow
   does this every Sunday and fails loudly if a number has changed. Each forecast names the SHA-256 of the committed
   model file that produced it.
4. **Nothing is rewritten.** The `main` branch is protected against force-pushes and deletions; forecast and scorecard
   files are never edited after they are written, and the scorecard is regenerated from them, not maintained by hand.

## Data

* JAO Core publication tool, public API, no key: `finalComputation` (presolved CNECs), `maxNetPos`, `shadowPrices`, `netPos`.
* Day-ahead prices DE-LU and FR: SMARD (Bundesnetzagentur) via the energy-charts.info API, CC BY 4.0.
* Cached under `data/` (not committed).

## Next steps

* ENTSO-E day-ahead forecasts (wind, solar, load for DE and FR; free API token) as additional features.
* The same model for the other constraints that set the DE–FR and DE–NL spreads (Gronau–Hengelo, Ensdorf–Vigy, Pleinting–St. Peter).
* A calibrated P(bind) for each presolved CNEC, which turns the forecast into a predicted shadow-price map.
