# Scorecard: Core binding-constraint forecast

Last scoring run: 2026-11-19 21:42 UTC. All published days scored.


## Latest forecast: 2026-11-20

![Latest forecast, hour by hour](scorecard/chart_forecast.png)

| Product | P(spread > 0) | P50 (P10 to P90), €/MWh |
| --- | --- | --- |
| Base (24 h) | 0.66 | +12.7 (+2.0 to +79.0) |
| Peak (08–21) | 0.67 | +14.0 (+2.8 to +86.5) |

| Block | Expected binding hours | P(DE > FR) | Spread P50 (P10 to P90), €/MWh |
| --- | --- | --- | --- |
| night 00–05 | 3.6 | 0.77 | +11 (+1 to +72) |
| morning 06–09 | 3.1 | 0.93 | +16 (+9 to +87) |
| midday 10–14 | 3.3 | 0.84 | +12 (-3 to +85) |
| afternoon 15–17 | 2.8 | 0.96 | +18 (+9 to +108) |
| evening 18–20 | 1.8 | 0.86 | +12 (+2 to +70) |
| late 21–23 | 1.5 | 0.68 | +8 (-3 to +53) |

<details><summary>Hour by hour</summary>

| Hour (CET) | P(bind) | P(DE > FR) | P10 | P50 | P90 |
| --- | --- | --- | --- | --- | --- |
| 00 | 0.65 | 0.81 | -1 | +11 | +70 |
| 01 | 0.25 | 0.49 | -9 | +3 | +46 |
| 02 | 0.32 | 0.58 | -7 | +5 | +54 |
| 03 | 0.77 | 0.91 | +7 | +15 | +85 |
| 04 | 0.80 | 0.91 | +7 | +15 | +88 |
| 05 | 0.82 | 0.91 | +6 | +16 | +90 |
| 06 | 0.78 | 0.94 | +8 | +16 | +88 |
| 07 | 0.82 | 0.96 | +11 | +17 | +92 |
| 08 | 0.78 | 0.94 | +12 | +18 | +87 |
| 09 | 0.71 | 0.89 | +4 | +15 | +80 |
| 10 | 0.81 | 0.93 | +5 | +17 | +93 |
| 11 | 0.41 | 0.70 | -10 | +6 | +69 |
| 12 | 0.77 | 0.90 | -2 | +14 | +89 |
| 13 | 0.81 | 0.91 | +0 | +15 | +96 |
| 14 | 0.46 | 0.74 | -6 | +8 | +76 |
| 15 | 0.94 | 0.96 | +10 | +19 | +109 |
| 16 | 0.95 | 0.97 | +10 | +18 | +110 |
| 17 | 0.92 | 0.96 | +7 | +17 | +106 |
| 18 | 0.78 | 0.95 | +6 | +15 | +88 |
| 19 | 0.56 | 0.84 | +2 | +11 | +65 |
| 20 | 0.49 | 0.79 | -1 | +10 | +56 |
| 21 | 0.62 | 0.86 | -0 | +11 | +68 |
| 22 | 0.47 | 0.68 | -3 | +8 | +51 |
| 23 | 0.39 | 0.50 | -7 | +5 | +41 |

</details>

## Base and peak spread, day by day

Base is the 24-hour average DE−FR day-ahead spread; peak is the average over delivery 08:00–21:00 CET. The forecast is the average of the hourly P10, P50 and P90; P(> 0) is read off that band with a normal approximation.

| Day | Base P50 (P10 to P90) | Base actual | P(base > 0) | Peak P50 (P10 to P90) | Peak actual | P(peak > 0) |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-11-16 | -6.0 (-27.1 to +10.3) | +8.1 | 0.34 | -6.0 (-27.7 to +13.7) | -6.1 | 0.36 |
| 2026-11-11 | +8.1 (+0.1 to +52.6) | +64.4 | 0.65 | +7.5 (-1.5 to +52.2) | +101.0 | 0.64 |

### Base and peak skill (all counted days)

| Product | Days | P50 error, €/MWh | Climatology level error | Yesterday's value error | 80% band coverage | Sign hit | Sign Brier | Sign Brier, climatology |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Base | 2 | 35.2 | 37.4 | 24.9 | 50% | 50% | 0.279 | 0.274 |
| Peak | 2 | 46.8 | 53.6 | 57.0 | 50% | 100% | 0.130 | 0.250 |

Error columns are mean absolute differences between the forecast level and the outcome (lower is better). The climatology level is the hour-of-day climatology aggregated the same way, and yesterday's value is the previous day's realized product. Few days are counted so far, so read these figures as provisional.
Forecasts are issued each morning for the next CET day from the published JAO domain, before the day-ahead auction closes; only forecasts whose issue time precedes the publication of the results count (status `ex-ante`). Metrics compare each forecast with the hour-of-day climatology of the training window.

