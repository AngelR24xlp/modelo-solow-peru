"""Modelo de Solow adaptado para el Perú, 2000-2026: réplica robusta de Paredes-Soria et al. (2025).

Uso:
    python main.py                # usa los datos de data/
    python main.py --actualizar   # vuelve a descargar las series del BCRP

Autor: Angel Marchán Collazos
Fecha: 10 de octubre de 2026
"""
import argparse
import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.datos import RUTA_DATOS, cargar_datos, construir_base, descargar_bcrp
from src.modelos import (TRIMESTRES_COVID, ardl_limites, diagnosticos_var, dols, dummies_covid, granger,
                         irf_vecm_bootstrap, mco_replica, prueba_rendimientos_constantes, pronostico_vecm,
                         toda_yamamoto, validacion_fuera_muestra, var_diferencias, vecm)
from src.pruebas import bai_perron, johansen, raiz_unitaria, variables_log

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parent
FIG, TAB = RAIZ / "outputs" / "figuras", RAIZ / "outputs" / "tablas"
VARS = ["ly_sa", "lipri_sa", "lipub_sa", "ll_sa"]
X = VARS[1:]
K_AR_DIFF = 1
TIT = {"lipri_sa": "inversión privada", "lipub_sa": "inversión pública", "ll_sa": "PEA ocupada"}
ETQ = {"ly_sa": "PBI", "lipri_sa": "Inversión privada", "lipub_sa": "Inversión pública", "ll_sa": "PEA ocupada"}
# Elasticidades para la contabilidad del crecimiento (participación del capital = 0.4)
ELAS_CONTAB = {"k_pri": 0.30, "k_pub": 0.10, "pea": 0.60}


def guardar(df, nombre, indice=False):
    df.to_csv(TAB / f"{nombre}.csv", index=indice, float_format="%.4f")
    return df


def johansen_con_dummies(Y, p, D):
    """Traza de Johansen con dummies de impulso parcializadas (Johansen, Mosconi y Nielsen, 2000)."""
    from statsmodels.tsa.coint_tables import c_sjt, c_sja
    Y = np.asarray(Y)
    dY = np.diff(Y, axis=0)
    T = len(dY)
    Z0, Z1 = dY[p:], Y[p:-1]
    Z2 = np.hstack([np.ones((T - p, 1))] + [dY[p - i:T - i] for i in range(1, p + 1)] + [np.asarray(D)[p + 1:]])
    res = lambda A: A - Z2 @ np.linalg.lstsq(Z2, A, rcond=None)[0]
    R0, R1 = res(Z0), res(Z1)
    n = len(R0)
    S00, S11, S01 = R0.T @ R0 / n, R1.T @ R1 / n, R0.T @ R1 / n
    ev = np.sort(np.linalg.eigvals(np.linalg.solve(S11, S01.T @ np.linalg.solve(S00, S01))).real)[::-1]
    k = Y.shape[1]
    filas = []
    for i in range(k):
        tr, mx = -n * np.sum(np.log(1 - ev[i:])), -n * np.log(1 - ev[i])
        filas.append({"H0: rango ≤": i, "Valor propio": ev[i], "Traza": tr, "VC traza 5%": c_sjt(k - i, 0)[1],
                      "Máx. valor propio": mx, "VC máx. 5%": c_sja(k - i, 0)[1]})
    t = pd.DataFrame(filas)
    t["Rechaza (traza)"] = t["Traza"] > t["VC traza 5%"]
    t["Rechaza (máx.)"] = t["Máx. valor propio"] > t["VC máx. 5%"]
    return t, int(t["Rechaza (traza)"].cumprod().sum())


