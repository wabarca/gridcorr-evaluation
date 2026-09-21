# -*- coding: utf-8 -*-
"""
Scientific and visualization constants for CHIRPS & CHIRTS evaluations.
"""

import os
import matplotlib as mpl
mpl.use("Agg")
from matplotlib import font_manager

# Missing data / fill values
FILL_VALUE = -99.0

# Spanish month names abbreviations
MONTH_NAMES_ES = {
    1: "Ene",
    2: "Feb",
    3: "Mar",
    4: "Abr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dic",
}

# Climate seasons definition (Central America Climate Outlook Forum - FCAC + Standard Meteorological)
SEASONS = {
    # Foro del Clima de América Central (FCAC)
    "DJFM": {"months": [12, 1, 2, 3], "cross_year": True},
    "A": {"months": [4], "cross_year": False},
    "MJJ": {"months": [5, 6, 7], "cross_year": False},
    "ASO": {"months": [8, 9, 10], "cross_year": False},
    "N": {"months": [11], "cross_year": False},
    # Estaciones Meteorológicas Estándar
    "DJF": {"months": [12, 1, 2], "cross_year": True},
    "MAM": {"months": [3, 4, 5], "cross_year": False},
    "JJA": {"months": [6, 7, 8], "cross_year": False},
    "SON": {"months": [9, 10, 11], "cross_year": False},
    "JJAS": {"months": [6, 7, 8, 9], "cross_year": False},
}

from matplotlib.colors import ListedColormap
import numpy as np

# Custom 20-color palette for precipitation (CHIRPS)
CHIRPS_RAIN_COLORS = [
    "#FBF2B7",
    "#E7EA86",
    "#D2E154",
    "#B0D073",
    "#8EBF92",
    "#79BAA1",
    "#64B4AF",
    "#4EBDC6",
    "#4BC7DB",
    "#49ACD4",
    "#258CCF",
    "#3162CB",
    "#2653B2",
    "#1B4499",
    "#103E9A",
    "#383082",
    "#4C2976",
    "#602169",
    "#5A104C",
    "#3A012E",
]

CHIRPS_RAIN_CMAP = ListedColormap(CHIRPS_RAIN_COLORS, name="chirps_rain_custom")
try:
    mpl.colormaps.register(name="chirps_rain_custom", cmap=CHIRPS_RAIN_CMAP, force=True)
except Exception:
    pass

# Color palettes & styling
COLOR_PALETTES = {
    "chirts_field": "RdYlBu_r",
    "chirps_field": "chirps_rain_custom",
    "delta_divergent": "RdBu_r",
    "improvement_divergent": "RdBu_r",
    "coolwarm": "coolwarm",
    "pastel_orange": "#fdd0a2",
    "edge_orange": "#e6550d",
    "pastel_blue": "#c6dbef",
    "edge_blue": "#2171b5",
    "pastel_green": "#c7e9c0",
    "edge_green": "#238b45",
    "grid_alpha": 0.25,
}

# 3 Distinct scales for precipitation (CHIRPS)
# 1. Daily rain (0 - 500 mm, step 25 mm -> 20 intervals / 21 edges)
CHIRPS_DAILY_LEVELS = np.arange(0, 525, 25)
CHIRPS_DAILY_TICKS = np.arange(0, 550, 50)
CHIRPS_DAILY_VMAX = 500.0

# 2. Monthly / Seasonal rain (0 - 2000 mm, step 100 mm -> 20 intervals / 21 edges)
CHIRPS_PERIOD_LEVELS = np.arange(0, 2100, 100)
CHIRPS_PERIOD_TICKS = np.arange(0, 2200, 200)
CHIRPS_PERIOD_VMAX = 2000.0

# 3. Annual rain (0 - 4000 mm, step 200 mm -> 20 intervals / 21 edges)
CHIRPS_ANNUAL_LEVELS = np.arange(0, 4200, 200)
CHIRPS_ANNUAL_TICKS = np.arange(0, 4400, 400)
CHIRPS_ANNUAL_VMAX = 4000.0

# Default plotting scales
CHIRPS_BINS = 20
CHIRPS_MAX_MM = 4000.0

CHIRTS_BINS = 25
CHIRTS_VMIN = 0.0
CHIRTS_VMAX = 50.0

# Default extents (xmin, xmax, ymin, ymax)
DEFAULT_EXTENTS = {
    "el_salvador": (-90.3, -87.5, 13.0, 14.6),
    "centroamerica": (-93.0, -77.0, 7.0, 19.0),
}

# Month ticks and labels for DOY climatology
DOY_MONTH_TICKS = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
DOY_MONTH_LABELS = [
    "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"
]

# Configure Cartopy Data Directory if present
cartopy_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cartopy_data")
if os.path.exists(cartopy_dir):
    os.environ["CARTOPY_DATA_DIR"] = cartopy_dir

# Font configuration
preferred_font = "Calibri"
available_fonts = {f.name for f in font_manager.fontManager.ttflist}
if preferred_font in available_fonts:
    mpl.rcParams["font.family"] = preferred_font
else:
    mpl.rcParams["font.family"] = "DejaVu Sans"

mpl.rcParams["axes.titlesize"] = 12
mpl.rcParams["figure.titlesize"] = 14
mpl.rcParams["axes.labelsize"] = 10
mpl.rcParams["xtick.labelsize"] = 9
mpl.rcParams["ytick.labelsize"] = 9