| Window | Hours | Days | Bind Brier | Bind Brier, climatology | Bind hit | Bind hit, climatology | Sign Brier | Sign Brier, climatology | Sign hit | Sign hit, climatology |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| All ex-ante forecasts | 144 | 6 | 0.163 | 0.209 | 79% | 67% | 0.206 | 0.268 | 69% | 59% |
| Last 14 days | 144 | 6 | 0.163 | 0.209 | 79% | 67% | 0.206 | 0.268 | 69% | 59% |
| Afternoon hours 13–19 CET | 42 | 6 | 0.133 | 0.216 | 79% | 57% | 0.149 | 0.234 | 74% | 64% |

## By day: afternoon block 15–17 CET and binding hours

| Day | P(DE > FR), 15–17 | Spread P50 (P10–P90), 15–17, €/MWh | Actual spread 15–17, €/MWh | Binding hours expected | Binding hours actual | French net position, GW (realized, day mean) |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-11-16 | 0.23 | -3 (-22 to +28) | -6.6 | 3.0 | 11 | +1.4 |
| 2026-11-11 | 0.59 | +7 (-2 to +54) | +104.1 | 11.1 | 15 | +5.8 |
| 2026-11-10 | 0.68 | +6 (-8 to +62) | +85.0 | 4.8 | 5 | +5.6 |
| 2026-11-09 | 0.81 | +10 (-0 to +72) | +76.8 | 9.7 | 0 | +2.9 |
| 2026-11-08 | 0.29 | +5 (-2 to +49) | +3.6 | 2.6 | 2 | +0.8 |
| 2026-11-05 | 0.47 | n/a | -5.3 | 5.5 | 0 | -3.6 |

## Spread quantiles (DE−FR, €/MWh)

| Days | Pinball loss | Pinball, climatology | 80% band coverage | Coverage, climatology | P50 MAE | Climatology median MAE | Zero MAE | Persistence D-1 MAE | Band width |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 10.47 | 11.54 | 50% | 61% | 28.7 | 29.7 | 29.0 | 31.3 | 39 |

Pinball loss is averaged over the 10th, 50th and 90th percentiles; lower is better. Coverage is the share of hours whose realized spread fell inside the P10–P90 band (target 80%).

A positive French net position means France exported into Core; Creys–St-Vulbas is France's export path and cannot bind on days when France imports.

Afternoon-block sign hit rate: 83% over 6 days; share of days with a positive afternoon spread: 67%.

## Reliability of P(bind)

| Forecast bin | Hours | Mean forecast | Observed frequency |
| --- | --- | --- | --- |
| (0.0, 0.2] | 79 | 0.07 | 0.15 |
| (0.2, 0.4] | 30 | 0.30 | 0.13 |
| (0.4, 0.6] | 15 | 0.49 | 0.40 |
| (0.6, 0.8] | 15 | 0.69 | 0.53 |
| (0.8, 1.0] | 5 | 0.88 | 0.60 |

## Model and backtest

Logistic models on the D-1 published Core domain (Creys–St-Vulbas RAM, loading and minRAM top-up, French max net positions) plus hour-of-day climatology; trained on 2026-09-01 to 2026-11-15 (1823 hour-rows). Held-out backtest 2026-10-29 to 2026-11-15: binding AUC 0.88, Brier 0.124 vs 0.178 climatology; sign AUC 0.84, Brier 0.184 vs 0.233; spread quantiles pinball 7.32 vs 7.72 climatology, P50 MAE 20.4 vs 20.5 for a zero forecast.

## Last scored day: 2026-11-16

![Last scored day](scorecard/chart_scored.png)

## Skill through the day (all counted days)

| Block | Hours | Sign skill | Binding skill | Quantile skill | 80% band coverage | Mean realized spread, €/MWh |
| --- | --- | --- | --- | --- | --- | --- |
| night 00–05 | 36 | building up: 6 of 7 days | | | | +13.6 |
| morning 06–09 | 24 | building up: 6 of 7 days | | | | +32.7 |
| midday 10–14 | 30 | building up: 6 of 7 days | | | | +22.0 |
| afternoon 15–17 | 18 | building up: 6 of 7 days | | | | +42.9 |
| evening 18–20 | 18 | building up: 6 of 7 days | | | | +14.7 |
| late 21–23 | 18 | building up: 6 of 7 days | | | | +4.3 |

Skill is 1 minus the model's squared (or pinball) error divided by that of the hour-of-day climatology: positive means better than climatology, zero equal, negative worse. Coverage should be near 80%. A block shows figures once it has 7 counted days.