def main(actualizar=False):
    FIG.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    if actualizar:
        descargar_bcrp()
        construir_base().round(4).to_csv(RUTA_DATOS)
    df = cargar_datos()
    L, estacional = variables_log(df)
    dum = dummies_covid(L.index)
    R = {"periodo": f"{df.index[0]}-{df.index[-1]}", "n_obs": len(df),
         "trimestres_imputados": [str(q) for q in df.index[df["pea_imputada"] == 1]],
         "dummies": TRIMESTRES_COVID, "k_ar_diff": K_AR_DIFF}

    # 1. Estadística descriptiva (en niveles)
    desc = df[["pbi", "i_pri", "i_pub", "pea"]].describe().T
    from scipy.stats import jarque_bera, kurtosis, skew
    desc["asimetría"] = [skew(df[c]) for c in desc.index]
    desc["curtosis"] = [kurtosis(df[c], fisher=False) for c in desc.index]
    desc["JB p-valor"] = [jarque_bera(df[c]).pvalue for c in desc.index]
    desc.index = ["PBI (mill. S/ 2007)", "Inversión privada (mill. S/ 2007)", "Inversión pública (mill. S/ 2007)",
                  "PEA ocupada Lima (miles)"]
    guardar(desc.drop(columns=["25%", "75%"]), "01_descriptivos", True)

    anual = df[["pbi", "i_pri", "i_pub"]].groupby(df.index.year).sum()
    anual["pea"] = df["pea"].groupby(df.index.year).mean()
    crec = anual.pct_change() * 100
    completos = df.groupby(df.index.year).size() == 4
    guardar(crec[completos].dropna().round(2), "02_crecimiento_anual", True)

    # 2. Raíz unitaria y quiebres
    ur = guardar(raiz_unitaria(L, VARS), "03_raiz_unitaria")
    R["orden_integracion"] = dict(zip(ur["variable"], ur["Orden de integración"]))
    Xbp = sm.add_constant(L[X]).values
    bp_tabla, cortes = bai_perron(L["ly_sa"].values, Xbp, max_quiebres=4, tamano_min=16)
    R["quiebres_bai_perron"] = [str(L.index[c]) for c in cortes]
    bp_tabla["cortes"] = bp_tabla["cortes"].apply(lambda c: ", ".join(str(L.index[i]) for i in c))
    guardar(bp_tabla, "04_bai_perron")

    # 3. Réplica MCO del paper
    mco, vif = mco_replica(L)
    tabla_mco = pd.DataFrame({"coef": mco.params, "error_std_HAC": mco.bse, "p_valor": mco.pvalues})
    tabla_mco.index = ["Constante"] + [ETQ[c] for c in X]
    guardar(tabla_mco, "05_mco_replica", True)
    guardar(vif.to_frame(), "05b_vif", True)
    R["mco"] = {"r2_aj": mco.rsquared_adj, "coef": dict(zip(tabla_mco.index, tabla_mco["coef"])),
                "p": dict(zip(tabla_mco.index, tabla_mco["p_valor"])), "dw": float(sm.stats.durbin_watson(mco.resid))}

    # 4. Cointegración de Johansen
    tj, rango = johansen_con_dummies(L[VARS], K_AR_DIFF, dum.values)
    guardar(tj, "06_johansen")
    tj_sin, rango_sin = johansen(L[VARS], K_AR_DIFF)
    R["johansen"] = {"rango": rango, "rango_sin_dummies": rango_sin, "traza0": tj["Traza"][0],
                     "vc0": tj["VC traza 5%"][0], "traza1": tj["Traza"][1], "vc1": tj["VC traza 5%"][1]}

    # 5. VECM principal
    mv, lp, aj = vecm(L, VARS, K_AR_DIFF, dum)
    guardar(lp, "07_vecm_largo_plazo")
    guardar(aj, "08_vecm_ajuste")
    R["vecm"] = {"lp": lp.set_index("variable")[["elasticidad", "p_valor"]].to_dict("index"),
                 "alfa_pbi": float(aj["alfa"][0]), "p_alfa_pbi": float(aj["p_valor"][0]),
                 "vida_media": float(np.log(0.5) / np.log(1 + aj["alfa"][0])) if aj["alfa"][0] < 0 else None}

    # 6. Robustez de las elasticidades de largo plazo
    filas = []
    def agrega(nombre, elas, pvals=None):
        fila = {"especificación": nombre}
        for i, c in enumerate(X):
            fila[ETQ[c]] = elas[i]
            fila[f"p {ETQ[c]}"] = None if pvals is None else pvals[i]
        filas.append(fila)
    agrega(f"VECM(k={K_AR_DIFF}) con dummies COVID [principal]", lp["elasticidad"].values, lp["p_valor"].values)
    for k in (2, 3):
        _, l2, _ = vecm(L, VARS, k, dum)
        agrega(f"VECM(k={k}) con dummies COVID", l2["elasticidad"].values, l2["p_valor"].values)
    sub = L.loc["2001Q3":]
    _, l3, _ = vecm(sub, VARS, K_AR_DIFF, dummies_covid(sub.index))
    agrega("VECM sin PEA retropolada (2001T3-2026T2)", l3["elasticidad"].values, l3["p_valor"].values)
    pre = L.loc[:"2019Q4"]
    _, l4, _ = vecm(pre, VARS, K_AR_DIFF, None)
    agrega("VECM pre-COVID (2000T1-2019T4)", l4["elasticidad"].values, l4["p_valor"].values)
    md = dols(L, X, dummies=dum)
    agrega("MCO dinámicos (DOLS ±2)", md.params[X].values, md.pvalues[X].values)
    mdt = dols(L, X, tendencia=True, dummies=dum)
    agrega("DOLS con tendencia (PTF exógena)", mdt.params[X].values, mdt.pvalues[X].values)
    agrega("MCO en niveles (réplica del paper)", mco.params[X].values, mco.pvalues[X].values)
    rob = guardar(pd.DataFrame(filas), "09_robustez_largo_plazo")
    suma, wstat, wp = prueba_rendimientos_constantes(mdt, X)
    R["crs"] = {"suma": suma, "wald": wstat, "p": wp}
    R["robustez"] = rob.to_dict("records")

    uecm, lim, elas_ardl, ecm_ardl, orden = ardl_limites(L, X, dummies=dum)
    guardar(pd.DataFrame({"estadístico F": [lim.statistic], "p-valor I(0)": [lim.pvalue["lower"]],
                          "p-valor I(1)": [lim.pvalue["upper"]], "ECM (y_{t-1})": [ecm_ardl],
                          "orden ARDL": [str(orden)]}), "10_ardl_limites")
    R["ardl"] = {"F": lim.statistic, "p_inf": float(lim.pvalue["lower"]), "p_sup": float(lim.pvalue["upper"]),
                 "ecm": float(ecm_ardl), "orden": str(orden)}

    # 7. VAR en diferencias (como en el paper): IRF, FEVD, Granger, diagnósticos
    rv, sel = var_diferencias(L, VARS, dum)
    rv4, _ = var_diferencias(L, VARS, dum, rezagos=4)
    seleccion = pd.DataFrame({"criterio": ["AIC", "BIC", "HQIC", "FPE"],
                              "rezagos": [sel.aic, sel.bic, sel.hqic, sel.fpe]})
    guardar(seleccion, "11_seleccion_rezagos")
    R["var"] = {"p": rv.k_ar, "seleccion": dict(zip(seleccion.criterio, seleccion.rezagos))}
    diag = guardar(diagnosticos_var(rv), "12_diagnosticos_var")
    R["diagnosticos"] = diag.to_dict("records")
    gr = guardar(granger(rv, "ly_sa"), "13_granger")
    gr4 = guardar(granger(rv4, "ly_sa"), "13b_granger_4_rezagos")
    ty = guardar(toda_yamamoto(L, VARS, max(rv.k_ar, 2), 1, dum), "14_toda_yamamoto")
    R["granger"], R["granger4"], R["toda_yamamoto"] = gr.to_dict("records"), gr4.to_dict("records"), ty.to_dict("records")

    fevd = rv.fevd(12).decomp[0]
    fevd = pd.DataFrame(fevd * 100, columns=[ETQ[c] for c in VARS], index=range(1, 13))
    fevd.index.name = "trimestre"
    guardar(fevd, "15_descomposicion_varianza_pbi", True)
    R["fevd"] = {h: fevd.loc[h].to_dict() for h in (1, 4, 8, 12)}

    # 8. IRF del VECM con bootstrap
    irf, irf_inf, irf_sup = irf_vecm_bootstrap(L, VARS, K_AR_DIFF, dum, horizonte=20, repeticiones=300)
    tabla_irf = pd.DataFrame({ETQ[c]: irf[:, 0, j] * 100 for j, c in enumerate(VARS)})
    tabla_irf.index.name = "trimestre"
    guardar(tabla_irf, "16_irf_vecm_pbi", True)
    R["irf"] = {ETQ[c]: {"h4": irf[4, 0, j] * 100, "h20": irf[20, 0, j] * 100,
                         "sig20": bool(irf_inf[20, 0, j] > 0 or irf_sup[20, 0, j] < 0)} for j, c in enumerate(VARS)}

    # 9. Validación fuera de muestra y pronóstico 2026
    val, pron_val = validacion_fuera_muestra(L, VARS, K_AR_DIFF)
    guardar(val, "17_validacion_fuera_muestra")
    R["validacion"] = val.to_dict("records")
    pasos = 4 - df.index[-1].quarter if df.index[-1].quarter < 4 else 4
    idx_fc = pd.period_range(L.index[-1] + 1, periods=pasos, freq="Q")
    D = L[VARS].diff().dropna()
    fc_var, lo_var, hi_var = rv.forecast_interval(D.values[-rv.k_ar:], pasos, alpha=0.05,
                                                 exog_future=np.zeros((pasos, dum.shape[1])))
    base = L["ly_sa"].iloc[-1]
    sd = (hi_var[:, 0] - fc_var[:, 0]) / 1.96
    sd_acum = np.sqrt(np.cumsum(sd ** 2))
    ly_var = base + np.cumsum(fc_var[:, 0])
    vfc, vlo, vhi = pronostico_vecm(L, VARS, K_AR_DIFF, dum, pasos)
    estac = np.array([estacional["ly"].loc[q - 4] for q in idx_fc])
    pron = pd.DataFrame({"ln_pbi_sa_var": ly_var, "ln_pbi_sa_vecm": vfc["ly_sa"].values}, index=idx_fc)
    pron["ln_pbi_sa"] = pron["ln_pbi_sa_var"]
    pron["pbi"] = np.exp(pron["ln_pbi_sa"] + estac)
    pron["pbi_inf95"] = np.exp(pron["ln_pbi_sa"] - 1.96 * sd_acum + estac)
    pron["pbi_sup95"] = np.exp(pron["ln_pbi_sa"] + 1.96 * sd_acum + estac)
    pron["pbi_vecm"] = np.exp(pron["ln_pbi_sa_vecm"] + estac)
    pron.index.name = "trimestre"
    guardar(pron, "18_pronostico_pbi_2026", True)
    ultimo = df.index[-1].year
    obs = df["pbi"][df.index.year == ultimo].sum()
    anio_prev = df["pbi"][df.index.year == ultimo - 1].sum()
    total = obs + pron["pbi"].sum()
    R["pronostico"] = {"anio": ultimo, "pbi_anual": total, "crec": (total / anio_prev - 1) * 100,
                       "crec_inf": ((obs + pron["pbi_inf95"].sum()) / anio_prev - 1) * 100,
                       "crec_sup": ((obs + pron["pbi_sup95"].sum()) / anio_prev - 1) * 100,
                       "crec_vecm": ((obs + pron["pbi_vecm"].sum()) / anio_prev - 1) * 100,
                       "trimestres": [str(q) for q in idx_fc]}

    # 10. Contabilidad del crecimiento (stocks de capital por inventario perpetuo)
    cont = pd.DataFrame(index=anual.index)
    stocks = df[["k_pri", "k_pub", "pea"]].groupby(df.index.year).mean()
    gy = np.log(anual["pbi"]).diff() * 100
    for c, e in ELAS_CONTAB.items():
        cont[f"aporte_{c}"] = e * np.log(stocks[c]).diff() * 100
    cont["crec_pbi"] = gy
    cont["ptf"] = cont["crec_pbi"] - cont[[f"aporte_{c}" for c in ELAS_CONTAB]].sum(axis=1)
    cont = cont[completos].dropna()
    guardar(cont, "19_contabilidad_crecimiento", True)
    periodos = {"2001-2008": (2001, 2008), "2009-2013": (2009, 2013), "2014-2019": (2014, 2019),
                "2020-2025": (2020, 2025)}
    resumen_cont = pd.DataFrame({k: cont.loc[a:b].mean() for k, (a, b) in periodos.items()}).T
    guardar(resumen_cont, "19b_contabilidad_por_periodos", True)
    R["contabilidad"] = resumen_cont.to_dict("index")

    graficos(df, L, cortes, irf, irf_inf, irf_sup, rv, fevd, pron_val, pron, cont)
    (RAIZ / "outputs" / "resultados.json").write_text(json.dumps(R, indent=2, ensure_ascii=False, default=float))
    imprimir(R)
    return R


