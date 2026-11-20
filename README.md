# fbcast: a daily, public day-ahead forecast for the Core region

Every morning this repository forecasts the next CET day in the Core flow-based region, hour by hour: the DE−FR day-ahead
spread with a P10–P90 band, the probability that Germany prices above France, the German and French prices, and the hours in
which the Core domain's most price-relevant French constraint (RTE's Creys–St-Vulbas Ouest 400 kV line) will bind. The forecast
is issued before the 12:00 CET auction closes and committed to this repository; the next afternoon it is scored against the
published results. The commit history is the track record, and nothing in it is edited afterwards.

`SCORECARD.md` is rebuilt after every scoring run and is the place to look first.

## Information set and timing

| When (CET, winter) | What JAO publishes | What this repo does |
| --- | --- | --- |
| D-2, evening (about 20:00) | D-2 congestion forecast for D (`d2CF`: vertical load, generation, Core net position per hub) and reference programmes on the non-Core borders (`refprog`) | — |
| D-1, about 09:55 | Final flow-based domain for D (`finalComputation`), max net positions (`maxNetPos`), max bilateral exchanges (`maxExchanges`) | `fbcast.forecast` builds features and issues `forecasts/D.json` |
| D-1, 12:00 | Day-ahead auction closes | — |
| D-1, about 13:05 | Results for D: shadow prices (`shadowPrices`), net positions, prices | `fbcast.score` scores the forecast for D, `fbcast.report` rebuilds `SCORECARD.md` |

A forecast counts only if its issue time precedes the publication of the results it predicts; `fbcast.forecast` records both
timestamps and marks a forecast `late` if the results already exist. Late forecasts are kept but excluded from the scorecard.
Each file also records gate closure and whether it was issued before it (`issued_before_gate_closure`); the scorecard reports
that count separately.

**Scheduling.** GitHub starts scheduled workflows late: every scheduled run of this repository from 4 to 19 November 2026 began
4.5 to 10.5 hours after its cron time, so the forecasts of those weeks that count are the ones started by hand. The forecast
workflow therefore has a slot every 30 minutes from 21:07 to 11:37 CET, and a run does not have to start at the right moment:
any run that starts between 07:30 CET and gate closure waits for JAO to publish the domain and then issues. A run that starts
before 07:30 CET, or after the day's forecast exists, stops at its first step.

## What is forecast, per hour of day D

* `p_bind`: probability that Creys–St-Vulbas Ouest (either circuit) carries a positive shadow price in the hour.
* `p_de_above_fr`: probability that the DE–LU day-ahead price exceeds the FR price in the hour.
* `spread_p10`, `spread_p50`, `spread_p90`: the 10th, 50th and 90th percentiles of the DE−FR spread in €/MWh.
* `de_p10/p50/p90` and `fr_p10/p50/p90`: the same percentiles of the DE–LU and FR day-ahead prices.
* `grid_p_de_above_fr`, `grid_p10/p50/p90`: the grid-only model's spread forecast for the same hour, kept so that the two models are
  scored on identical hours.

Each file also carries a summary per block of the day and the two products a spread is quoted in: **base**, the average DE−FR
spread over all 24 hours, and **peak**, the average over delivery 08:00–21:00 CET (hours beginning 08 to 20, every day of the week;
set `PEAK_WEEKDAYS_ONLY = True` in `fbcast/features.py` for an exchange-style Monday to Friday peak). `model.spread_model` says
which model produced the spread forecast: `fundamentals`, or `grid` on a day when the fundamentals inputs were not on JAO in time.

## Two models

### Grid model: will the constraint bind?

A logistic regression on the D-1 published domain plus hour-of-day climatology: for Creys–St-Vulbas the presolved flag, RAM/Fmax,
loading (Fref/Fmax) and minRAM top-up (AMR/Fmax); the French max export and max import net positions; a weekend flag. One
structural rule is applied afterwards: when neither circuit of the line is in the presolved domain for an hour, the line cannot
carry a shadow price, so `p_bind` is capped at 0.01. The same inputs also drive the grid-only spread forecast (a logistic
regression for the sign and three linear quantile regressions), which was the forecast of record until the fundamentals model
was added and remains in every file as the comparator.

