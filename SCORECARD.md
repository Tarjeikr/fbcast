# Scorecard: Core binding-constraint forecast

Last scoring run: 2026-11-10 20:31 UTC. All published days scored.


## Latest forecast: 2026-11-11

![Latest forecast, hour by hour](scorecard/chart_forecast.png)

| Product | P(spread > 0) | P50 (P10 to P90), €/MWh |
| --- | --- | --- |
| Base (24 h) | 0.65 | +8.1 (+0.1 to +52.6) |
| Peak (08–21) | 0.64 | +7.5 (-1.5 to +52.2) |

| Block | Expected binding hours | P(DE > FR) | Spread P50 (P10 to P90), €/MWh |
| --- | --- | --- | --- |
| night 00–05 | 4.1 | 0.79 | +12 (+3 to +70) |
| morning 06–09 | 1.9 | 0.69 | +8 (+3 to +48) |
| midday 10–14 | 3.6 | 0.88 | +13 (+3 to +77) |
| afternoon 15–17 | 1.0 | 0.59 | +7 (-2 to +54) |
| evening 18–20 | 0.0 | 0.38 | -0 (-9 to +19) |
| late 21–23 | 0.5 | 0.33 | +2 (-4 to +16) |

<details><summary>Hour by hour</summary>

| Hour (CET) | P(bind) | P(DE > FR) | P10 | P50 | P90 |
| --- | --- | --- | --- | --- | --- |
| 00 | 0.48 | 0.67 | -1 | +8 | +48 |
| 01 | 0.21 | 0.34 | -10 | +0 | +21 |
| 02 | 0.68 | 0.85 | +2 | +12 | +70 |
| 03 | 0.88 | 0.96 | +7 | +16 | +91 |
| 04 | 0.95 | 0.97 | +11 | +18 | +97 |
| 05 | 0.90 | 0.95 | +10 | +18 | +93 |
| 06 | 0.71 | 0.93 | +9 | +14 | +75 |
| 07 | 0.40 | 0.71 | +3 | +6 | +42 |
| 08 | 0.21 | 0.35 | -6 | +1 | +20 |
| 09 | 0.53 | 0.77 | +5 | +10 | +55 |
| 10 | 0.77 | 0.93 | +5 | +14 | +81 |
| 11 | 0.77 | 0.93 | +4 | +15 | +84 |
| 12 | 0.66 | 0.86 | +2 | +12 | +72 |
| 13 | 0.74 | 0.89 | +3 | +14 | +81 |
| 14 | 0.62 | 0.81 | +3 | +11 | +67 |
| 15 | 0.60 | 0.73 | +2 | +10 | +65 |
| 16 | 0.42 | 0.45 | -1 | +6 | +45 |
| 17 | 0.01 | 0.60 | -8 | +5 | +52 |
| 18 | 0.01 | 0.53 | -5 | +2 | +29 |
| 19 | 0.01 | 0.30 | -13 | -2 | +15 |
| 20 | 0.01 | 0.31 | -9 | -0 | +14 |
| 21 | 0.16 | 0.35 | -7 | +0 | +15 |
| 22 | 0.15 | 0.35 | +4 | +4 | +16 |
| 23 | 0.17 | 0.29 | -8 | +0 | +16 |

</details>

## Base and peak spread, day by day

Base is the 24-hour average DE−FR day-ahead spread; peak is the average over delivery 08:00–21:00 CET. The forecast is the average of the hourly P10, P50 and P90; P(> 0) is read off that band with a normal approximation.

| Day | Base P50 (P10 to P90) | Base actual | P(base > 0) | Peak P50 (P10 to P90) | Peak actual | P(peak > 0) |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-11-11 | +8.1 (+0.1 to +52.6) | +64.4 | 0.65 | +7.5 (-1.5 to +52.2) | +101.0 | 0.64 |

### Base and peak skill (all counted days)

| Product | Days | P50 error, €/MWh | Climatology level error | Yesterday's value error | 80% band coverage | Sign hit | Sign Brier | Sign Brier, climatology |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Base | 1 | 56.3 | 65.5 | 17.4 | 0% | 100% | 0.122 | 0.274 |
| Peak | 1 | 93.5 | 101.3 | 47.8 | 0% | 100% | 0.130 | 0.255 |

Error columns are mean absolute differences between the forecast level and the outcome (lower is better). The climatology level is the hour-of-day climatology aggregated the same way, and yesterday's value is the previous day's realized product. Few days are counted so far, so read these figures as provisional.
Forecasts are issued each morning for the next CET day from the published JAO domain, before the day-ahead auction closes; only forecasts whose issue time precedes the publication of the results count (status `ex-ante`). Metrics compare each forecast with the hour-of-day climatology of the training window.

