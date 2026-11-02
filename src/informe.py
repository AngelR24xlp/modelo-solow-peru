"""Genera el informe Word a partir de los resultados producidos por main.py."""
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

RAIZ = Path(__file__).resolve().parents[1]
FIG, TAB = RAIZ / "outputs" / "figuras", RAIZ / "outputs" / "tablas"
DIR_INF = RAIZ / "informe"
FUENTE = "Fuente: BCRP. Elaboración propia con base en main.py."
AZUL = RGBColor(0x1F, 0x4E, 0x79)


class Informe:
    def __init__(self):
        self.doc = Document()
        self.n_tab = self.n_fig = self.n_ec = 0
        sec = self.doc.sections[0]
        sec.top_margin = sec.bottom_margin = Cm(2.5)
        sec.left_margin = sec.right_margin = Cm(2.5)
        est = self.doc.styles["Normal"]
        est.font.name, est.font.size = "Calibri", Pt(11)
        est.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
        est.paragraph_format.space_after = Pt(6)
        est.paragraph_format.line_spacing = 1.15
        for n in ("Heading 1", "Heading 2", "Title"):
            self.doc.styles[n].font.color.rgb = AZUL
        (DIR_INF / "ecuaciones").mkdir(parents=True, exist_ok=True)

    def h(self, texto, nivel=1):
        self.doc.add_heading(texto, nivel)

    def p(self, texto, negrita=False, cursiva=False, centrado=False):
        par = self.doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER if centrado else WD_ALIGN_PARAGRAPH.JUSTIFY
        # **texto** en negrita
        for i, trozo in enumerate(texto.split("**")):
            r = par.add_run(trozo)
            r.bold = negrita or i % 2 == 1
            r.italic = cursiva
        return par

    def viñetas(self, items):
        for it in items:
            par = self.doc.add_paragraph(style="List Bullet")
            for i, trozo in enumerate(it.split("**")):
                par.add_run(trozo).bold = i % 2 == 1

    def nota(self, texto):
        par = self.doc.add_paragraph()
        r = par.add_run(texto)
        r.italic, r.font.size = True, Pt(8.5)

    def ecuacion(self, latex):
        self.n_ec += 1
        ruta = DIR_INF / "ecuaciones" / f"ec{self.n_ec}.png"
        fig = plt.figure(figsize=(14, 1.4))
        fig.text(0.5, 0.5, f"${latex}$", fontsize=15, ha="center", va="center")
        fig.savefig(ruta, dpi=200, bbox_inches="tight", pad_inches=0.05, transparent=True)
        plt.close(fig)
        img = plt.imread(ruta)
        par = self.doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.add_run().add_picture(str(ruta), width=Cm(min(img.shape[1] / 200 * 2.54 * 0.8, 13.5)))
        par.add_run(f"     ({self.n_ec})")

    def figura(self, nombre, titulo, ancho=16):
        self.n_fig += 1
        cap = self.doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.add_run(f"Figura {self.n_fig}. ").bold = True
        cap.add_run(titulo)
        self.doc.add_picture(str(FIG / nombre), width=Cm(ancho))
        self.doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        self.nota(FUENTE)
        return self.n_fig

    def tabla(self, df, titulo, dec=3, nota=FUENTE, fuente_pt=8.5):
        self.n_tab += 1
        cap = self.doc.add_paragraph()
        cap.add_run(f"Tabla {self.n_tab}. ").bold = True
        cap.add_run(titulo)
        t = self.doc.add_table(rows=1, cols=len(df.columns))
        t.style = "Light Grid Accent 1"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for j, c in enumerate(df.columns):
            t.rows[0].cells[j].text = str(c)
        for _, fila in df.iterrows():
            celdas = t.add_row().cells
            for j, v in enumerate(fila):
                if isinstance(v, (bool,)) or (hasattr(v, "dtype") and v.dtype == bool):
                    txt = "Sí" if v else "No"
                elif isinstance(v, float):
                    txt = "" if pd.isna(v) else f"{v:,.{dec}f}"
                else:
                    txt = str(v)
                celdas[j].text = txt
        for fila in t.rows:
            for c in fila.cells:
                for par in c.paragraphs:
                    for r in par.runs:
                        r.font.size = Pt(fuente_pt)
        if nota:
            self.nota(nota)
        return self.n_tab

    def salto(self):
        self.doc.add_page_break()


