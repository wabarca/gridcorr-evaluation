import os
import time
import datetime
from typing import Optional
import streamlit as st

from ..application.models import AnalysisRequest, AnalysisResult
from ..application.validators import validate_analysis_request
from ..application.services import detect_existing_results, clear_existing_results
from ..application.task_manager import task_manager, TaskStatus, TaskState
from .components.sidebar import render_sidebar
from .components.maps_viewer import render_maps_viewer
from .components.stations_viewer import render_stations_viewer
from .components.doy_viewer import render_doy_viewer
from .components.metrics_viewer import render_metrics_viewer
from .components.export_viewer import render_export_viewer
from .components.documentation import render_scientific_documentation


@st.fragment(run_every="1s")
def render_active_task_monitor():
    """
    Componente reactivo fragmentado que consulta el estado del TaskManager cada segundo
    sin bloquear el Event Loop de Streamlit ni causar desconexiones de WebSocket.
    """
    active_task = task_manager.get_active_task()
    if active_task is None:
        return

    snap = active_task.get_snapshot()
    status = snap["status"]

    if status == TaskStatus.RUNNING:
        st.markdown("### ⚙️ Procesamiento Científico en Segundo Plano")

        prog_col, stop_col = st.columns([4, 1])
        with prog_col:
            st.progress(snap["progress"])
            mins, secs = divmod(int(snap["elapsed_seconds"]), 60)
            time_str = f"{mins:02d}:{secs:02d}"
            st.info(f"⏳ **{int(snap['progress'] * 100)}%** — {snap['current_message']} *(Tiempo transcurrido: {time_str})*")

        with stop_col:
            if st.button("🛑 Detener Cálculo", key="btn_stop_bg_task", use_container_width=True, type="secondary"):
                active_task.request_cancel()
                st.toast("🛑 Solicitud de cancelación enviada...", icon="🛑")
                st.rerun(scope="fragment")

        with st.expander("📋 Registro de Ejecución en Tiempo Real (Consola)", expanded=True):
            recent_logs = snap["logs"][-35:] if snap["logs"] else ["Iniciando ejecución..."]
            st.code("\n".join(recent_logs), language="bash")

    elif status == TaskStatus.COMPLETED:
        st.success("🎉 ¡Análisis completado exitosamente!")
        st.session_state["analysis_result"] = snap["result"]
        task_manager.clear_active_task(force=True)
        st.rerun()

    elif status == TaskStatus.CANCELLED:
        st.warning("🛑 **Cálculo detenido por el usuario.**")
        if snap["result"] is not None:
            st.session_state["analysis_result"] = snap["result"]
        task_manager.clear_active_task(force=True)
        st.rerun()

    elif status == TaskStatus.FAILED:
        st.error(f"❌ **Error durante el procesamiento:** {snap['error']}")
        if snap["result"] is not None:
            st.session_state["analysis_result"] = snap["result"]
        task_manager.clear_active_task(force=True)
        st.rerun()


