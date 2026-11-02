# Modelo de Solow adaptado para el Perú, 2000–2026

**Autor:** Angel Marchán Collazos — Universidad Nacional Mayor de San Marcos  
**Fecha de elaboración:** 10 de octubre de 2026

El modelo estima cómo influyen la **inversión privada**, la **inversión pública** (infraestructura) y la **PEA ocupada** en el **PBI real** del Perú. Usa datos trimestrales del BCRP desde 2000T1 hasta el último trimestre publicado (2026T2) y proyecta el resto de 2026.

## Qué agrega respecto al paper

| Etapa | Paper | Este repositorio |
|---|---|---|
| Periodo | 2000–2022 | 2000T1–2026T2 y pronóstico de 2026T3–T4 |
| Estacionalidad | — | STL robusto |
| Raíz unitaria | ADF | ADF, Phillips-Perron, KPSS, Zivot-Andrews |
| Quiebres | — | Bai-Perron (programación dinámica, BIC) |
| Pandemia | — | Dummies de impulso 2020T2–T4 |
| Largo plazo | MCO, Johansen, VECM | MCO con errores HAC, Johansen con dummies, VECM, DOLS, prueba de límites ARDL |
| Robustez | — | Rezagos alternativos, muestra sin PEA retropolada, periodo pre-COVID, tendencia de PTF |
| Corto plazo | IRF, FEVD, Granger | IRF del VECM con bandas bootstrap, FEVD, Granger, Toda-Yamamoto |
| Diagnóstico | — | Portmanteau, normalidad, estabilidad, ARCH |
| Pronóstico | — | Validación fuera de muestra (VECM, VAR, ARIMA, paseo aleatorio) y pronóstico de 2026 |
| Contabilidad | — | Stocks de capital por inventario perpetuo y residuo de Solow (PTF) |

## Resultados principales

- **Cointegración:** la prueba de la traza de Johansen encuentra un vector de cointegración.
- **Elasticidades de largo plazo (VECM):** inversión privada **0.49**, inversión pública **−0.32** y PEA ocupada **1.60**. Las tres son significativas al 1 %.
- **Corrección hacia el equilibrio:** el PBI corrige el 5.8 % del desequilibrio cada trimestre.
- **Causalidad:** la inversión privada causa al PBI según Granger (p = 0.001) y Toda-Yamamoto (p = 0.003). La inversión pública y la PEA no lo causan.
- **Robustez:** en las 8 especificaciones, la inversión privada tiene signo positivo y la pública, negativo.
- **Pronóstico 2026:** el PBI crecería **3.3 %**, con un intervalo de confianza del 95 % entre 1.4 % y 5.4 %.

## Uso

```bash
pip install -r requirements.txt
python main.py                # usa los datos guardados en data/
python main.py --actualizar   # intenta descargar de nuevo las series del BCRP
python main.py --sin-informe  # solo tablas y figuras (sin Word ni PowerPoint)
```

## Datos

| Variable | Serie BCRP |
|---|---|
| PBI real (mill. S/ 2007) | PN02538AQ |
| Inversión bruta fija privada (mill. S/ 2007) | PN02533AQ |
| Inversión bruta fija pública (mill. S/ 2007) | PN02534AQ |
| PEA ocupada, Lima Metropolitana (miles) | PN38051GM |

## Limitaciones

- **PEA ocupada:** corresponde a Lima Metropolitana, no al total nacional. Los trimestres 2000T1–2001T1 se retropolaron a partir del crecimiento del PBI.
- **Datos de 2026:** los observados llegan solo hasta 2026T2; 2026T3 y 2026T4 son pronósticos.
- **Bloqueo del BCRP:** el portal a veces bloquea las descargas automáticas. En ese caso, `--actualizar` usa las copias guardadas en `data/bcrp/`.
- **Supuestos propios:** las depreciaciones (5 % para el capital privado y 4 % para el público) y las participaciones factoriales usadas en la contabilidad del crecimiento.

## Autoría

Proyecto elaborado por **Angel Marchán Collazos** (UNMSM) 
