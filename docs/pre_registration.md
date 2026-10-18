# Pre-registration memo — regional quarterly birth rate, Kazakhstan

Written 18 October 2026, before any data were loaded or any regression run. Binding. Later changes are listed in the "Deviations" part of Section 3 of the note: what changed, why, and what the pre-registered specification produced.

**Dependent variable.** y(i,t) = ln CBR(i,t) − ln CBR(i,t−4). CBR = 4 × 1,000 × births / average population, for 16 harmonised regions, quarterly.

**Mechanism and factors.** Births follow conception by about 3 quarters, so every driver enters with a lag of at least 3 quarters.

| Factor | Transformation | Lag | Sign | Channel |
| --- | --- | --- | --- | --- |
| Marriage rate (per 1,000) | yoy log change | 3 | + | Most first births are within marriage; more marriages mean more conceptions within a year |
| Real average wage | yoy log change of nominal wage − yoy log change of regional CPI | 4 | + | Income effect; finances are the most-cited barrier to more children (Kassimova et al., 2026) |
| Unemployment rate | yoy change, pp | 4 | − | Job insecurity makes couples postpone births (Adserà, 2004; García-Pereiro et al., 2024) |
| Housing commissioned per 1,000 | yoy log change | 4 | + | Eases the housing constraint (Kassimova et al., 2026); price channel per Dettling & Kearney (2014) |

Plus the dependent variable lagged 1 and 4 quarters.

**Specification.** Panel ARDL with region fixed effects (OLS), Driscoll–Kraay standard errors (Bartlett kernel, floor(4(T/100)^(2/9)) lags). The model is estimated in year-on-year changes, so no levels regression is run.

**Integration tests.** ADF (constant, AIC lag ≤ 4) and KPSS (level null) per region, on ln CBR and every regressor. Maddala–Wu Fisher combination of the ADF p-values. Monte Carlo p-values with seed 20261018. Chow tests at 2015Q3, 2020Q2 and 2022Q3. Engle–Granger test of ln CBR on ln marriage rate, for information only.

**Falsification.**
1. Hold-out RMSE ratio (model/benchmark) ≥ 1.00 → the model has no forecasting value.
2. The marriage coefficient is not > 0 at 5% (one-sided) → the core mechanism is rejected.

**Benchmark.** Seasonal random walk: CBR(i,t+1) = CBR(i,t−3).

**Out of sample.** Estimate once on the first 80% of quarters. Forecast each of the last 20% of quarters one step ahead. Report RMSE and MAE in births per 1,000, the ratio, and a Diebold–Mariano test.

**Robustness.**
1. Drop 2020Q2–2021Q4.
2. No lagged dependent variable.
3. Births count instead of the rate.
