"""Econometric tools written out from their textbook formulas (numpy/scipy only),
so every number can be traced to a line of code and explained at the defence.

References for the formulas:
  Driscoll & Kraay (1998) standard errors; Newey & West (1987) Bartlett kernel.
  Dickey & Fuller (1979) ADF; Kwiatkowski, Phillips, Schmidt & Shin (1992) KPSS.
  Maddala & Wu (1999) Fisher panel unit-root test; Pesaran (2004) CD test.
  Engle & Granger (1987); Breusch & Pagan (1979); Jarque & Bera (1980);
  Diebold & Mariano (1995).
P-values for ADF, KPSS and Engle-Granger come from Monte Carlo simulation
under the null with a fixed seed, so they are exact for the sample size used.
"""
import numpy as np
from scipy import stats

_SIM_CACHE = {}


# ------------------------------------------------------------- panel OLS
def within(X, y, groups):
    """Fixed-effects (within) transformation: subtract each region's mean."""
    Xd, yd = X.copy(), y.copy()
    for g in np.unique(groups):
        i = groups == g
        Xd[i] -= X[i].mean(axis=0)
        yd[i] -= y[i].mean()
    return Xd, yd


def nw_lags(T):
    return int(np.floor(4 * (T / 100.0) ** (2.0 / 9.0)))


def driscoll_kraay(Xd, e, times, lags=None):
    """Driscoll-Kraay covariance: Newey-West applied to the cross-sectional
    sums of the scores, robust to heteroskedasticity, autocorrelation and
    correlation across regions."""
    ut = np.unique(times)
    H = np.array([(Xd[times == t] * e[times == t, None]).sum(axis=0) for t in ut])
    T = len(ut)
    L = nw_lags(T) if lags is None else lags
    S = H.T @ H
    for l in range(1, L + 1):
        w = 1 - l / (L + 1)
        G = H[l:].T @ H[:-l]
        S += w * (G + G.T)
    XtX_inv = np.linalg.inv(Xd.T @ Xd)
    n, k = Xd.shape
    adj = (n - 1) / (n - k)
    return adj * XtX_inv @ S @ XtX_inv, T


def panel_fe(X, y, groups, times, names):
    """FE regression with Driscoll-Kraay SEs. Returns a dict."""
    Xd, yd = within(X, y, groups)
    beta, *_ = np.linalg.lstsq(Xd, yd, rcond=None)
    e = yd - Xd @ beta
    V, T = driscoll_kraay(Xd, e, times)
    se = np.sqrt(np.diag(V))
    tval = beta / se
    df = T - 1
    p = 2 * stats.t.sf(np.abs(tval), df)
    alphas = {g: float(y[groups == g].mean() - X[groups == g].mean(axis=0) @ beta) for g in np.unique(groups)}
    n, k = Xd.shape
    ng = len(alphas)
    sigma2 = float(e @ e / (n - k - ng))
    r2_within = 1 - (e @ e) / (yd @ yd)
    return {"names": list(names), "beta": beta, "se": se, "t": tval, "p": p, "cov": V,
            "alpha": alphas, "resid": e, "Xd": Xd, "sigma2": sigma2, "n": n, "T": T,
            "df": df, "r2_within": float(r2_within), "n_groups": ng}


def wald(beta, V, R, df=None):
    """Wald test of R beta = 0; F version with df denominator if given."""
    Rb = R @ beta
    W = float(Rb @ np.linalg.inv(R @ V @ R.T) @ Rb)
    q = R.shape[0]
    if df:
        return W / q, float(stats.f.sf(W / q, q, df))
    return W, float(stats.chi2.sf(W, q))


# ------------------------------------------------------------ unit roots
def _ols(X, y):
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    return b, e


def adf_stat(z, p):
    """t-statistic on gamma in dz_t = c + gamma z_{t-1} + sum d_j dz_{t-j} + e."""
    z = np.asarray(z, float)
    dz = np.diff(z)
    n = len(dz) - p
    Y = dz[p:]
    cols = [np.ones(n), z[p:-1]] + [dz[p - j:-j] for j in range(1, p + 1)]
    X = np.column_stack(cols)
    b, e = _ols(X, Y)
    s2 = e @ e / (n - X.shape[1])
    se = np.sqrt(s2 * np.linalg.inv(X.T @ X)[1, 1])
    return b[1] / se, n, e, X.shape[1]


