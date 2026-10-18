## Section 3 numbers (generated)

Sample: 2016Q1-2026Q2, 16 regions, 34 quarters, 543 region-quarters. Within R2 = 0.400. Specifications run: 4.

| Regressor | Expected sign | Coefficient | Driscoll-Kraay SE | p-value |
| --- | --- | --- | --- | --- |
| Own momentum (lag 1) |  | 0.622 | 0.083 | 0.000 |
| Own momentum (lag 4) |  | -0.135 | 0.089 | 0.140 |
| Marriage rate, last published year (yoy log change), lag 1 | + | 0.096 | 0.052 | 0.077 |
| Real per-capita income, last published year (yoy log change), lag 1 | + | 0.229 | 0.073 | 0.004 |
| Housing per resident, last published year (yoy log change), lag 1 | + | -0.253 | 0.234 | 0.286 |

**Diagnostics (3 lines).**
Serial correlation (lags 1-4) p = 0.001; Breusch-Pagan p = 0.066; Jarque-Bera p = 0.000.
Max VIF = 1.26; Pesaran CD p = 0.000 (mean cross-region residual correlation 0.443).
Chow stability tests - 2018Q2: p = 0.000; 2020Q2: p = 0.000; 2022Q3: p = 0.000.

**Out of sample.**
Hold-out 2024Q4-2026Q2 (7 quarters, 112 forecasts). RMSE model 1.667 vs benchmark 2.042 (ratio 0.816); MAE 1.425 vs 1.782 (ratio 0.800). Winner on RMSE: **model**. Diebold-Mariano p = 0.077.

Falsification rule 1 (beat benchmark): passed. Rule 2 (marriage > 0 at 5%, one-sided): passed.

**Integration.**
- ln_cbr: Fisher-ADF p = 1.000, ADF rejects in 0% and KPSS rejects in 88% of regions -> unit root (both tests agree).
- y: Fisher-ADF p = 0.406, ADF rejects in 0% and KPSS rejects in 0% of regions -> inconclusive (tests disagree).
- m: not tested: annual series repeated over 4 quarters (about 10 values per region, too few for ADF/KPSS).
- w: not tested: annual series repeated over 4 quarters (about 10 values per region, too few for ADF/KPSS).
- h: not tested: annual series repeated over 4 quarters (about 10 values per region, too few for ADF/KPSS).
- Engle-Granger (ln CBR on ln marriage rate), Fisher p = 0.000. Not needed for validity: no levels regression is run.

**Economic size (one-standard-deviation move, births per 1,000 at the sample mean).**
- Own momentum (lag 1): 0.898
- Own momentum (lag 4): -0.173
- Marriage rate, last published year (yoy log change), lag 1: 0.115
- Real per-capita income, last published year (yoy log change), lag 1: 0.239
- Housing per resident, last published year (yoy log change), lag 1: -0.080

## Robustness (Section 4 table)

| Check | Marriage coef | p | RMSE ratio | Winner |
| --- | --- | --- | --- | --- |
| Main specification | 0.096 | 0.077 | 0.816 | model |
| Alt. sample: drop 2020Q2-2021Q4 | 0.092 | 0.217 | 0.861 | model |
| Alt. specification: no lagged dependent variable | 0.015 | 0.886 | 0.898 | model |
| Alt. measure: births count instead of rate | 0.104 | 0.056 | 1.074 | benchmark |

## Deviations from pre-registration

- Sample starts 2014Q1, estimation from 2016Q1 (pre-registered: 2010Q1): Taldau publishes quarterly births by region only from January-March 2014; pre-registered result: not estimable: no quarterly regional births before 2014.
- Marriage rate enters as the last published annual year-on-year change (lag 1 quarter after publication) instead of the quarterly change lagged 3 quarters: Taldau gives registered marriages by region only annually; pre-registered result: not estimable with annual data.
- Real wage replaced by real per-capita money income (annual, deflated by the regional CPI annual average): no quarterly regional wage series was downloaded; per-capita income is the closest regional income measure obtained; pre-registered result: not estimated.
- Housing commissioned replaced by housing per resident (m2, annual): the housing-commissioned series was not obtained; the housing-stock series measures the same space constraint, more slowly; pre-registered result: not estimated.
- Population after January 2024 projected at each region's growth over the previous 12 months: the downloaded population file ends at 1 January 2024; pre-registered result: the pre-registration assumed published population for every quarter.
- Chow break dates 2018Q2 / 2020Q2 / 2022Q3 instead of 2015Q3 / 2020Q2 / 2022Q3: 2015Q3 falls before the first estimation quarter (2016Q1); 2018Q2 is the South Kazakhstan / Shymkent split; pre-registered result: 2015Q3 not testable inside the sample.
- Driver 'Unemployment rate (yoy change, pp)' dropped: series not available in data/raw; pre-registered result: not estimable.

## Headline

Kazakhstan 2026Q2: 14.63 births per 1,000 (annualised).
Forecast 2026Q3: 15.74. Replication tolerance: +/-0.01 per 1,000.
