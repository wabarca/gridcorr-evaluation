# -*- coding: utf-8 -*-
"""
Maps viewer UI component: Side-by-side maps, Delta GRID fields, and Station residual maps.
Includes scientific explanations, interpretation guides, and statistical summaries.
"""

import os
import glob
import numpy as np
import pandas as pd
import streamlit as st
from ...application.models import AnalysisResult


def render_maps_viewer(result: AnalysisResult) -> None:
    """
    Renderiza la galería interactiva de mapas generados con explicaciones científicas y estadísticos.
    """
    st.subheader("🗺️ Mapas Cartográficos de Comparación y Diferencias Espaciales")

    if not result.generated_maps:
        st.info("No se han generado mapas todavía. Configure los parámetros en el panel lateral y presione 'Ejecutar Análisis'.")
        return

    # Categorizar mapas rigurosamente según su tipología cartográfica
    def is_side_by_side(path: str) -> bool:
        bname = os.path.basename(path).lower()
        # Excluir explícitamente diagnósticos, residuos, gráficos y rankings
        if any(k in bname for k in ["delta", "residual", "improvement", "boxplot", "scatter", "rmse", "kge", "climatology", "bars", "ranking", "summary"]):
            return False
        # Excluir cualquier archivo ubicado en la estructura de carpetas /eval/
        parts = [part.lower() for part in os.path.normpath(path).split(os.sep)]
        if "eval" in parts:
            return False
        # Debe coincidir con mapas comparativos estándar
        return any(k in bname for k in ["anual", "annual", "daily", "period", "accum", "mean", "max", "min"]) or ("_" in bname and any(c.isdigit() for c in bname))

    side_by_side_maps = [m for m in result.generated_maps if is_side_by_side(m)]
    delta_field_maps = [m for m in result.generated_maps if "delta_grid_field" in os.path.basename(m).lower()]
    delta_station_maps = [m for m in result.generated_maps if "delta_grid_stations" in os.path.basename(m).lower()]
    residual_maps = [m for m in result.generated_maps if "residual" in os.path.basename(m).lower()]
    improvement_maps = [m for m in result.generated_maps if "improvement" in os.path.basename(m).lower()]

    map_tab1, map_tab2, map_tab3, map_tab4 = st.tabs([
        f"Comparación Lado a Lado ({len(side_by_side_maps)})",
        f"Campo de anomalías ΔGRID ({len(delta_field_maps)})",
        f"ΔGRID y Residuos en Estaciones ({len(delta_station_maps) + len(residual_maps)})",
        f"Mejora Espacial % RMSE ({len(improvement_maps)})",
    ])

    # -------------------------------------------------------------
    # TAB 1: Comparación Lado a Lado
    # -------------------------------------------------------------
    with map_tab1:
        with st.expander("📖 **Explicación Científica e Interpretación: Mapas Lado a Lado**", expanded=False):
            st.markdown(
                """
                ### 🔬 ¿Qué calcula y representa este producto?
                - **Panel Izquierdo (Original / Raw)**: Muestra el campo continuo espacial estimado originalmente por satélite (**CHIRPS** para precipitación acumulada o **CHIRTS** para temperatura diaria/media/extrema).
                - **Panel Derecho (Corregido / Merged)**: Muestra el campo corregido tras el proceso de calibración espacial con datos de estaciones meteorológicas terrestres mediante la metodología CDT.
                - **Puntos Circulares**: Representan las estaciones meteorológicas terrestres utilizadas, coloreadas con la misma escala cromática para evaluar la concordancia visual in-situ.

                ### 🧭 ¿Cómo interpretar este mapa?
                - **Ajuste Topográfico**: Observe cómo en zonas montañosas o cordilleras volcánicas, la corrección CDT introduce gradientes altitudinales y de relieve realistas (a través del DEM).
                - **Consistencia Punto-Grilla**: Si los círculos de las estaciones se camuflan perfectamente con el color de fondo de la malla, indica una calibración exitosa con error residual cercano a cero.
                - **Corrección de Sesgo Húmedo/Seco**: Permite identificar áreas donde el satélite sobreestimaba o subestimaba la precipitación/temperatura antes de la corrección.
                """
            )

        if side_by_side_maps:
            selected_sbs = st.selectbox(
                "Seleccione el mapa a visualizar:",
                options=side_by_side_maps,
                format_func=lambda x: os.path.basename(x),
                key="select_sbs_map"
            )
            if selected_sbs and os.path.exists(selected_sbs):
                st.image(selected_sbs, caption=f"Mapa: {os.path.basename(selected_sbs)}", width="stretch")

                # 1. Búsqueda directa del archivo CSV compañero de comparación
                target_csv = None
                neighbor_cmp = selected_sbs.replace(".png", "_cmp_estaciones.csv")
                neighbor_csv = selected_sbs.replace(".png", ".csv")

                if os.path.exists(neighbor_cmp):
                    target_csv = neighbor_cmp
                elif os.path.exists(neighbor_csv):
                    target_csv = neighbor_csv
                else:
                    # Extraer identificador temporal (año de 4 dígitos o período tipo YYYY-MM o YYYYMMDD)
                    bname = os.path.basename(selected_sbs).replace(".png", "")
                    tokens = [t for t in bname.split("_") if any(c.isdigit() for c in t)]
                    all_csvs = glob.glob(os.path.join(result.output_dir, "**", "*.csv"), recursive=True)

                    for token in tokens:
                        matches = [c for c in all_csvs if token in os.path.basename(c) and "cmp_estaciones" in os.path.basename(c)]
                        if matches:
                            target_csv = matches[0]
                            break
                        matches = [c for c in all_csvs if token in os.path.basename(c) and "daily_timeseries" not in os.path.basename(c)]
                        if matches:
                            target_csv = matches[0]
                            break

                    if not target_csv and all_csvs:
                        cmp_csvs = [c for c in all_csvs if "cmp_estaciones" in os.path.basename(c)]
                        target_csv = cmp_csvs[0] if cmp_csvs else all_csvs[0]

                if target_csv and os.path.exists(target_csv):
                    try:
                        df_st = pd.read_csv(target_csv)
                        # Identificar año/etiqueta para el título
                        bname = os.path.basename(selected_sbs).replace(".png", "")
                        tokens = [t for t in bname.split("_") if any(c.isdigit() for c in t)]
                        time_label = f"Año/Período {tokens[0]}" if tokens else "Período Evaluado"

                        # Si es un CSV diario con serie larga, filtrar por la fecha/año si está disponible
                        if tokens and "year" in df_st.columns and len(df_st) > 200 and tokens[0].isdigit() and len(tokens[0]) == 4:
                            df_st = df_st[df_st["year"] == int(tokens[0])]
                        elif tokens and "date" in df_st.columns and len(df_st) > 200:
                            df_st = df_st[df_st["date"].astype(str).str.startswith(str(tokens[0]))]

                        # Mapeo de columnas representativas (Observado, Original, Corregido)
                        col_map = {}
                        for col in df_st.columns:
                            cl = col.lower()
                            if (cl in ["obs", "accum_obs", "precip_station", "tmax_station", "tmin_station", "obs_val", "precip_accum", "tmax_mean", "tmin_mean"] or cl.endswith("_obs")) and "Observado (Estaciones)" not in col_map.values():
                                col_map[col] = "Observado (Estaciones)"
                            elif cl in ["grid_raw", "raw", "chirps_raw", "chirts_raw", "original", "grid_original"] and "Original (Satélite)" not in col_map.values():
                                col_map[col] = "Original (Satélite)"
                            elif cl in ["grid_corr", "corr", "chirps_corr", "chirts_corr", "corregido", "grid_corregido"] and "Corregido (CDT)" not in col_map.values():
                                col_map[col] = "Corregido (CDT)"

                        matched_cols = list(col_map.keys())
                        if not matched_cols:
                            # Fallback: columnas numéricas no espaciales
                            exclude = ["lat", "lon", "latitude", "longitude", "year", "month", "day", "elevation", "dem", "station_id", "err_raw", "err_corr", "abs_err_raw", "abs_err_corr", "rel_err_raw_pct", "rel_err_corr_pct"]
                            matched_cols = [c for c in df_st.select_dtypes(include=[np.number]).columns if c.lower() not in exclude][:3]
                            for c in matched_cols:
                                col_map[c] = c

                        if matched_cols:
                            # Si contiene múltiples fechas por estación, agregar por estación para que N represente el total de estaciones físicas
                            if "station_id" in df_st.columns and len(df_st) > 50:
                                df_st = df_st.groupby("station_id", as_index=False)[matched_cols].mean(numeric_only=True)

                            df_display = df_st[matched_cols].rename(columns=col_map)
                            stat_df = df_display.describe().T[["count", "mean", "std", "min", "25%", "50%", "75%", "max"]]
                            stat_df.columns = ["N Estaciones", "Media", "Desv. Est.", "Mínimo", "P25", "Mediana (P50)", "P75", "Máximo"]

                            # Ordenar filas en el orden lógico estándar
                            desired_order = ["Observado (Estaciones)", "Original (Satélite)", "Corregido (CDT)"]
                            ordered_index = [idx for idx in desired_order if idx in stat_df.index] + [idx for idx in stat_df.index if idx not in desired_order]
                            stat_df = stat_df.reindex(ordered_index)

                            st.markdown(f"#### 📊 Estadísticos Descriptivos en Estaciones ({time_label})")
                            format_dict = {
                                "N Estaciones": "{:.0f}",
                                "Media": "{:.2f}",
                                "Desv. Est.": "{:.2f}",
                                "Mínimo": "{:.2f}",
                                "P25": "{:.2f}",
                                "Mediana (P50)": "{:.2f}",
                                "P75": "{:.2f}",
                                "Máximo": "{:.2f}",
                            }
                            st.dataframe(stat_df.style.format(format_dict), width="stretch")
                    except Exception as e:
                        st.warning(f"No se pudo generar la tabla estadística descriptiva: {e}")
        else:
            st.info("ℹ️ No hay mapas lado a lado disponibles en esta ejecución. Asegúrese de que las fechas y el rango temporal contengan datos válidos.")

    # -------------------------------------------------------------
    # TAB 2: Campo de anomalías ΔGRID
    # -------------------------------------------------------------
    with map_tab2:
        with st.expander("📖 **Explicación Científica e Interpretación: Campo de anomalías ΔGRID**", expanded=False):
            st.markdown(
                """
                ### 🔬 ¿Qué calcula y representa este producto?
                - **Fórmula**: $\\Delta\\text{GRID} = \\text{GRID}_{\\text{corregido}} - \\text{GRID}_{\\text{original}}$
                - **Representación**: Es una superficie continua 2D raster que cuantifica la magnitud exacta del ajuste aplicado por el algoritmo CDT en cada pixel del territorio.

                ### 🧭 ¿Cómo interpretar este mapa?
                - **Colores Rojos / Cálidos (+)**: Indican que la corrección aumentó el valor de la variable (el satélite crudo subestimaba la magnitud).
                - **Colores Azules / Fríos (−)**: Indican que la corrección disminuyó el valor (el satélite crudo sobreestimaba la variable).
                - **Zonas Blancas / Neutras (≈ 0)**: Áreas donde el satélite coincidía adecuadamente con el patrón regional o donde no hubo modificaciones sustanciales.
                """
            )

        if delta_field_maps:
            selected_df = st.selectbox(
                "Seleccione el campo ΔGRID a visualizar:",
                options=delta_field_maps,
                format_func=lambda x: os.path.basename(x),
                key="select_delta_field_map"
            )
            if selected_df and os.path.exists(selected_df):
                st.image(selected_df, caption=f"Campo ΔGRID: {os.path.basename(selected_df)}", width="stretch")
        else:
            st.info("ℹ️ **¿Por qué no se visualiza este campo?**\nEl campo continuo espacial ΔGRID se genera cuando se evalúa la serie multianual completa con la opción de evaluación estadística (`--eval`) habilitada.")

    # -------------------------------------------------------------
    # TAB 3: ΔGRID y Residuos en Estaciones
    # -------------------------------------------------------------
    with map_tab3:
        with st.expander("📖 **Explicación Científica e Interpretación: Residuos y ΔGRID en Estaciones**", expanded=False):
            st.markdown(
                """
                ### 🔬 ¿Qué calcula y representa este producto?
                - **Residuo en Estación**: $\\text{Residuo} = \\text{Rejilla Corregida} - \\text{Observación Terrestre}$
                - **ΔGRID Puntual**: Diferencia extraída exactamente en las coordenadas geográficas $(\\text{lon}, \\text{lat})$ de cada estación.

                ### 🧭 ¿Cómo interpretar este mapa?
                - Permite diagnosticar si existen estaciones específicas con errores locales sistemáticos persistentes (por ejemplo, estaciones costeras o en cumbres volcánicas con microclimas muy localizados).
                - Círculos cercanos a cero (color blanco/neutro) demuestran que el algoritmo de combinación respetó fielmente la observación in-situ.
                """
            )

        station_maps = delta_station_maps + residual_maps
        if station_maps:
            selected_st = st.selectbox(
                "Seleccione el mapa de estaciones a visualizar:",
                options=station_maps,
                format_func=lambda x: os.path.basename(x),
                key="select_station_map"
            )
            if selected_st and os.path.exists(selected_st):
                st.image(selected_st, caption=f"Mapa de estaciones: {os.path.basename(selected_st)}", width="stretch")
        else:
            st.info("ℹ️ **¿Por qué no se visualiza este mapa?**\nRequiere que el archivo CSV de estaciones contenga datos numéricos válidos en las mismas coordenadas y fechas que la rejilla NetCDF.")

    # -------------------------------------------------------------
    # TAB 4: Mejora Espacial (% Mejora RMSE)
    # -------------------------------------------------------------
    with map_tab4:
        with st.expander("📖 **Explicación Científica e Interpretación: Porcentaje de Mejora Espacial**", expanded=False):
            st.markdown(
                """
                ### 🔬 ¿Qué calcula y representa este producto?
                - **Fórmula**: $\\%\\text{ Mejora} = 100 \\times \\frac{\\text{RMSE}_{\\text{raw}} - \\text{RMSE}_{\\text{corr}}}{\\text{RMSE}_{\\text{raw}}}$
                - Cada estación se dibuja sobre el mapa con un tamaño y color proporcional a la reducción porcentual del error cuadrático medio.

                ### 🧭 ¿Cómo interpretar este mapa?
                - **Valores > 0% (Verde/Azul)**: La calibración CDT mejoró la precisión del dato satelital, reduciendo el error con respecto a la estación terrestre.
                - **Valores > 50%**: Representan zonas con excelente asimilación y reducción de error de más de la mitad.
                - **Valores ≤ 0% (Rojo)**: Indican puntos donde la corrección no logró reducir el error o existían discrepancias severas en la estación.
                """
            )

        if improvement_maps:
            selected_imp = st.selectbox(
                "Seleccione el mapa de mejora a visualizar:",
                options=improvement_maps,
                format_func=lambda x: os.path.basename(x),
                key="select_imp_map"
            )
            if selected_imp and os.path.exists(selected_imp):
                st.image(selected_imp, caption=f"Mapa de Mejora: {os.path.basename(selected_imp)}", width="stretch")
        else:
            st.info("ℹ️ **¿Por qué no se visualiza este mapa?**\nLos mapas de mejora espacial (% ΔRMSE) requieren una evaluación multianual (mínimo 2 años) con la opción `--eval` activa.")
