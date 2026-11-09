# Scorecard: Core binding-constraint forecast

Last scoring run: 2026-11-09 10:43 UTC. All published days scored.

Forecasts are issued each morning for the next CET day from the published JAO domain, before the day-ahead auction closes; only forecasts whose issue time precedes the publication of the results count (status `ex-ante`). Metrics compare each forecast with the hour-of-day climatology of the training window.

| Window | Hours | Days | Bind Brier | Bind Brier, climatology | Bind hit | Bind hit, climatology | Sign Brier | Sign Brier, climatology | Sign hit | Sign hit, climatology |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| All ex-ante forecasts | 72 | 3 | 0.111 | 0.121 | 86% | 90% | 0.151 | 0.145 | 75% | 83% |
| Last 14 days | 72 | 3 | 0.111 | 0.121 | 86% | 90% | 0.151 | 0.145 | 75% | 83% |
| Afternoon hours 13–19 CET | 21 | 3 | 0.191 | 0.225 | 71% | 67% | 0.166 | 0.214 | 71% | 67% |

## By day: afternoon block 15–17 CET and binding hours

| Day | P(DE > FR), 15–17 | Spread P50 (P10–P90), 15–17, €/MWh | Actual spread 15–17, €/MWh | Binding hours expected | Binding hours actual | French net position, GW (realized, day mean) |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-11-09 | 0.81 | +10 (-0 to +72) | +76.8 | 9.7 | 0 | +2.9 |
| 2026-11-08 | 0.29 | +5 (-2 to +49) | +3.6 | 2.6 | 2 | +0.8 |
| 2026-11-05 | 0.47 | n/a | -5.3 | 5.5 | 0 | -3.6 |

## Spread quantiles (DE−FR, €/MWh)

| Days | Pinball loss | Pinball, climatology | 80% band coverage | Coverage, climatology | P50 MAE | Climatology median MAE | Zero MAE | Persistence D-1 MAE | Band width |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 4.67 | 3.93 | 56% | 90% | 12.4 | 8.7 | 8.1 | 8.3 | 34 |

Pinball loss is averaged over the 10th, 50th and 90th percentiles; lower is better. Coverage is the share of hours whose realized spread fell inside the P10–P90 band (target 80%).

A positive French net position means France exported into Core; Creys–St-Vulbas is France's export path and cannot bind on days when France imports.

Afternoon-block sign hit rate: 67% over 3 days; share of days with a positive afternoon spread: 67%.

## Reliability of P(bind)

| Forecast bin | Hours | Mean forecast | Observed frequency |
| --- | --- | --- | --- |
| (0.0, 0.2] | 37 | 0.07 | 0.00 |
| (0.2, 0.4] | 19 | 0.29 | 0.00 |
| (0.4, 0.6] | 8 | 0.48 | 0.25 |
| (0.6, 0.8] | 6 | 0.70 | 0.00 |
| (0.8, 1.0] | 2 | 0.82 | 0.00 |

## Model and backtest

Logistic models on the D-1 published Core domain (Creys–St-Vulbas RAM, loading and minRAM top-up, French max net positions) plus hour-of-day climatology; trained on 2026-09-02 to 2026-11-05 (1558 hour-rows). Held-out backtest 2026-10-19 to 2026-11-05: binding AUC 0.82, Brier 0.156 vs 0.200 climatology; sign AUC 0.87, Brier 0.140 vs 0.215; spread quantiles pinball 6.92 vs 7.88 climatology, P50 MAE 19.2 vs 21.2 for a zero forecast.
