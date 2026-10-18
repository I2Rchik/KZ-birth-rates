## Section 3 numbers (generated)

Sample: 2016Q1-2026Q2, 16 regions, 30 quarters, 480 region-quarters. Within R2 = 0.391. Specifications run: 4.

| Regressor | Expected sign | Coefficient | Driscoll-Kraay SE | p-value |
| --- | --- | --- | --- | --- |
| Own momentum (lag 1) |  | 0.639 | 0.086 | 0.000 |
| Own momentum (lag 4) |  | -0.102 | 0.077 | 0.195 |
| Marriage rate (yoy log change), lag 3 | + | -0.041 | 0.015 | 0.012 |
| Real per-capita income (yoy log change), lag 4 | + | 0.116 | 0.068 | 0.098 |
| Housing per resident, last published year (yoy log change), lag 1 | + | -0.114 | 0.246 | 0.648 |

**Diagnostics (3 lines).**
Serial correlation (lags 1-4) p = 0.000; Breusch-Pagan p = 0.004; Jarque-Bera p = 0.000.
Max VIF = 1.31; Pesaran CD p = 0.000 (mean cross-region residual correlation 0.471).
Chow stability tests - 2018Q2: p = 0.000; 2020Q2: p = 0.000; 2022Q3: p = 0.000.

**Out of sample.**
Hold-out 2025Q1-2026Q2 (6 quarters, 96 forecasts). RMSE model 1.672 vs benchmark 2.059 (ratio 0.812); MAE 1.383 vs 1.797 (ratio 0.770). Winner on RMSE: **model**. Diebold-Mariano p = 0.073.

Falsification rule 1 (beat benchmark): passed. Rule 2 (marriage > 0 at 5%, one-sided): FAILED.

**Integration.**
- ln_cbr: Fisher-ADF p = 1.000, ADF rejects in 0% and KPSS rejects in 88% of regions -> unit root (both tests agree).
- y: Fisher-ADF p = 0.406, ADF rejects in 0% and KPSS rejects in 0% of regions -> inconclusive (tests disagree).
- m: Fisher-ADF p = 0.000, ADF rejects in 94% and KPSS rejects in 0% of regions -> stationary (both tests agree).
- w: Fisher-ADF p = 0.000, ADF rejects in 31% and KPSS rejects in 0% of regions -> stationary (both tests agree).
- h: not tested: annual series repeated over 4 quarters (about 10 values per region, too few for ADF/KPSS).
- Engle-Granger (ln CBR on ln marriage rate), Fisher p = 0.827. Not needed for validity: no levels regression is run.

**Economic size (one-standard-deviation move, births per 1,000 at the sample mean).**
- Own momentum (lag 1): 0.938
- Own momentum (lag 4): -0.135
- Marriage rate (yoy log change), lag 3: -0.159
- Real per-capita income (yoy log change), lag 4: 0.157
- Housing per resident, last published year (yoy log change), lag 1: -0.036

## Robustness (Section 4 table)

| Check | Marriage coef | p | RMSE ratio | Winner |
| --- | --- | --- | --- | --- |
| Main specification | -0.041 | 0.012 | 0.812 | model |
| Alt. sample: drop 2020Q2-2021Q4 | -0.036 | 0.204 | 0.846 | model |
| Alt. specification: no lagged dependent variable | -0.031 | 0.355 | 0.977 | model |
| Alt. measure: births count instead of rate | -0.042 | 0.014 | 1.016 | benchmark |

## Deviations from pre-registration

- Sample starts 2014Q1, estimation from 2016Q1 (pre-registered: 2010Q1): Taldau publishes quarterly births and marriages by region only from January-March 2014; pre-registered result: not estimable: no quarterly regional births before 2014.
- Real wage replaced by real per-capita money income (quarterly, deflated by the regional CPI; same lag 4): no quarterly regional wage series was downloaded; per-capita income is the closest quarterly regional income measure obtained; pre-registered result: not estimated.
- Housing commissioned replaced by housing per resident (m2, annual, last published year): the housing-commissioned series was not obtained; the housing-stock series measures the same space constraint, more slowly; pre-registered result: not estimated.
- Population after January 2024 projected at each region's growth over the previous 12 months: the downloaded population file ends at 1 January 2024; pre-registered result: the pre-registration assumed published population for every quarter.
- Chow break dates 2018Q2 / 2020Q2 / 2022Q3 instead of 2015Q3 / 2020Q2 / 2022Q3: 2015Q3 falls before the first estimation quarter (2016Q1); 2018Q2 is the South Kazakhstan / Shymkent split; pre-registered result: 2015Q3 not testable inside the sample.
- Driver 'Unemployment rate (yoy change, pp)' dropped: series not available in data/raw; pre-registered result: not estimable.

## Headline

Kazakhstan 2026Q2: 14.63 births per 1,000 (annualised).
Forecast 2026Q3: 15.85. Replication tolerance: +/-0.01 per 1,000.