Backtest (strict time split, trained to 18 Oct, tested 19 Oct–5 Nov 2026, 432 hours): binding AUC 0.82, Brier 0.156 against
0.200 for climatology, hit rate 77% against 66%.

The grid model knows the network and nothing else. It cannot see a tight German system or a long French one, and in the week
of 17 November 2026, when the DE−FR base spread reached +147 and +164 €/MWh, its median stayed between +3 and +13.

### Fundamentals model: how far apart will the prices clear?

Gradient-boosted quantile regressions (scikit-learn `HistGradientBoostingRegressor`, one per percentile and target) and a
gradient-boosted classifier for the sign, fitted on every hour since Core flow-based market coupling started in June 2022.
All inputs are public before the auction and come from two places:

* **JAO's pre-coupling publication for D.** The D-2 congestion forecast gives, per hub, the TSOs' own forecast of vertical load,
  generation and Core net position. Vertical load is load net of the generation embedded in distribution grids, so it carries the
  TSOs' wind, solar and temperature view; the forecast net position says on which side of the domain they expect each hub to sit.
  The reference programmes give the expected exchanges on the non-Core borders (France with Switzerland, Italy, Spain and Great
  Britain; Germany with Switzerland; the Dutch and Belgian links to Great Britain). The max net positions and max bilateral
  exchanges say how much the domain lets each hub export and import.
* **The market up to yesterday.** DE and FR prices and Core net positions of D-1, D-2 and D-7, their daily statistics, weekly and
  monthly price levels, and how wrong yesterday's forecast net positions were.

No TSO wind or solar forecast is used: the transparency rules only require the day-ahead versions by 18:00 on D-1, six hours
after gate closure, and they were not on the public feed before the auction when checked. No weather model is used either.

The spread is modelled relative to last week's price level (the higher of the two zones' mean prices) and multiplied back. A
decoupled France then looks the same to the trees at €60 and at €200 power, which made no difference on average and a clear
difference when the price level moved in November 2026. Prices are modelled raw; scaling them was worse in the same test.

**Band calibration.** Raw quantile regressions under-cover. Every retrain therefore measures, on its own out-of-sample
walk-forward errors of the last 90 days, how wide each half of the band should have been to hold 80% of outcomes, and stores
those factors with the model (`model.fund.band_factors` in each forecast). Daily base and peak bands get their own factors from
180 days of daily errors (`model.product_cal`), because averaging hourly bands overstates the uncertainty of a daily mean.

### Backtest of the fundamentals model

Walk-forward with monthly refits, 1 November 2025 to 20 November 2026 (385 days, 9,239 hours). Every prediction comes from a
model that had seen nothing from its own month.

| Hourly DE−FR spread | Fundamentals model | Climatology, last 60 days | Yesterday's value | Zero |
| --- | --- | --- | --- | --- |
| Pinball loss (mean of P10, P50, P90) | 5.87 | 8.74 | — | — |
| P50 absolute error, €/MWh | 17.4 | 26.8 | 25.3 | 31.0 |
| Sign: Brier score | 0.108 | 0.192 | — | — |
| Sign: hit rate | 85% | 72% | — | — |

| Daily products and prices, P50 error in €/MWh | Fundamentals model | Yesterday's value | Climatology |
| --- | --- | --- | --- |
| Base spread (sign right on 90% of days) | 11.8 | 17.8 | 21.7 |
| Peak spread (sign right on 89% of days) | 14.3 | 23.5 | 24.2 |
| DE price, hourly (mean price 120) | 19.7 | 31.9 | — |
| FR price, hourly (mean price 93) | 21.4 | 27.9 | — |

Coverage of the 80% band: 71% of hours raw; 77% of hours, 79% of daily base and 77% of daily peak outcomes with the calibration a
live forecast would have had at each date (factors from earlier days only). The bands are still a little narrow.

