# -*- coding: utf-8 -*-
"""
Export and download manager UI component.
Includes directory explorer, interactive file viewer, and ZIP package creation.
"""

import os
import io
import time
import zipfile
import pandas as pd
import streamlit as st
from ...application.models import AnalysisResult


def _create_zip_bundle(output_dir: str) -> bytes:
    """Empaqueta todos los archivos de salida en un buffer ZIP en memoria."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, output_dir)
                zf.write(file_path, arcname=rel_path)
    buffer.seek(0)
    return buffer.getvalue()


def _format_bytes(size_bytes: int) -> str:
    """Formatea bytes en formato legible (KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def render_export_viewer(result: AnalysisResult) -> None:
    """
    Renderiza el centro de descargas, explorador de directorios y previsualizador de archivos.
    """
    st.subheader("📦 Centro de Exportación, Descargas y Explorador de Directorio")

    out_dir = result.output_dir
    all_files = result.generated_maps + result.generated_plots + result.generated_csvs

    if not all_files and not (out_dir and os.path.exists(out_dir)):
        st.info("No hay archivos generados disponibles para descargar o explorar.")
        return

    st.success(f"Se han generado un total de **{len(all_files)} archivos clave** en el directorio local:")
    st.code(out_dir, language="bash")

    # Botón de descarga ZIP consolidado
    if out_dir and os.path.exists(out_dir):
        zip_bytes = _create_zip_bundle(out_dir)
        st.download_button(
            label="📥 Descargar Paquete ZIP Completo con Todos los Resultados",
            data=zip_bytes,
            file_name="resultados_evaluacion_chirpts.zip",
            mime="application/zip",
            type="primary",
            width="stretch"
        )

    st.markdown("---")

    # =========================================================================
    # SECCIÓN: EXPLORADOR DE DIRECTORIO DE RESULTADOS
    # =========================================================================
    st.markdown("### 📂 Explorador de Archivos y Subcarpetas Locales")
    st.caption("Inspeccione y previsualice en vivo cualquier producto generado en el disco duro sin salir de la plataforma.")

    if out_dir and os.path.exists(out_dir):
        file_records = []
        for root, _, files in os.walk(out_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, out_dir)
                size = os.path.getsize(fpath)
                mtime = os.path.getmtime(fpath)
                ext = os.path.splitext(fname)[1].lower()

                category = "Otro"
                if ext == ".png":
                    category = "🖼️ Imagen / Mapa PNG"
                elif ext == ".csv":
                    category = "📊 Tabla CSV"
                elif ext in [".nc", ".nc4"]:
                    category = "🛰️ Malla NetCDF"
                elif ext in [".txt", ".log"]:
                    category = "📄 Texto / Log"

                file_records.append({
                    "Subcarpeta": os.path.dirname(rel_path) if os.path.dirname(rel_path) else ".",
                    "Archivo": fname,
                    "Tipo": category,
                    "Tamaño": _format_bytes(size),
                    "Tamaño_Bytes": size,
                    "Última Modificación": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime)),
                    "Ruta_Absoluta": fpath
                })

        if file_records:
            df_files = pd.DataFrame(file_records)

            col_filt1, col_filt2 = st.columns([2, 2])
            with col_filt1:
                categories = ["Todas"] + sorted(df_files["Tipo"].unique().tolist())
                sel_cat = st.selectbox("Filtrar por tipo de archivo:", options=categories, key="filter_export_category")
            with col_filt2:
                search_kw = st.text_input("Buscar por nombre o palabra clave:", placeholder="ej. 1995, bias, station...", key="search_export_files")

            df_display = df_files.copy()
            if sel_cat != "Todas":
                df_display = df_display[df_display["Tipo"] == sel_cat]
            if search_kw:
                df_display = df_display[df_display["Archivo"].str.contains(search_kw, case=False, na=False) | df_display["Subcarpeta"].str.contains(search_kw, case=False, na=False)]

            st.dataframe(
                df_display[["Subcarpeta", "Archivo", "Tipo", "Tamaño", "Última Modificación"]].reset_index(drop=True),
                width="stretch"
            )

            # Previsualizador interactivo
            st.markdown("#### 👁️ Previsualizador Rápido de Archivo")
            preview_options = df_display["Ruta_Absoluta"].tolist()
            if preview_options:
                sel_preview = st.selectbox(
                    "Seleccione un archivo de la lista para previsualizar:",
                    options=preview_options,
                    format_func=lambda x: f"{os.path.basename(os.path.dirname(x))}/{os.path.basename(x)}" if os.path.dirname(x) != out_dir else os.path.basename(x),
                    key="select_preview_file"
                )

                if sel_preview and os.path.exists(sel_preview):
                    ext = os.path.splitext(sel_preview)[1].lower()
                    p_col1, p_col2 = st.columns([3, 1])
                    with p_col2:
                        with open(sel_preview, "rb") as f_prev:
                            file_data = f_prev.read()
                        mime_type = "image/png" if ext == ".png" else ("text/csv" if ext == ".csv" else "application/octet-stream")
                        st.download_button(
                            label=f"⬇️ Descargar {os.path.basename(sel_preview)}",
                            data=file_data,
                            file_name=os.path.basename(sel_preview),
                            mime=mime_type,
                            key=f"dl_single_prev_{sel_preview}"
                        )
                        st.caption(f"📁 **Ruta:** `{sel_preview}`")

                    with p_col1:
                        if ext == ".png":
                            st.image(sel_preview, caption=os.path.basename(sel_preview), width="stretch")
                        elif ext == ".csv":
                            try:
                                df_csv_prev = pd.read_csv(sel_preview)
                                st.dataframe(df_csv_prev.head(100), width="stretch")
                                st.caption(f"Mostrando primeras 100 filas de {len(df_csv_prev)} registros.")
                            except Exception as ex:
                                st.warning(f"No se pudo cargar vista previa de la tabla CSV: {ex}")
                        elif ext in [".txt", ".log"]:
                            try:
                                with open(sel_preview, "r", encoding="utf-8", errors="ignore") as f_txt:
                                    st.text_area("Contenido del archivo:", f_txt.read(), height=250)
                            except Exception as ex:
                                st.warning(f"No se pudo leer archivo de texto: {ex}")
                        else:
                            st.info(f"Vista previa no disponible para archivos con extensión `{ext}`. Use el botón de descarga.")
        else:
            st.info("No se encontraron archivos en la carpeta de salida.")

    st.markdown("---")
    st.markdown("#### 📄 Descargas Rápidas")
    col_maps, col_csvs = st.columns(2)

    with col_maps:
        st.markdown("**Mapas y Gráficos (PNG)**")
        img_files = result.generated_maps + result.generated_plots
        for img_path in img_files[:15]:
            if os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    data = f.read()
                st.download_button(
                    label=f"🖼️ {os.path.basename(img_path)}",
                    data=data,
                    file_name=os.path.basename(img_path),
                    mime="image/png",
                    key=f"dl_fast_{img_path}"
                )
        if len(img_files) > 15:
            st.caption(f"...y {len(img_files) - 15} imágenes adicionales disponibles en el explorador.")

    with col_csvs:
        st.markdown("**Tablas y Series de Datos (CSV)**")
        for csv_path in result.generated_csvs[:15]:
            if os.path.exists(csv_path):
                with open(csv_path, "rb") as f:
                    data = f.read()
                st.download_button(
                    label=f"📊 {os.path.basename(csv_path)}",
                    data=data,
                    file_name=os.path.basename(csv_path),
                    mime="text/csv",
                    key=f"dl_fast_csv_{csv_path}"
                )
        if len(result.generated_csvs) > 15:
            st.caption(f"...y {len(result.generated_csvs) - 15} tablas adicionales disponibles en el explorador.")

