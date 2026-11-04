# Scorecard: Core binding-constraint forecast

Forecasts are issued each morning for the next CET day from the published JAO domain, before the day-ahead auction closes; only forecasts whose issue time precedes the publication of the results count (status `ex-ante`). Metrics compare each forecast with the hour-of-day climatology of the training window.

No ex-ante forecasts scored yet.

## Model and backtest

Logistic models on the D-1 published Core domain (Creys–St-Vulbas RAM, loading and minRAM top-up, French max net positions) plus hour-of-day climatology; trained on 2026-09-02 to 2026-11-03 (1510 hour-rows). Held-out backtest 2026-10-17 to 2026-11-03: binding AUC 0.83, Brier 0.157 vs 0.215 climatology; sign AUC 0.86, Brier 0.144 vs 0.220; spread level MAE 23.5 vs 23.8 for a zero forecast (no level skill claimed).
