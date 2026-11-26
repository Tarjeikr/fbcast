# Scorecard: German and French day-ahead prices, base and peak

Forecasts of the German (DE-LU) and French day-ahead base and peak prices and of the DE−FR spread, issued every morning before the 12:00 CET auction and scored the next day against the prices that cleared. Base is all hours of the day; peak is Monday to Friday, 08:00 to 20:00 CET.

Last scoring run: 2026-11-26 01:06 UTC.

## Forecast for Thursday 26 November 2026

Issued 25 Nov at 10:58 CET, before the auction closed. €/MWh: the P50, with the P10 to P90 band in brackets.

| | Base | Peak |
| --- | --- | --- |
| DE | 264 (244 to 321) | 290 (264 to 390) |
| FR | 252 (232 to 296) | 276 (249 to 354) |
| DE−FR | −0 (−8 to +2) | +0 (−8 to +4) |

## Record since Wednesday 25 November 2026: 1 day counted

| | Days | Error, €/MWh | Error of yesterday's price | In band |
| --- | --- | --- | --- | --- |
| DE base | 1 | 27.4 | 45.5 | 1 of 1 |
| DE peak | 1 | 53.5 | 74.1 | 1 of 1 |
| FR base | 1 | 37.8 | 34.3 | 1 of 1 |
| FR peak | 1 | 60.3 | 49.4 | 1 of 1 |
| DE−FR base | 1 | 2.4 | 11.2 | 1 of 1 |
| DE−FR peak | 1 | 6.3 | 24.7 | 0 of 1 |

Error is the average absolute difference between the P50 and the price that cleared. The benchmark is the same error for a forecast that repeats the product's last delivered price: yesterday's for base, the previous weekday's for peak. In band counts the days on which the outcome fell inside the P10 to P90 band, which should be about four in five.

A forecast counts only if it was issued before the results were published; 1 of the 1 were issued before the auction closed. Not counted, because issued late: Wed 25 Nov.

## Day by day: forecast → price that cleared, €/MWh

| Day | DE base | DE peak | FR base | FR peak | DE−FR base | DE−FR peak |
| --- | --- | --- | --- | --- | --- | --- |
| Thu 26 Nov | 264 → 292 | 290 → 343 | 252 → 289 | 276 → 337 | −0 → +2 | +0 → +7 * |

\* The price cleared outside the P10 to P90 band.

## Backtest of the model

The live record above is the test that counts. This is what to expect from it: a walk-forward backtest from Sat 1 Nov 2025 to Fri 20 Nov 2026, refitted every month, in which every forecast comes from a model that had seen nothing from its own month.

| | Days | Average price | Error, €/MWh | Error of yesterday's price | In band |
| --- | --- | --- | --- | --- | --- |
| DE base | 385 | 118 | 12.9 | 26.5 | 80% |
| DE peak | 275 | 119 | 18.4 | 32.9 | 79% |
| FR base | 385 | 92 | 14.7 | 21.7 | 78% |
| FR peak | 275 | 90 | 19.4 | 26.7 | 76% |
| DE−FR base | 385 | +26 | 12.0 | 17.7 | 79% |
| DE−FR peak | 275 | +29 | 16.2 | 26.4 | 77% |

## Where things are

How the forecast is made: `README.md`. Each forecast as issued, hour by hour: `forecasts/`. Each day's score: `scorecard/`. Forecasts issued before Wed 25 Nov 2026 came from the first, grid-only version of this project; they remain in the same folders and are not part of this record.
