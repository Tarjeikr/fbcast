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
* `spread_p10`, `spread_p50`, `spread_p90`: the 10th, 50th and 90th percentiles of the DE−FR spread in €/MWh, from quantile
  regressions on the same information set. The median is the level forecast; the P10–P90 band is a forecast of how wide
  the hour's outcome can be. (`e_spread`, a mean-regression value, is kept in the files for continuity; it has no skill.)

All of these are issued for every hour of the CET day. Each forecast file also carries a summary per block of the day (night
00–05, morning 06–09, midday 10–14, afternoon 15–17, evening 18–20, late 21–23): expected binding hours, probability of
Germany above France, and the mean P50 with its P10–P90 band. `SCORECARD.md` shows the latest forecast hour by hour (chart
and table), the last scored day against its outcome, and each block's skill against climatology once the block has 7 counted
days.

Where the skill sits (backtests, two held-out windows): the probability of Germany above France beats climatology in every
block except late evening, where it is level; the spread level (P50) is clearly better than climatology only at night
(about 20% lower pinball loss) and roughly level elsewhere; and the 80% bands under-cover in the volatile hours (39–57%
at midday and in the afternoon, 62–85% elsewhere). The live scorecard reports coverage by block so the bands can be
recalibrated on real out-of-sample days rather than on the backtest.

## Model

Two logistic regressions and three linear quantile regressions (P10, P50, P90), all on the D-1 published domain plus
hour-of-day climatology:

* Creys–St-Vulbas: presolved flag, RAM/Fmax, loading (Fref/Fmax), minRAM top-up (AMR/Fmax);
* French max export and max import net positions for the hour;
* hour-of-day climatology from the training window, weekend flag;
* for the spread models, additionally the binding probability and the hour's climatological sign, level and quantiles.

One structural rule is applied after the models: when neither circuit of the line is in the presolved Core domain for an hour,
the line cannot carry a shadow price, so `p_bind` is capped at 0.01 (53 of 53 such hours in the training history and 24 of 24 in
the two backtest windows had no binding). It was added on 8 Nov 2026 after the 9 Nov forecast gave 0.7 for hours in which the
line was absent from the domain; forecasts issued from 9 Nov record it under `model.rules`.

No lagged realized values are used. On the 2026 data they added noise, and leaving them out means a forecast
depends only on what JAO publishes for the target day, which keeps the audit trail simple. Models are refit weekly
(`fbcast.train`, Mondays) on all history; the backtest is stored with the model in `models/bundle.json`.

## Backtest (strict time split, trained to 18 Oct, tested 19 Oct–5 Nov 2026, 432 hours)

| Target | AUC | Brier | Brier, climatology | Hit rate | Hit rate, climatology |
| --- | --- | --- | --- | --- | --- |
| Creys–St-Vulbas binds | 0.82 | 0.156 | 0.200 | 77% | 66% |
| DE price above FR | 0.87 | 0.140 | 0.215 | 78% | 64% |

| Spread quantiles (€/MWh) | Model | Climatology quantiles | Zero forecast | Persistence D-1 |
| --- | --- | --- | --- | --- |
| Pinball loss (mean of P10, P50, P90) | 6.9 | 7.9 | — | — |
| P50 absolute error | 19.2 | 21.5 | 21.2 | 33.8 |
| 80% band coverage | 76% | 75% | — | — |

The binding model's skill comes from the published loading of the line (Fref/Fmax) and the size of its minRAM
top-up; the sign model's skill comes from the same variables plus the French export room. The level of the spread is
only weakly forecastable from this information set: the median beats the climatological median and a zero forecast
by about 10% and persistence by more than 40%, and the band is honest about the rest.

## Base and peak

Besides the hourly forecasts, every forecast and the scorecard carry the two products a spread is quoted in: **base**, the average
DE−FR day-ahead spread over all 24 hours, and **peak**, the average over delivery 08:00–21:00 CET (hours beginning 08 to 20, every
day of the week; set `PEAK_WEEKDAYS_ONLY = True` in `fbcast/features.py` for an exchange-style Monday to Friday peak).

The forecast of each product is the average of the hourly P10, P50 and P90 over its hours, which is exact when the hourly errors
move together (they largely do within a day) and slightly too narrow otherwise. `P(spread > 0)` is read off that band with a normal
approximation (width from P10–P90, floor €1/MWh). Each forecast file records both under `summary.products`; the scorecard compares
them with the realized product, with the hour-of-day climatology aggregated the same way, and with yesterday's realized value.

Backtest (trained to 18 Oct, tested on 18 days; the 32 days from 4 Oct give the same picture with narrower bands):

| 18 held-out days, €/MWh | P50 error | Constant (training median) | Yesterday's value | 80% band coverage | Sign hit | Sign Brier | Sign Brier, climatology |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Base | 16.8 | 19.5 | 28.5 | 72% | 78% | 0.200 | 0.253 |
| Peak | 24.9 | 27.3 | 40.6 | 67% | 78% | 0.201 | 0.250 |

The level beats a constant by 10–15% and yesterday's value by about 40%, the sign probability is clearly better than climatology,
and the bands cover 50–72% of outcomes rather than 80%, so treat the width as a lower bound until the live scorecard says otherwise.

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