| Window | Hours | Days | Bind Brier | Bind Brier, climatology | Bind hit | Bind hit, climatology | Sign Brier | Sign Brier, climatology | Sign hit | Sign hit, climatology |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| All ex-ante forecasts | 120 | 5 | 0.116 | 0.182 | 85% | 72% | 0.170 | 0.257 | 72% | 61% |
| Last 14 days | 120 | 5 | 0.116 | 0.182 | 85% | 72% | 0.170 | 0.257 | 72% | 61% |
| Afternoon hours 13–19 CET | 35 | 5 | 0.149 | 0.229 | 77% | 57% | 0.168 | 0.239 | 71% | 63% |

## By day: afternoon block 15–17 CET and binding hours

| Day | P(DE > FR), 15–17 | Spread P50 (P10–P90), 15–17, €/MWh | Actual spread 15–17, €/MWh | Binding hours expected | Binding hours actual | French net position, GW (realized, day mean) |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-11-11 | 0.59 | +7 (-2 to +54) | +104.1 | 11.1 | 15 | +5.8 |
| 2026-11-10 | 0.68 | +6 (-8 to +62) | +85.0 | 4.8 | 5 | +5.6 |
| 2026-11-09 | 0.81 | +10 (-0 to +72) | +76.8 | 9.7 | 0 | +2.9 |
| 2026-11-08 | 0.29 | +5 (-2 to +49) | +3.6 | 2.6 | 2 | +0.8 |
| 2026-11-05 | 0.47 | n/a | -5.3 | 5.5 | 0 | -3.6 |

## Spread quantiles (DE−FR, €/MWh)

| Days | Pinball loss | Pinball, climatology | 80% band coverage | Coverage, climatology | P50 MAE | Climatology median MAE | Zero MAE | Persistence D-1 MAE | Band width |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | 11.34 | 12.67 | 50% | 60% | 31.7 | 33.1 | 32.5 | 27.0 | 39 |

Pinball loss is averaged over the 10th, 50th and 90th percentiles; lower is better. Coverage is the share of hours whose realized spread fell inside the P10–P90 band (target 80%).

A positive French net position means France exported into Core; Creys–St-Vulbas is France's export path and cannot bind on days when France imports.

Afternoon-block sign hit rate: 80% over 5 days; share of days with a positive afternoon spread: 80%.

## Reliability of P(bind)

| Forecast bin | Hours | Mean forecast | Observed frequency |
| --- | --- | --- | --- |
| (0.0, 0.2] | 58 | 0.06 | 0.02 |
| (0.2, 0.4] | 28 | 0.30 | 0.14 |
| (0.4, 0.6] | 14 | 0.49 | 0.43 |
| (0.6, 0.8] | 15 | 0.69 | 0.53 |
| (0.8, 1.0] | 5 | 0.88 | 0.60 |

## Model and backtest

Logistic models on the D-1 published Core domain (Creys–St-Vulbas RAM, loading and minRAM top-up, French max net positions) plus hour-of-day climatology; trained on 2026-09-01 to 2026-11-08 (1655 hour-rows). Held-out backtest 2026-10-22 to 2026-11-08: binding AUC 0.84, Brier 0.139 vs 0.187 climatology; sign AUC 0.87, Brier 0.132 vs 0.202; spread quantiles pinball 5.84 vs 6.44 climatology, P50 MAE 16.4 vs 16.8 for a zero forecast.

## Last scored day: 2026-11-11

![Last scored day](scorecard/chart_scored.png)

## Skill through the day (all counted days)

| Block | Hours | Sign skill | Binding skill | Quantile skill | 80% band coverage | Mean realized spread, €/MWh |
| --- | --- | --- | --- | --- | --- | --- |
| night 00–05 | 30 | building up: 5 of 7 days | | | | +8.2 |
| morning 06–09 | 20 | building up: 5 of 7 days | | | | +39.6 |
| midday 10–14 | 25 | building up: 5 of 7 days | | | | +28.2 |
| afternoon 15–17 | 15 | building up: 5 of 7 days | | | | +52.8 |
| evening 18–20 | 15 | building up: 5 of 7 days | | | | +17.9 |
| late 21–23 | 15 | building up: 5 of 7 days | | | | +3.3 |

Skill is 1 minus the model's squared (or pinball) error divided by that of the hour-of-day climatology: positive means better than climatology, zero equal, negative worse. Coverage should be near 80%. A block shows figures once it has 7 counted days.
