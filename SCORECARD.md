# Scorecard: German and French day-ahead prices, base and peak

Forecasts of the German (DE-LU) and French day-ahead base and peak prices and of the DE−FR spread, issued every morning before the 12:00 CET auction and scored the next day against the prices that cleared. Base is all hours of the day; peak is Monday to Friday, 08:00 to 20:00 CET.

Last scoring run: 2026-11-22 20:26 UTC.

## Forecast

The first forecast of this record has not been issued yet.

## Backtest of the model

The live record is the test that counts, once it has started. This is what to expect from it: a walk-forward backtest from Sat 1 Nov 2025 to Fri 20 Nov 2026, refitted every month, in which every forecast comes from a model that had seen nothing from its own month.

| | Days | Average price | Error, €/MWh | Error of yesterday's price | In band |
| --- | --- | --- | --- | --- | --- |
| DE base | 385 | 118 | 12.9 | 26.5 | 80% |
| DE peak | 275 | 119 | 18.4 | 32.9 | 79% |
| FR base | 385 | 92 | 14.7 | 21.7 | 78% |
| FR peak | 275 | 90 | 19.4 | 26.7 | 76% |
| DE−FR base | 385 | +26 | 12.0 | 17.7 | 79% |
| DE−FR peak | 275 | +29 | 16.2 | 26.4 | 77% |

## Where things are

How the forecast is made: `README.md`. Each forecast as issued, hour by hour: `forecasts/`. Each day's score: `scorecard/`. The forecasts already in those folders came from the first, grid-only version of this project and are not part of this record.