def estrellas(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def con_estrellas(coef, p, dec=3):
    return f"{coef:.{dec}f}{estrellas(p)}"


def leer(nombre):
    return pd.read_csv(TAB / f"{nombre}.csv")


def generar_informe(R, ruta=None):
    ruta = Path(ruta or DIR_INF / "Informe_Modelo_Solow_Peru_2000_2026.docx")
    d = Informe()
    doc = d.doc
    lp = R["vecm"]["lp"]
    ip, ig, il = (lp[k]["elasticidad"] for k in ("I privada", "I pública", "PEA ocupada"))
    pr = R["pronostico"]
    jo = R["johansen"]
    val = pd.DataFrame(R["validacion"])
    mejor = val.iloc[0]
    rmse = dict(zip(val["modelo"], val["RMSE (%)"]))
    gr = {g["H0"]: g["p_valor"] for g in R["granger"]}
    gr4 = {g["H0"]: g["p_valor"] for g in R["granger4"]}
    ty = {g["H0"]: g["p_valor"] for g in R["toda_yamamoto"]}
    fe = R["fevd"]["12"] if "12" in R["fevd"] else R["fevd"][12]
    irf = R["irf"]
    ar = R["ardl"]
    rob = pd.DataFrame(R["robustez"])
    cont = R["contabilidad"]
    fin = R["periodo"].split("-")[1]
    imput = R["trimestres_imputados"]

    # ---------- Portada ----------
    doc.add_paragraph("\n\n")
    tit = doc.add_paragraph()
    tit.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = tit.add_run("Determinantes del producto y crecimiento económico en el Perú, 2000–2026")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(20), AZUL
    d.p("Una extensión robusta del modelo de Solow adaptado con cointegración, VECM, ARDL y validación "
        "fuera de muestra", cursiva=True, centrado=True)
    doc.add_paragraph("\n")
    d.p("Angel Marchán", negrita=True, centrado=True)
    d.p("Universidad Nacional Mayor de San Marcos", centrado=True)
    d.p(f"Lima, {['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'][date.today().month-1]} de {date.today().year}", centrado=True)
    doc.add_paragraph("\n")
    d.p("Informe reescrito a partir del código Python del repositorio modelo-solow-peru. Todas las cifras, "
        "tablas y figuras fueron generadas por main.py con datos del Banco Central de Reserva del Perú (BCRP). "
        "Basado metodológicamente en Paredes-Soria et al. (2025), Journal of Risk and Financial Management, "
        "18(3), 112.", cursiva=True, centrado=True)
    d.salto()

    # ---------- Resumen ----------
    d.h("Resumen")
    d.p(f"Este estudio estima los determinantes del producto peruano entre 2000T1 y {fin} con un modelo de "
        "Solow ampliado en el que el producto depende de la inversión bruta fija privada, la inversión bruta "
        "fija pública (proxy de infraestructura) y la población ocupada. Partiendo del diseño de Paredes-Soria "
        "et al. (2025), se refuerza la estrategia empírica con ajuste estacional STL robusto, cuatro pruebas de "
        "raíz unitaria (ADF, Phillips-Perron, KPSS y Zivot-Andrews), quiebres múltiples de Bai-Perron, "
        "cointegración de Johansen con dummies de impulso por la pandemia, un VECM con funciones impulso-respuesta "
        "bootstrap, MCO dinámicos (DOLS), la prueba de límites ARDL, causalidad de Granger y Toda-Yamamoto, "
        "validación fuera de muestra y un pronóstico para 2026. "
        f"La prueba de la traza identifica un vector de cointegración (rango = {jo['rango']}). En el largo plazo, "
        f"un aumento de 1% en la inversión privada eleva el PBI en {ip:.2f}%, mientras que la PEA ocupada tiene "
        f"una elasticidad de {il:.2f} y la inversión pública una elasticidad negativa de {ig:.2f}. El PBI corrige "
        f"{abs(R['vecm']['alfa_pbi'])*100:.1f}% del desequilibrio de largo plazo cada trimestre. La inversión "
        f"privada causa en sentido de Granger al PBI (p = {gr['ΔI privada no causa a ΔPBI']:.3f}), resultado "
        f"confirmado por Toda-Yamamoto (p = {ty['I privada no causa a PBI']:.3f}). El signo positivo de la inversión "
        "privada y negativo de la inversión pública se mantiene en las ocho especificaciones de robustez. Con datos "
        f"observados hasta {fin}, el modelo proyecta un crecimiento del PBI de {pr['crec']:.1f}% en {pr['anio']} "
        f"(intervalo de 95%: {pr['crec_inf']:.1f}% a {pr['crec_sup']:.1f}%).")
    d.p("**Palabras clave:** modelo de Solow, inversión privada, inversión pública, empleo, VECM, ARDL, Perú.")
    d.p("**Clasificación JEL:** C32, E22, H54, O47, O54.")
    d.salto()

    # ---------- 1. Introducción ----------
    d.h("1. Introducción")
    d.p("El Perú fue una de las economías de mayor crecimiento de América Latina en la primera década del siglo XXI, "
        "impulsado por el auge de los precios de las materias primas, la estabilidad macroeconómica y una fuerte "
        "expansión de la inversión. A partir de 2014 el crecimiento se desaceleró, la pandemia de 2020 provocó la "
        "mayor contracción en décadas y la recuperación posterior estuvo marcada por la inestabilidad política y "
        "la caída de la inversión privada en 2023. Entender qué factores sostienen el producto en el largo plazo "
        "es, por tanto, central para el diseño de la política económica.")
    d.p("Paredes-Soria et al. (2025) adaptan el modelo de Solow ampliado para el Perú en el periodo 2000–2022 "
        "y estudian la relación entre el PBI, la inversión privada, la inversión pública y la población ocupada "
        "mediante pruebas de raíz unitaria, cointegración de Johansen, modelos VAR y VECM, funciones impulso-"
        "respuesta, descomposición de varianza y causalidad de Granger. El presente informe reescribe ese análisis "
        "a partir de un código propio en Python y lo extiende en cuatro direcciones:")
    d.viñetas([
        f"**Periodo:** se amplía la muestra a 2000T1–{fin}, incorporando la pandemia, la recuperación y "
        f"la información disponible de {pr['anio']}, y se proyecta el resto de {pr['anio']}.",
        "**Robustez de las pruebas:** se combinan ADF, Phillips-Perron, KPSS y Zivot-Andrews, y se identifican "
        "quiebres estructurales múltiples con el algoritmo de Bai-Perron.",
        "**Robustez de las estimaciones:** la relación de largo plazo se contrasta con DOLS, ARDL, distintos "
        "rezagos, submuestras y errores estándar robustos (HAC); las funciones impulso-respuesta usan bandas bootstrap.",
        "**Validación:** se evalúa la capacidad predictiva fuera de muestra frente a modelos de referencia y se "
        "realiza una contabilidad del crecimiento con stocks de capital construidos por inventario perpetuo.",
    ])
    d.p("El informe se organiza así: la sección 2 presenta el marco teórico; la sección 3, los datos y la "
        "metodología; la sección 4, los resultados; la sección 5 discute los hallazgos; y la sección 6 concluye.")

    # ---------- 2. Marco teórico ----------
    d.h("2. Marco teórico")
    d.h("2.1 El modelo de Solow ampliado", 2)
    d.p("En el modelo neoclásico de Solow (1956) el producto se genera con capital y trabajo bajo rendimientos "
        "decrecientes de cada factor, y el crecimiento de largo plazo del producto por trabajador depende del "
        "progreso tecnológico exógeno. Mankiw, Romer y Weil (1992) amplían el modelo incorporando capital humano, "
        "mientras que Aschauer (1989) y Barro (1990) destacan el papel del capital público (infraestructura) como "
        "factor productivo diferenciado. Siguiendo esta tradición, se plantea la función de producción:")
    d.ecuacion(r"Y_t = A_t\, K_{p,t}^{\alpha}\, K_{g,t}^{\gamma}\, L_t^{\beta}")
    d.p("donde Y es el PBI real, A la productividad total de factores (PTF), Kp y Kg los stocks de capital privado "
        "y público, y L el empleo. Como en Paredes-Soria et al. (2025), la versión empírica sustituye los stocks por "
        "los flujos de inversión, que el BCRP publica trimestralmente, y toma logaritmos:")
    d.ecuacion(r"\ln Y_t = a + \alpha \ln I_{p,t} + \gamma \ln I_{g,t} + \beta \ln L_t + u_t")
    d.p("Con flujos de inversión los coeficientes deben leerse como elasticidades de largo plazo del producto "
        "respecto a la inversión y no como participaciones factoriales; por ello no se espera que sumen uno.")
    d.h("2.2 Inversión pública, inversión privada y crecimiento", 2)
    d.p("La inversión pública puede complementar a la privada al reducir costos de transporte y logística "
        "(efecto atracción o crowding-in), pero también puede desplazarla si compite por recursos o se ejecuta "
        "con baja eficiencia (crowding-out). Además, en economías como la peruana la inversión pública suele tener "
        "un componente contracíclico —se expande cuando la economía se desacelera—, lo que puede producir una "
        "correlación de largo plazo negativa con el producto aun cuando su efecto productivo sea positivo. La "
        "evidencia empírica es, por tanto, una cuestión a resolver con los datos.")

    # ---------- 3. Datos y metodología ----------
    d.h("3. Datos y metodología")
    d.h("3.1 Datos", 2)
    d.p(f"Se utilizan {R['n_obs']} observaciones trimestrales (2000T1–{fin}) descargadas de la API de "
        "estadísticas del BCRP. La Tabla 1 resume las variables.")
    variables = pd.DataFrame({
        "Variable": ["PBI real", "Inversión bruta fija privada", "Inversión bruta fija pública", "PEA ocupada"],
        "Código BCRP": ["PN02538AQ", "PN02533AQ", "PN02534AQ", "PN38051GM"],
        "Unidad": ["Mill. S/ de 2007", "Mill. S/ de 2007", "Mill. S/ de 2007", "Miles de personas"],
        "Frecuencia original": ["Trimestral", "Trimestral", "Trimestral", "Mensual (prom. móvil 3 meses)"],
    })
    d.tabla(variables, "Variables y fuentes", nota="Fuente: BCRP, series estadísticas.")
    d.p("Tratamiento de los datos:")
    d.viñetas([
        "**PEA ocupada:** la serie del BCRP corresponde a Lima Metropolitana (Encuesta Permanente de Empleo, INEI) "
        "y se agrega a frecuencia trimestral promediando los meses disponibles. Los trimestres anteriores al inicio "
        f"de la serie ({', '.join(imput)}) se retropolan con una regresión del crecimiento del empleo sobre el "
        "crecimiento del PBI y dummies estacionales; la especificación de robustez sin estos trimestres confirma "
        "que no alteran los resultados.",
        "**Ajuste estacional:** las series en logaritmos se desestacionalizan con STL robusto (Cleveland et al., "
        "1990), que es resistente a valores atípicos como los de 2020.",
        "**Pandemia:** se incluyen dummies de impulso para 2020T2, 2020T3 y 2020T4.",
        "**Stocks de capital:** para la contabilidad del crecimiento se construyen stocks de capital privado y "
        "público por el método de inventario perpetuo, con depreciación anual de 5% y 4%, respectivamente "
        "(supuestos del autor).",
        f"**Datos de {pr['anio']}:** la información observada llega hasta {fin}; los trimestres "
        f"{' y '.join(pr['trimestres'])} son pronósticos del modelo.",
    ])
    d.ecuacion(r"K_t = (1-\delta)\,K_{t-1} + I_t,\qquad K_0 = \frac{\bar I_{0}}{g + \delta}")

    d.h("3.2 Estrategia econométrica", 2)
    d.p("El análisis sigue cinco etapas. Primero, se determina el orden de integración con ADF, Phillips-Perron "
        "(hipótesis nula de raíz unitaria), KPSS (nula de estacionariedad) y Zivot-Andrews (raíz unitaria con un "
        "quiebre endógeno). Segundo, se buscan quiebres múltiples en la relación de producción con el algoritmo de "
        "programación dinámica de Bai y Perron (2003), seleccionando el número de quiebres por BIC. Tercero, se "
        "prueba la cointegración con el procedimiento de Johansen (1991), parcializando las dummies de la pandemia. "
        "Cuarto, se estima el modelo vectorial de corrección de errores (VECM):")
    d.ecuacion(r"\Delta y_t = \alpha\,\beta' y_{t-1} + \sum_{i=1}^{k}\Gamma_i\,\Delta y_{t-i} + \mu + \Phi D_t + \varepsilon_t")
    d.p("donde y = (ln PBI, ln Ip, ln Ig, ln L)', β contiene la relación de largo plazo normalizada en el PBI, α "
        "las velocidades de ajuste y D las dummies de la pandemia. El número de rezagos se elige por AIC. Quinto, "
        "se verifica la robustez de β con MCO dinámicos (Stock y Watson, 1993):")
    d.ecuacion(r"\ln Y_t = c + \theta' x_t + \sum_{j=-2}^{2}\phi_j'\,\Delta x_{t-j} + \Phi D_t + e_t")
    d.p("y con la prueba de límites de Pesaran, Shin y Smith (2001) sobre el modelo ARDL en forma de corrección de "
        "errores, válida aunque los regresores mezclen variables I(0) e I(1):")
    d.ecuacion(r"\Delta \ln Y_t = c + \pi_y \ln Y_{t-1} + \pi_x' x_{t-1} + \sum_{i}\psi_i \Delta \ln Y_{t-i} + \sum_{j}\omega_j' \Delta x_{t-j} + e_t")
    d.p("La dinámica de corto plazo se analiza con funciones impulso-respuesta ortogonalizadas del VECM con bandas "
        "bootstrap de 90% (300 réplicas), la descomposición de varianza y la causalidad de Granger de un VAR en "
        "diferencias, complementada con el procedimiento de Toda y Yamamoto (1995), que no requiere conocer el orden "
        "de integración. Finalmente, se comparan pronósticos fuera de muestra (2024T1 en adelante) del VECM, del VAR "
        "en diferencias, de un ARIMA(1,1,0) con deriva y de un paseo aleatorio con deriva, y se descompone el "
        "crecimiento con la ecuación de contabilidad:")
    d.ecuacion(r"g_Y = 0.30\,g_{K_p} + 0.10\,g_{K_g} + 0.60\,g_L + g_{PTF}")
    d.salto()

    # ---------- 4. Resultados ----------
    d.h("4. Resultados")
    d.h("4.1 Hechos estilizados", 2)
    d.figura("01_variables.png", f"Variables del modelo, 2000T1–{fin}")
    ca = leer("02_crecimiento_anual").set_index("trimestre")
    d.p(f"La Figura 1 muestra la evolución de las series. El PBI creció en promedio "
        f"{ca.loc[2001:2013,'pbi'].mean():.1f}% anual entre 2001 y 2013 y {ca.loc[2014:2019,'pbi'].mean():.1f}% "
        f"entre 2014 y 2019. En 2020 cayó {abs(ca.loc[2020,'pbi']):.1f}% y en 2021 rebotó {ca.loc[2021,'pbi']:.1f}%. "
        f"La inversión privada es la variable más volátil: creció más de 20% anual entre 2006 y 2008, cayó "
        f"{abs(ca.loc[2009,'i_pri']):.1f}% en 2009 y {abs(ca.loc[2023,'i_pri']):.1f}% en 2023, y se recuperó "
        f"{ca.loc[2025,'i_pri']:.1f}% en 2025. La inversión pública, en cambio, aumentó {ca.loc[2009,'i_pub']:.1f}% "
        "en 2009, en plena desaceleración, lo que ilustra su carácter contracíclico.")
    desc = leer("01_descriptivos").rename(columns={"Unnamed: 0": "Variable", "count": "N", "mean": "Media",
                                                     "std": "Desv. est.", "min": "Mín.", "50%": "Mediana",
                                                     "max": "Máx.", "asimetría": "Asimetría",
                                                     "curtosis": "Curtosis", "JB p-valor": "JB (p)"})
    desc["N"] = desc["N"].astype(int).astype(str)
    d.tabla(desc, "Estadística descriptiva (niveles trimestrales)", dec=2, fuente_pt=7.5)

    d.h("4.2 Orden de integración", 2)
    ur = leer("03_raiz_unitaria")
    d.tabla(ur, "Pruebas de raíz unitaria (p-valores)", dec=3, fuente_pt=7,
            nota="Nota: niveles con constante y tendencia; diferencias con constante. KPSS tiene como hipótesis nula "
                 "la estacionariedad (p-valores truncados entre 0.01 y 0.10). " + FUENTE)
    d.p("El PBI y las dos series de inversión no rechazan la raíz unitaria en niveles con ADF, mientras que KPSS "
        "rechaza la estacionariedad; en primeras diferencias todas las pruebas coinciden en que son estacionarias, "
        "por lo que se clasifican como I(1). La PEA ocupada, en cambio, rechaza la raíz unitaria en niveles con las "
        "tres pruebas, de modo que se comporta como estacionaria alrededor de una tendencia. Zivot-Andrews ubica los "
        f"quiebres en {ur.loc[0,'Quiebre ZA']} (PBI), {ur.loc[1,'Quiebre ZA']} (inversión privada) y "
        f"{ur.loc[3,'Quiebre ZA']} (empleo). Esta mezcla de órdenes de integración justifica complementar a Johansen "
        "con ARDL y Toda-Yamamoto, que son robustos a ella.")

    d.h("4.3 Quiebres estructurales", 2)
    bp = leer("04_bai_perron").fillna("—")
    d.tabla(bp, "Quiebres múltiples de Bai-Perron en la función de producción", dec=4)
    d.figura("02_quiebres_bai_perron.png", "Crecimiento interanual del PBI y quiebres estimados", ancho=15)
    d.p(f"El BIC selecciona {len(R['quiebres_bai_perron'])} quiebres ({', '.join(R['quiebres_bai_perron'])}), que "
        "coinciden con el inicio del superciclo de materias primas, la salida de la crisis financiera internacional "
        "y el fin del ciclo de inversión minera previo a la pandemia. Su existencia advierte que los parámetros pueden "
        "variar en el tiempo, por lo que se reportan estimaciones por submuestras.")

    d.h("4.4 Réplica: regresión en niveles", 2)
    mco = leer("05_mco_replica").rename(columns={"Unnamed: 0": "Variable", "coef": "Coeficiente",
                                                   "error_std_HAC": "Error est. (HAC)", "p_valor": "p-valor"})
    vif = leer("05b_vif")
    d.tabla(mco, f"Regresión log-log del PBI por MCO (R² ajustado = {R['mco']['r2_aj']:.3f})", dec=3)
    d.p(f"Como en el artículo base, la regresión en niveles tiene un ajuste muy alto (R² ajustado = "
        f"{R['mco']['r2_aj']:.3f}). Solo la inversión privada es significativa (elasticidad "
        f"{R['mco']['coef']['Inversión privada']:.3f}). Sin embargo, el estadístico de Durbin-Watson es "
        f"{R['mco']['dw']:.2f} y los factores de inflación de varianza llegan a {vif['VIF'].max():.1f}, lo que indica "
        "autocorrelación severa y multicolinealidad: con variables I(1) esta regresión puede ser espuria y sus errores "
        "estándar no son confiables. Por eso la inferencia de largo plazo se basa en las técnicas de cointegración.")

    d.h("4.5 Cointegración de Johansen", 2)
    tj = leer("06_johansen")
    d.tabla(tj, "Pruebas de la traza y del máximo valor propio (con dummies COVID)", dec=3, fuente_pt=7.5)
    d.p(f"La prueba de la traza rechaza la ausencia de cointegración ({jo['traza0']:.1f} > {jo['vc0']:.1f}) pero no "
        f"rechaza que exista a lo sumo un vector ({jo['traza1']:.1f} < {jo['vc1']:.1f}). Se adopta, por tanto, un rango "
        "de cointegración igual a uno. El estadístico del máximo valor propio rechaza marginalmente r ≤ 1, lo que, junto "
        "con la estacionariedad de la PEA, sugiere cautela; por ello la relación se contrasta con otros estimadores.")

    d.h("4.6 Relación de largo plazo y corrección de errores (VECM)", 2)
    lpt = leer("07_vecm_largo_plazo").rename(columns={"variable": "Variable", "elasticidad": "Elasticidad",
                                                      "error_std": "Error est.", "p_valor": "p-valor"})
    ajt = leer("08_vecm_ajuste").rename(columns={"ecuación": "Ecuación", "alfa": "α (ajuste)",
                                                 "error_std": "Error est.", "p_valor": "p-valor"})
    d.tabla(lpt, f"VECM: elasticidades de largo plazo del PBI (k = {R['k_ar_diff']} rezago en diferencias)", dec=3)
    d.ecuacion(rf"\ln Y_t = {ip:.3f}\,\ln I_{{p,t}} {ig:+.3f}\,\ln I_{{g,t}} {il:+.3f}\,\ln L_t + \mu + ect_t")
    d.tabla(ajt, "VECM: coeficientes de ajuste al equilibrio", dec=3)
    vm = R["vecm"]["vida_media"]
    d.p(f"Las tres elasticidades son significativas al 1%. Un aumento permanente de 1% en la inversión privada se "
        f"asocia con un PBI {ip:.2f}% mayor en el largo plazo y un aumento de 1% en la población ocupada con un PBI "
        f"{il:.2f}% mayor. La inversión pública muestra una elasticidad negativa ({ig:.2f}). El coeficiente de ajuste "
        f"del PBI es negativo y significativo (α = {R['vecm']['alfa_pbi']:.3f}, p = {R['vecm']['p_alfa_pbi']:.3f}): "
        f"cuando el producto se ubica por encima de su nivel de equilibrio, se corrige "
        f"{abs(R['vecm']['alfa_pbi'])*100:.1f}% de la brecha cada trimestre"
        + (f", con una vida media de {vm:.1f} trimestres." if vm else "."))

    d.h("4.7 Robustez de la relación de largo plazo", 2)
    rt = rob.copy()
    for c in ("Inversión privada", "Inversión pública", "PEA ocupada"):
        rt[c] = [con_estrellas(v, p) for v, p in zip(rob[c], rob[f"p {c}"])]
    rt = rt[["especificación", "Inversión privada", "Inversión pública", "PEA ocupada"]]
    rt.columns = ["Especificación", "Inversión privada", "Inversión pública", "PEA ocupada"]
    d.tabla(rt, "Elasticidades de largo plazo bajo especificaciones alternativas",
            nota="Nota: *** p<0.01, ** p<0.05, * p<0.10. DOLS con errores HAC. " + FUENTE)
    pri_pos = (rob["Inversión privada"] > 0).all()
    pub_neg = (rob["Inversión pública"] < 0).all()
    d.p(f"La inversión privada mantiene un efecto positivo en {'todas las' if pri_pos else 'la mayoría de las'} "
        f"especificaciones, con elasticidades entre {rob['Inversión privada'].min():.2f} y "
        f"{rob['Inversión privada'].max():.2f}; la inversión pública conserva el signo negativo en "
        f"{'todas' if pub_neg else 'la mayoría'}. Excluir los trimestres retropolados de la PEA prácticamente no cambia "
        "los resultados. En la submuestra previa a la pandemia la elasticidad de la inversión privada es menor, lo que "
        "concuerda con los quiebres estructurales detectados. La elasticidad del empleo es la más sensible: cuando se "
        "incluye una tendencia determinística (que captura el crecimiento de la PTF) cae a "
        f"{rob.loc[rob['especificación'].str.contains('tendencia'),'PEA ocupada'].iloc[0]:.2f} y deja de ser "
        "significativa, por lo que su magnitud en el VECM recoge en parte la tendencia común de productividad. En el "
        f"DOLS con tendencia, la suma de elasticidades es {R['crs']['suma']:.2f} (prueba de Wald de suma unitaria: "
        f"p = {R['crs']['p']:.3f}).")
    d.p(f"La prueba de límites ARDL arroja un estadístico F = {ar['F']:.2f}, con p-valor de {ar['p_sup']:.3f} frente a "
        f"la cota superior I(1), lo que respalda la existencia de una relación de largo plazo al 5%. No obstante, el "
        f"coeficiente del PBI rezagado en la ecuación uniecuacional es cercano a cero ({ar['ecm']:.3f}), por lo que la "
        "corrección de errores se identifica mejor en el sistema VECM que en una sola ecuación; las elasticidades "
        "ARDL resultan imprecisas y no se usan para la interpretación.")

    d.h("4.8 Funciones impulso-respuesta", 2)
    d.figura("03_irf_vecm.png", "Respuesta del PBI a choques de una desviación estándar (VECM, bandas bootstrap de 90%)")
    sig = lambda v: "significativa" if irf[v]["sig20"] else "no significativa"
    d.p(f"Un choque de inversión privada eleva el PBI en {irf['Inversión privada']['h4']:.2f}% al cabo de un año y "
        f"en {irf['Inversión privada']['h20']:.2f}% después de cinco años, respuesta permanente y "
        f"{sig('Inversión privada')} al 90%. El choque de empleo genera un efecto de "
        f"{irf['PEA ocupada']['h20']:.2f}% ({sig('PEA ocupada')}). El choque de inversión pública produce una respuesta "
        f"de {irf['Inversión pública']['h20']:.2f}% a cinco años, {sig('Inversión pública')}: la banda de confianza "
        "incluye el cero, lo que matiza la lectura del coeficiente negativo de largo plazo.")
    d.figura("04_irf_var_diferencias.png", "Respuesta acumulada del PBI en el VAR en diferencias (bandas Monte Carlo de 90%)")

    d.h("4.9 Descomposición de la varianza", 2)
    fv = leer("15_descomposicion_varianza_pbi")
    d.tabla(fv[fv["trimestre"].isin([1, 2, 4, 8, 12])].astype({"trimestre": int}),
            "Descomposición de la varianza del error de pronóstico del PBI (%)", dec=2)
    d.figura("05_descomposicion_varianza.png", "Descomposición de la varianza del PBI", ancho=13)
    d.p(f"A doce trimestres, {fe['PBI']:.1f}% de la varianza del error de pronóstico del PBI se explica por sus "
        f"propios choques, {fe['Inversión privada']:.1f}% por la inversión privada, {fe['Inversión pública']:.1f}% "
        f"por la inversión pública y {fe['PEA ocupada']:.1f}% por el empleo. Entre los determinantes considerados, la "
        "inversión privada es la principal fuente de fluctuaciones de corto plazo del producto.")

    d.h("4.10 Causalidad", 2)
    g = leer("13_granger").rename(columns={"p_valor": "p-valor"})
    d.tabla(g, f"Causalidad de Granger en el VAR en diferencias (p = {R['var']['p']})", dec=3)
    t = leer("14_toda_yamamoto").rename(columns={"p_valor": "p-valor"})
    d.tabla(t, "Causalidad de Toda-Yamamoto (VAR en niveles, p + dmax rezagos)", dec=3, fuente_pt=7.5)
    d.p(f"La causalidad es unidireccional desde la inversión privada hacia el PBI: se rechaza que la inversión privada "
        f"no cause al PBI (p = {gr['ΔI privada no causa a ΔPBI']:.3f}) pero no lo contrario "
        f"(p = {gr['ΔPBI no causa a ΔI privada']:.3f}). El resultado se mantiene con cuatro rezagos "
        f"(p = {gr4['ΔI privada no causa a ΔPBI']:.3f}) y con Toda-Yamamoto (p = {ty['I privada no causa a PBI']:.3f}). "
        f"No se encuentra causalidad de la inversión pública (p = {gr['ΔI pública no causa a ΔPBI']:.3f}) ni del "
        f"empleo (p = {gr['ΔPEA ocupada no causa a ΔPBI']:.3f}) hacia el PBI en el corto plazo.")

    d.h("4.11 Diagnóstico", 2)
    dg = leer("12_diagnosticos_var").rename(columns={"prueba": "Prueba", "estadístico": "Estadístico",
                                                     "p_valor": "p-valor"})
    d.tabla(dg, "Pruebas de diagnóstico del VAR", dec=3)
    dd = {x["prueba"]: x for x in R["diagnosticos"]}
    port = next(v for k, v in dd.items() if k.startswith("Portmanteau"))
    raiz = next(v for k, v in dd.items() if k.startswith("Raíz"))
    d.p(f"No hay evidencia de autocorrelación residual (Portmanteau, p = {port['p_valor']:.3f}) ni de efectos ARCH, y "
        f"el sistema es estable (raíz máxima = {raiz['estadístico']:.3f} < 1). Se rechaza la normalidad conjunta, "
        "algo habitual en series con choques extremos como los de 2020; por ello las bandas de confianza se obtienen "
        "por bootstrap y la inferencia usa errores robustos.")

    d.h(f"4.12 Validación fuera de muestra y pronóstico {pr['anio']}", 2)
    d.tabla(val, "Error de pronóstico del PBI desestacionalizado, 2024T1 en adelante (%)", dec=2)
    d.p(f"El modelo con menor error es {mejor['modelo']} (RMSE = {mejor['RMSE (%)']:.2f}%), seguido muy de cerca por el "
        f"VAR en diferencias ({rmse['VAR en diferencias']:.2f}%). Ambos superan ampliamente al paseo aleatorio "
        f"({rmse['Paseo aleatorio con deriva']:.2f}%), mientras que el VECM ({rmse['VECM']:.2f}%) es el menos preciso "
        "a corto plazo: su fortaleza es identificar la relación de equilibrio, no pronosticar trimestre a trimestre. "
        "Por ello el pronóstico central se obtiene con el VAR en diferencias, el mejor modelo multivariado, y el VECM "
        "se reporta como escenario alternativo.")
    pt = leer("18_pronostico_pbi_2026")[["trimestre", "pbi", "pbi_inf95", "pbi_sup95", "pbi_vecm"]]
    pt.columns = ["Trimestre", "PBI (VAR)", "Límite inferior 95%", "Límite superior 95%", "PBI (VECM)"]
    d.tabla(pt, "Pronóstico del PBI trimestral (millones de soles de 2007)", dec=0)
    d.figura("06_pronostico.png", "Validación fuera de muestra y pronóstico del PBI")
    d.p(f"Combinando los trimestres observados de {pr['anio']} con los pronosticados, el PBI de {pr['anio']} "
        f"alcanzaría S/ {pr['pbi_anual']/1000:,.1f} mil millones de 2007, lo que implica un crecimiento de "
        f"{pr['crec']:.1f}% (intervalo de 95%: {pr['crec_inf']:.1f}% a {pr['crec_sup']:.1f}%). El escenario VECM "
        f"proyecta {pr['crec_vecm']:.1f}%.")

    d.h("4.13 Contabilidad del crecimiento", 2)
    cp = pd.DataFrame(cont).T.reset_index()
    cp.columns = ["Periodo", "Capital privado", "Capital público", "Trabajo", "Crecimiento PBI", "PTF"]
    cp = cp[["Periodo", "Crecimiento PBI", "Capital privado", "Capital público", "Trabajo", "PTF"]]
    d.tabla(cp, "Contabilidad del crecimiento por periodos (promedio anual, puntos porcentuales)", dec=2)
    d.figura("07_contabilidad_crecimiento.png", "Contribuciones anuales al crecimiento del PBI")
    c1, c4 = cont["2001-2008"], cont["2020-2025"]
    d.p(f"Entre 2001 y 2008 la PTF aportó {c1['ptf']:.1f} puntos del crecimiento promedio de {c1['crec_pbi']:.1f}%, "
        f"mientras que entre 2020 y 2025 su contribución fue de {c4['ptf']:.1f} puntos. La acumulación de capital "
        f"privado pasó de aportar {c1['aporte_k_pri']:.1f} puntos en 2001–2008 a {cont['2009-2013']['aporte_k_pri']:.1f} "
        "en 2009–2013, y desde entonces su contribución ha disminuido. La desaceleración del crecimiento peruano "
        "responde, sobre todo, al agotamiento de las ganancias de productividad. Estos resultados dependen de los "
        "supuestos de depreciación y participaciones factoriales y de usar el empleo de Lima como proxy nacional.")

    # ---------- 5. Discusión ----------
    d.h("5. Discusión")
    d.p("Los resultados confirman, con una muestra más larga y técnicas más exigentes, la conclusión central del "
        "enfoque de Paredes-Soria et al. (2025): el PBI, la inversión y el empleo comparten una relación de equilibrio "
        "de largo plazo, y la inversión privada es el motor más robusto del producto peruano. Este hallazgo es "
        "consistente con el crecimiento liderado por la inversión minera y de infraestructura privada del periodo "
        "2004–2013 y con la caída del crecimiento cuando la inversión privada se contrajo en 2014–2017 y en 2023.")
    d.p("La elasticidad negativa de la inversión pública no debe interpretarse como evidencia de que la "
        "infraestructura es improductiva. Tres explicaciones son compatibles con los datos: (i) la inversión pública "
        "peruana se ha usado de forma contracíclica, lo que genera una correlación negativa con el producto; (ii) "
        "existen problemas de calidad y eficiencia en su ejecución, documentados por la Contraloría y el MEF; y (iii) "
        "puede desplazar parcialmente a la inversión privada. Además, la respuesta impulso del PBI a la inversión pública "
        "no es significativa y la causalidad de Granger no se verifica, lo que indica que su efecto es, como mínimo, "
        "incierto.")
    d.p("La contribución del empleo es positiva y significativa en el VECM, aunque su magnitud es sensible a la "
        "inclusión de una tendencia de productividad. La mejora metodológica más importante respecto al artículo base "
        "es mostrar qué resultados resisten distintas especificaciones —el efecto de la inversión privada— y cuáles "
        "dependen de supuestos —la magnitud de la elasticidad del empleo y de la inversión pública—.")

    # ---------- 6. Conclusiones ----------
    d.h("6. Conclusiones y recomendaciones")
    d.viñetas([
        f"Existe una relación de cointegración entre el PBI, la inversión privada, la inversión pública y el empleo "
        f"en el Perú durante 2000T1–{fin}; el PBI se ajusta al equilibrio a una velocidad de "
        f"{abs(R['vecm']['alfa_pbi'])*100:.1f}% por trimestre.",
        f"La inversión privada es el determinante más robusto: elasticidad de largo plazo de {ip:.2f}, causalidad de "
        "Granger y Toda-Yamamoto hacia el PBI y respuesta impulso positiva y permanente.",
        f"El empleo tiene un efecto positivo ({il:.2f} en el VECM), aunque sensible a la especificación.",
        "La inversión pública no muestra un efecto positivo identificable sobre el producto; su relación de largo plazo "
        "es negativa y su efecto de corto plazo no es significativo.",
        f"El modelo proyecta un crecimiento de {pr['crec']:.1f}% para {pr['anio']}, con un intervalo de 95% entre "
        f"{pr['crec_inf']:.1f}% y {pr['crec_sup']:.1f}%.",
        "Recomendaciones de política: priorizar la predictibilidad institucional y regulatoria para sostener la "
        "inversión privada; mejorar la calidad, selección y ejecución de la inversión pública (y su complementariedad "
        "con la privada, por ejemplo mediante asociaciones público-privadas y obras por impuestos); y promover la "
        "productividad, cuya contribución al crecimiento se ha reducido.",
    ])

    d.h("Limitaciones")
    d.viñetas([
        "La PEA ocupada corresponde a Lima Metropolitana y no al total nacional; los trimestres iniciales son retropolados.",
        f"Los datos observados llegan a {fin}; el resto de {pr['anio']} es un pronóstico.",
        "Se usan flujos de inversión como en el artículo base; los stocks de capital dependen de supuestos de depreciación.",
        "El análisis no incluye capital humano, términos de intercambio ni variables institucionales, que podrían "
        "explicar parte de la PTF.",
        "Los resultados son asociaciones dinámicas; la identificación causal estructural requeriría supuestos adicionales.",
    ])

    d.h("Reproducibilidad")
    d.p("Todo el análisis se ejecuta con «python main.py» desde el repositorio "
        "https://github.com/AngelR24xlp/modelo-solow-peru. Los módulos src/datos.py, src/pruebas.py y src/modelos.py "
        "contienen la descarga de datos, las pruebas y los modelos; src/informe.py genera este documento. Las tablas "
        "se guardan en outputs/tablas y las figuras en outputs/figuras.")

    d.h("Referencias")
    refs = [
        "Aschauer, D. A. (1989). Is public expenditure productive? Journal of Monetary Economics, 23(2), 177–200.",
        "Bai, J., & Perron, P. (2003). Computation and analysis of multiple structural change models. Journal of "
        "Applied Econometrics, 18(1), 1–22.",
        "Banco Central de Reserva del Perú (2026). Series estadísticas. https://estadisticas.bcrp.gob.pe",
        "Barro, R. J. (1990). Government spending in a simple model of endogenous growth. Journal of Political "
        "Economy, 98(5), S103–S125.",
        "Cleveland, R. B., Cleveland, W. S., McRae, J. E., & Terpenning, I. (1990). STL: A seasonal-trend "
        "decomposition procedure based on loess. Journal of Official Statistics, 6(1), 3–73.",
        "Johansen, S. (1991). Estimation and hypothesis testing of cointegration vectors in Gaussian vector "
        "autoregressive models. Econometrica, 59(6), 1551–1580.",
        "Kwiatkowski, D., Phillips, P. C. B., Schmidt, P., & Shin, Y. (1992). Testing the null hypothesis of "
        "stationarity against the alternative of a unit root. Journal of Econometrics, 54(1–3), 159–178.",
        "Mankiw, N. G., Romer, D., & Weil, D. N. (1992). A contribution to the empirics of economic growth. "
        "Quarterly Journal of Economics, 107(2), 407–437.",
        "Paredes-Soria, A., Paredes-Egúsquiza, A. S., Villagómez-Chinchay, J. A., De Velazco Borda, J. L., & "
        "Chávez-Díaz, J. M. (2025). Adapting the extended Solow model: The impact of output determinants on economic "
        "growth in Peru from 2000 to 2022. Journal of Risk and Financial Management, 18(3), 112. "
        "https://doi.org/10.3390/jrfm18030112",
        "Pesaran, M. H., Shin, Y., & Smith, R. J. (2001). Bounds testing approaches to the analysis of level "
        "relationships. Journal of Applied Econometrics, 16(3), 289–326.",
        "Phillips, P. C. B., & Perron, P. (1988). Testing for a unit root in time series regression. Biometrika, "
        "75(2), 335–346.",
        "Solow, R. M. (1956). A contribution to the theory of economic growth. Quarterly Journal of Economics, "
        "70(1), 65–94.",
        "Stock, J. H., & Watson, M. W. (1993). A simple estimator of cointegrating vectors in higher order integrated "
        "systems. Econometrica, 61(4), 783–820.",
        "Toda, H. Y., & Yamamoto, T. (1995). Statistical inference in vector autoregressions with possibly integrated "
        "processes. Journal of Econometrics, 66(1–2), 225–250.",
        "Zivot, E., & Andrews, D. W. K. (1992). Further evidence on the great crash, the oil-price shock, and the "
        "unit-root hypothesis. Journal of Business & Economic Statistics, 10(3), 251–270.",
    ]
    for ref in refs:
        par = doc.add_paragraph(ref)
        par.paragraph_format.left_indent = Cm(1)
        par.paragraph_format.first_line_indent = Cm(-1)

    ruta.parent.mkdir(parents=True, exist_ok=True)
    doc.save(ruta)
    print(f"Informe guardado en {ruta}")
    return ruta
