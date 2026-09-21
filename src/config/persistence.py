# -*- coding: utf-8 -*-
"""
Configuration persistence module.
Saves and loads user-configured paths, parameters, and application state to disk
so settings survive browser inactivity, tab reloads, and Streamlit session disconnects.
"""

import os
import json
from typing import Dict, Any, Optional

SETTINGS_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "user_settings.json")
)


def load_user_settings() -> Dict[str, Any]:
    """
    Carga la configuración persistida del usuario desde el archivo JSON local.
    Si no existe o ocurre un error, retorna un diccionario vacío.
    """
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_user_settings(data: Dict[str, Any]) -> None:
    """
    Guarda la configuración persistente en el archivo JSON local.
    """
    try:
        current = load_user_settings()
        current.update(data)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_stored_paths_for_var(product: str, var: str) -> Dict[str, str]:
    """
    Obtiene las rutas personalizadas guardadas para una combinación dada de producto y variable.
    """
    settings = load_user_settings()
    paths_by_var = settings.get("paths_by_var", {})
    key = f"{product.lower()}_{var.lower()}"
    return paths_by_var.get(key, {})


def set_stored_paths_for_var(product: str, var: str, paths: Dict[str, str]) -> None:
    """
    Almacena las rutas personalizadas para una combinación de producto y variable.
    """
    settings = load_user_settings()
    if "paths_by_var" not in settings:
        settings["paths_by_var"] = {}
    key = f"{product.lower()}_{var.lower()}"
    settings["paths_by_var"][key] = paths
    save_user_settings(settings)
