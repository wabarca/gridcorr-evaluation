# -*- coding: utf-8 -*-
"""
Day of Year (DOY) Climatology viewer UI component.
Includes scientific explanations, interpretation of annual cycles, and station climatological metrics.
"""

import os
import glob
import streamlit as st
import pandas as pd
from ...application.models import AnalysisResult, ProcessingMode, PeriodType
from ...config.constants import MONTH_NAMES_ES


def render_doy_viewer(result: AnalysisResult) -> None:
    """
    Renderiza el visor interactivo de ciclo anual climatológico diario (DOY) con explicaciones y estadísticas.
    """
    req = result.request
    is_period = req and (
        req.mode == ProcessingMode.PERIOD
        or getattr(req, "period_type", None) in ["season", "months", PeriodType.SEASON, PeriodType.MONTHS]
    )

    if is_period:
        if req.period_type == "season" and req.season:
            period_desc = f"Temporada {req.season}"
        elif req.period_type == "months" and req.months:
            months_list = req.months if isinstance(req.months, list) else [req.months]
            if len(months_list) == 1:
                period_desc = f"Mes de {MONTH_NAMES_ES.get(months_list[0], f'M{months_list[0]}')}"
            else:
                period_desc = f"Meses {MONTH_NAMES_ES.get(months_list[0], '')[:3]}–{MONTH_NAMES_ES.get(months_list[-1], '')[:3]}"
        else:
            period_desc = "Período Seleccionado"
        title_main = f"📅 Ciclo Climatológico Diario por Estación — {period_desc}"
    elif req and req.yini and req.yend and req.yini == req.yend:
        period_desc = f"Año {req.yini}"
        title_main = f"📅 Serie Diaria (DOY 1–365) por Estación — Año {req.yini}"
    elif req and req.yini and req.yend:
        period_desc = f"{req.yini}–{req.yend}"
        title_main = f"📅 Climatología de Día del Año (DOY 1–365) por Estación ({period_desc})"
    else:
        period_desc = "Serie Completa"
        title_main = "📅 Climatología de Día del Año (DOY 1–365) por Estación"

    st.subheader(title_main)

    with st.expander("📖 **Explicación Científica e Interpretación: Ciclo Climatológico Diario (DOY)**", expanded=False):
        st.markdown(
            r"""
            ### 🔬 ¿Qué calcula y representa este producto?
            - **Ciclo Diario (DOY / Días del Período)**: Agrupa y promedia los registros a escala diaria para el período seleccionado (año completo, temporada climática o mes) para construir la curva del ciclo diario.
            - **Curva Continua (Línea Sólida)**: Representa el promedio ($\mu$) para las observaciones terrestres (negro), el producto original (rojo) y el corregido (azul/verde).
            - **Bandas Sombreadas ($\pm 1\sigma$)**: Representan la desviación estándar interanual, delimitando la variabilidad climática natural esperada para cada día del calendario.
            - **Líneas Punteadas Superiores e Inferiores**: Marcan los valores extremos absolutos (máximo y mínimo histórico) registrados.

            ### 🧭 ¿Cómo interpretar este gráfico?
            - **Fidelidad Temporal y Estacional**: Permite evaluar si el satélite replica fielmente la variabilidad y marcha diaria de la temperatura o lluvia.
            - **Corrección de Amplitud**: Si la curva corregida se superpone de manera continua sobre la curva observada, confirma que la calibración eliminó desfases y sesgos diarios.
            """
        )

    if not result.doy_stations or not result.doy_plots_by_station:
        curr_mode = result.request.mode.value if result.request else "anual"
        st.warning(
            f"ℹ️ **No se encontraron datos o curvas de Climatología Diaria para `{period_desc}`.**\n\n"
            f"- **Modo ejecutado actualmente:** `{curr_mode}`.\n"
            "- **Recomendación:** Verifique que la ruta del archivo CSV de estaciones contenga observaciones válidas y que los directorios de datos NetCDF contengan la serie diaria del período evaluado."
        )
        return

    col1, col2 = st.columns([1, 2])
    is_precip = result.request and "precip" in result.request.var.lower()

    with col1:
        station_id = st.selectbox(
            "Seleccione la Estación Meteorológica:",
            options=sorted(result.doy_stations),
            index=0,
            key="select_doy_station"
        )

        is_single_year = req and req.yini and req.yend and req.yini == req.yend

        if is_precip:
            view_opts = ["Panel Completo (Acumulado / Máximo / Promedio)", "Acumulado Progresivo (Accum)", "Promedio Diario (Mean)", "Máximo Diario (Max)"]
            key_map = {
                "Panel Completo (Acumulado / Máximo / Promedio)": "tripanel",
                "Acumulado Progresivo (Accum)": "accum",
                "Promedio Diario (Mean)": "mean",
                "Máximo Diario (Max)": "max",
            }
            view_type = st.radio(
                "Tipo de Visualización DOY:",
                options=view_opts,
                index=0,
                key="select_doy_view_type"
            )
        else:
            view_type = st.radio(
                "Tipo de Visualización DOY:",
                options=["Panel Completo (3 Paneles: Max / Mean / Min)", "Media Diaria (Mean)", "Máximo Diario (Max)", "Mínimo Diario (Min)"],
                index=0,
                key="select_doy_view_type"
            )
            key_map = {
                "Panel Completo (3 Paneles: Max / Mean / Min)": "tripanel",
                "Media Diaria (Mean)": "mean",
                "Máximo Diario (Max)": "max",
                "Mínimo Diario (Min)": "min",
            }

    with col2:
        plots_for_st = result.doy_plots_by_station.get(station_id, {})
        selected_key = key_map.get(view_type, "tripanel")
        plot_path = plots_for_st.get(selected_key)

        if plot_path and os.path.exists(plot_path):
            st.image(plot_path, caption=f"Ciclo Diario — Estación {station_id} ({period_desc})", width="stretch")
        else:
            st.warning(f"No se encontró el gráfico para la estación {station_id} ({selected_key}).")

    # Mostrar tabla estadística DOY si existe el CSV
    csv_candidates = glob.glob(os.path.join(result.output_dir, "**", f"*clim*station_{station_id}.csv"), recursive=True)
    if not csv_candidates:
        csv_candidates = glob.glob(os.path.join(result.output_dir, "**", f"*doy*{station_id}.csv"), recursive=True)

    if csv_candidates:
        df_doy = pd.read_csv(csv_candidates[0])
        st.markdown(f"#### 📊 Resumen Estadístico Diario — Estación `{station_id}` ({period_desc})")

        is_precip = result.request and "precip" in result.request.var.lower()

        if is_precip and "obs_accum" in df_doy.columns:
            c_stat1, c_stat2, c_stat3, c_stat4 = st.columns(4)
            with c_stat1:
                st.metric("Acumulado Total Obs.", f"{df_doy['obs_accum'].iloc[-1]:.1f} mm")
            with c_stat2:
                st.metric("Acumulado Total Raw", f"{df_doy['raw_accum'].iloc[-1]:.1f} mm")
            with c_stat3:
                st.metric("Acumulado Total Corregido", f"{df_doy['corr_accum'].iloc[-1]:.1f} mm")
            with c_stat4:
                bias_accum = df_doy['corr_accum'].iloc[-1] - df_doy['obs_accum'].iloc[-1]
                st.metric("Sesgo Acumulado Residual", f"{bias_accum:+.1f} mm")
        else:
            unit_str = "mm/día" if is_precip else "°C"
            c_stat1, c_stat2, c_stat3, c_stat4 = st.columns(4)
            with c_stat1:
                st.metric("Media Diaria Obs.", f"{df_doy['obs_mean'].mean():.2f} {unit_str}" if "obs_mean" in df_doy else "N/A")
            with c_stat2:
                st.metric("Media Diaria Raw", f"{df_doy['raw_mean'].mean():.2f} {unit_str}" if "raw_mean" in df_doy else "N/A")
            with c_stat3:
                st.metric("Media Diaria Corregido", f"{df_doy['corr_mean'].mean():.2f} {unit_str}" if "corr_mean" in df_doy else "N/A")
            with c_stat4:
                bias_corr = (df_doy['corr_mean'].mean() - df_doy['obs_mean'].mean()) if ('corr_mean' in df_doy and 'obs_mean' in df_doy) else 0.0
                st.metric("Sesgo Medio Residual", f"{bias_corr:+.2f} {unit_str}")

        with st.expander(f"📄 Ver Tabla de Datos Diarios ({period_desc})", expanded=False):
            st.dataframe(df_doy, width="stretch")
            st.download_button(
                "⬇️ Descargar CSV Climatología Diaria",
                data=df_doy.to_csv(index=False),
                file_name=f"clim_doy_{station_id}.csv",
                mime="text/csv",
                key=f"download_doy_csv_{station_id}"
            )
