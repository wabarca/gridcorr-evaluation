# -*- coding: utf-8 -*-
"""
Sidebar configuration and analysis parameters UI component.
"""

import os
from typing import Tuple, Optional
import streamlit as st

from ...application.models import (
    AnalysisRequest,
    ProductType,
    ProcessingMode,
    StatType,
    PeriodType,
)
from ...config.constants import SEASONS, DEFAULT_EXTENTS


def render_sidebar() -> Tuple[AnalysisRequest, bool, bool, str]:
    """
    Renderiza el panel lateral con la configuración completa de análisis y navegación.

    Retorna
    -------
    tuple
        (request, run_clicked, validate_clicked, nav_section)
    """
    st.sidebar.title("🌦️ GridCorr Toolkit")

    # Selector de Navegación Principal
    nav_section = st.sidebar.radio(
        "**Sección del Sistema**",
        options=["📊 Evaluación & Análisis", "📚 Documentación & Manual"],
        index=0,
        help="Alterne entre la plataforma de procesamiento/evaluación y el manual científico integral."
    )

    if "Documentación" in nav_section:
        st.sidebar.markdown("---")
        st.sidebar.subheader("📑 Contenido del Manual")
        st.sidebar.markdown(
            """
            - 💻 **1. Manual de Instalación**
            - 🚀 **2. Manual de Utilización**
            - 📥 **3. Productos de Entrada**
            - 🧮 **4. Métricas Calculadas**
            - 🗺️ **5. Catálogo de Imágenes**
            - 📖 **6. Referencias Justificadas**
            """
        )
        st.sidebar.info("Utilice las pestañas interactivas en la pantalla principal para explorar el contenido.")

        # Generar request por defecto para mantener consistencia
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        default_csv = os.path.join(root_dir, "DATA", "centroamerica", "datos", "station_data", "tmax_formato_cdt_elsalvador.csv")
        default_raw = os.path.join(root_dir, "DATA", "centroamerica", "cdt_original_data", "CHIRTS_TMax_CDT_NetCDF_Format")
        default_mrg = os.path.join(root_dir, "DATA", "centroamerica", "cdt_corrected_data", "CHIRTS_tmax_MERGED_TEMP_Data_1ene1991_31dic2020", "DATA")
        default_out = os.path.join(root_dir, "salidas_evaluacion")
        default_req = AnalysisRequest(
            product=ProductType.CHIRTS,
            csv_path=default_csv,
            dir_original=default_raw,
            dir_merged=default_mrg,
            out_dir=default_out,
            var="tmax",
            stat=StatType.MEAN,
        )
        return default_req, False, False, nav_section

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Configuración de Análisis")

    from ...config.persistence import (
        load_user_settings,
        save_user_settings,
        get_stored_paths_for_var,
        set_stored_paths_for_var,
    )

    saved_settings = load_user_settings()

    # Selector de Producto con memoria persistente
    default_prod_idx = 1 if saved_settings.get("last_product") == "chirps" else 0
    product_str = st.sidebar.radio(
        "**Producto Climático**",
        options=["CHIRTS (Temperatura)", "CHIRPS (Precipitación)"],
        index=default_prod_idx,
        help="Seleccione si desea evaluar campos de temperatura (CHIRTS) o precipitación (CHIRPS)."
    )
    is_chirts = "CHIRTS" in product_str
    product = ProductType.CHIRTS if is_chirts else ProductType.CHIRPS

    if is_chirts:
        default_var_idx = 1 if saved_settings.get("last_var") == "tmin" else 0
        var = st.sidebar.selectbox(
            "Variable de Temperatura",
            options=["tmax", "tmin"],
            index=default_var_idx,
            help="Seleccione Temperatura Máxima (tmax) o Mínima (tmin)."
        )
    else:
        var = "precip"

    mode_options = [
        "annual (Mapas anuales por estadístico)",
        "daily (Mapa para una fecha específica)",
        "daily-eval (Evaluación diaria serie completa & DOY)",
        "period (Por temporadas o meses)",
    ]
    saved_mode = saved_settings.get("last_mode", "annual")
    default_mode_idx = 0
    for idx_m, m_opt in enumerate(mode_options):
        if saved_mode in m_opt:
            default_mode_idx = idx_m
            break

    mode_str = st.sidebar.selectbox(
        "Modo de Operación",
        options=mode_options,
        index=default_mode_idx,
        help="Seleccione el modo de análisis temporal."
    )
    if "daily-eval" in mode_str:
        mode = ProcessingMode.DAILY_EVAL
    elif "daily (" in mode_str:
        mode = ProcessingMode.DAILY
    elif "period" in mode_str:
        mode = ProcessingMode.PERIOD
    else:
        mode = ProcessingMode.ANNUAL

    if is_chirts:
        stat_str = st.sidebar.selectbox(
            "Estadístico",
            options=["mean", "max", "min", "all"],
            index=0,
            help="Estadístico espacial/temporal a calcular."
        )
        stat = StatType(stat_str)
    else:
        stat_options = ["accum", "mean", "max", "min"] if mode == ProcessingMode.PERIOD else ["accum"]
        stat_str = st.sidebar.selectbox(
            "Estadístico de Precipitación",
            options=stat_options,
            index=0,
            help="Estadístico espacial/temporal para precipitación (acumulado o promedio)."
        )
        stat = StatType(stat_str)

    # Rutas base por defecto en el repositorio
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

    if is_chirts:
        fb_csv = os.path.join(root_dir, "DATA", "centroamerica", "datos", "station_data", f"{var}_formato_cdt_elsalvador.csv")
        fb_raw = os.path.join(root_dir, "DATA", "centroamerica", "cdt_original_data", "CHIRTS_TMax_CDT_NetCDF_Format" if var == "tmax" else "CHIRTS_TMin_CDT_NetCDF_Format")
        fb_mrg = os.path.join(root_dir, "DATA", "centroamerica", "cdt_corrected_data", f"CHIRTS_{var}_MERGED_TEMP_Data_1ene1991_31dic2020", "DATA")
        fb_dem = os.path.join(root_dir, "DATA", "centroamerica", "datos", "dem", "gebco_2024_el_salvador.nc")
    else:
        fb_csv = os.path.join(root_dir, "DATA", "centroamerica", "datos", "station_data", "lluvia_formato_cdt_elsalvador.csv")
        fb_raw = os.path.join(root_dir, "DATA", "centroamerica", "cdt_original_data", "CHIRPSv2_CDT_NetCDF_Format")
        fb_mrg = os.path.join(root_dir, "DATA", "centroamerica", "cdt_corrected_data", "CHIRPSv2_pr_MERGED_RAIN_Data_1ene1991_31dic2020", "DATA")
        fb_dem = os.path.join(root_dir, "DATA", "centroamerica", "datos", "dem", "gebco_2024.nc")

    # Cargar rutas guardadas o usar fallbacks si el archivo existe
    stored_paths = get_stored_paths_for_var(product.value, var)
    default_csv = stored_paths.get("csv_path") or fb_csv
    default_raw = stored_paths.get("dir_original") or fb_raw
    default_mrg = stored_paths.get("dir_merged") or fb_mrg
    default_dem = stored_paths.get("dem_path") or fb_dem
    default_out = stored_paths.get("out_dir") or saved_settings.get("out_dir", "./salidas")

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Parámetros Temporales")

    date_str = None
    saved_yini = int(saved_settings.get("yini", 1991))
    saved_yend = int(saved_settings.get("yend", 2020))
    yini, yend = saved_yini, saved_yend
    period_type = None
    season = None
    all_seasons = False
    months = None

    if mode == ProcessingMode.DAILY:
        import datetime
        default_d = datetime.date(1991, 1, 1)
        date_input = st.sidebar.date_input(
            "Fecha a evaluar",
            value=default_d,
            min_value=datetime.date(1950, 1, 1),
            max_value=datetime.date(2050, 12, 31),
            help="Seleccione la fecha diaria a evaluar (disponible desde 1950 hasta 2050)."
        )
        date_str = date_input.strftime("%Y-%m-%d") if date_input else "1991-01-01"
    elif mode in [ProcessingMode.ANNUAL, ProcessingMode.PERIOD, ProcessingMode.DAILY_EVAL]:
        col_y1, col_y2 = st.sidebar.columns(2)
        with col_y1:
            yini = st.number_input("Año Inicial", min_value=1950, max_value=2050, value=yini, step=1)
        with col_y2:
            yend = st.number_input("Año Final", min_value=1950, max_value=2050, value=yend, step=1)

        if mode == ProcessingMode.PERIOD:
            pt_choice = st.sidebar.radio("Tipo de Período", options=["Estación Climática (Season)", "Meses Específicos"], index=0)
            if "Season" in pt_choice:
                period_type = PeriodType.SEASON
                season_choice = st.sidebar.selectbox("Temporada", options=["Todas (--all-seasons)"] + list(SEASONS.keys()), index=0)
                if season_choice == "Todas (--all-seasons)":
                    all_seasons = True
                else:
                    season = season_choice
            else:
                period_type = PeriodType.MONTHS
                months_selected = st.sidebar.multiselect(
                    "Seleccione los Meses",
                    options=list(range(1, 13)),
                    default=[5, 6, 7],
                    format_func=lambda m: f"{m:02d} - {['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'][m-1]}"
                )
                months = months_selected or [5, 6, 7]

    st.sidebar.markdown("---")
    st.sidebar.subheader("📂 Rutas de Archivos y Directorios")

    from .file_browser import render_file_picker_button

    # Manejo de estado para rutas reactivas al producto o variable seleccionada
    product_var_key = (is_chirts, var if is_chirts else "precip")
    if "last_prod_var" not in st.session_state or st.session_state["last_prod_var"] != product_var_key:
        st.session_state["last_prod_var"] = product_var_key
        st.session_state["input_csv_path"] = default_csv
        st.session_state["input_raw_dir"] = default_raw
        st.session_state["input_mrg_dir"] = default_mrg
        st.session_state["input_dem_path"] = default_dem
        st.session_state["input_out_dir"] = default_out

    if "input_csv_path" not in st.session_state:
        st.session_state["input_csv_path"] = default_csv
    if "input_raw_dir" not in st.session_state:
        st.session_state["input_raw_dir"] = default_raw
    if "input_mrg_dir" not in st.session_state:
        st.session_state["input_mrg_dir"] = default_mrg
    if "input_dem_path" not in st.session_state:
        st.session_state["input_dem_path"] = default_dem
    if "input_out_dir" not in st.session_state:
        st.session_state["input_out_dir"] = default_out

    # CSV de Estaciones
    st.sidebar.markdown("**1. CSV de Estaciones (CDT):**")
    csv_path = st.sidebar.text_input("Ruta CSV", key="input_csv_path", label_visibility="collapsed")
    with st.sidebar:
        render_file_picker_button(
            target_session_key="input_csv_path",
            target_type="csv",
            initial_dir=os.path.dirname(csv_path) if csv_path else None,
            label="Seleccionar CSV...",
        )

    # NetCDF Original
    st.sidebar.markdown("**2. Directorio NetCDF Originales:**")
    dir_original = st.sidebar.text_input("Ruta Originales", key="input_raw_dir", label_visibility="collapsed")
    with st.sidebar:
        render_file_picker_button(
            target_session_key="input_raw_dir",
            target_type="dir",
            initial_dir=dir_original if dir_original else None,
            label="Seleccionar Carpeta Originales...",
        )

    # NetCDF Corregido
    st.sidebar.markdown("**3. Directorio NetCDF Corregidos:**")
    dir_merged = st.sidebar.text_input("Ruta Corregidos", key="input_mrg_dir", label_visibility="collapsed")
    with st.sidebar:
        render_file_picker_button(
            target_session_key="input_mrg_dir",
            target_type="dir",
            initial_dir=dir_merged if dir_merged else None,
            label="Seleccionar Carpeta Corregidos...",
        )

    # DEM (Relieve topográfico para mapas)
    st.sidebar.markdown("**4. Archivo DEM Topográfico (NetCDF, Opcional):**")
    dem_path = st.sidebar.text_input("Ruta DEM", key="input_dem_path", label_visibility="collapsed")
    with st.sidebar:
        render_file_picker_button(
            target_session_key="input_dem_path",
            target_type="nc",
            initial_dir=os.path.dirname(dem_path) if dem_path else None,
            label="Seleccionar Archivo DEM...",
        )

    # Directorio de Salida
    st.sidebar.markdown("**5. Directorio Base de Salida:**")
    out_dir = st.sidebar.text_input("Ruta Salida", key="input_out_dir", label_visibility="collapsed")
    with st.sidebar:
        render_file_picker_button(
            target_session_key="input_out_dir",
            target_type="dir",
            initial_dir=out_dir if out_dir else None,
            label="Seleccionar Carpeta de Salida...",
        )

    # Extensión espacial
    st.sidebar.markdown("---")
    st.sidebar.subheader("🗺️ Dominio Espacial (Extent)")
    st.sidebar.caption("🌐 **Automático:** El dominio se extrae dinámicamente de las dimensiones del dataset original NetCDF.")

    extent = None
    with st.sidebar.expander("🛠️ Personalizar Coordenadas Manualmente (Opcional)", expanded=False):
        use_manual_extent = st.checkbox("Definir coordenadas manuales", value=False)
        if use_manual_extent:
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                xmin = st.number_input("Lon Min (xmin)", value=-90.5, step=0.1)
                ymin = st.number_input("Lat Min (ymin)", value=13.0, step=0.1)
            with col_e2:
                xmax = st.number_input("Lon Max (xmax)", value=-87.5, step=0.1)
                ymax = st.number_input("Lat Max (ymax)", value=14.6, step=0.1)
            extent = (float(xmin), float(xmax), float(ymin), float(ymax))

    # Opciones de Estadísticos y Evaluación
    st.sidebar.markdown("---")
    st.sidebar.subheader("📐 Selección de Estadísticos")

    with st.sidebar.expander("⚙️ Configurar Estadísticos a Calcular", expanded=False):
        use_error_metrics = st.checkbox("Error Continuo (Bias, MAE, RMSE, PBIAS)", value=True, help="Calcula sesgo medio, errores absolutos y cuadráticos.")
        use_efficiency = st.checkbox("Eficiencia (KGE + componentes, NSE, Willmott d1)", value=True, help="Eficiencia de Kling-Gupta y Nash-Sutcliffe.")
        
        use_rain_cat = False
        rain_th = 1.0
        if not is_chirts:
            use_rain_cat = st.checkbox("Detección Categórica de Lluvia (POD, FAR, CSI, FBI)", value=True, help="Matriz de contingencia de aciertos y falsas alarmas.")
            rain_th = st.slider(
                "Umbral de lluvia diaria (mm)",
                min_value=0.1,
                max_value=25.0,
                value=1.0,
                step=0.5,
                help=(
                    "Criterio de corte o umbral mínimo (τ en mm) para clasificar un día como 'lluvioso' "
                    "(evento de precipitación, P ≥ τ) vs 'seco' (P < τ).\n\n"
                    "Este umbral alimenta directamente la tabla de contingencia 2×2 (Aciertos, Falsas Alarmas, "
                    "Fallos, No-eventos correctos) utilizada para calcular todas las métricas dicotómicas/categóricas "
                    "de lluvia: POD (Probabilidad de Detección), FAR (Tasa de Falsa Alarma), CSI (Índice de Éxito Crítico), "
                    "FBI (Sesgo de Frecuencia), ETS (Equitable Threat Score) y HSS (Heidke Skill Score)."
                )
            )

        use_extremes = st.checkbox("Cuantiles Extremos (P90, P95, P99)", value=True, help="Diagnóstico de extremos y colas de distribución.")

    # Estilo Visual
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎨 Estilo Visual y Paletas")
    color_theme = st.sidebar.selectbox(
        "Tema Gráfico",
        options=["Pastel Climatológico (Recomendado)", "Científica Viridis/Turbo", "Clásica Alto Contraste"],
        index=0,
        help="Ajusta la paleta de colores para figuras, boxplots y curvas temporales."
    )

    theme_code = "pastel" if "Pastel" in color_theme else ("scientific" if "Científica" in color_theme else "classic")

    label_mode_choice = st.sidebar.selectbox(
        "🏷️ Etiquetas de Estaciones en Mapas",
        options=[
            "🔄 Automático (Según escala y densidad)",
            "🔢 Forzar Etiquetas Numéricas (Siempre mostrar)",
            "📍 Solo Marcadores (Sin etiquetas flotantes)",
        ],
        index=0,
        help="Permite forzar o adaptar la visualización de los valores numéricos sobre cada estación en los mapas."
    )
    if "Forzar" in label_mode_choice:
        show_labels_val = True
        label_mode_val = "always"
    elif "Solo Marcadores" in label_mode_choice:
        show_labels_val = False
        label_mode_val = "never"
    else:
        show_labels_val = None
        label_mode_val = "auto"

    # Opciones adicionales
    eval_stats = st.sidebar.checkbox("Generar Productos de Evaluación Estadística (--eval)", value=True)
    export_csv = st.sidebar.checkbox("Exportar CSVs de Comparación y Métricas", value=True)

    # Persistir rutas actuales y opciones en user_settings.json
    try:
        set_stored_paths_for_var(
            product=product.value,
            var=var,
            paths={
                "csv_path": csv_path.strip(),
                "dir_original": dir_original.strip(),
                "dir_merged": dir_merged.strip(),
                "dem_path": dem_path.strip() if dem_path else "",
                "out_dir": out_dir.strip(),
            },
        )
        save_user_settings({
            "last_product": product.value,
            "last_var": var,
            "last_mode": mode.value,
            "yini": yini,
            "yend": yend,
            "out_dir": out_dir.strip(),
        })
    except Exception:
        pass

    # Construir objeto AnalysisRequest
    req = AnalysisRequest(
        product=product,
        csv_path=csv_path.strip(),
        dir_original=dir_original.strip(),
        dir_merged=dir_merged.strip(),
        out_dir=out_dir.strip(),
        var=var,
        stat=stat,
        dem_path=dem_path.strip() if dem_path else None,
        prefix_original="temp_" if is_chirts else "precip_",
        mode=mode,
        yini=int(yini),
        yend=int(yend),
        date_str=date_str,
        period_type=period_type,
        season=season,
        all_seasons=all_seasons,
        months=months,
        eval_stats=eval_stats,
        export_csv=export_csv,
        extent=extent,
        rain_threshold=float(rain_th),
        color_theme=theme_code,
        show_labels=show_labels_val,
        label_mode=label_mode_val,
    )

    st.sidebar.markdown("---")
    col_btn1, col_btn2 = st.sidebar.columns(2)
    with col_btn1:
        validate_clicked = st.button("🔍 Validar Entradas", width="stretch")
    with col_btn2:
        run_clicked = st.button("🚀 Ejecutar Análisis", type="primary", width="stretch")

    return req, run_clicked, validate_clicked, nav_section
