"""Genera la presentación PowerPoint a partir de los resultados producidos por main.py.

Autor: Angel Marchán Collazos
Fecha: 10 de octubre de 2026
"""
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Cm, Pt

from src import AUTOR, FECHA, FECHA_ISO, INSTITUCION

RAIZ = Path(__file__).resolve().parents[1]
FIG, TAB = RAIZ / "outputs" / "figuras", RAIZ / "outputs" / "tablas"
DIR_PPT = RAIZ / "presentacion"
AZUL, ROJO, GRIS, BLANCO = (RGBColor(0x1F, 0x4E, 0x79), RGBColor(0xC0, 0x50, 0x4D),
                            RGBColor(0x59, 0x59, 0x59), RGBColor(0xFF, 0xFF, 0xFF))
ANCHO, ALTO = Cm(33.867), Cm(19.05)


class Diapositivas:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = ANCHO, ALTO
        self.n = 0
        (DIR_PPT / "ecuaciones").mkdir(parents=True, exist_ok=True)

    def _texto(self, s, x, y, w, h, texto, tam=16, color=GRIS, negrita=False, alinear=PP_ALIGN.LEFT):
        tf = s.shapes.add_textbox(x, y, w, h).text_frame
        tf.word_wrap = True
        for i, linea in enumerate(texto.split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = alinear
            r = p.add_run()
            r.text = linea
            r.font.size, r.font.bold, r.font.color.rgb = Pt(tam), negrita, color
        return tf

    def _rect(self, s, x, y, w, h, color):
        r = s.shapes.add_shape(1, x, y, w, h)
        r.fill.solid()
        r.fill.fore_color.rgb = color
        r.line.fill.background()
        return r

    def nueva(self, titulo):
        self.n += 1
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        self._rect(s, 0, 0, ANCHO, Cm(2.6), AZUL)
        self._texto(s, Cm(1.2), Cm(0.45), Cm(31), Cm(1.8), titulo, 28, BLANCO, True)
        self._rect(s, 0, ALTO - Cm(1.1), ANCHO, Cm(0.06), AZUL)
        self._texto(s, Cm(1.2), ALTO - Cm(1.0), Cm(25), Cm(0.8),
                    f"{AUTOR}  |  {INSTITUCION}  |  {FECHA}", 10, GRIS)
        self._texto(s, ANCHO - Cm(3), ALTO - Cm(1.0), Cm(2), Cm(0.8), str(self.n), 10, GRIS, alinear=PP_ALIGN.RIGHT)
        return s

    def vinetas(self, s, items, x=Cm(1.5), y=Cm(3.3), w=Cm(31), h=Cm(14), tam=18):
        tf = s.shapes.add_textbox(x, y, w, h).text_frame
        tf.word_wrap = True
        for i, it in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(9)
            r0 = p.add_run()
            r0.text = "▪ "
            r0.font.color.rgb, r0.font.size = ROJO, Pt(tam)
            for j, trozo in enumerate(it.split("**")):
                r = p.add_run()
                r.text = trozo
                r.font.size, r.font.bold = Pt(tam), j % 2 == 1
                r.font.color.rgb = AZUL if j % 2 == 1 else GRIS

    def imagen(self, s, nombre, x, y, w=None, h=None):
        s.shapes.add_picture(str(FIG / nombre), x, y, width=w, height=h)

    def tabla(self, s, df, x, y, w, tam=12, dec=3):
        filas, cols = df.shape[0] + 1, df.shape[1]
        t = s.shapes.add_table(filas, cols, x, y, w, Cm(0.9) * filas).table
        for j, c in enumerate(df.columns):
            t.cell(0, j).text = str(c)
        for i, (_, fila) in enumerate(df.iterrows(), start=1):
            for j, v in enumerate(fila):
                t.cell(i, j).text = f"{v:,.{dec}f}" if isinstance(v, float) else str(v)
        for i in range(filas):
            for j in range(cols):
                for p in t.cell(i, j).text_frame.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(tam)
                        r.font.bold = i == 0
        return t

    def ecuacion(self, s, latex, x, y, h=Cm(1.6), w=None):
        ruta = DIR_PPT / "ecuaciones" / f"ec{abs(hash(latex))}.png"
        fig = plt.figure(figsize=(14, 1.4))
        fig.text(0.5, 0.5, f"${latex}$", fontsize=22, ha="center", va="center", color="#1f4e79")
        fig.savefig(ruta, dpi=200, bbox_inches="tight", pad_inches=0.05, transparent=True)
        plt.close(fig)
        s.shapes.add_picture(str(ruta), x, y, width=w, height=None if w else h)

    def nota(self, s, texto, y=ALTO - Cm(1.9)):
        self._texto(s, Cm(1.2), y, Cm(31), Cm(0.8), texto, 11, GRIS)


def generar_presentacion(R, ruta=None):
    ruta = Path(ruta or DIR_PPT / "Presentacion_Modelo_Solow_Peru_2000_2026.pptx")
    D = Diapositivas()
    lp = R["vecm"]["lp"]
    ip, ig, il = (lp[k]["elasticidad"] for k in ("I privada", "I pública", "PEA ocupada"))
    pr, jo, ar = R["pronostico"], R["johansen"], R["ardl"]
    fin = R["periodo"].split("-")[1]
    gr = {g["H0"]: g["p_valor"] for g in R["granger"]}
    ty = {g["H0"]: g["p_valor"] for g in R["toda_yamamoto"]}
    fe = R["fevd"]["12"] if "12" in R["fevd"] else R["fevd"][12]
    irf = R["irf"]
    val = pd.DataFrame(R["validacion"])
    cont = R["contabilidad"]
    alfa = abs(R["vecm"]["alfa_pbi"]) * 100

    # 1. Portada
    D.n += 1
    s = D.prs.slides.add_slide(D.prs.slide_layouts[6])
    D._rect(s, 0, 0, ANCHO, ALTO, AZUL)
    D._rect(s, Cm(1.5), Cm(10.0), Cm(4), Cm(0.15), ROJO)
    D._texto(s, Cm(1.5), Cm(3), Cm(30), Cm(4.5),
             "Determinantes del producto y crecimiento\neconómico en el Perú, 2000–2026", 30, BLANCO, True)
    D._texto(s, Cm(1.5), Cm(7.9), Cm(30), Cm(1.8),
             "Una extensión robusta del modelo de Solow adaptado: cointegración, VECM, ARDL y pronóstico",
             18, RGBColor(0xDD, 0xE6, 0xF0))
    D._texto(s, Cm(1.5), Cm(10.8), Cm(30), Cm(4), f"{AUTOR}\n{INSTITUCION}\nLima, {FECHA}", 22, BLANCO, True)
    D._texto(s, Cm(1.5), Cm(16.3), Cm(31), Cm(1.5),
             "Basado en Paredes-Soria et al. (2025), Journal of Risk and Financial Management, 18(3), 112. "
             "Resultados generados con el código Python del autor.", 12, RGBColor(0xDD, 0xE6, 0xF0))

    s = D.nueva("Motivación y objetivo")
    D.vinetas(s, [
        "El Perú creció **más de 6% anual** entre 2002 y 2013, pero se desaceleró desde 2014, cayó "
        "**10.9% en 2020** y la inversión privada se contrajo en 2023.",
        "Pregunta: ¿qué factores sostienen el producto peruano en el largo plazo: **inversión privada, inversión "
        "pública (infraestructura) o empleo**?",
        f"Objetivo: estimar un **modelo de Solow ampliado** para 2000T1–{fin} con técnicas robustas de series de "
        f"tiempo y proyectar el PBI de {pr['anio']}.",
        "Punto de partida: Paredes-Soria et al. (2025), que estudian el periodo 2000–2022 con VAR/VECM.",
    ])

    s = D.nueva("Aporte respecto al paper de referencia")
    comp = pd.DataFrame({
        "Etapa": ["Periodo", "Raíz unitaria", "Quiebres y COVID", "Largo plazo", "Corto plazo", "Validación"],
        "Paper base": ["2000–2022", "ADF", "—", "MCO, Johansen, VECM", "IRF, FEVD, Granger", "—"],
        "Este trabajo": [f"2000T1–{fin} + pronóstico", "ADF, PP, KPSS, Zivot-Andrews",
                         "Bai-Perron, STL robusto, dummies 2020", "Johansen, VECM, DOLS, ARDL, HAC",
                         "IRF bootstrap, FEVD, Granger, Toda-Yamamoto", "Fuera de muestra, contabilidad del crecimiento"],
    })
    D.tabla(s, comp, Cm(1.5), Cm(3.5), Cm(30.8), tam=15)

    s = D.nueva("Marco teórico: modelo de Solow ampliado")
    D.ecuacion(s, r"Y_t = A_t\, K_{p,t}^{\alpha}\, K_{g,t}^{\gamma}\, L_t^{\beta}", Cm(9), Cm(3.4))
    D.ecuacion(s, r"\ln Y_t = a + \alpha \ln I_{p,t} + \gamma \ln I_{g,t} + \beta \ln L_t + u_t", Cm(5), Cm(5.6))
    D.vinetas(s, [
        "Solow (1956) y Mankiw, Romer y Weil (1992): el producto depende de capital, trabajo y productividad.",
        "Aschauer (1989), Barro (1990): el capital público (infraestructura) como factor productivo.",
        "La inversión pública puede **atraer** (crowding-in) o **desplazar** (crowding-out) a la privada.",
        "Con flujos de inversión, los coeficientes son **elasticidades de largo plazo**, no participaciones factoriales.",
    ], y=Cm(8.2), tam=17)

    s = D.nueva("Datos: BCRP, frecuencia trimestral")
    datos = pd.DataFrame({
        "Variable": ["PBI real", "Inversión bruta fija privada", "Inversión bruta fija pública", "PEA ocupada (Lima)"],
        "Serie BCRP": ["PN02538AQ", "PN02533AQ", "PN02534AQ", "PN38051GM"],
        "Unidad": ["Mill. S/ 2007", "Mill. S/ 2007", "Mill. S/ 2007", "Miles de personas"],
    })
    D.tabla(s, datos, Cm(1.5), Cm(3.4), Cm(30.8), tam=15)
    D.vinetas(s, [
        f"**{R['n_obs']} trimestres** (2000T1–{fin}); {' y '.join(pr['trimestres'])} son pronóstico.",
        "Ajuste estacional **STL robusto**; dummies de impulso para **2020T2–2020T4**.",
        f"PEA de {', '.join(R['trimestres_imputados'])} retropolada con el crecimiento del PBI.",
        "Stocks de capital por **inventario perpetuo** (δ = 5% privado, 4% público) para la contabilidad.",
    ], y=Cm(8.6), tam=16)

    s = D.nueva("Evolución de las variables")
    D.imagen(s, "01_variables.png", Cm(4.5), Cm(2.9), h=Cm(14.8))

    s = D.nueva("Orden de integración y quiebres estructurales")
    ur = pd.read_csv(TAB / "03_raiz_unitaria.csv")[["variable", "ADF nivel (p)", "KPSS nivel (p)",
                                                    "ZA nivel (p)", "Quiebre ZA", "ADF dif. (p)",
                                                    "Orden de integración"]].rename(columns={"variable": "Variable", "Orden de integración": "Orden"})
    D.tabla(s, ur, Cm(1), Cm(3.3), Cm(16.2), tam=10)
    D.imagen(s, "02_quiebres_bai_perron.png", Cm(17.5), Cm(3.3), w=Cm(15.5))
    D.vinetas(s, [
        "PBI e inversiones: **I(1)**; PEA ocupada: estacionaria en tendencia.",
        f"Bai-Perron (BIC): quiebres en **{', '.join(R['quiebres_bai_perron'])}**.",
        "La mezcla I(0)/I(1) justifica usar también **ARDL y Toda-Yamamoto**.",
    ], x=Cm(1), y=Cm(10.8), w=Cm(31), tam=16)

    s = D.nueva("Cointegración y relación de largo plazo (VECM)")
    lpt = pd.read_csv(TAB / "07_vecm_largo_plazo.csv")
    lpt.columns = ["Variable", "Coef.", "E.E.", "z", "p-valor"]
    D.ecuacion(s, rf"\ln Y_t = {ip:.3f}\,\ln I_{{p,t}} {ig:+.3f}\,\ln I_{{g,t}} {il:+.3f}\,\ln L_t", Cm(7), Cm(3.1), w=Cm(20))
    D.tabla(s, lpt, Cm(1.5), Cm(5.6), Cm(15), tam=14)
    D.vinetas(s, [
        f"Johansen (traza): **rango = {jo['rango']}** ({jo['traza0']:.1f} > {jo['vc0']:.1f}; "
        f"{jo['traza1']:.1f} < {jo['vc1']:.1f}).",
        f"+1% inversión privada → **+{ip:.2f}% PBI** de largo plazo.",
        f"+1% empleo → **+{il:.2f}% PBI**; inversión pública: **{ig:.2f}**.",
        f"El PBI corrige **{alfa:.1f}%** del desequilibrio por trimestre (p = {R['vecm']['p_alfa_pbi']:.3f}).",
    ], x=Cm(17.5), y=Cm(5.4), w=Cm(15.5), tam=16)
    D.vinetas(s, [f"Prueba de límites ARDL: F = {ar['F']:.2f}, p(I(1)) = {ar['p_sup']:.3f} → respalda la "
                  "relación de largo plazo."], x=Cm(1.5), y=Cm(10.4), w=Cm(15), tam=15)

    s = D.nueva("Robustez de las elasticidades de largo plazo")
    rob = pd.DataFrame(R["robustez"])
    est = lambda p: "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""
    rt = pd.DataFrame({"Especificación": rob["especificación"]})
    for c in ("Inversión privada", "Inversión pública", "PEA ocupada"):
        rt[c] = [f"{v:.3f}{est(p)}" for v, p in zip(rob[c], rob[f"p {c}"])]
    D.tabla(s, rt, Cm(1.5), Cm(3.3), Cm(30.8), tam=13)
    D.nota(s, "*** p<0.01, ** p<0.05, * p<0.10. La inversión privada es positiva y la pública negativa en todas las "
              "especificaciones.")

    s = D.nueva("Impulso-respuesta del PBI (VECM, bootstrap 90%)")
    D.imagen(s, "03_irf_vecm.png", Cm(1.2), Cm(3.0), w=Cm(31.5))
    sig = lambda v: "significativo" if irf[v]["sig20"] else "no significativo"
    D.vinetas(s, [
        f"Inversión privada: **+{irf['Inversión privada']['h4']:.2f}%** a 1 año y "
        f"**+{irf['Inversión privada']['h20']:.2f}%** a 5 años ({sig('Inversión privada')}).",
        f"Empleo: **{irf['PEA ocupada']['h20']:+.2f}%** a 5 años ({sig('PEA ocupada')}); inversión pública: "
        f"**{irf['Inversión pública']['h20']:+.2f}%** ({sig('Inversión pública')}).",
    ], y=Cm(13.3), tam=16)

    s = D.nueva("Descomposición de varianza y causalidad")
    D.imagen(s, "05_descomposicion_varianza.png", Cm(1), Cm(3.2), w=Cm(16))
    D.vinetas(s, [
        f"A 12 trimestres: PBI propio **{fe['PBI']:.1f}%**, inversión privada **{fe['Inversión privada']:.1f}%**, "
        f"pública {fe['Inversión pública']:.1f}%, empleo {fe['PEA ocupada']:.1f}%.",
        f"Granger: inversión privada → PBI (**p = {gr['ΔI privada no causa a ΔPBI']:.3f}**); "
        f"PBI → inversión privada (p = {gr['ΔPBI no causa a ΔI privada']:.3f}).",
        f"Toda-Yamamoto lo confirma (**p = {ty['I privada no causa a PBI']:.3f}**).",
        f"Sin causalidad de la inversión pública (p = {gr['ΔI pública no causa a ΔPBI']:.3f}) ni del empleo "
        f"(p = {gr['ΔPEA ocupada no causa a ΔPBI']:.3f}).",
    ], x=Cm(17.5), y=Cm(3.4), w=Cm(15.5), tam=16)

    s = D.nueva(f"Validación fuera de muestra y pronóstico {pr['anio']}")
    D.imagen(s, "06_pronostico.png", Cm(1), Cm(2.9), w=Cm(21))
    v = val.copy()
    v.columns = ["Modelo", "RMSE (%)", "MAE (%)"]
    D.tabla(s, v, Cm(22.5), Cm(3.2), Cm(10.6), tam=11, dec=2)
    D.vinetas(s, [
        f"Crecimiento del PBI {pr['anio']}: **{pr['crec']:.1f}%**",
        f"IC 95%: {pr['crec_inf']:.1f}% a {pr['crec_sup']:.1f}%",
        f"Escenario VECM: {pr['crec_vecm']:.1f}%",
    ], x=Cm(22.5), y=Cm(8.4), w=Cm(10.6), tam=16)
    D.nota(s, "Pronóstico central: VAR en diferencias, el mejor modelo multivariado en la validación 2024T1 en adelante.")

    s = D.nueva("Contabilidad del crecimiento")
    D.imagen(s, "07_contabilidad_crecimiento.png", Cm(1), Cm(2.9), w=Cm(21.5))
    D.vinetas(s, [
        f"2001–2008: PBI {cont['2001-2008']['crec_pbi']:.1f}%, PTF **{cont['2001-2008']['ptf']:.1f} pp**.",
        f"2014–2019: PBI {cont['2014-2019']['crec_pbi']:.1f}%, PTF **{cont['2014-2019']['ptf']:.1f} pp**.",
        f"2020–2025: PBI {cont['2020-2025']['crec_pbi']:.1f}%, PTF **{cont['2020-2025']['ptf']:.1f} pp**.",
        "La desaceleración refleja sobre todo el **agotamiento de la productividad**.",
    ], x=Cm(23), y=Cm(3.4), w=Cm(10), tam=15)

    s = D.nueva("Conclusiones")
    D.vinetas(s, [
        f"PBI, inversión y empleo están **cointegrados**; el PBI corrige {alfa:.1f}% del desequilibrio por trimestre.",
        f"La **inversión privada** es el determinante más robusto: elasticidad {ip:.2f}, causalidad de Granger y "
        "Toda-Yamamoto, respuesta impulso positiva y permanente.",
        f"El **empleo** aporta positivamente ({il:.2f}), pero su magnitud es sensible a la especificación.",
        "La **inversión pública** no muestra un efecto positivo identificable: posible uso contracíclico, "
        "problemas de eficiencia o desplazamiento de la privada.",
        f"Proyección: crecimiento de **{pr['crec']:.1f}%** en {pr['anio']}.",
    ], tam=18)

    s = D.nueva("Recomendaciones y limitaciones")
    D._texto(s, Cm(1.5), Cm(3.2), Cm(15), Cm(1), "Recomendaciones", 20, AZUL, True)
    D.vinetas(s, [
        "Predictibilidad institucional y regulatoria para sostener la inversión privada.",
        "Mejorar selección, calidad y ejecución de la inversión pública; APP y obras por impuestos.",
        "Agenda de productividad: capital humano, formalización e innovación.",
    ], x=Cm(1.5), y=Cm(4.4), w=Cm(15), tam=16)
    D._texto(s, Cm(17.5), Cm(3.2), Cm(15), Cm(1), "Limitaciones", 20, ROJO, True)
    D.vinetas(s, [
        "PEA de Lima Metropolitana como proxy del empleo nacional.",
        f"Datos observados hasta {fin}; el resto de {pr['anio']} es pronóstico.",
        "Supuestos de depreciación y participaciones en la contabilidad.",
        "Asociaciones dinámicas, no identificación causal estructural.",
    ], x=Cm(17.5), y=Cm(4.4), w=Cm(15.5), tam=16)

    D.n += 1
    s = D.prs.slides.add_slide(D.prs.slide_layouts[6])
    D._rect(s, 0, 0, ANCHO, ALTO, AZUL)
    D._texto(s, Cm(1.5), Cm(5.5), Cm(31), Cm(2.5), "¡Gracias!", 44, BLANCO, True, PP_ALIGN.CENTER)
    D._texto(s, Cm(1.5), Cm(8.5), Cm(31), Cm(4), f"{AUTOR}\n{INSTITUCION}\n{FECHA}", 20, BLANCO,
             alinear=PP_ALIGN.CENTER)
    D._texto(s, Cm(1.5), Cm(13.5), Cm(31), Cm(1.5), "Código y datos: github.com/AngelR24xlp/modelo-solow-peru",
             16, RGBColor(0xDD, 0xE6, 0xF0), alinear=PP_ALIGN.CENTER)

    cp = D.prs.core_properties
    cp.author = cp.last_modified_by = AUTOR
    cp.title = "Determinantes del producto y crecimiento económico en el Perú, 2000-2026"
    cp.created = cp.modified = datetime.fromisoformat(FECHA_ISO)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    D.prs.save(ruta)
    print(f"Presentación guardada en {ruta}")
    return ruta
