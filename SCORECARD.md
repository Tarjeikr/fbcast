# Scorecard: German and French day-ahead prices, base and peak

Forecasts of the German (DE-LU) and French day-ahead base and peak prices and of the DE−FR spread, issued every morning before the 12:00 CET auction and scored the next day against the prices that cleared. Base is all hours of the day; peak is Monday to Friday, 08:00 to 20:00 CET.

Last scoring run: 2026-11-28 16:23 UTC.

## Forecast for Sunday 29 November 2026

Issued 28 Nov at 10:20 CET, before the auction closed. €/MWh: the P50, with the P10 to P90 band in brackets.

| | Base | Peak |
| --- | --- | --- |
| DE | 198 (181 to 241) | – |
| FR | 200 (173 to 242) | – |
| DE−FR | −6 (−35 to +3) | – |

There is no peak product on a Sunday.

## Record since Wednesday 25 November 2026: 4 days counted

| | Days | Error, €/MWh | Error of yesterday's price | In band |
| --- | --- | --- | --- | --- |
| DE base | 4 | 18.5 | 41.8 | 3 of 4 |
| DE peak | 2 | 29.9 | 39.1 | 2 of 2 |
| FR base | 4 | 22.2 | 36.1 | 3 of 4 |
| FR peak | 2 | 41.3 | 29.2 | 2 of 2 |
| DE−FR base | 4 | 5.0 | 7.0 | 4 of 4 |
| DE−FR peak | 2 | 7.7 | 14.8 | 1 of 2 |

Error is the average absolute difference between the P50 and the price that cleared. The benchmark is the same error for a forecast that repeats the product's last delivered price: yesterday's for base, the previous weekday's for peak. In band counts the days on which the outcome fell inside the P10 to P90 band, which should be about four in five.

A forecast counts only if it was issued before the results were published; 4 of the 4 were issued before the auction closed. Not counted, because issued late: Wed 25 Nov.

## Day by day: forecast → price that cleared, €/MWh

| Day | DE base | DE peak | FR base | FR peak | DE−FR base | DE−FR peak |
| --- | --- | --- | --- | --- | --- | --- |
| Sun 29 Nov | 198 → 190 | – | 200 → 204 | – | −6 → −14 | – |
| Sat 28 Nov | 230 → 192 * | – | 236 → 201 * | – | −3 → −9 | – |
| Fri 27 Nov | 302 → 302 | 341 → 348 | 286 → 299 | 323 → 346 | +7 → +3 | +11 → +2 |
| Thu 26 Nov | 264 → 292 | 290 → 343 | 252 → 289 | 276 → 337 | −0 → +2 | +0 → +7 * |

\* The price cleared outside the P10 to P90 band.

## Backtest of the model

The live record above is the test that counts. This is what to expect from it: a walk-forward backtest from Sat 1 Nov 2025 to Fri 27 Nov 2026, refitted every month, in which every forecast comes from a model that had seen nothing from its own month.

| | Days | Average price | Error, €/MWh | Error of yesterday's price | In band |
| --- | --- | --- | --- | --- | --- |
| DE base | 392 | 120 | 13.2 | 26.5 | 80% |
| DE peak | 280 | 122 | 18.7 | 32.8 | 79% |
| FR base | 392 | 94 | 15.3 | 22.3 | 78% |
| FR peak | 280 | 94 | 20.0 | 26.9 | 75% |
| DE−FR base | 392 | +26 | 12.1 | 18.3 | 79% |
| DE−FR peak | 280 | +29 | 16.0 | 26.5 | 77% |

## Where things are

How the forecast is made: `README.md`. Each forecast as issued, hour by hour: `forecasts/`. Each day's score: `scorecard/`. Forecasts issued before Wed 25 Nov 2026 came from the first, grid-only version of this project; they remain in the same folders and are not part of this record.