def adf(z, maxlag=4, rng=None, reps=2000):
    """ADF with constant; lag chosen by AIC on a common sample."""
    z = np.asarray(z, float)
    z = z[~np.isnan(z)]
    if len(z) < 20:
        return None
    best = None
    for p in range(0, maxlag + 1):
        dz = np.diff(z)[maxlag - p:]
        zz = z[maxlag - p:]
        t, n, e, k = adf_stat(zz, p)
        aic = n * np.log(e @ e / n) + 2 * k
        if best is None or aic < best[0]:
            best = (aic, p)
    p = best[1]
    t, n, _, _ = adf_stat(z, p)
    sims = _sim("adf", n, reps, rng)
    return {"stat": float(t), "lags": p, "n": int(n), "pvalue": float((sims <= t).mean()),
            "cv5": float(np.quantile(sims, 0.05))}


def kpss_stat(z, lags=None):
    z = np.asarray(z, float)
    n = len(z)
    e = z - z.mean()
    S = np.cumsum(e)
    L = int(np.floor(12 * (n / 100) ** 0.25)) if lags is None else lags
    s2 = e @ e / n
    for l in range(1, L + 1):
        s2 += 2 * (1 - l / (L + 1)) * (e[l:] @ e[:-l]) / n
    return (S @ S) / (n ** 2 * s2), L


def kpss(z, rng=None, reps=2000):
    """KPSS level-stationarity test (null: stationary)."""
    z = np.asarray(z, float)
    z = z[~np.isnan(z)]
    if len(z) < 20:
        return None
    eta, L = kpss_stat(z)
    sims = _sim("kpss", len(z), reps, rng)
    return {"stat": float(eta), "lags": L, "n": len(z), "pvalue": float((sims >= eta).mean()),
            "cv5": float(np.quantile(sims, 0.95))}


def engle_granger(y, x, rng=None, reps=2000):
    """Residual-based cointegration test of y on x (null: no cointegration)."""
    ok = ~(np.isnan(y) | np.isnan(x))
    y, x = y[ok], x[ok]
    if len(y) < 20:
        return None
    X = np.column_stack([np.ones(len(x)), x])
    _, e = _ols(X, y)
    t, n, _, _ = adf_stat(e, 1)
    sims = _sim("eg", len(y), reps, rng)
    return {"stat": float(t), "n": len(y), "pvalue": float((sims <= t).mean()),
            "cv5": float(np.quantile(sims, 0.05))}


def _sim(kind, n, reps, rng):
    key = (kind, n, reps)
    if key in _SIM_CACHE:
        return _SIM_CACHE[key]
    rng = rng or np.random.default_rng(20261018)
    out = np.empty(reps)
    for r in range(reps):
        if kind == "adf":
            z = np.cumsum(rng.standard_normal(n + 1))
            out[r] = adf_stat(z, 0)[0]
        elif kind == "kpss":
            out[r] = kpss_stat(rng.standard_normal(n))[0]
        elif kind == "eg":
            a, b = np.cumsum(rng.standard_normal(n)), np.cumsum(rng.standard_normal(n))
            X = np.column_stack([np.ones(n), b])
            _, e = _ols(X, a)
            out[r] = adf_stat(e, 1)[0]
    _SIM_CACHE[key] = out
    return out


def fisher_panel(pvalues):
    """Maddala-Wu: -2 sum ln p ~ chi2(2N) under the null that every series has a unit root."""
    p = np.clip(np.array([v for v in pvalues if v is not None]), 1e-4, 1)
    stat = -2 * np.log(p).sum()
    return {"stat": float(stat), "df": 2 * len(p), "pvalue": float(stats.chi2.sf(stat, 2 * len(p)))}


