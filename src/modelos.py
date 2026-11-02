"""Modelos econométricos: modelo de Solow adaptado (Paredes-Soria et al., 2025) y extensiones robustas."""
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm
from statsmodels.stats.diagnostic import het_arch
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tsa.api import VAR
from statsmodels.tsa.ardl import UECM, ardl_select_order
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.vector_ar.vecm import VECM

TRIMESTRES_COVID = ["2020Q2", "2020Q3", "2020Q4"]
NOMBRES = {"ly": "PBI", "lipri": "I privada", "lipub": "I pública", "ll": "PEA ocupada",
           "lkpri": "K privado", "lkpub": "K público"}


def dummies_covid(indice):
    d = pd.DataFrame(0.0, index=indice, columns=[f"d{q}" for q in TRIMESTRES_COVID])
    for q in TRIMESTRES_COVID:
        if pd.Period(q, freq="Q") in indice:
            d.loc[pd.Period(q, freq="Q"), f"d{q}"] = 1.0
    return d.loc[:, d.sum() > 0]


def _nombre(c):
    return NOMBRES.get(c.replace("_sa", ""), c)


# ---------------------------------------------------------------- 1. Réplica MCO del paper
def mco_replica(L, x=("lipri_sa", "lipub_sa", "ll_sa"), y="ly_sa"):
    """Regresión log-log del paper (Tabla 3), con errores HAC de Newey-West y VIF."""
    X = sm.add_constant(L[list(x)])
    m = sm.OLS(L[y], X).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
    vif = pd.Series([variance_inflation_factor(X.values, i) for i in range(1, X.shape[1])],
                    index=[_nombre(c) for c in x], name="VIF")
    return m, vif


# ---------------------------------------------------------------- 2. MCO dinámicos (Stock-Watson)
def dols(L, x, y="ly_sa", adelantos=2, rezagos=2, tendencia=False, dummies=None):
    d = pd.DataFrame({"y": L[y]})
    for c in x:
        d[c] = L[c]
        dx = L[c].diff()
        for j in range(-adelantos, rezagos + 1):
            d[f"d_{c}_{j}"] = dx.shift(j)
    if tendencia:
        d["tendencia"] = np.arange(len(d))
    if dummies is not None:
        d = d.join(dummies)
    d = d.dropna()
    m = sm.OLS(d["y"], sm.add_constant(d.drop(columns="y"))).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
    return m


def prueba_rendimientos_constantes(modelo, x):
    """Wald H0: la suma de elasticidades es igual a 1 (rendimientos constantes a escala)."""
    r = " + ".join(x) + " = 1"
    w = modelo.wald_test(r, scalar=True)
    return float(sum(modelo.params[c] for c in x)), float(w.statistic), float(w.pvalue)


# ---------------------------------------------------------------- 3. ARDL y prueba de límites
def ardl_limites(L, x, y="ly_sa", dummies=None, max_rezago=4):
    """ARDL con selección por AIC, forma de corrección de errores (UECM) y prueba de límites de
    Pesaran, Shin y Smith (2001), caso 3: constante no restringida, sin tendencia."""
    endog, exog = L[y], L[list(x)]
    sel = ardl_select_order(endog, max_rezago, exog, max_rezago, trend="c", fixed=dummies, ic="aic")
    orden_ar = max(sel.model.ardl_order[0], 1)
    orden_x = {c: max(o, 1) for c, o in zip(x, sel.model.ardl_order[1:])}
    uecm = UECM(endog, orden_ar, exog, orden_x, trend="c", fixed=dummies).fit(cov_type="HAC",
                                                                              cov_kwds={"maxlags": 4})
    limites = uecm.bounds_test(case=3)
    elas = ardl_largo_plazo_se(uecm, x, y)
    ecm = uecm.params[f"{y}.L1"]
    return uecm, limites, elas, ecm, (orden_ar, orden_x)


def ardl_largo_plazo_se(uecm, x, y="ly_sa"):
    """Errores estándar de las elasticidades de largo plazo por el método delta."""
    p, V = uecm.params, uecm.cov_params()
    phi = p[f"{y}.L1"]
    filas = []
    for c in x:
        b = p[f"{c}.L1"]
        theta = -b / phi
        g = np.zeros(len(p))
        g[p.index.get_loc(f"{c}.L1")] = -1 / phi
        g[p.index.get_loc(f"{y}.L1")] = b / phi ** 2
        se = float(np.sqrt(g @ V.values @ g))
        filas.append({"variable": _nombre(c), "elasticidad": theta, "error_std": se,
                      "z": theta / se, "p_valor": 2 * (1 - norm.cdf(abs(theta / se)))})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- 4. VECM