def graficos(df, L, cortes, irf, lo, hi, rv, fevd, pron_val, pron, cont):
    plt.rcParams.update({"figure.dpi": 130, "axes.grid": True, "grid.alpha": 0.3, "font.size": 9})
    t = df.index.to_timestamp()

    fig, ax = plt.subplots(2, 2, figsize=(11, 6.5))
    for a, (c, sa, tit) in zip(ax.flat, [("pbi", "ly", "PBI real (mill. S/ 2007)"),
                                         ("i_pri", "lipri", "Inversión bruta fija privada"),
                                         ("i_pub", "lipub", "Inversión bruta fija pública"),
                                         ("pea", "ll", "PEA ocupada, Lima Metropolitana (miles)")]):
        a.plot(t, df[c], color="#9ab", lw=1, label="Original")
        a.plot(t, np.exp(L[f"{sa}_sa"]), color="#1f4e79", lw=1.6, label="Desestacionalizada (STL)")
        if c == "pea":
            imp = df["pea_imputada"] == 1
            a.plot(t[imp], df.loc[imp, c], "o", color="#c0504d", ms=3, label="Retropolada")
        a.set_title(tit)
    ax[0, 0].legend(fontsize=7)
    ax[1, 1].legend(fontsize=7)
    fig.suptitle("Perú: variables del modelo de Solow adaptado, 2000T1-%s" % df.index[-1])
    fig.tight_layout()
    fig.savefig(FIG / "01_variables.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(t, df["pbi"].pct_change(4) * 100, color="#1f4e79", label="Crecimiento interanual del PBI (%)")
    for c in cortes:
        ax.axvline(t[c], color="#c0504d", ls="--", lw=1.2)
        ax.text(t[c], ax.get_ylim()[1] * 0.85, f" {L.index[c]}", color="#c0504d", fontsize=8)
    ax.set_title("Quiebres estructurales de Bai-Perron en la función de producción")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "02_quiebres_bai_perron.png")
    plt.close(fig)

    fig, ax = plt.subplots(1, 3, figsize=(12, 3.8))
    h = np.arange(irf.shape[0])
    for j, a in enumerate(ax):
        k = j + 1
        a.fill_between(h, lo[:, 0, k] * 100, hi[:, 0, k] * 100, color="#1f4e79", alpha=0.2, label="IC 90% bootstrap")
        a.plot(h, irf[:, 0, k] * 100, color="#1f4e79", lw=2)
        a.axhline(0, color="k", lw=0.8)
        a.set_title(f"PBI ante choque de {TIT[VARS[k]]}")
        a.set_xlabel("Trimestres")
    ax[0].set_ylabel("% (desviación del ln PBI)")
    ax[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG / "03_irf_vecm.png")
    plt.close(fig)

    irfv = rv.irf(12)
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.8))
    lo_c, hi_c = irfv.cum_errband_mc(orth=True, repl=500, signif=0.10, seed=7)
    for j, a in enumerate(ax):
        k = j + 1
        a.fill_between(range(13), lo_c[:, 0, k] * 100, hi_c[:, 0, k] * 100, color="#9bbb59", alpha=0.3)
        a.plot(irfv.orth_cum_effects[:, 0, k] * 100, color="#4f6228", lw=2)
        a.axhline(0, color="k", lw=0.8)
        a.set_title(f"PBI acumulado: choque de {TIT[VARS[k]]}")
        a.set_xlabel("Trimestres")
    fig.tight_layout()
    fig.savefig(FIG / "04_irf_var_diferencias.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.stackplot(fevd.index, fevd.T.values, labels=fevd.columns,
                 colors=["#1f4e79", "#c0504d", "#9bbb59", "#f79646"], alpha=0.85)
    ax.set(title="Descomposición de la varianza del error de pronóstico del PBI", xlabel="Trimestres",
           ylabel="%", ylim=(0, 100))
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "05_descomposicion_varianza.png")
    plt.close(fig)

    fig, ax = plt.subplots(1, 2, figsize=(12, 4))
    tv = pron_val.index.to_timestamp()
    ax[0].plot(tv, np.exp(pron_val["real"]), "k-o", ms=3, label="Observado")
    for c in pron_val.columns.drop("real"):
        ax[0].plot(tv, np.exp(pron_val[c]), "--", label=c)
    ax[0].set_title("Validación fuera de muestra (PBI desestacionalizado)")
    ax[0].legend(fontsize=7)
    hist = df["pbi"].loc["2022Q1":]
    tp = pron.index.to_timestamp()
    ax[1].plot(hist.index.to_timestamp(), hist, "k-o", ms=3, label="Observado")
    ax[1].plot(tp, pron["pbi"], "o-", color="#c0504d", label="Pronóstico VAR")
    ax[1].plot(tp, pron["pbi_vecm"], "s--", color="#1f4e79", label="Pronóstico VECM")
    ax[1].fill_between(tp, pron["pbi_inf95"], pron["pbi_sup95"], color="#c0504d", alpha=0.2, label="IC 95%")
    ax[1].set_title("PBI trimestral y pronóstico (mill. S/ 2007)")
    ax[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG / "06_pronostico.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 4.5))
    cols = {"aporte_k_pri": ("Capital privado", "#1f4e79"), "aporte_k_pub": ("Capital público", "#9bbb59"),
            "aporte_pea": ("Trabajo", "#f79646"), "ptf": ("PTF (residuo de Solow)", "#c0504d")}
    pos, neg = np.zeros(len(cont)), np.zeros(len(cont))
    for c, (n, col) in cols.items():
        v = cont[c].values
        ax.bar(cont.index, np.where(v > 0, v, 0), bottom=pos, color=col, label=n)
        ax.bar(cont.index, np.where(v < 0, v, 0), bottom=neg, color=col)
        pos += np.where(v > 0, v, 0)
        neg += np.where(v < 0, v, 0)
    ax.plot(cont.index, cont["crec_pbi"], "ko-", ms=4, label="Crecimiento del PBI")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_ylim(min(neg.min(), cont["crec_pbi"].min()) - 1.5, max(pos.max(), cont["crec_pbi"].max()) + 1.5)
    ax.set(title="Contabilidad del crecimiento del Perú (puntos porcentuales)", xlabel="Año")
    ax.legend(ncol=5, fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(FIG / "07_contabilidad_crecimiento.png")
    plt.close(fig)


def imprimir(R):
    print(f"\nMuestra: {R['periodo']} ({R['n_obs']} trimestres)")
    print(f"Johansen: rango de cointegración = {R['johansen']['rango']}")
    print("VECM - elasticidades de largo plazo:")
    for v, d in R["vecm"]["lp"].items():
        print(f"  {v:<18} {d['elasticidad']:7.3f}  (p={d['p_valor']:.3f})")
    print(f"  Velocidad de ajuste del PBI: {R['vecm']['alfa_pbi']:.3f} (p={R['vecm']['p_alfa_pbi']:.3f})")
    p = R["pronostico"]
    print(f"Pronóstico {p['anio']}: crecimiento del PBI {p['crec']:.2f}% (IC95% {p['crec_inf']:.2f}% a {p['crec_sup']:.2f}%)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--actualizar", action="store_true")
    ap.add_argument("--sin-informe", action="store_true", help="No generar el informe Word ni la presentación")
    a = ap.parse_args()
    resultados = main(a.actualizar)
    if not a.sin_informe:
        from src.informe import generar_informe
        from src.presentacion import generar_presentacion
        generar_informe(resultados)
        generar_presentacion(resultados)
