"""Datos trimestrales del BCRP para Perú, 2000-2026.

Autor: Angel Marchán Collazos
Fecha: 10 de octubre de 2026
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm

RAIZ = Path(__file__).resolve().parents[1]
DIR_BCRP = RAIZ / "data" / "bcrp"
RUTA_DATOS = RAIZ / "data" / "peru_trimestral_2000_2026.csv"

SERIES = {
    "PN02538AQ": "pbi",     # PBI real (millones de S/ de 2007)
    "PN02533AQ": "i_pri",   # Inversión bruta fija privada (millones de S/ de 2007)
    "PN02534AQ": "i_pub",   # Inversión bruta fija pública (millones de S/ de 2007)
    "PN38051GM": "pea",     # Empleo en Lima Metropolitana, promedio móvil 3 meses (miles)
}
MESES = {"Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4, "May": 5, "Jun": 6, "Jul": 7,
         "Ago": 8, "Set": 9, "Sep": 9, "Oct": 10, "Nov": 11, "Dic": 12}

# Tasas de depreciación trimestrales para el inventario perpetuo
DEPRECIACION = {"i_pri": 0.05 / 4, "i_pub": 0.04 / 4}


def descargar_bcrp(inicio="2000-1", fin="2026-4"):
    """Descarga las series de la API del BCRP. Si el portal bloquea la descarga, se usan los JSON de data/bcrp."""
    DIR_BCRP.mkdir(parents=True, exist_ok=True)
    for codigo in SERIES:
        freq_ini, freq_fin = (inicio, fin) if codigo.endswith("Q") else (f"{inicio[:4]}-1", f"{fin[:4]}-12")
        url = f"https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{codigo}/json/{freq_ini}/{freq_fin}"
        try:
            r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            json.loads(r.text)
        except (requests.RequestException, ValueError) as e:
            print(f"Aviso: no se pudo descargar {codigo} ({type(e).__name__}); se usa la copia local.")
            continue
        (DIR_BCRP / f"{codigo}.json").write_text(r.text)


def _leer_json(codigo):
    d = json.loads((DIR_BCRP / f"{codigo}.json").read_text())
    fechas, valores = [], []
    for p in d["periods"]:
        v = p["values"][0]
        if v in ("n.d.", ""):
            continue
        nombre = p["name"]
        if nombre.startswith("T"):
            trim, anio = nombre[1:].split(".")
            fechas.append(pd.Period(f"20{anio}Q{trim}", freq="Q"))
        else:
            mes, anio = nombre.split(".")
            fechas.append(pd.Period(f"{anio}-{MESES[mes]:02d}", freq="M"))
        valores.append(float(v))
    return pd.Series(valores, index=pd.PeriodIndex(fechas))


def stock_capital(inversion, delta, anios_base=5):
    """Inventario perpetuo: K_t = (1 - delta) K_{t-1} + I_t, con K_0 = I_0 / (g + delta)."""
    g = (inversion.iloc[4 * anios_base] / inversion.iloc[0]) ** (1 / (4 * anios_base)) - 1
    k = np.empty(len(inversion))
    k[0] = inversion.iloc[:4].mean() / (max(g, 0.0) + delta)
    for t in range(1, len(inversion)):
        k[t] = (1 - delta) * k[t - 1] + inversion.iloc[t]
    return pd.Series(k, index=inversion.index)


def retropolar_empleo(df):
    """Completa 2000T1-2001T1 (antes de la Encuesta Permanente de Empleo) con una regresión de
    Okun inversa: dlog(PEA) = a + b*dlog(PBI) + estacionales, estimada con 2001T3-2007T4."""
    d = pd.DataFrame({"dl": np.log(df["pea"]).diff(), "dy": np.log(df["pbi"]).diff()})
    d["q"] = d.index.quarter
    X = pd.get_dummies(d["q"], prefix="q", drop_first=True, dtype=float)
    X["dy"] = d["dy"]
    X = sm.add_constant(X)
    muestra = d["dl"].notna() & (d.index <= pd.Period("2007Q4"))
    m = sm.OLS(d.loc[muestra, "dl"], X[muestra]).fit()
    pea = df["pea"].copy()
    primero = pea.first_valid_index()
    pos = pea.index.get_loc(primero)
    for i in range(pos - 1, -1, -1):
        dl_sig = float(m.predict(X.iloc[[i + 1]]).iloc[0])
        pea.iloc[i] = pea.iloc[i + 1] / np.exp(dl_sig)
    return pea, pea.index < primero


def construir_base():
    df = pd.DataFrame({n: _leer_json(c) for c, n in SERIES.items() if c.endswith("Q")})
    pea_m = _leer_json("PN38051GM")
    # Promedio trimestral; el último trimestre puede estar incompleto (se promedian los meses disponibles)
    pea_q = pea_m.groupby(pea_m.index.asfreq("Q")).mean()
    df["pea"] = pea_q.reindex(df.index)
    df = df.loc[: df["pbi"].last_valid_index()]
    df["pea"], imputado = retropolar_empleo(df)
    df["pea_imputada"] = imputado.astype(int)
    for inv, delta in DEPRECIACION.items():
        df[f"k_{inv[2:]}"] = stock_capital(df[inv], delta)
    df.index.name = "trimestre"
    return df


def cargar_datos(ruta=RUTA_DATOS):
    df = pd.read_csv(ruta, index_col="trimestre")
    df.index = pd.PeriodIndex(df.index, freq="Q")
    return df


if __name__ == "__main__":
    base = construir_base()
    base.round(4).to_csv(RUTA_DATOS)
    print(base.head(8)); print(base.tail(6)); print(base.describe().T)