def vecm(L, cols, k_ar_diff=1, dummies=None, deterministic="co"):
    m = VECM(L[cols], exog=None if dummies is None else dummies.values, k_ar_diff=k_ar_diff,
             coint_rank=1, deterministic=deterministic).fit()
    beta = m.beta[:, 0] / m.beta[0, 0]
    se_beta = m.stderr_beta[:, 0] if m.stderr_beta.shape[0] == len(cols) else np.r_[0, m.stderr_beta[:, 0]]
    lp = pd.DataFrame({"variable": [_nombre(c) for c in cols[1:]],
                       "elasticidad": -beta[1:], "error_std": se_beta[1:]})
    lp["z"] = lp["elasticidad"] / lp["error_std"]
    lp["p_valor"] = 2 * (1 - norm.cdf(lp["z"].abs()))
    ajuste = pd.DataFrame({"ecuación": [f"Δ{_nombre(c)}" for c in cols], "alfa": m.alpha[:, 0],
                           "error_std": m.stderr_alpha[:, 0], "p_valor": m.pvalues_alpha[:, 0]})
    return m, lp, ajuste


def _componente_deterministico(m, datos):
    """y_t - sum A_i y_{t-i} - u_t para la representación VAR en niveles (incluye constante y dummies)."""
    A = m.var_rep
    p = A.shape[0]
    Y = np.asarray(datos)
    det = np.zeros((len(Y) - p, Y.shape[1]))
    for t in range(p, len(Y)):
        det[t - p] = Y[t] - sum(A[i] @ Y[t - 1 - i] for i in range(p))
    return det - np.asarray(m.resid)


def irf_vecm_bootstrap(L, cols, k_ar_diff, dummies, horizonte=20, repeticiones=300, semilla=123,
                       deterministic="co"):
    """IRF ortogonalizadas del VECM en niveles con bandas al 90% por bootstrap de residuos."""
    m, _, _ = vecm(L, cols, k_ar_diff, dummies, deterministic)
    base = m.irf(horizonte).orth_irfs
    Y = L[cols].values
    p = m.var_rep.shape[0]
    det = _componente_deterministico(m, Y)
    u = np.asarray(m.resid)
    u = u - u.mean(axis=0)
    rng = np.random.default_rng(semilla)
    sims = []
    for _ in range(repeticiones):
        us = u[rng.integers(0, len(u), len(u))]
        Ys = Y.copy()
        for t in range(p, len(Y)):
            Ys[t] = sum(m.var_rep[i] @ Ys[t - 1 - i] for i in range(p)) + det[t - p] + us[t - p]
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ms = VECM(Ys, exog=None if dummies is None else dummies.values, k_ar_diff=k_ar_diff,
                          coint_rank=1, deterministic=deterministic).fit()
            sims.append(ms.irf(horizonte).orth_irfs)
        except Exception:
            continue
    sims = np.array(sims)
    return base, np.percentile(sims, 5, axis=0), np.percentile(sims, 95, axis=0)


# ---------------------------------------------------------------- 5. VAR en diferencias (paper)
def var_diferencias(L, cols, dummies=None, rezagos=None, max_rezagos=8):
    D = L[cols].diff().dropna()
    ex = None if dummies is None else dummies.loc[D.index]
    modelo = VAR(D, exog=ex)
    seleccion = modelo.select_order(max_rezagos)
    p = rezagos or max(seleccion.aic, 1)
    res = modelo.fit(p)
    return res, seleccion


def diagnosticos_var(res, rezagos_lm=12):
    blanco = res.test_whiteness(nlags=rezagos_lm, adjusted=True)
    normal = res.test_normality()
    arch = {c: het_arch(res.resid[c], nlags=4)[1] for c in res.resid.columns}
    filas = [{"prueba": f"Portmanteau ajustada ({rezagos_lm} rezagos)", "estadístico": blanco.test_statistic,
              "p_valor": blanco.pvalue},
             {"prueba": "Normalidad Jarque-Bera multivariada", "estadístico": normal.test_statistic,
              "p_valor": normal.pvalue},
             {"prueba": "Raíz máxima del polinomio (estabilidad < 1)",
              "estadístico": float(np.max(np.abs(1 / res.roots))), "p_valor": np.nan}]
    for c, pv in arch.items():
        filas.append({"prueba": f"ARCH-LM(4) Δ{_nombre(c)}", "estadístico": np.nan, "p_valor": pv})
    return pd.DataFrame(filas)


