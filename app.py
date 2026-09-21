# -*- coding: utf-8 -*-
"""
Main Entry point for Streamlit Web Application.
Execute with: streamlit run app.py
"""

import sys
import os

# Asegurar que el directorio raíz esté en sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.gui.app import run_gui_app

if __name__ == "__main__":
    run_gui_app()