### Both models on the same days

Weekly walk-forward of both models, 19 October to 20 November 2026 (33 days, 791 hours), which includes the mid-November blow-out:

| | Climatology | Grid only | Fundamentals |
| --- | --- | --- | --- |
| Pinball loss | 13.44 | 11.82 | 9.48 |
| P50 absolute error, €/MWh | 34.2 | 32.0 | 27.0 |
| 80% band coverage | 65% | 63% | 76% |
| Sign: Brier score | 0.246 | 0.162 | 0.130 |
| Daily base, P50 error, €/MWh | — | 29.4 | 22.2 |

| Base spread, €/MWh | Actual | Grid only, P50 | Fundamentals, P50 (band) |
| --- | --- | --- | --- |
| 17 Nov | +147.0 | +6.6 | +43.2 (−2.6 to +79.1) |
| 18 Nov | +82.0 | +3.5 | +25.9 (−4.5 to +64.3) |
| 19 Nov | +164.5 | +8.7 | +82.2 (+16.1 to +111.1) |
| 20 Nov | +91.0 | +12.7 | +100.7 (+27.3 to +138.5) |

The fundamentals model had the direction and adapted within two days, but it did not call the size of the move on the 17th,
and three of the four outcomes fell outside its band. That is the honest state of it: a third better than climatology over a
year, and still surprised by a regime it had not seen.

## The live record

Version 1 (grid model only) issued the forecasts from 4 November 2026. Version 2 adds the fundamentals model from the first
forecast after the retrain that introduced it; each file states its version. `SCORECARD.md` reports the spread forecast by
model of record, both models on the same days, the price forecasts against yesterday's price, and how many counted forecasts
were issued before gate closure.

## The book: calls priced against the market

A scorecard shows whether a forecast has skill; `BOOK.md` shows what a view was worth. A call is a paper position with a size,
entered at a published market price and written to `book/calls/` by a GitHub Actions run, so it carries GitHub's signature
and timestamp and an OpenTimestamps proof. It is never edited: a forward is marked at later settlement prices and closed by a
second file; left open, it settles against the average day-ahead price of its delivery period. A long-term transmission right
bought at a JAO auction is entered at the clearing price and valued hour by hour at max(sink price − source price, 0) from
public day-ahead prices, with nothing typed in after the entry. Every call states its reasoning when it is opened, and the
report shows winners and losers alike. Calls are opened with the `call (open)` workflow and marked or closed with
`call (mark or close)`.

## Running it

```
pip install -r requirements.txt
python -m fbcast.train                      # grid model from 1 Sep 2026; fundamentals model from June 2022 with a 12-month walk-forward
python -m fbcast.forecast --wait-minutes 45 # issues tomorrow's forecast once the domain is on JAO
python -m fbcast.score                      # scores every issued forecast whose results are published
python -m fbcast.report                     # rewrites SCORECARD.md
```

The first training run downloads about 4,000 two-day windows from JAO (ten minutes or so) and five years of prices; they are
cached under `data/`, and the `retrain` workflow keeps that cache between its weekly runs. Cron times are UTC.

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

* JAO Core publication tool, public API, no key: `finalComputation` (presolved CNECs), `maxNetPos`, `maxExchanges`, `d2CF`,
  `refprog`, `shadowPrices`, `netPos`.
* Day-ahead prices DE-LU and FR: SMARD (Bundesnetzagentur) via the energy-charts.info API, CC BY 4.0.
* Cached under `data/` (not committed).

## Next steps

* An evening forecast on D-2: the congestion forecast and reference programmes are on JAO about 16 hours before gate closure.
* DE–NL and FR–BE spreads from the same inputs, and binding probabilities for the constraints that set them
  (Gronau–Hengelo, Ensdorf–Vigy, Pleinting–St. Peter).
* A weather-model input for German wind and solar, to see the onset of a scarcity day that the TSOs' D-2 view understates.