def granger(res, objetivo):
    filas = []
    for c in res.names:
        if c == objetivo:
            continue
        ida = res.test_causality(objetivo, [c], kind="f")
        vuelta = res.test_causality(c, [objetivo], kind="f")
        filas.append({"H0": f"Δ{_nombre(c)} no causa a Δ{_nombre(objetivo)}", "F": ida.test_statistic,
                      "p_valor": ida.pvalue})
        filas.append({"H0": f"Δ{_nombre(objetivo)} no causa a Δ{_nombre(c)}", "F": vuelta.test_statistic,
                      "p_valor": vuelta.pvalue})
    return pd.DataFrame(filas)


def toda_yamamoto(L, cols, p, dmax=1, dummies=None):
    """Causalidad de Toda-Yamamoto (1995): VAR en niveles con p + dmax rezagos y Wald sobre los p primeros.
    Válida con series I(0), I(1) o cointegradas."""
    Y = L[cols]
    k = p + dmax
    lags = pd.concat({f"{c}_L{i}": Y[c].shift(i) for c in cols for i in range(1, k + 1)}, axis=1)
    X = sm.add_constant(lags)
    if dummies is not None:
        X = X.join(dummies)
    filas = []
    for dep in cols:
        d = pd.concat([Y[dep], X], axis=1).dropna()
        m = sm.OLS(d[dep], d.drop(columns=dep)).fit()
        for causa in cols:
            if causa == dep:
                continue
            restr = [f"{causa}_L{i} = 0" for i in range(1, p + 1)]
            w = m.wald_test(", ".join(restr), scalar=True)
            filas.append({"H0": f"{_nombre(causa)} no causa a {_nombre(dep)}", "Chi2": float(w.statistic) * p,
                          "gl": p, "p_valor": float(w.pvalue)})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- 6. Pronóstico y validación
def pronostico_vecm(L, cols, k_ar_diff, dummies, pasos, deterministic="co", alpha=0.05):
    m, _, _ = vecm(L, cols, k_ar_diff, dummies, deterministic)
    ex_fc = None if dummies is None else np.zeros((pasos, dummies.shape[1]))
    media, inf, sup = m.predict(steps=pasos, alpha=alpha, exog_fc=ex_fc)
    idx = pd.period_range(L.index[-1] + 1, periods=pasos, freq="Q")
    return (pd.DataFrame(media, index=idx, columns=cols), pd.DataFrame(inf, index=idx, columns=cols),
            pd.DataFrame(sup, index=idx, columns=cols))


def validacion_fuera_muestra(L, cols, k_ar_diff, corte="2023Q4", deterministic="co"):
    """Pronóstico dinámico desde `corte` y comparación de errores (ln PBI desestacionalizado)."""
    ent = L.loc[:corte]
    prueba = L.loc[pd.Period(corte, freq="Q") + 1:]
    h = len(prueba)
    dum = dummies_covid(ent.index)
    real = prueba[cols[0]]
    pron = {}
    pron["VECM"] = pronostico_vecm(ent, cols, k_ar_diff, dum, h, deterministic)[0][cols[0]].values
    rv, _ = var_diferencias(ent, cols, dum, rezagos=max(k_ar_diff, 1))
    dfc = rv.forecast(ent[cols].diff().dropna().values[-rv.k_ar:], h, exog_future=np.zeros((h, dum.shape[1])))
    pron["VAR en diferencias"] = ent[cols[0]].iloc[-1] + np.cumsum(dfc[:, 0])
    ar = ARIMA(ent[cols[0]].values, order=(1, 1, 0), trend="t", exog=dum.values).fit()
    pron["ARIMA(1,1,0) con deriva"] = ar.forecast(h, exog=np.zeros((h, dum.shape[1])))
    deriva = ent[cols[0]].diff().loc["2010Q1":].mean()
    pron["Paseo aleatorio con deriva"] = ent[cols[0]].iloc[-1] + deriva * np.arange(1, h + 1)
    filas = []
    for n, f in pron.items():
        e = (real.values - f) * 100
        filas.append({"modelo": n, "RMSE (%)": np.sqrt(np.mean(e ** 2)), "MAE (%)": np.mean(np.abs(e))})
    return pd.DataFrame(filas).sort_values("RMSE (%)"), pd.DataFrame(pron, index=prueba.index).assign(real=real)
