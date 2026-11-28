# Scorecard: German and French day-ahead prices, base and peak

Forecasts of the German (DE-LU) and French day-ahead base and peak prices and of the DE−FR spread, issued every morning before the 12:00 CET auction and scored the next day against the prices that cleared. Base is all hours of the day; peak is Monday to Friday, 08:00 to 20:00 CET.

Last scoring run: 2026-11-28 00:40 UTC.

## Forecast for Saturday 28 November 2026

Issued 27 Nov at 10:24 CET, before the auction closed. €/MWh: the P50, with the P10 to P90 band in brackets.

| | Base | Peak |
| --- | --- | --- |
| DE | 230 (206 to 274) | – |
| FR | 236 (210 to 272) | – |
| DE−FR | −3 (−21 to −1) | – |

There is no peak product on a Saturday.

## Record since Wednesday 25 November 2026: 3 days counted

| | Days | Error, €/MWh | Error of yesterday's price | In band |
| --- | --- | --- | --- | --- |
| DE base | 3 | 21.9 | 55.2 | 2 of 3 |
| DE peak | 2 | 29.9 | 39.1 | 2 of 2 |
| FR base | 3 | 28.5 | 47.2 | 2 of 3 |
| FR peak | 2 | 41.3 | 29.2 | 2 of 2 |
| DE−FR base | 3 | 4.2 | 8.0 | 3 of 3 |
| DE−FR peak | 2 | 7.7 | 14.8 | 1 of 2 |

Error is the average absolute difference between the P50 and the price that cleared. The benchmark is the same error for a forecast that repeats the product's last delivered price: yesterday's for base, the previous weekday's for peak. In band counts the days on which the outcome fell inside the P10 to P90 band, which should be about four in five.

A forecast counts only if it was issued before the results were published; 3 of the 3 were issued before the auction closed. Not counted, because issued late: Wed 25 Nov.

## Day by day: forecast → price that cleared, €/MWh

| Day | DE base | DE peak | FR base | FR peak | DE−FR base | DE−FR peak |
| --- | --- | --- | --- | --- | --- | --- |
| Sat 28 Nov | 230 → 192 * | – | 236 → 201 * | – | −3 → −9 | – |
| Fri 27 Nov | 302 → 302 | 341 → 348 | 286 → 299 | 323 → 346 | +7 → +3 | +11 → +2 |
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
