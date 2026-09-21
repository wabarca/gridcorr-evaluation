# -*- coding: utf-8 -*-
"""
Stations performance and improvement viewer UI component.
Includes scientific explanations, statistical interpretation, and error distribution metrics.
"""

import os
import glob
import pandas as pd
import numpy as np
import streamlit as st
from ...application.models import AnalysisResult


def render_stations_viewer(result: AnalysisResult) -> None:
    """
    Renderiza el análisis espacial y diagnóstico de mejora en estaciones con explicaciones y estadísticas.
    """
    st.subheader("📍 Desempeño, Distribución de Errores y Diagnóstico en Estaciones")

    improvement_maps = [m for m in result.generated_maps if any(k in os.path.basename(m).lower() for k in ["improvement", "mejora"])]
    boxplots = [p for p in result.generated_plots if "boxplot" in os.path.basename(p).lower()]
    scatters = [p for p in result.generated_plots if "scatter" in os.path.basename(p).lower()]

    if not (improvement_maps or boxplots or scatters):
        st.warning(
            "ℹ️ **¿Por qué no están disponibles los gráficos de desempeño por estación?**\n\n"
            "Los diagramas de dispersión, boxplots y mapas de porcentaje de mejora (ΔRMSE%) se calculan durante el análisis multianual con evaluación estadística habilitada.\n\n"
            "**Causas técnicas habituales:**\n"
            "- La opción **'Generar Productos de Evaluación Estadística (--eval)'** no estuvo activa en la ejecución.\n"
            "- El rango temporal analizado comprende menos de 2 años con observaciones continuas en estaciones.\n"
            "- Las series de estaciones no coinciden en fecha con los archivos NetCDF disponibles.\n\n"
            "**Sugerencia:** Active la casilla de evaluación estadística y asegúrese de que el rango de años contenga registros de estaciones coincidentes."
        )
        return

    st_tab1, st_tab2, st_tab3 = st.tabs([
        "Diagramas de Caja y Distribución (Boxplots)",
        "Diagramas de Dispersión (Scatter Plots)",
        "Mejora Relativa (% ΔRMSE) en Estaciones",
    ])

    def _format_boxplot_label(path: str) -> str:
        bname = os.path.basename(path)
        name_no_ext = os.path.splitext(bname)[0]
        # Example: boxplot_residuals_precip_accum -> Boxplot de Residuos (precip_accum)
        clean = name_no_ext.replace("boxplot_", "").replace("_", " ")
        if "residuals" in clean or "residuos" in clean:
            return f"📦 Residuos: {clean.title()}"
        elif "rmse" in clean:
            return f"📉 RMSE: {clean.title()}"
        return f"📦 {clean.title()}"

    def _format_scatter_label(path: str) -> str:
        bname = os.path.basename(path)
        name_no_ext = os.path.splitext(bname)[0]
        # Example: scatter_obs_vs_grid_precip_accum_ene_1991.png -> Observado vs Rejilla: Ene 1991 (precip_accum)
        # scatter_obs_vs_grid_precip_accum.png -> Observado vs Rejilla: Resumen Global (precip_accum)
        clean = name_no_ext.replace("scatter_obs_vs_grid_", "").replace("scatter_", "")
        parts = clean.split("_")
        if len(parts) >= 3 and parts[-1].isdigit():
            # has period and year at the end, e.g. ['precip', 'accum', 'ene', '1991'] or ['tmax', 'mean', 'aso', '1991']
            period = parts[-2].upper()
            year = parts[-1]
            var = " ".join(parts[:-2])
            return f"📈 Obs vs Rejilla — {period} {year} ({var})"
        elif len(parts) >= 2 and parts[-1].isdigit():
            # has year at the end, e.g. ['precip', 'accum', '1991']
            year = parts[-1]
            var = " ".join(parts[:-1])
            return f"📈 Obs vs Rejilla — Año {year} ({var})"
        else:
            var = " ".join(parts)
            return f"📈 Obs vs Rejilla — Resumen Global ({var})"

    def _format_map_label(path: str) -> str:
        bname = os.path.basename(path)
        name_no_ext = os.path.splitext(bname)[0]
        clean = name_no_ext.replace("map_stations_improvement_", "").replace("map_stations_", "").replace("_", " ")
        return f"🗺️ Mejora % RMSE ({clean})"

    # -------------------------------------------------------------
    # TAB 1: Diagramas de Caja (Boxplots)
    # -------------------------------------------------------------
    with st_tab1:
        with st.expander("📖 **Explicación Científica e Interpretación: Diagramas de Caja (Boxplots)**", expanded=False):
            st.markdown(
                """
                ### 🔬 ¿Qué calcula y representa este gráfico?
                - **Distribución de Residuos**: Muestra la distribución estadística de los errores ($g_i - o_i$) para el producto Original (Raw) frente al Corregido (Merged).
                - **Elementos del Boxplot**:
                  - **Línea Central (Mediana / P50)**: Sesgo central típico. Si está en cero, el producto no presenta sesgo medio.
                  - **Caja (Rango Intercuartílico IQR, P25 a P75)**: Contiene el 50% central de los datos. Cajas más compactas reflejan mayor consistencia.
                  - **Bigotes (Percentiles P10 y P90)**: Representan el comportamiento en colas de la distribución excluyendo casos extremos.
                  - **Puntos (Jitter)**: Muestran los valores individuales de cada estación/año superpuestos con ligera dispersión horizontal para evitar sobrelapamiento.

                ### 🧭 ¿Cómo interpretar este gráfico?
                - **Reducción de Varianza**: Si la caja verde (Corregido) es notablemente más angosta que la roja (Original) y está centrada en la línea discontinua $y=0$, la corrección CDT eliminó con éxito el sesgo y la dispersión.
                """
            )

        if boxplots:
            sel_box = st.selectbox("Seleccione Boxplot a visualizar:", options=boxplots, format_func=_format_boxplot_label, key="select_boxplot")
            if sel_box and os.path.exists(sel_box):
                st.image(sel_box, caption=os.path.basename(sel_box), width="stretch")
        else:
            st.info("No hay boxplots generados en esta corrida.")

    # -------------------------------------------------------------
    # TAB 2: Diagramas de Dispersión (Scatter Plots)
    # -------------------------------------------------------------
    with st_tab2:
        with st.expander("📖 **Explicación Científica e Interpretación: Diagramas de Dispersión (Scatter Plots)**", expanded=False):
            st.markdown(
                """
                ### 🔬 ¿Qué calcula y representa este producto?
                - **Observado vs Rejilla**: Contrasta el valor medido en la estación terrestre ($X$) contra el valor extraído en la celda de rejilla ($Y$).
                - **Línea de Referencia 1:1 ($y=x$)**: Representa la concordancia perfecta ideal donde la estimación satelital coincide con la estación terrestre.
                - **Línea de Regresión Lineal (OLS)**: Muestra la pendiente ($m$) e intercepto ($b$) del ajuste empírico.

                ### 🧭 ¿Cómo interpretar este gráfico?
                - **Proximidad a la diagonal 1:1**: Los puntos del producto corregido (azul/verde) deben alinearse estrechamente sobre la línea diagonal de $45^\\circ$.
                - **Coeficiente de Correlación ($R$)**: Valores de $R \\to 1.00$ indican una excelente correlación lineal y reproducción de la variabilidad temporal y espacial.
                - **Sub/Sobrestimación**: Puntos sistemáticamente por debajo de la diagonal $1:1$ revelan subestimación satelital; por encima reflejan sobreestimación.
                """
            )

        if scatters:
            sel_sc = st.selectbox("Seleccione Scatter Plot a visualizar:", options=scatters, format_func=_format_scatter_label, key="select_scatter")
            if sel_sc and os.path.exists(sel_sc):
                st.image(sel_sc, caption=os.path.basename(sel_sc), width="stretch")
        else:
            st.info("No hay diagramas de dispersión generados en esta corrida.")

    # -------------------------------------------------------------
    # TAB 3: Mapas de Mejora en Estaciones
    # -------------------------------------------------------------
    with st_tab3:
        with st.expander("📖 **Explicación Científica e Interpretación: Mapa de Mejora en Estaciones**", expanded=False):
            st.markdown(
                """
                ### 🔬 ¿Qué calcula y representa este producto?
                - Muestra la ubicación geográfica precisa de las estaciones evaluadas con un código de colores que indica el **Porcentaje de Mejora en RMSE**:
                  $$\\%\\text{ Mejora} = 100 \\times \\frac{\\text{RMSE}_{\\text{raw}} - \\text{RMSE}_{\\text{corr}}}{\\text{RMSE}_{\\text{raw}}}$$
                - Permite evaluar visualmente el impacto geográfico de la corrección en relación con la topografía (relieve sombreado DEM).

                ### 🧭 ¿Cómo interpretar este mapa?
                - Puntos en tonos verdes y azules confirman reducción efectiva del error.
                - Puntos de gran tamaño reflejan estaciones con alto impacto de mejora tras la calibración espacial.
                """
            )

        if improvement_maps:
            sel_map = st.selectbox("Seleccione mapa de mejora:", options=improvement_maps, format_func=_format_map_label, key="select_imp_stations")
            if sel_map and os.path.exists(sel_map):
                st.image(sel_map, caption=os.path.basename(sel_map), width="stretch")
        else:
            st.info("No hay mapas de mejora disponibles en esta corrida.")