def run_gui_app():
    """Punto de entrada principal de la interfaz Streamlit."""
    st.set_page_config(
        page_title="CHIRTS & CHIRPS Evaluation Toolkit",
        page_icon="🌦️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Encabezado principal
    st.title("🌦️ CHIRTS & CHIRPS Evaluation & Visualization Platform")
    st.markdown(
        """
        **Plataforma Científica para la Evaluación, Comparación y Diagnóstico de Productos Grillados Climatológicos**  
        *Desarrollado por:* **William Abarca**  
        *Institución:* Gerencia de Meteorología, Observatorio de Amenazas y Recursos Naturales, Ministerio de Medio Ambiente y Recursos Naturales (MARN)
        """
    )
    st.markdown("---")

    # Inicializar estado de sesión
    if "analysis_result" not in st.session_state:
        st.session_state["analysis_result"] = None

    # Renderizar Sidebar
    req, run_clicked, validate_clicked, nav_section = render_sidebar()

    # Si el usuario seleccionó la sección de Documentación en el menú principal
    if "Documentación" in nav_section:
        render_scientific_documentation()
        return

    # Manejar botón de validación previa
    if validate_clicked:
        val_res = validate_analysis_request(req)
        if val_res.is_valid:
            st.success("✅ **Validación Exitosa**: Todos los archivos, rutas y parámetros son correctos y están listos para ejecutarse.")
            if val_res.warnings:
                for w in val_res.warnings:
                    st.warning(f"⚠️ {w}")

            with st.expander("📋 **Resumen de Configuración y Rutas Verificadas**", expanded=True):
                c_conf1, c_conf2 = st.columns(2)
                with c_conf1:
                    st.markdown("#### ⚙️ Parámetros del Análisis")
                    st.markdown(f"- **Producto:** `{req.product.value.upper()}`")
                    st.markdown(f"- **Variable:** `{req.var.upper()}`")
                    st.markdown(f"- **Modo:** `{req.mode.value}`")
                    st.markdown(f"- **Estadístico:** `{req.stat.value}`")
                    if req.mode.value == "daily":
                        st.markdown(f"- **Fecha:** `{req.date_str}`")
                    elif req.mode.value == "period":
                        period_label = req.season if req.season else (f"Meses {req.months}" if req.months else "Temporada")
                        st.markdown(f"- **Período:** `{period_label}` ({req.yini}–{req.yend})")
                    else:
                        st.markdown(f"- **Rango de Años:** `{req.yini}` — `{req.yend}` ({req.yend - req.yini + 1} años)")

                with c_conf2:
                    st.markdown("#### 🗺️ Opciones Cartográficas y Salidas")
                    ext_str = f"`{req.extent}`" if req.extent else "*(Automático según dominio)*"
                    st.markdown(f"- **Extensión Espacial:** {ext_str}")
                    st.markdown(f"- **Evaluación Estadística (`--eval`):** `{'Sí' if req.eval_stats else 'No'}`")
                    st.markdown(f"- **Exportación de CSVs:** `{'Sí' if req.export_csv else 'No'}`")
                    st.markdown(f"- **Tema Visual:** `{req.color_theme.title()}`")
                    st.markdown(f"- **Etiquetas en Estaciones:** `{req.label_mode.title()}`")

                st.markdown("---")
                st.markdown("#### 📂 Rutas de Entrada y Salida Verificadas")
                st.markdown(f"- 📊 **CSV de Estaciones Terrestres:** `{req.csv_path}`")
                st.markdown(f"- 🛰️ **Directorio NetCDF Original (Raw):** `{req.dir_original}`")
                st.markdown(f"- 🧩 **Directorio NetCDF Corregido (CDT Merged):** `{req.dir_merged}`")
                if req.dem_path:
                    st.markdown(f"- 🏔️ **Modelo Digital de Elevación (DEM):** `{req.dem_path}`")
                st.markdown(f"- 💾 **Directorio de Salida de Resultados:** `{req.out_dir}`")
        else:
            st.error("❌ **Errores de validación encontrados:**")
            for err in val_res.errors:
                st.error(f"• {err}")

    # Verificar si hay una tarea en ejecución en segundo plano
    active_task = task_manager.get_active_task()
    is_task_running = active_task is not None and active_task.status == TaskStatus.RUNNING

    if run_clicked and not is_task_running:
        val_res = validate_analysis_request(req)
        if not val_res.is_valid:
            st.error("❌ **No se puede iniciar el análisis debido a errores de configuración:**")
            for err in val_res.errors:
                st.error(f"• {err}")
        else:
            task_manager.start_task(req, clear_first=False)
            st.session_state["analysis_result"] = None
            st.rerun()

    # Si una tarea está ejecutándose en background, mostrar monitor reactivo y no renderizar pestañas aún
    if is_task_running:
        render_active_task_monitor()
        return

    # Presentación de Resultados o Detección de Resultados Previos
    result: Optional[AnalysisResult] = st.session_state.get("analysis_result", None)

    if result is None:
        # Detectar si ya existen archivos calculados en el directorio de salida
        existing_result = detect_existing_results(req.out_dir, req)
        if existing_result is not None and (existing_result.generated_maps or existing_result.generated_csvs):
            meta = existing_result.completion_metadata or {}
            is_comp = existing_result.is_completed

            if is_comp:
                completed_time = meta.get("completed_at", "")
                time_str = f" ({completed_time[:19].replace('T', ' ')})" if completed_time else ""
                st.success(
                    f"✅ **Ejecución previa COMPLETADA exitosamente{time_str} en `{req.out_dir}`:**\n\n"
                    f"- 🗺️ **{len(existing_result.generated_maps)}** mapas espaciales generados\n"
                    f"- 📊 **{len(existing_result.generated_plots)}** gráficos diagnósticos y estadísticos\n"
                    f"- 📁 **{len(existing_result.generated_csvs)}** archivos de datos y métricas CSV\n\n"
                    f"Todos los productos están completos y listos para ser visualizados o analizados."
                )
                col_load, col_recalc, col_clean = st.columns([1.5, 1, 1])
                with col_load:
                    if st.button("📂 Visualizar Resultados Existentes", use_container_width=True, type="primary"):
                        st.session_state["analysis_result"] = existing_result
                        st.rerun()
                with col_recalc:
                    if st.button("🔄 Limpiar y Recalcular", use_container_width=True, help="Elimina los archivos previos y ejecuta el cálculo desde cero"):
                        val_res = validate_analysis_request(req)
                        if val_res.is_valid:
                            task_manager.start_task(req, clear_first=True)
                            st.session_state["analysis_result"] = None
                            st.rerun()
                        else:
                            st.error("❌ Parámetros inválidos para recalcular.")
                with col_clean:
                    if st.button("🧹 Limpiar Resultados", use_container_width=True, help="Elimina los archivos del directorio de salida y reinicia a la pantalla inicial"):
                        clear_existing_results(req.out_dir)
                        st.session_state["analysis_result"] = None
                        st.toast("✅ Resultados eliminados correctamente del disco.", icon="🧹")
                        st.rerun()
            else:
                st.warning(
                    f"⚠️ **Ejecución previa INCONCLUSA o interrumpida detectada en `{req.out_dir}`:**\n\n"
                    f"- 🗺️ **{len(existing_result.generated_maps)}** mapas espaciales parciales\n"
                    f"- 📊 **{len(existing_result.generated_plots)}** gráficos parciales\n"
                    f"- 📁 **{len(existing_result.generated_csvs)}** archivos CSV parciales\n\n"
                    f"El proceso anterior no finalizó por completo. Se recomienda hacer clic en **'Limpiar y Recalcular'** para generar la evaluación completa de manera consistente."
                )
                col_recalc, col_load, col_clean = st.columns([1.5, 1, 1])
                with col_recalc:
                    if st.button("🚀 Limpiar y Recalcular (Recomendado)", use_container_width=True, type="primary", help="Elimina los archivos parciales y ejecuta el cálculo completo"):
                        val_res = validate_analysis_request(req)
                        if val_res.is_valid:
                            task_manager.start_task(req, clear_first=True)
                            st.session_state["analysis_result"] = None
                            st.rerun()
                        else:
                            st.error("❌ Parámetros inválidos para recalcular.")
                with col_load:
                    if st.button("📂 Inspeccionar Archivos Parciales", use_container_width=True, type="secondary"):
                        st.session_state["analysis_result"] = existing_result
                        st.rerun()
                with col_clean:
                    if st.button("🧹 Limpiar Resultados", use_container_width=True, help="Elimina los archivos del directorio de salida y reinicia a la pantalla inicial"):
                        clear_existing_results(req.out_dir)
                        st.session_state["analysis_result"] = None
                        st.toast("✅ Resultados eliminados correctamente del disco.", icon="🧹")
                        st.rerun()
        else:
            st.info("👈 Configure los parámetros en el panel lateral y haga clic en **'Ejecutar Análisis'**.")
            with st.expander("📚 Consultar Documentación Científica y Justificación de Estadísticos", expanded=False):
                render_scientific_documentation()

    elif result is not None:
        # Barra superior de acciones para resultados activos
        col_title, col_clean_act, col_recalc_act = st.columns([3, 1, 1])
        with col_title:
            prod_name = result.request.product.value.upper() if result.request else "CLIMÁTICO"
            st.subheader(f"📊 Resultados de Evaluación — {prod_name}")
        with col_clean_act:
            if st.button("🧹 Limpiar Resultados", help="Elimina los archivos del directorio de salida y reinicia la vista", use_container_width=True):
                if result.output_dir:
                    clear_existing_results(result.output_dir)
                st.session_state["analysis_result"] = None
                st.toast("✅ Directorio limpiado y vista restablecida.", icon="🧹")
                st.rerun()
        with col_recalc_act:
            if st.button("🔄 Limpiar y Recalcular", help="Borra las salidas existentes y vuelve a calcular desde cero", use_container_width=True):
                val_res = validate_analysis_request(req)
                if val_res.is_valid:
                    task_manager.start_task(req, clear_first=True)
                    st.session_state["analysis_result"] = None
                    st.rerun()
                else:
                    st.error("❌ Parámetros inválidos para recalcular.")

    # Renderizar pestañas interactivas si existen resultados activos
    if result is not None:
        main_tab1, main_tab2, main_tab3, main_tab4, main_tab5, main_tab6, main_tab7 = st.tabs([
            "🗺️ Mapas Cartográficos y Espaciales",
            "📍 Desempeño en Estaciones",
            "📅 Climatología DOY",
            "📊 Métricas y Rankings",
            "📦 Exportación y Descargas",
            "📋 Registro de Ejecución",
            "📚 Documentación Científica",
        ])

        with main_tab1:
            render_maps_viewer(result)

        with main_tab2:
            render_stations_viewer(result)

        with main_tab3:
            render_doy_viewer(result)

        with main_tab4:
            render_metrics_viewer(result)

        with main_tab5:
            render_export_viewer(result)

        with main_tab6:
            st.subheader("📋 Registro Detallado de Ejecución")
            
            # Tarjetas resumen de estado
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                status_label = "✅ Exitoso" if result.success else "🛑 Detenido / Error"
                st.metric("Estado", status_label)
            with c2:
                st.metric("Mapas Generados", len(result.generated_maps))
            with c3:
                st.metric("Gráficos Generados", len(result.generated_plots))
            with c4:
                st.metric("Archivos CSV", len(result.generated_csvs))

            st.markdown("---")
            log_text = "\n".join(result.execution_logs) if result.execution_logs else "No hay registros disponibles."
            st.text_area("Consola de eventos y pasos ejecutados:", value=log_text, height=350)
            
            st.download_button(
                "📥 Descargar Registro de Ejecución (.log)",
                data=log_text,
                file_name="registro_ejecucion_evaluacion.log",
                mime="text/plain",
                use_container_width=False
            )

        with main_tab7:
            render_scientific_documentation()


if __name__ == "__main__":
    run_gui_app()
