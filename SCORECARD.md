# Scorecard: Core binding-constraint forecast

Forecasts are issued each morning for the next CET day from the published JAO domain, before the day-ahead auction closes; only forecasts whose issue time precedes the publication of the results count (status `ex-ante`). Metrics compare each forecast with the hour-of-day climatology of the training window.

| Window | Hours | Days | Bind Brier | Bind Brier, climatology | Bind hit | Bind hit, climatology | Sign Brier | Sign Brier, climatology | Sign hit | Sign hit, climatology |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| All ex-ante forecasts | 24 | 1 | 0.094 | 0.138 | 92% | 83% | 0.104 | 0.123 | 83% | 83% |
| Last 14 days | 24 | 1 | 0.094 | 0.138 | 92% | 83% | 0.104 | 0.123 | 83% | 83% |
| Afternoon hours 13–19 CET | 7 | 1 | 0.200 | 0.269 | 71% | 57% | 0.118 | 0.232 | 86% | 57% |

## Afternoon block 15–17 CET, by day

| Day | P(DE > FR) | Actual spread, €/MWh | Forecast spread, €/MWh | Binding hours expected | Binding hours actual |
| --- | --- | --- | --- | --- | --- |
| 2026-11-05 | 0.47 | -5.3 | +18.4 | 5.5 | 0 |

Afternoon-block sign hit rate: 100% over 1 days; share of days with a positive afternoon spread: 0%.

## Reliability of P(bind)

| Forecast bin | Hours | Mean forecast | Observed frequency |
| --- | --- | --- | --- |
| (0.0, 0.2] | 12 | 0.07 | 0.00 |
| (0.2, 0.4] | 7 | 0.28 | 0.00 |
| (0.4, 0.6] | 3 | 0.42 | 0.00 |
| (0.6, 0.8] | 2 | 0.72 | 0.00 |

## Model and backtest

Logistic models on the D-1 published Core domain (Creys–St-Vulbas RAM, loading and minRAM top-up, French max net positions) plus hour-of-day climatology; trained on 2026-09-02 to 2026-11-03 (1510 hour-rows). Held-out backtest 2026-10-17 to 2026-11-03: binding AUC 0.83, Brier 0.157 vs 0.215 climatology; sign AUC 0.86, Brier 0.144 vs 0.220; spread level MAE 23.5 vs 23.8 for a zero forecast (no level skill claimed).
