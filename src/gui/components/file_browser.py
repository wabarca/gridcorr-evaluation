# -*- coding: utf-8 -*-
"""
File and Directory native dialog picker component for Streamlit UI.
Allows selecting files (.csv, .nc) or folders via native OS file dialogs (tkinter).
"""

import os
import streamlit as st
from typing import Optional


def open_native_dialog(
    target_type: str = "dir",
    initial_dir: Optional[str] = None,
) -> Optional[str]:
    """
    Abre un cuadro de diálogo nativo del sistema operativo (Windows / Linux / macOS)
    para seleccionar archivos o carpetas usando Tkinter.

    Parámetros
    ----------
    target_type : str
        'dir' (carpetas), 'csv' (archivos CSV), 'nc' (archivos NetCDF), 'file' (cualquier archivo).
    initial_dir : str, opcional
        Directorio o ruta de inicio para el explorador.

    Retorna
    -------
    str o None
        Ruta absoluta seleccionada si se eligió un archivo/carpeta, de lo contrario None.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        start_dir = initial_dir if (initial_dir and os.path.exists(initial_dir)) else os.getcwd()
        if os.path.isfile(start_dir):
            start_dir = os.path.dirname(start_dir)

        selected = ""
        if target_type == "dir":
            selected = filedialog.askdirectory(
                initialdir=start_dir,
                title="Seleccionar Carpeta",
            )
        elif target_type == "csv":
            selected = filedialog.askopenfilename(
                initialdir=start_dir,
                title="Seleccionar Archivo CSV de Estaciones (CDT)",
                filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")],
            )
        elif target_type == "nc":
            selected = filedialog.askopenfilename(
                initialdir=start_dir,
                title="Seleccionar Archivo NetCDF (DEM)",
                filetypes=[("Archivos NetCDF", "*.nc *.nc4"), ("Todos los archivos", "*.*")],
            )
        else:
            selected = filedialog.askopenfilename(
                initialdir=start_dir,
                title="Seleccionar Archivo",
                filetypes=[("Todos los archivos", "*.*")],
            )

        root.destroy()
        if selected:
            return os.path.abspath(selected)
        return None
    except Exception as e:
        st.warning(f"No se pudo abrir el cuadro de diálogo nativo: {e}")
        return None


def on_dialog_button_click(
    target_session_key: str,
    target_type: str,
    initial_dir: Optional[str] = None,
) -> None:
    """
    Callback de Streamlit para abrir el cuadro de diálogo y actualizar
    directamente el estado de session_state antes de instanciar el widget.
    """
    chosen = open_native_dialog(target_type=target_type, initial_dir=initial_dir)
    if chosen:
        st.session_state[target_session_key] = chosen


def render_file_picker_button(
    target_session_key: str,
    target_type: str = "dir",
    initial_dir: Optional[str] = None,
    label: str = "Explorar",
    key_prefix: Optional[str] = None,
) -> None:
    """
    Renderiza un botón que abre un cuadro de diálogo nativo y actualiza
    de forma reactiva la clave de session_state asociada.
    """
    prefix = key_prefix or target_session_key
    button_label = f"📁 {label}" if target_type == "dir" else f"📄 {label}"
    
    st.button(
        button_label,
        key=f"{prefix}_dialog_btn",
        on_click=on_dialog_button_click,
        args=(target_session_key, target_type, initial_dir),
        help=f"Abrir cuadro de diálogo para seleccionar {'carpeta' if target_type == 'dir' else 'archivo'}",
    )


# Alias de compatibilidad
render_file_browser_modal = render_file_picker_button
