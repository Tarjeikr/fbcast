# Scorecard: Core binding-constraint forecast

Last scoring run: 2026-11-09 23:04 UTC. All published days scored.

Forecasts are issued each morning for the next CET day from the published JAO domain, before the day-ahead auction closes; only forecasts whose issue time precedes the publication of the results count (status `ex-ante`). Metrics compare each forecast with the hour-of-day climatology of the training window.

| Window | Hours | Days | Bind Brier | Bind Brier, climatology | Bind hit | Bind hit, climatology | Sign Brier | Sign Brier, climatology | Sign hit | Sign hit, climatology |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| All ex-ante forecasts | 96 | 4 | 0.110 | 0.135 | 86% | 84% | 0.167 | 0.205 | 73% | 72% |
| Last 14 days | 96 | 4 | 0.110 | 0.135 | 86% | 84% | 0.167 | 0.205 | 73% | 72% |
| Afternoon hours 13–19 CET | 28 | 4 | 0.160 | 0.216 | 75% | 64% | 0.164 | 0.216 | 71% | 71% |

## By day: afternoon block 15–17 CET and binding hours

| Day | P(DE > FR), 15–17 | Spread P50 (P10–P90), 15–17, €/MWh | Actual spread 15–17, €/MWh | Binding hours expected | Binding hours actual | French net position, GW (realized, day mean) |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-11-10 | 0.68 | +6 (-8 to +62) | +85.0 | 4.8 | 5 | +5.6 |
| 2026-11-09 | 0.81 | +10 (-0 to +72) | +76.8 | 9.7 | 0 | +2.9 |
| 2026-11-08 | 0.29 | +5 (-2 to +49) | +3.6 | 2.6 | 2 | +0.8 |
| 2026-11-05 | 0.47 | n/a | -5.3 | 5.5 | 0 | -3.6 |

## Spread quantiles (DE−FR, €/MWh)

| Days | Pinball loss | Pinball, climatology | 80% band coverage | Coverage, climatology | P50 MAE | Climatology median MAE | Zero MAE | Persistence D-1 MAE | Band width |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | 8.10 | 8.82 | 56% | 72% | 22.9 | 22.4 | 21.8 | 21.1 | 35 |

Pinball loss is averaged over the 10th, 50th and 90th percentiles; lower is better. Coverage is the share of hours whose realized spread fell inside the P10–P90 band (target 80%).

A positive French net position means France exported into Core; Creys–St-Vulbas is France's export path and cannot bind on days when France imports.

Afternoon-block sign hit rate: 75% over 4 days; share of days with a positive afternoon spread: 75%.

## Reliability of P(bind)

| Forecast bin | Hours | Mean forecast | Observed frequency |
| --- | --- | --- | --- |
| (0.0, 0.2] | 51 | 0.06 | 0.02 |
| (0.2, 0.4] | 25 | 0.30 | 0.04 |
| (0.4, 0.6] | 11 | 0.49 | 0.36 |
| (0.6, 0.8] | 7 | 0.69 | 0.14 |
| (0.8, 1.0] | 2 | 0.82 | 0.00 |

## Model and backtest

Logistic models on the D-1 published Core domain (Creys–St-Vulbas RAM, loading and minRAM top-up, French max net positions) plus hour-of-day climatology; trained on 2026-09-01 to 2026-11-08 (1655 hour-rows). Held-out backtest 2026-10-22 to 2026-11-08: binding AUC 0.84, Brier 0.139 vs 0.187 climatology; sign AUC 0.87, Brier 0.132 vs 0.202; spread quantiles pinball 5.84 vs 6.44 climatology, P50 MAE 16.4 vs 16.8 for a zero forecast.