# ----------------------------------------------------------- diagnostics
def serial_correlation(res, groups, times, lags=(1, 2, 3, 4)):
    """Panel LM-type test: regress residuals on own lags within region (plus
    the regressors), Wald test that all lag coefficients are zero (DK cov)."""
    e, Xd = res["resid"], res["Xd"]
    rows = []
    idx = {(g, t): i for i, (g, t) in enumerate(zip(groups, times))}
    for i, (g, t) in enumerate(zip(groups, times)):
        lagged = [e[idx[(g, t - l)]] if (g, t - l) in idx else np.nan for l in lags]
        rows.append(lagged)
    E = np.array(rows)
    ok = ~np.isnan(E).any(axis=1)
    Z = np.column_stack([Xd[ok], E[ok]])
    b, ee = _ols(Z, e[ok])
    V, T = driscoll_kraay(Z, ee, times[ok])
    k = Xd.shape[1]
    R = np.zeros((len(lags), Z.shape[1]))
    for j in range(len(lags)):
        R[j, k + j] = 1
    F, p = wald(b, V, R, df=T - 1)
    return {"stat": F, "pvalue": p, "lags": list(lags), "rho1": float(b[k])}


def breusch_pagan(res):
    e2 = res["resid"] ** 2
    Z = np.column_stack([np.ones(len(e2)), res["Xd"]])
    _, u = _ols(Z, e2)
    r2 = 1 - (u @ u) / ((e2 - e2.mean()) @ (e2 - e2.mean()))
    lm = len(e2) * r2
    return {"stat": float(lm), "df": res["Xd"].shape[1], "pvalue": float(stats.chi2.sf(lm, res["Xd"].shape[1]))}


def jarque_bera(res):
    r = stats.jarque_bera(res["resid"])
    e = res["resid"]
    return {"stat": float(r.statistic), "pvalue": float(r.pvalue),
            "skew": float(stats.skew(e)), "kurtosis": float(stats.kurtosis(e, fisher=False))}


def vif(Xd, names):
    out = {}
    for j, nm in enumerate(names):
        others = np.delete(Xd, j, axis=1)
        _, u = _ols(np.column_stack([np.ones(len(Xd)), others]), Xd[:, j])
        r2 = 1 - (u @ u) / ((Xd[:, j] - Xd[:, j].mean()) @ (Xd[:, j] - Xd[:, j].mean()))
        out[nm] = float(1 / (1 - r2)) if r2 < 1 else float("inf")
    return out


def chow(X, y, groups, times, names, t_break):
    """Parameter stability: interact every regressor with a post-break dummy;
    F-test (Driscoll-Kraay) that all interactions are zero."""
    post = (times >= t_break).astype(float)
    if post.sum() < X.shape[1] * 3 or (1 - post).sum() < X.shape[1] * 3:
        return None
    Xb = np.column_stack([X, X * post[:, None], post])
    r = panel_fe(Xb, y, groups, times, list(names) + [f"{n}_post" for n in names] + ["post"])
    k = X.shape[1]
    R = np.zeros((k + 1, Xb.shape[1]))
    for j in range(k + 1):
        R[j, k + j] = 1
    F, p = wald(r["beta"], r["cov"], R, df=r["df"])
    return {"stat": F, "pvalue": p}


def pesaran_cd(resid, groups, times):
    """Pesaran (2004) CD test for cross-sectional dependence in residuals."""
    gs = np.unique(groups)
    series = {g: dict(zip(times[groups == g], resid[groups == g])) for g in gs}
    rhos, Ts = [], []
    for a in range(len(gs)):
        for b in range(a + 1, len(gs)):
            common = sorted(set(series[gs[a]]) & set(series[gs[b]]))
            if len(common) < 8:
                continue
            u = np.array([series[gs[a]][t] for t in common])
            v = np.array([series[gs[b]][t] for t in common])
            rhos.append(np.corrcoef(u, v)[0, 1])
            Ts.append(len(common))
    N = len(gs)
    cd = np.sqrt(2 / (N * (N - 1))) * np.sum(np.sqrt(Ts) * np.array(rhos))
    return {"stat": float(cd), "pvalue": float(2 * stats.norm.sf(abs(cd))), "mean_rho": float(np.mean(rhos))}


def diebold_mariano(e_model, e_bench, times):
    """DM test on squared-error loss, averaged across regions per quarter
    (one-step-ahead, so no HAC lags needed beyond 0)."""
    ut = np.unique(times)
    d = np.array([np.mean(e_model[times == t] ** 2 - e_bench[times == t] ** 2) for t in ut])
    if len(d) < 3:
        return None
    stat = d.mean() / np.sqrt(d.var(ddof=1) / len(d))
    return {"stat": float(stat), "pvalue": float(2 * stats.t.sf(abs(stat), len(d) - 1)), "n_quarters": len(d)}
