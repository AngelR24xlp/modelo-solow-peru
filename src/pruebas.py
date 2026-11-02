"""Pruebas de raíz unitaria, quiebre estructural y cointegración."""
import warnings

import numpy as np
import pandas as pd
import ruptures as rpt
import statsmodels.api as sm
from arch.unitroot import PhillipsPerron
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.stattools import adfuller, kpss, zivot_andrews
from statsmodels.tsa.vector_ar.vecm import coint_johansen

ETIQUETAS = {"ly": "ln PBI", "lkpri": "ln K privado", "lkpub": "ln K público", "ll": "ln PEA ocupada",
             "lipri": "ln I privada", "lipub": "ln I pública"}


def desestacionalizar(serie, periodo=4):
    """Ajuste estacional STL robusto (la serie debe estar en logaritmos)."""
    res = STL(serie, period=periodo, robust=True).fit()
    return serie - res.seasonal, res.seasonal


def variables_log(df):
    """Logaritmos de las series y su versión desestacionalizada (sufijo _sa)."""
    base = {"ly": "pbi", "lkpri": "k_pri", "lkpub": "k_pub", "ll": "pea", "lipri": "i_pri", "lipub": "i_pub"}
    out = pd.DataFrame({k: np.log(df[v]) for k, v in base.items()}, index=df.index)
    estacional = {}
    for c in list(out.columns):
        out[f"{c}_sa"], estacional[c] = desestacionalizar(out[c])
    return out, pd.DataFrame(estacional)


def _pvalor_kpss(x, reg):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return kpss(x, regression=reg, nlags="auto")[1]


def raiz_unitaria(datos, variables):
    """ADF, Phillips-Perron y KPSS en niveles (con tendencia) y primeras diferencias (con constante),
    y Zivot-Andrews (un quiebre endógeno en intercepto y tendencia) en niveles."""
    filas = []
    for v in variables:
        x = datos[v].dropna()
        dx = x.diff().dropna()
        za = zivot_andrews(x.values, regression="ct", autolag="AIC")
        quiebre = x.index[za[4]] if za[4] < len(x) else None
        filas.append({
            "variable": ETIQUETAS.get(v.replace("_sa", ""), v),
            "ADF nivel (p)": adfuller(x, regression="ct", autolag="AIC")[1],
            "PP nivel (p)": PhillipsPerron(x, trend="ct").pvalue,
            "KPSS nivel (p)": _pvalor_kpss(x, "ct"),
            "ZA nivel (p)": za[1],
            "Quiebre ZA": str(quiebre),
            "ADF dif. (p)": adfuller(dx, regression="c", autolag="AIC")[1],
            "PP dif. (p)": PhillipsPerron(dx, trend="c").pvalue,
            "KPSS dif. (p)": _pvalor_kpss(dx, "c"),
        })
    t = pd.DataFrame(filas)
    t["Orden de integración"] = np.where((t["ADF dif. (p)"] < 0.05) | (t["PP dif. (p)"] < 0.05), "I(1)", "I(2)?")
    t.loc[(t["ADF nivel (p)"] < 0.05) & (t["PP nivel (p)"] < 0.05), "Orden de integración"] = "I(0)"
    return t


def bai_perron(y, X, max_quiebres=5, tamano_min=12):
    """Quiebres múltiples en la regresión y = X b (Bai-Perron vía programación dinámica, selección por BIC)."""
    senal = np.column_stack([y, X])
    algo = rpt.Dynp(model="linear", min_size=tamano_min, jump=1).fit(senal)
    n, k = len(y), X.shape[1]
    resultados = []
    for m in range(0, max_quiebres + 1):
        cortes = algo.predict(n_bkps=m) if m > 0 else [n]
        ssr, ini = 0.0, 0
        for fin in cortes:
            res = sm.OLS(y[ini:fin], X[ini:fin]).fit()
            ssr += res.ssr
            ini = fin
        bic = n * np.log(ssr / n) + (m + 1) * k * np.log(n) + m * np.log(n)
        resultados.append({"quiebres": m, "SSR": ssr, "BIC": bic, "cortes": cortes[:-1]})
    tabla = pd.DataFrame(resultados)
    mejor = tabla.loc[tabla["BIC"].idxmin()]
    return tabla, list(mejor["cortes"])


def johansen(datos, k_ar_diff, det_order=0):
    """Prueba de cointegración de Johansen: traza y máximo valor propio (valores críticos al 5%)."""
    r = coint_johansen(datos, det_order, k_ar_diff)
    filas = []
    for i in range(datos.shape[1]):
        filas.append({"H0: rango ≤": i, "Traza": r.lr1[i], "VC traza 5%": r.cvt[i, 1],
                      "Máx. valor propio": r.lr2[i], "VC máx. 5%": r.cvm[i, 1],
                      "Rechaza (traza)": r.lr1[i] > r.cvt[i, 1], "Rechaza (máx.)": r.lr2[i] > r.cvm[i, 1]})
    t = pd.DataFrame(filas)
    rango = int(t["Rechaza (traza)"].cumprod().sum())
    return t, rango
