# -*- coding: utf-8 -*-
"""
===============================================================================
Evaluación y visualización de CHIRTS vs CHIRTS Corregido
===============================================================================

Autor:        William Abarca
Contacto:     abarca.will@gmail.com
Fecha:        2026-02-01
Versión:      1.0 (Código funcional para evaluación CHIRTS)

Licencia:     GNU General Public License v3.0 (GPL-3.0)

Este programa es software libre: usted puede redistribuirlo y/o modificarlo
bajo los términos de la Licencia Pública General de GNU publicada por la Free
Software Foundation, ya sea la versión 3 de la Licencia, o (a su elección)
cualquier versión posterior.

Este programa se distribuye con la esperanza de que sea útil, pero SIN NINGUNA
GARANTÍA; sin incluso la garantía implícita de COMERCIALIZACIÓN o IDONEIDAD PARA
UN PROPÓSITO PARTICULAR. Vea la Licencia Pública General de GNU para más detalles.

Usted debería haber recibido una copia de la Licencia Pública General de GNU
junto con este programa. En caso contrario, vea <https://www.gnu.org/licenses/>.

-------------------------------------------------------------------------------
DESCRIPCIÓN
-------------------------------------------------------------------------------
Este script implementa un flujo completo para:

- Leer datos observados de estaciones (formato CSV tipo CDT).
- Cargar datos diarios en formato NetCDF de:
    * CHIRTS original
    * CHIRTS corregido
- Calcular estadísticos espaciales:
    * mean, max, min
- Generar mapas para visualización de resultados:
    * Mapas lado-a-lado (CHIRTS vs CHIRTS corregido)
    * Mapas de campo ΔGRID = Corregido − Original
    * Mapas de puntos en estaciones (ΔGRID en estaciones)
    * Mapas de mejora por estación (ΔRMSE, ΔMAE, etc.)
- Incluir relieve (hillshade) a partir de un DEM en NetCDF.
- Evaluar desempeño diario:
    * Bias, MAE, RMSE
    * Resúmenes globales y por estación
- Exportar CSV de comparación por estación:
    * obs, grid_raw, grid_corr
    * errores, errores absolutos y relativos
- Soportar diferentes modos de operación:
    * annual      : mapas por año con estadístico (mean/max/min)
    * daily       : mapas para un día específico
    * daily-eval  : evaluación diaria completa en toda la serie temporal
    * period      : mapas por períodos (estaciones climáticas o meses)

-------------------------------------------------------------------------------
USO (RESUMEN)
-------------------------------------------------------------------------------
Ver al final del archivo o ejecutar:

    python mapas_acumulados_chirts_anuales.py --help

para la lista completa de opciones y ejemplos de ejecución.

-------------------------------------------------------------------------------
DEPENDENCIAS PRINCIPALES
-------------------------------------------------------------------------------
- numpy
- pandas
- xarray
- matplotlib
- cartopy
- adjustText
- netCDF4
-------------------------------------------------------------------------------
FORMATO DE ENTRADAS
-------------------------------------------------------------------------------
1) CSV de estaciones (formato CDT):
   - Primera fila: IDs de estaciones
   - Segunda fila: longitudes
   - Tercera fila: latitudes
   - Cuarta fila: elevaciones
   - Filas siguientes: fecha (YYYYMMDD) + valores por estación

2) CHIRTS original diario:
   - Archivos tipo: <prefix>YYYYMMDD.nc  (por defecto: temp_YYYYMMDD.nc)

3) CHIRTS corregido diario:
   - Archivos tipo: <var>_mrg_YYYYMMDD.nc  (ej: tmax_mrg_19910101.nc)

4) DEM en NetCDF:
   - Un campo de elevación con coordenadas lat/lon

-------------------------------------------------------------------------------
MODOS DE EJECUCIÓN Y EJEMPLOS
-------------------------------------------------------------------------------

1) MODO ANUAL (mapas por año con estadístico):

python mapas_acumulados_chirts_anuales.py \
  --csv estaciones_tmax_formato_cdt.csv \
  --dir-chirts /datos/CHIRTS/CDT_NetCDF_Format/ \
  --dir-merged /datos/CHIRTS/MERGED_TEMP_Data_1Jan1991_31Dec2020/DATA/ \
  --var tmax \
  --stat max | mean | min | all \
  --mode annual \
  --dem elevacion.nc \
  --yini 1991 \
  --yend 2020 \
  --out ./salidas

2) MODO DIARIO (mapa para una fecha específica, es obligatorio el parámetro --date YYYY-MM-DD):

python mapas_acumulados_chirts_anuales.py \
  --csv estaciones_tmax_formato_cdt.csv \
  --dir-chirts /datos/CHIRTS/CDT_NetCDF_Format/ \
  --dir-merged /datos/CHIRTS/MERGED_TEMP_Data_1Jan1991_31Dec2020/DATA/ \
  --var tmax \
  --stat max | mean | min | all \
  --mode daily \
  --dem elevacion.nc \
  --date 1991-01-01 \
  --out ./salidas

3) MODO EVALUACIÓN DIARIA (serie completa):

python mapas_acumulados_chirts_anuales.py \
  --csv estaciones_tmax_formato_cdt.csv \
  --dir-chirts /datos/CHIRTS/CDT_NetCDF_Format/ \
  --dir-merged /datos/CHIRTS/MERGED_TEMP_Data_1Jan1991_31Dec2020/DATA/ \
  --var tmax \
  --mode daily-eval \
  --out ./salidas

Esto genera:
- Serie diaria completa
- Resumen global (Bias, MAE, RMSE)
- Resumen por estación

4) MODO PERÍODO - ESTACIÓN CLIMÁTICA (ej: DJFM):

python mapas_acumulados_chirts_anuales.py \
  --csv estaciones_tmax_formato_cdt.csv \
  --dir-chirts /datos/CHIRTS/CDT_NetCDF_Format/ \
  --dir-merged /datos/CHIRTS/MERGED_TEMP_Data_1Jan1991_31Dec2020/DATA/ \
  --var tmax \
  --stat max | mean | min | all \
  --mode period \
  --period-type season \
  --season DJFM | A | MJJ | ASO | N | --all-seasons \
  --yini 1991 \
  --yend 2020 \
  --dem elevacion.nc \
  --out ./salidas

5) MODO PERÍODO - MESES ESPECÍFICOS (ej: mayo-junio-julio):

python mapas_acumulados_chirts_anuales.py \
  --csv estaciones_tmax_formato_cdt.csv \
  --dir-chirts /datos/CHIRTS/CDT_NetCDF_Format/ \
  --dir-merged /datos/CHIRTS/MERGED_TEMP_Data_1Jan1991_31Dec2020/DATA/ \
  --var tmax \
  --stat max | mean | min | all \
  --mode period \
  --period-type months \
  --months 5,6,7 \
  --yini 1991 \
  --yend 2020 \
  --dem elevacion.nc \
  --out ./salidas

===============================================================================

"""
# ------------------------- Librerias y constantes -------------------------

import os
import re
import glob
import argparse
import warnings
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import xarray as xr

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, LightSource
from matplotlib import font_manager

import cartopy.crs as ccrs
import cartopy.feature as cfeature

warnings.filterwarnings("ignore")

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

os.environ["CARTOPY_DATA_DIR"] = os.path.join(os.path.dirname(__file__), "cartopy_data")

try:
    from adjustText import adjust_text
except ImportError:
    adjust_text = None

FILL_VALUE = -99.0

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

SEASONS = {
    "DJFM": {"months": [12, 1, 2, 3], "cross_year": True},
    "A": {"months": [4], "cross_year": False},
    "MJJ": {"months": [5, 6, 7], "cross_year": False},
    "ASO": {"months": [8, 9, 10], "cross_year": False},
    "N": {"months": [11], "cross_year": False},
}


PASTEL_ORANGE = "#fdd0a2"
EDGE_ORANGE = "#e6550d"
POINT_BLUE = "#1f77b4"
POINT_ORANGE = "#ff7f0e"
GRID_ALPHA = 0.25
PASTEL_BLUE = "#c6dbef"
PASTEL_GREEN = "#c7e9c0"
EDGE_BLUE = "#2171b5"
EDGE_GREEN = "#238b45"

# ------------------------- Funciones -------------------------


def process_year_worker(args):
    """
    Procesa un año completo de observaciones y genera la serie diaria de
    comparación entre CHIRTS original y corregido en estaciones.

    Parámetros
    ----------
    args : tuple
        (year, df_obs_long, dir_chirts, dir_merged, var, prefix_chirts)

    Retorna
    -------
    pandas.DataFrame
        Serie diaria del año con columnas: date, station_id, lon, lat, elev,
        obs, raw, corr.
    """
    year, df_obs_long, dir_chirts, dir_merged, var, prefix_chirts = args

    df_year = df_obs_long[df_obs_long["year"] == year]

    df_year_daily = build_daily_timeseries(
        df_obs_long=df_year,
        dir_chirts=dir_chirts,
        dir_merged=dir_merged,
        var=var,
        prefix_chirts=prefix_chirts,
    )

    return df_year_daily


def parse_cdt_csv(csv_path: str, value_name: str):
    """
    Lee un CSV de estaciones en formato CDT y lo convierte a formato largo.

    El archivo debe contener:
    - Fila 1: IDs de estaciones
    - Fila 2: longitudes
    - Fila 3: latitudes
    - Fila 4: elevaciones
    - Filas siguientes: fecha (YYYYMMDD) + valores por estación

    Parámetros
    ----------
    csv_path : str
        Ruta al archivo CSV.
    value_name : str
        Nombre de la columna de valores en el DataFrame largo (ej. 'tmax_station').

    Retorna
    -------
    meta : pandas.DataFrame
        Metadatos de estaciones con columnas: station_id, lon, lat, elev.
    df_obs_long : pandas.DataFrame
        Observaciones en formato largo con columnas: date, station_id, <value_name>,
        lon, lat, elev, year.
    """
    with open(csv_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    if len(lines) < 5:
        raise ValueError("CSV muy corto: se requieren al menos 5 líneas.")

    stations_raw = [s.strip() for s in lines[0].split(",")]
    lons_raw = [s.strip() for s in lines[1].split(",")]
    lats_raw = [s.strip() for s in lines[2].split(",")]
    elvs_raw = [s.strip() for s in lines[3].split(",")]

    station_ids = stations_raw[1:]
    lons = [float(x) if x not in ("", "NA", "-99") else np.nan for x in lons_raw[1:]]
    lats = [float(x) if x not in ("", "NA", "-99") else np.nan for x in lats_raw[1:]]
    elevs = [float(x) if x not in ("", "NA", "-99") else np.nan for x in elvs_raw[1:]]

    n = len(station_ids)
    if not (n == len(lons) == len(lats) == len(elevs)):
        raise ValueError("Metadatos no cuadran (IDs, lon, lat, elev).")

    date_pat = re.compile(r"^\d{8}$")
    data_rows = []
    for row in lines[4:]:
        if not row.strip():
            continue
        parts = [p.strip() for p in row.split(",")]
        date_str = parts[0]
        if not date_pat.match(date_str):
            continue
        vals = []
        for x in parts[1 : 1 + n]:
            if x in ("", "NA"):
                vals.append(np.nan)
            else:
                try:
                    v = float(x)
                    if v == FILL_VALUE:
                        v = np.nan
                    vals.append(v)
                except Exception:
                    vals.append(np.nan)

        data_rows.append([date_str] + vals)

    df_obs = pd.DataFrame(data_rows, columns=["date"] + station_ids)

    meta = pd.DataFrame(
        {"station_id": station_ids, "lon": lons, "lat": lats, "elev": elevs}
    )
    df_obs_long = df_obs.melt(
        id_vars="date", var_name="station_id", value_name=value_name
    )
    df_obs_long = df_obs_long.merge(meta, on="station_id", how="left")
    df_obs_long["year"] = df_obs_long["date"].str.slice(0, 4).astype(int)

    return meta, df_obs_long


def _figsize_from_extent(extent, base_height=5.5):
    """
    Calcula el tamaño de figura (ancho, alto) a partir de un extent geográfico,
    preservando la relación de aspecto del dominio.

    Parámetros
    ----------
    extent : tuple
        (xmin, xmax, ymin, ymax) en coordenadas geográficas.
    base_height : float, opcional
        Altura base de la figura en pulgadas.

    Retorna
    -------
    tuple
        (width, height) en pulgadas, ajustado al aspecto del extent.
    """
    xmin, xmax, ymin, ymax = extent
    dx = xmax - xmin
    dy = ymax - ymin
    if dy <= 0:
        return (base_height, base_height)
    aspect = dx / dy
    width = base_height * aspect
    return (width, base_height)


def _rename_coords_latlon(da: xr.DataArray) -> xr.DataArray:
    """
    Normaliza los nombres de coordenadas de un DataArray a 'lon' y 'lat'.

    Renombra automáticamente coordenadas comunes como 'longitude', 'x' → 'lon'
    y 'latitude', 'y' → 'lat', si existen.

    Parámetros
    ----------
    da : xarray.DataArray
        DataArray de entrada con coordenadas espaciales.

    Retorna
    -------
    xarray.DataArray
        DataArray con coordenadas renombradas a 'lon' y 'lat' cuando aplica.
    """
    coord_map = {}
    for cn in list(da.coords):
        low = cn.lower()
        if low in ["longitude", "long", "lon", "x"]:
            coord_map[cn] = "lon"
        elif low in ["latitude", "lat", "y"]:
            coord_map[cn] = "lat"
    if coord_map:
        da = da.rename(coord_map)
    return da


def load_annual_temp_stat(data_dir, year, prefix, varname, stat):
    """
    Carga archivos NetCDF diarios de un año (o subconjunto disponible) y calcula
    un estadístico sobre el período cubierto por los archivos encontrados.

    Busca archivos con patrón: <prefix><year>*.nc, concatena en tiempo y
    calcula el estadístico solicitado (mean, max o min).

    Parámetros
    ----------
    data_dir : str
        Directorio con los NetCDF diarios.
    year : int
        Año a procesar.
    prefix : str
        Prefijo de los archivos (ej. 'temp_').
    varname : str
        Nombre de la variable a extraer del NetCDF.
    stat : str
        Estadístico a calcular: 'mean', 'max' o 'min'.

    Retorna
    -------
    xarray.DataArray
        Campo anual con el estadístico solicitado.
    """
    glob_pat = os.path.join(data_dir, f"{prefix}{year}*.nc")
    files = sorted(glob.glob(glob_pat))
    if not files:
        raise FileNotFoundError(f"No se encontraron archivos: {glob_pat}")

    das = []
    for fp in files:
        ds = xr.open_dataset(fp)
        v = varname if varname in ds else list(ds.data_vars)[0]
        da = _rename_coords_latlon(ds[v])

        if "time" in da.coords and getattr(da["time"], "size", 0) == 1:
            da = da.squeeze("time", drop=True)

        da = da.where(da != FILL_VALUE)
        das.append(da)
        ds.close()

    da_all = xr.concat(das, dim="time")

    if stat == "mean":
        return da_all.mean("time", skipna=True)
    elif stat == "max":
        return da_all.max("time", skipna=True)
    elif stat == "min":
        return da_all.min("time", skipna=True)
    else:
        raise ValueError("stat inválido")


def annual_station_stat(
    df_obs_long: pd.DataFrame, year: int, stat: str, value_name: str
):
    """
    Calcula un estadístico anual de observaciones por estación.

    Filtra el DataFrame al año indicado y calcula mean, max o min por estación.

    Parámetros
    ----------
    df_obs_long : pandas.DataFrame
        Observaciones en formato largo con columnas que incluyen: year,
        station_id, lon, lat, elev y la columna de valores.
    year : int
        Año a procesar.
    stat : str
        Estadístico a calcular: 'mean', 'max' o 'min'.
    value_name : str
        Nombre de la columna con los valores observados.

    Retorna
    -------
    pandas.DataFrame
        DataFrame con columnas: station_id, lon, lat, elev, obs.
    """
    sub = df_obs_long[df_obs_long["year"] == year].copy()

    if stat == "mean":
        g = sub.groupby("station_id", as_index=False)[value_name].mean()
    elif stat == "max":
        g = sub.groupby("station_id", as_index=False)[value_name].max()
    elif stat == "min":
        g = sub.groupby("station_id", as_index=False)[value_name].min()
    else:
        raise ValueError("stat inválido")

    g = g.rename(columns={value_name: "obs"})
    st = sub[["station_id", "lon", "lat", "elev"]].drop_duplicates()
    out = g.merge(st, on="station_id", how="left")
    return out[["station_id", "lon", "lat", "elev", "obs"]]


def _place_text_no_overlap(ax, x, y, text, placed, dx=0.15, dy=0.15, max_tries=12):
    """
    Coloca una etiqueta de texto en un eje evitando solapamientos con etiquetas previas.

    Intenta desplazar la posición del texto siguiendo un patrón de offsets hasta que
    no se superponga con los bounding boxes ya colocados o se alcance el número máximo
    de intentos.

    Parámetros
    ----------
    ax : matplotlib.axes.Axes
        Eje donde se dibuja el texto.
    x, y : float
        Coordenadas del punto de referencia del texto (en datos del eje).
    text : str
        Texto a dibujar.
    placed : list
        Lista de bounding boxes ya colocados, usada para detectar solapamientos.
    dx, dy : float, opcional
        Desplazamientos en coordenadas de datos usados para probar nuevas posiciones.
    max_tries : int, opcional
        Número máximo de intentos de recolocación.

    Retorna
    -------
    matplotlib.text.Text
        Objeto de texto creado.
    """
    t = ax.text(
        x,
        y,
        text,
        transform=ax.transData,
        fontsize=7,
        ha="left",
        va="bottom",
        color="black",
        bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.85),
        zorder=6,
    )
    ax.figure.canvas.draw_idle()
    bbox = t.get_window_extent(renderer=ax.figure.canvas.get_renderer()).expanded(
        1.05, 1.05
    )
    pattern = [
        (dx, dy),
        (dx, -dy),
        (-dx, -dy),
        (-dx, dy),
        (dx, 0),
        (-dx, 0),
        (0, dy),
        (0, -dy),
    ]
    tries = 0
    while any(bbox.overlaps(b) for b in placed) and tries < max_tries:
        offx, offy = pattern[tries % len(pattern)]
        t.set_position((x + offx, y + offy))
        ax.figure.canvas.draw_idle()
        bbox = t.get_window_extent(renderer=ax.figure.canvas.get_renderer()).expanded(
            1.05, 1.05
        )
        tries += 1
    placed.append(bbox)
    return t


def plot_side_by_side(
    da_left: xr.DataArray,
    da_right: xr.DataArray,
    dem: xr.DataArray,
    year: int,
    var: str,
    stat: str,
    stations_obs_year: pd.DataFrame,
    out_png: str,
    bins: int = 25,
    vmin: float = 0.0,
    vmax: float = 50.0,
    cmap: str = "RdYlBu_r",
    extent: Optional[Tuple[float, float, float, float]] = None,
    render_mode: str = "alpha",
):
    """
    Genera un mapa comparativo lado a lado entre CHIRTS original y CHIRTS corregido.

    Dibuja dos paneles con la misma escala de colores y el mismo dominio espacial,
    superpone relieve (hillshade) a partir de un DEM y agrega los valores observados
    en estaciones como puntos con etiquetas. El panel izquierdo muestra el campo
    original y el panel derecho el campo corregido.

    Parámetros
    ----------
    da_left : xarray.DataArray
        Campo de CHIRTS original.
    da_right : xarray.DataArray
        Campo de CHIRTS corregido.
    dem : xarray.DataArray
        Modelo digital de elevación para el sombreado de relieve.
    year : int
        Año (o etiqueta temporal) a mostrar en el título.
    var : str
        Variable ('tmax' o 'tmin').
    stat : str
        Estadístico ('mean', 'max', 'min' o 'daily').
    stations_obs_year : pandas.DataFrame
        DataFrame con columnas: station_id, lon, lat, elev, obs.
    out_png : str
        Ruta del archivo PNG de salida.
    bins : int, opcional
        Número de intervalos para la escala discreta de colores.
    vmin, vmax : float, opcional
        Límites de la escala de colores.
    cmap : str, opcional
        Colormap a usar.
    extent : tuple, opcional
        (xmin, xmax, ymin, ymax) para fijar el dominio del mapa.
    render_mode : str, opcional
        Modo de renderizado del fondo (reservado para futuras variantes).

    Retorna
    -------
    None
        Guarda la figura en disco en la ruta indicada por `out_png`.
    """
    da_left = _rename_coords_latlon(da_left)
    da_right = _rename_coords_latlon(da_right)
    dem = _rename_coords_latlon(dem)

    proj = ccrs.PlateCarree()

    if extent is None:
        lon_vals = da_left["lon"].values
        lat_vals = da_left["lat"].values
        xmin = float(np.nanmin(lon_vals))
        xmax = float(np.nanmax(lon_vals))
        ymin = float(np.nanmin(lat_vals))
        ymax = float(np.nanmax(lat_vals))
        dx = (xmax - xmin) * 0.01
        dy = (ymax - ymin) * 0.01
        extent = (xmin - dx, xmax + dx, ymin - dy, ymax + dy)

    from matplotlib.gridspec import GridSpec

    fig_w, fig_h = _figsize_from_extent(extent, base_height=5.5)
    gap = 0.15
    fig = plt.figure(figsize=(fig_w * 2 + gap, fig_h * 1.3), dpi=150)

    gs = GridSpec(
        2,
        2,
        figure=fig,
        height_ratios=[0.06, 1.0],
        width_ratios=[1, 1],
    )

    fig.subplots_adjust(
        left=0.01,
        right=0.99,
        bottom=0.12,
        top=0.96,
        wspace=0.00,
        hspace=0.04,
    )

    ax_title = fig.add_subplot(gs[0, :])
    ax_title.axis("off")
    ax_title.text(
        0.5,
        1.5,
        "Comparación CHIRTS vs CHIRTS-Corregido\nPuntos: estadístico OBSERVADO (estaciones)",
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
        zorder=11,
    )
    ax_title.set_zorder(10)

    ax1 = fig.add_subplot(gs[1, 0], projection=proj)
    ax2 = fig.add_subplot(gs[1, 1], projection=proj)

    ax1.set_adjustable("box")
    ax2.set_adjustable("box")
    ax1.set_aspect("auto")
    ax2.set_aspect("auto")
    ax1.set_anchor("C")
    ax2.set_anchor("C")

    levels = np.linspace(vmin, vmax, bins + 1)
    norm = BoundaryNorm(levels, ncolors=plt.get_cmap(cmap).N, clip=False)

    ls = LightSource(azdeg=315, altdeg=45)
    hs = ls.hillshade(dem.values, vert_exag=1, dx=1, dy=1)
    hs_masked = np.where(dem.values > 0, hs, np.nan)

    # ================= Panel izquierdo =================
    ax1.set_title(
        f"CHIRTS Original— {var.upper()} {stat} - {year}",
        fontsize=10,
        fontweight="bold",
    )
    ax1.set_xlabel("Longitud", fontsize=9, fontweight="bold")
    ax1.set_ylabel("Latitud", fontsize=9, fontweight="bold")

    ax1.coastlines(resolution="10m", linewidth=0.6)
    ax1.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.6)

    states = cfeature.NaturalEarthFeature(
        category="cultural",
        name="admin_1_states_provinces_lines",
        scale="10m",
        facecolor="none",
        edgecolor="black",
    )
    ax1.add_feature(states, linewidth=0.5, alpha=0.6)

    ax1.set_extent(extent, crs=proj)
    gl1 = ax1.gridlines(
        draw_labels=True, linewidth=0.3, color="gray", alpha=0.5, linestyle="--"
    )
    gl1.right_labels = False
    gl1.top_labels = False
    gl1.xlabel_style = {"size": 8, "weight": "bold"}
    gl1.ylabel_style = {"size": 8, "weight": "bold"}

    ax1.imshow(
        hs_masked,
        extent=[
            float(dem.lon.min()),
            float(dem.lon.max()),
            float(dem.lat.min()),
            float(dem.lat.max()),
        ],
        origin="lower",
        transform=proj,
        cmap="gray",
        alpha=0.5,
        zorder=0,
    )

    lonL = da_left["lon"].values
    latL = da_left["lat"].values
    mesh1 = ax1.pcolormesh(
        lonL,
        latL,
        da_left.values,
        transform=proj,
        cmap=cmap,
        norm=norm,
        shading="auto",
        alpha=0.75,
        zorder=1,
    )

    texts_left = []
    for _, r in stations_obs_year.iterrows():
        ax1.plot(
            r["lon"],
            r["lat"],
            marker="o",
            markersize=3.5,
            markeredgecolor="k",
            markerfacecolor="white",
            transform=proj,
            zorder=5,
        )
        if pd.notna(r["obs"]):
            if adjust_text is None:
                if not hasattr(ax1, "_placed_left"):
                    ax1._placed_left = []
                _place_text_no_overlap(
                    ax1, r["lon"], r["lat"], f"{r['obs']:.1f}", ax1._placed_left
                )
            else:
                t = ax1.text(
                    r["lon"],
                    r["lat"],
                    f"{r['obs']:.1f}",
                    transform=proj,
                    fontsize=7,
                    ha="left",
                    va="bottom",
                    color="black",
                    bbox=dict(
                        boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.6
                    ),
                    zorder=6,
                )
                texts_left.append(t)

    # ================= Panel derecho =================
    ax2.set_title(
        f"CHIRTS Corregido — {var.upper()} {stat} - {year}",
        fontsize=10,
        fontweight="bold",
    )
    ax2.set_xlabel("Longitud", fontsize=9, fontweight="bold")
    ax2.set_ylabel("")

    ax2.coastlines(resolution="10m", linewidth=0.6)
    ax2.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.6)

    states = cfeature.NaturalEarthFeature(
        category="cultural",
        name="admin_1_states_provinces_lines",
        scale="10m",
        facecolor="none",
        edgecolor="black",
    )
    ax2.add_feature(states, linewidth=0.5, alpha=0.6)

    ax2.set_extent(extent, crs=proj)
    gl2 = ax2.gridlines(
        draw_labels=True, linewidth=0.3, color="gray", alpha=0.5, linestyle="--"
    )
    gl2.xlabel_style = {"size": 8, "weight": "bold"}
    gl2.ylabel_style = {"size": 8, "weight": "bold"}
    gl2.right_labels = True
    gl2.top_labels = False
    gl2.left_labels = False

    ax2.imshow(
        hs_masked,
        extent=[
            float(dem.lon.min()),
            float(dem.lon.max()),
            float(dem.lat.min()),
            float(dem.lat.max()),
        ],
        origin="lower",
        transform=proj,
        cmap="gray",
        alpha=0.5,
        zorder=0,
    )

    lonR = da_right["lon"].values
    latR = da_right["lat"].values
    mesh2 = ax2.pcolormesh(
        lonR,
        latR,
        da_right.values,
        transform=proj,
        cmap=cmap,
        norm=norm,
        shading="auto",
        alpha=0.75,
        zorder=1,
    )

    texts_right = []
    for _, r in stations_obs_year.iterrows():
        ax2.plot(
            r["lon"],
            r["lat"],
            marker="o",
            markersize=3.5,
            markeredgecolor="k",
            markerfacecolor="white",
            transform=proj,
            zorder=5,
        )
        if pd.notna(r["obs"]):
            if adjust_text is None:
                if not hasattr(ax2, "_placed_right"):
                    ax2._placed_right = []
                _place_text_no_overlap(
                    ax2, r["lon"], r["lat"], f"{r['obs']:.1f}", ax2._placed_right
                )
            else:
                t = ax2.text(
                    r["lon"],
                    r["lat"],
                    f"{r['obs']:.1f}",
                    transform=proj,
                    fontsize=7,
                    ha="left",
                    va="bottom",
                    color="black",
                    bbox=dict(
                        boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.6
                    ),
                    zorder=6,
                )
                texts_right.append(t)

    if adjust_text is not None:
        adjust_text(
            texts_left,
            ax=ax1,
            expand_text=(1.05, 1.2),
            expand_points=(1.2, 1.4),
            only_move={"points": "y", "text": "xy"},
            arrowprops=dict(arrowstyle="-", lw=0.5, color="k", alpha=0.6),
        )
        adjust_text(
            texts_right,
            ax=ax2,
            expand_text=(1.05, 1.2),
            expand_points=(1.2, 1.4),
            only_move={"points": "y", "text": "xy"},
            arrowprops=dict(arrowstyle="-", lw=0.5, color="k", alpha=0.6),
        )

    cbar = fig.colorbar(
        mesh2,
        ax=[ax1, ax2],
        orientation="horizontal",
        fraction=0.05,
        pad=0.08,
        boundaries=levels,
        spacing="proportional",
    )
    cbar.set_label("Temperatura (°C)", fontsize=9, fontweight="bold")
    cbar.ax.tick_params(labelsize=8)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_delta_grid_field(
    da_raw,
    da_corr,
    dem,
    out_png,
    title,
    extent=None,
    cmap="RdBu_r",
    delta_override=None,
    units="°C",
):
    """
    Genera un mapa de campo de ΔGRID = CHIRTS Corregido − CHIRTS Original.

    Dibuja el campo de diferencias con escala divergente centrada en cero,
    superpone relieve (hillshade) a partir de un DEM y utiliza un estilo gráfico
    consistente con los mapas lado a lado (coastlines, borders, gridlines y
    colorbar horizontal tipo CHIRPS).

    Parámetros
    ----------
    da_raw : xarray.DataArray
        Campo de CHIRTS original.
    da_corr : xarray.DataArray
        Campo de CHIRTS corregido.
    dem : xarray.DataArray
        Modelo digital de elevación para el sombreado de relieve.
    out_png : str
        Ruta del archivo PNG de salida.
    title : str
        Título del mapa.
    extent : tuple, opcional
        (xmin, xmax, ymin, ymax) para fijar el dominio del mapa.
    cmap : str, opcional
        Colormap a usar (por defecto 'RdBu_r').
    delta_override : xarray.DataArray, opcional
        Campo de diferencias a usar directamente en lugar de calcular
        (da_corr − da_raw).
    units : str, opcional
        Unidades a mostrar en la etiqueta de la barra de colores.

    Retorna
    -------
    str
        Ruta del PNG generado.
    """
    dem = _rename_coords_latlon(dem)

    if delta_override is None:
        da_raw = _rename_coords_latlon(da_raw)
        da_corr = _rename_coords_latlon(da_corr)
        delta = da_corr - da_raw
    else:
        delta = _rename_coords_latlon(delta_override)

    proj = ccrs.PlateCarree()

    if extent is None:
        lon_vals = delta["lon"].values
        lat_vals = delta["lat"].values
        xmin = float(np.nanmin(lon_vals))
        xmax = float(np.nanmax(lon_vals))
        ymin = float(np.nanmin(lat_vals))
        ymax = float(np.nanmax(lat_vals))
        dx = (xmax - xmin) * 0.01
        dy = (ymax - ymin) * 0.01
        extent = (xmin - dx, xmax + dx, ymin - dy, ymax + dy)

    data = delta.values

    vmax = np.nanmax(np.abs(data))
    if not np.isfinite(vmax) or vmax == 0:
        vmax = 1.0
    vmin = -vmax

    figsize = _figsize_from_extent(extent, base_height=5.5)
    fig = plt.figure(figsize=figsize, dpi=150, constrained_layout=True)

    ax = plt.axes(projection=proj)
    ax.set_extent(extent, crs=proj)

    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.set_xlabel("Longitud", fontsize=9, fontweight="bold")
    ax.set_ylabel("Latitud", fontsize=9, fontweight="bold")

    ax.coastlines(resolution="10m", linewidth=0.6)
    ax.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.6)

    states = cfeature.NaturalEarthFeature(
        category="cultural",
        name="admin_1_states_provinces_lines",
        scale="10m",
        facecolor="none",
        edgecolor="black",
    )
    ax.add_feature(states, linewidth=0.2, alpha=0.6)

    gl = ax.gridlines(
        draw_labels=True, linewidth=0.3, color="gray", alpha=0.5, linestyle="--"
    )
    gl.right_labels = False
    gl.top_labels = False
    gl.xlabel_style = {"size": 8, "weight": "bold"}
    gl.ylabel_style = {"size": 8, "weight": "bold"}

    ls = LightSource(azdeg=315, altdeg=45)
    hs = ls.hillshade(dem.values, vert_exag=1, dx=1, dy=1)
    hs_masked = np.where(dem.values > 0, hs, np.nan)

    ax.imshow(
        hs_masked,
        extent=[
            float(dem.lon.min()),
            float(dem.lon.max()),
            float(dem.lat.min()),
            float(dem.lat.max()),
        ],
        origin="lower",
        transform=proj,
        cmap="gray",
        alpha=0.5,
        zorder=0,
    )

    mesh = ax.pcolormesh(
        delta["lon"],
        delta["lat"],
        data,
        transform=proj,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        shading="auto",
        alpha=0.85,
        zorder=1,
    )

    cbar = fig.colorbar(
        mesh,
        ax=ax,
        orientation="horizontal",
        fraction=0.05,
        pad=0.08,
    )
    cbar.set_label(
        f"Diferencia espacial - CHIRTS (Corregido − Original) [{units}]",
        fontsize=9,
        fontweight="bold",
    )
    cbar.ax.tick_params(labelsize=8)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=200)
    plt.close(fig)

    return out_png


def plot_delta_grid_at_stations(
    stations_df,
    dem,
    out_png,
    title,
    extent=None,
    cmap="RdBu_r",
    units="°C",
):
    """
    Genera un mapa de puntos de ΔGRID en estaciones (CHIRTS Corregido − CHIRTS Original).

    Dibuja las estaciones con una escala divergente centrada en cero, superpone
    relieve (hillshade) a partir de un DEM y utiliza un estilo gráfico consistente
    con los mapas lado a lado (coastlines, borders, gridlines y colorbar horizontal
    tipo CHIRPS). Incluye etiquetas numéricas evitando solapamientos.

    Parámetros
    ----------
    stations_df : pandas.DataFrame
        DataFrame con columnas: lat, lon, delta_grid.
    dem : xarray.DataArray
        Modelo digital de elevación para el sombreado de relieve.
    out_png : str
        Ruta del archivo PNG de salida.
    title : str
        Título del mapa.
    extent : tuple, opcional
        (xmin, xmax, ymin, ymax) para fijar el dominio del mapa.
    cmap : str, opcional
        Colormap a usar (por defecto 'RdBu_r').
    units : str, opcional
        Unidades a mostrar en la etiqueta de la barra de colores.

    Retorna
    -------
    str
        Ruta del PNG generado.
    """
    proj = ccrs.PlateCarree()

    dem = _rename_coords_latlon(dem)

    lats = stations_df["lat"].values
    lons = stations_df["lon"].values
    delta = stations_df["delta_grid"].values

    if extent is None:
        lon_vals = dem["lon"].values
        lat_vals = dem["lat"].values
        xmin = float(np.nanmin(lon_vals))
        xmax = float(np.nanmax(lon_vals))
        ymin = float(np.nanmin(lat_vals))
        ymax = float(np.nanmax(lat_vals))
        dx = (xmax - xmin) * 0.01
        dy = (ymax - ymin) * 0.01
        extent = (xmin - dx, xmax + dx, ymin - dy, ymax + dy)

    vmax = np.nanmax(np.abs(delta))
    if not np.isfinite(vmax) or vmax == 0:
        vmax = 1.0
    vmin = -vmax

    figsize = _figsize_from_extent(extent, base_height=5.5)
    fig = plt.figure(figsize=figsize, dpi=150, constrained_layout=True)

    ax = plt.axes(projection=proj)
    ax.set_extent(extent, crs=proj)

    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.set_xlabel("Longitud", fontsize=9, fontweight="bold")
    ax.set_ylabel("Latitud", fontsize=9, fontweight="bold")

    ax.coastlines(resolution="10m", linewidth=0.6)
    ax.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.6)

    states = cfeature.NaturalEarthFeature(
        category="cultural",
        name="admin_1_states_provinces_lines",
        scale="10m",
        facecolor="none",
        edgecolor="black",
    )
    ax.add_feature(states, linewidth=0.2, alpha=0.6)

    gl = ax.gridlines(
        draw_labels=True, linewidth=0.3, color="gray", alpha=0.5, linestyle="--"
    )
    gl.right_labels = False
    gl.top_labels = False
    gl.xlabel_style = {"size": 8, "weight": "bold"}
    gl.ylabel_style = {"size": 8, "weight": "bold"}

    ls = LightSource(azdeg=315, altdeg=45)
    hs = ls.hillshade(dem.values, vert_exag=1, dx=1, dy=1)
    hs_masked = np.where(dem.values > 0, hs, np.nan)

    ax.imshow(
        hs_masked,
        extent=[
            float(dem.lon.min()),
            float(dem.lon.max()),
            float(dem.lat.min()),
            float(dem.lat.max()),
        ],
        origin="lower",
        transform=proj,
        cmap="gray",
        alpha=0.5,
        zorder=0,
    )

    sc = ax.scatter(
        lons,
        lats,
        c=delta,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        s=70,
        edgecolors="k",
        linewidths=0.6,
        transform=proj,
        zorder=3,
    )

    cbar = fig.colorbar(
        sc,
        ax=ax,
        orientation="horizontal",
        fraction=0.05,
        pad=0.08,
    )
    cbar.set_label(
        f"Diferencia espacial - CHIRTS (Corregido − Original) en estaciones [{units}]",
        fontsize=9,
        fontweight="bold",
    )
    cbar.ax.tick_params(labelsize=8)

    placed = []
    for _, r in stations_df.iterrows():
        x, y, val = r["lon"], r["lat"], r["delta_grid"]
        if not np.isfinite(val):
            continue
        label = f"{val:+.2f}"
        _place_text_no_overlap(ax, x, y, label, placed, dx=0.20, dy=0.20, max_tries=15)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=200)
    plt.close(fig)

    return out_png


def export_cmp_csv_next_to_png(
    stations_obs_year, da_raw, da_corr, year, var, stat, out_png
):
    """
    Exporta un CSV de comparación por estación junto al PNG asociado.

    Para cada estación, extrae el valor de CHIRTS original y corregido en la
    rejilla más cercana, y calcula:
      - obs
      - grid_raw, grid_corr
      - err_raw, err_corr
      - abs_err_raw, abs_err_corr
      - rel_err_raw_pct, rel_err_corr_pct

    El archivo se guarda con el mismo nombre base del PNG y el sufijo
    '_cmp_estaciones.csv'.

    Parámetros
    ----------
    stations_obs_year : pandas.DataFrame
        DataFrame con información de estaciones y observaciones (incluye al menos
        station_id, lat, lon y una columna de observación).
    da_raw : xarray.DataArray
        Campo de CHIRTS original.
    da_corr : xarray.DataArray
        Campo de CHIRTS corregido.
    year : int
        Año o etiqueta temporal (solo informativo en el nombre de columnas).
    var : str
        Variable ('tmax' o 'tmin').
    stat : str
        Estadístico ('mean', 'max', 'min' o similar).
    out_png : str
        Ruta del PNG asociado.

    Retorna
    -------
    str
        Ruta del archivo CSV generado.
    """
    rows = []

    for _, row in stations_obs_year.iterrows():
        st = row["station_id"]
        lat = row["lat"]
        lon = row["lon"]

        obs_col = None
        if "obs" in row.index:
            obs_col = "obs"
        elif f"{var}_{stat}" in row.index:
            obs_col = f"{var}_{stat}"
        elif f"{var}_station" in row.index:
            obs_col = f"{var}_station"
        else:
            candidates = [c for c in row.index if c.startswith(f"{var}_")]
            if len(candidates) == 1:
                obs_col = candidates[0]
            else:
                raise KeyError(
                    f"No se pudo determinar la columna de observación para {var}. "
                    f"Columnas disponibles: {list(row.index)}"
                )

        obs = row[obs_col]

        try:
            raw_val = da_raw.sel(lat=lat, lon=lon, method="nearest").values.item()
        except Exception:
            raw_val = np.nan

        try:
            corr_val = da_corr.sel(lat=lat, lon=lon, method="nearest").values.item()
        except Exception:
            corr_val = np.nan

        err_raw = raw_val - obs if np.isfinite(raw_val) and np.isfinite(obs) else np.nan
        err_corr = (
            corr_val - obs if np.isfinite(corr_val) and np.isfinite(obs) else np.nan
        )

        abs_err_raw = np.abs(err_raw) if np.isfinite(err_raw) else np.nan
        abs_err_corr = np.abs(err_corr) if np.isfinite(err_corr) else np.nan

        if np.isfinite(obs) and obs != 0:
            rel_err_raw_pct = 100.0 * abs_err_raw / np.abs(obs)
            rel_err_corr_pct = 100.0 * abs_err_corr / np.abs(obs)
        else:
            rel_err_raw_pct = np.nan
            rel_err_corr_pct = np.nan

        rows.append(
            {
                "station_id": st,
                "lat": lat,
                "lon": lon,
                f"{var}_{stat}_obs": obs,
                "grid_raw": raw_val,
                "grid_corr": corr_val,
                "err_raw": err_raw,
                "err_corr": err_corr,
                "abs_err_raw": abs_err_raw,
                "abs_err_corr": abs_err_corr,
                "rel_err_raw_pct": rel_err_raw_pct,
                "rel_err_corr_pct": rel_err_corr_pct,
            }
        )

    df_out = pd.DataFrame(rows)

    base = os.path.splitext(out_png)[0]
    out_csv = f"{base}_cmp_estaciones.csv"
    df_out.to_csv(out_csv, index=False, float_format="%.4f")

    return out_csv


def load_daily_chirts_raw(dir_chirts, date_str, prefix="temp_"):
    """
    Carga un archivo diario de CHIRTS original en formato NetCDF.

    Busca un archivo con nombre <prefix>YYYYMMDD.nc dentro de `dir_chirts`,
    donde `date_str` se da en formato 'YYYY-MM-DD', y devuelve el DataArray
    de la variable contenida en el archivo.

    Parámetros
    ----------
    dir_chirts : str
        Directorio donde están los NetCDF diarios de CHIRTS original.
    date_str : str
        Fecha en formato 'YYYY-MM-DD'.
    prefix : str, opcional
        Prefijo del nombre de archivo (por defecto 'temp_').

    Retorna
    -------
    xarray.DataArray
        Campo diario de CHIRTS original.
    """
    ymd = date_str.replace("-", "")
    fname = f"{prefix}{ymd}.nc"
    path = os.path.join(dir_chirts, fname)

    if not os.path.exists(path):
        raise FileNotFoundError(f"No existe: {path}")

    ds = xr.open_dataset(path)
    da = list(ds.data_vars.values())[0]
    da = _rename_coords_latlon(da)
    return da


def load_daily_chirts_corr(dir_merged, date_str):
    """
    Carga un archivo diario de CHIRTS corregido en formato NetCDF.

    Busca automáticamente un archivo con patrón '*_mrg_YYYYMMDD.nc' dentro de
    `dir_merged`, donde `date_str` se da en formato 'YYYY-MM-DD'. Requiere que
    exista exactamente un archivo que coincida.

    Parámetros
    ----------
    dir_merged : str
        Directorio donde están los NetCDF diarios de CHIRTS corregido.
    date_str : str
        Fecha en formato 'YYYY-MM-DD'.

    Retorna
    -------
    xarray.DataArray
        Campo diario de CHIRTS corregido.
    """
    ymd = date_str.replace("-", "")
    pattern = os.path.join(dir_merged, f"*_mrg_{ymd}.nc")
    files = sorted(glob.glob(pattern))

    if len(files) == 0:
        raise FileNotFoundError(f"No se encontró archivo con patrón: {pattern}")
    if len(files) > 1:
        raise RuntimeError(f"Archivos ambiguos para {date_str}: {files}")

    path = files[0]
    ds = xr.open_dataset(path)
    da = list(ds.data_vars.values())[0]
    da = _rename_coords_latlon(da)
    return da


def daily_station_values(df_obs_long, date_str, value_name):
    """
    Extrae los valores observados de estaciones para una fecha específica.

    Filtra el DataFrame de observaciones al día indicado y devuelve un DataFrame
    con las columnas estándar: station_id, lon, lat, elev, obs.

    Parámetros
    ----------
    df_obs_long : pandas.DataFrame
        Observaciones en formato largo con columna 'date'.
    date_str : str
        Fecha en formato 'YYYY-MM-DD'.
    value_name : str
        Nombre de la columna con los valores observados.

    Retorna
    -------
    pandas.DataFrame
        DataFrame con columnas: station_id, lon, lat, elev, obs.
    """
    target_date = pd.to_datetime(date_str, format="%Y-%m-%d")
    df_day = df_obs_long[df_obs_long["date"] == target_date].copy()
    df_day = df_day.rename(columns={value_name: "obs"})
    return df_day[["station_id", "lon", "lat", "elev", "obs"]]


def compute_metrics(obs, grid):
    """
    Calcula métricas básicas de error entre observaciones y un campo en rejilla.

    Las métricas se definen como:
    - Bias  = mean(grid - obs)
      Mide el sesgo medio del campo en rejilla respecto a las observaciones.
      Valores positivos indican sobreestimación; negativos, subestimación.
    - MAE   = mean(|grid - obs|)
      Error absoluto medio, mide la magnitud promedio del error sin considerar
      el signo.
    - RMSE  = sqrt(mean((grid - obs)^2))
      Raíz del error cuadrático medio, penaliza más fuertemente los errores grandes.

    Todas las métricas se calculan ignorando valores NaN.

    Parámetros
    ----------
    obs : array-like
        Valores observados.
    grid : array-like
        Valores del modelo o rejilla.

    Retorna
    -------
    tuple
        (bias, mae, rmse)
    """
    obs = np.asarray(obs, dtype=float)
    grid = np.asarray(grid, dtype=float)
    diff = grid - obs
    bias = np.nanmean(diff)
    mae = np.nanmean(np.abs(diff))
    rmse = np.sqrt(np.nanmean(diff**2))
    return bias, mae, rmse


def build_daily_timeseries(df_obs_long, dir_chirts, dir_merged, var, prefix_chirts):
    """
    Construye una serie diaria de comparación en estaciones entre CHIRTS y observaciones.

    Para cada fecha presente en `df_obs_long`, carga una sola vez los campos diarios
    de CHIRTS original y corregido, muestrea ambos en las coordenadas de las estaciones
    usando vecino más cercano y construye un DataFrame con columnas estándar:
    date, station_id, lon, lat, elev, obs, raw, corr.

    Parámetros
    ----------
    df_obs_long : pandas.DataFrame
        Observaciones en formato largo con columnas que incluyen: date, station_id,
        lon, lat, elev y <var>_station.
    dir_chirts : str
        Directorio con los NetCDF diarios de CHIRTS original.
    dir_merged : str
        Directorio con los NetCDF diarios de CHIRTS corregido.
    var : str
        Variable base (ej. 'tmax' o 'tmin'), usada para identificar la columna
        de observaciones <var>_station.
    prefix_chirts : str
        Prefijo de los archivos diarios de CHIRTS original (ej. 'temp_').

    Retorna
    -------
    pandas.DataFrame
        DataFrame con columnas: date, station_id, lon, lat, elev, obs, raw, corr.
    """
    records = []

    df = df_obs_long.copy()

    for date_key, g in df.groupby("date"):
        if isinstance(date_key, pd.Timestamp):
            ymd = date_key.strftime("%Y%m%d")
        else:
            ymd = str(date_key)

        da_raw = load_daily_chirts_raw(dir_chirts, ymd, prefix_chirts)
        da_corr = load_daily_chirts_corr(dir_merged, ymd)

        da_raw = _rename_coords_latlon(da_raw)
        da_corr = _rename_coords_latlon(da_corr)

        lons = xr.DataArray(g["lon"].values, dims="points")
        lats = xr.DataArray(g["lat"].values, dims="points")

        try:
            raw_vals = da_raw.sel(lon=lons, lat=lats, method="nearest").values
        except Exception:
            raw_vals = np.full(len(g), np.nan)

        try:
            corr_vals = da_corr.sel(lon=lons, lat=lats, method="nearest").values
        except Exception:
            corr_vals = np.full(len(g), np.nan)

        for i, (_, r) in enumerate(g.iterrows()):
            records.append(
                {
                    "date": ymd,
                    "station_id": r["station_id"],
                    "lon": r["lon"],
                    "lat": r["lat"],
                    "elev": r["elev"],
                    "obs": r[f"{var}_station"],
                    "raw": raw_vals[i],
                    "corr": corr_vals[i],
                }
            )

    df_daily = pd.DataFrame.from_records(records)
    return df_daily


def process_year(year, df_obs_long, dir_chirts, dir_merged, var, prefix_chirts):
    """
    Procesa un año completo de observaciones y construye la serie diaria de comparación.

    Filtra `df_obs_long` al año indicado y delega en `build_daily_timeseries` la
    construcción del DataFrame con columnas: date, station_id, lon, lat, elev,
    obs, raw, corr.

    Parámetros
    ----------
    year : int
        Año a procesar.
    df_obs_long : pandas.DataFrame
        Observaciones en formato largo con columna 'year'.
    dir_chirts : str
        Directorio con los NetCDF diarios de CHIRTS original.
    dir_merged : str
        Directorio con los NetCDF diarios de CHIRTS corregido.
    var : str
        Variable base (ej. 'tmax' o 'tmin').
    prefix_chirts : str
        Prefijo de los archivos diarios de CHIRTS original.

    Retorna
    -------
    pandas.DataFrame
        Serie diaria del año con columnas: date, station_id, lon, lat, elev, obs, raw, corr.
    """
    df_year = df_obs_long[df_obs_long["year"] == year]
    return build_daily_timeseries(
        df_obs_long=df_year,
        dir_chirts=dir_chirts,
        dir_merged=dir_merged,
        var=var,
        prefix_chirts=prefix_chirts,
    )


def summarize_daily_global(df_daily, var):
    """
    Calcula métricas globales diarias de desempeño para CHIRTS original y corregido.

    A partir del DataFrame diario con columnas obs, raw y corr, calcula Bias, MAE
    y RMSE para ambos productos y reporta también las mejoras:
    Delta_RMSE = RMSE_raw − RMSE_corr
    Delta_MAE  = MAE_raw  − MAE_corr

    Parámetros
    ----------
    df_daily : pandas.DataFrame
        DataFrame con columnas: obs, raw, corr.
    var : str
        Nombre de la variable (ej. 'tmax' o 'tmin').

    Retorna
    -------
    pandas.DataFrame
        DataFrame de una fila con métricas globales:
        var, Bias_raw, Bias_corr, MAE_raw, MAE_corr, RMSE_raw, RMSE_corr,
        Delta_RMSE, Delta_MAE.
    """
    bias_raw, mae_raw, rmse_raw = compute_metrics(df_daily["obs"], df_daily["raw"])
    bias_corr, mae_corr, rmse_corr = compute_metrics(df_daily["obs"], df_daily["corr"])

    out = pd.DataFrame(
        [
            {
                "var": var,
                "Bias_raw": bias_raw,
                "Bias_corr": bias_corr,
                "MAE_raw": mae_raw,
                "MAE_corr": mae_corr,
                "RMSE_raw": rmse_raw,
                "RMSE_corr": rmse_corr,
                "Delta_RMSE": rmse_raw - rmse_corr,
                "Delta_MAE": mae_raw - mae_corr,
            }
        ]
    )
    return out


def summarize_daily_by_station(df_daily):
    """
    Calcula métricas diarias de desempeño por estación para CHIRTS original y corregido.

    Agrupa el DataFrame diario por station_id y, para cada estación, calcula Bias,
    MAE y RMSE para ambos productos, así como las mejoras:
    Delta_RMSE = RMSE_raw − RMSE_corr
    Delta_MAE  = MAE_raw  − MAE_corr

    Parámetros
    ----------
    df_daily : pandas.DataFrame
        DataFrame con columnas: station_id, obs, raw, corr.

    Retorna
    -------
    pandas.DataFrame
        DataFrame con una fila por estación y columnas:
        station_id, Bias_raw, Bias_corr, MAE_raw, MAE_corr,
        RMSE_raw, RMSE_corr, Delta_RMSE, Delta_MAE.
    """
    rows = []
    for sid, g in df_daily.groupby("station_id"):
        bias_raw, mae_raw, rmse_raw = compute_metrics(g["obs"], g["raw"])
        bias_corr, mae_corr, rmse_corr = compute_metrics(g["obs"], g["corr"])

        if rmse_raw > 0 and np.isfinite(rmse_raw):
            improvement_pct = 100.0 * (rmse_raw - rmse_corr) / rmse_raw
        else:
            improvement_pct = np.nan

        rows.append(
            {
                "station_id": sid,
                "Bias_raw": bias_raw,
                "Bias_corr": bias_corr,
                "MAE_raw": mae_raw,
                "MAE_corr": mae_corr,
                "RMSE_raw": rmse_raw,
                "RMSE_corr": rmse_corr,
                "Improvement_RMSE_pct": improvement_pct,
                "Delta_RMSE": rmse_raw - rmse_corr,
                "Delta_MAE": mae_raw - mae_corr,
            }
        )

    return pd.DataFrame(rows)


def get_dates_for_period(year, period_type, season=None, months=None):
    """
    Genera una lista de fechas diarias (YYYYMMDD) para un período definido.

    Soporta dos tipos de período:
    - 'season': usa la definición en el diccionario SEASONS, incluyendo temporadas
      que cruzan año (ej. DJFM).
    - 'months': usa una lista explícita de meses dentro del mismo año.

    Parámetros
    ----------
    year : int
        Año de referencia del período.
    period_type : str
        Tipo de período: 'season' o 'months'.
    season : str, opcional
        Clave de temporada en SEASONS (ej. 'DJFM', 'MJJ', etc.), requerida si
        period_type == 'season'.
    months : list of int, opcional
        Lista de meses (1–12), requerida si period_type == 'months'.

    Retorna
    -------
    list of str
        Lista de fechas en formato 'YYYYMMDD' que cubren el período solicitado.
    """
    dates = []

    if period_type == "season":
        cfg = SEASONS[season]
        months_list = cfg["months"]
        cross = cfg["cross_year"]

        for m in months_list:
            if cross and m == 12:
                y = year - 1
            else:
                y = year
            dates.extend(
                pd.date_range(
                    start=f"{y}-{m:02d}-01",
                    end=pd.Timestamp(f"{y}-{m:02d}-01") + pd.offsets.MonthEnd(1),
                    freq="D",
                )
            )

    elif period_type == "months":
        for m in months:
            dates.extend(
                pd.date_range(
                    start=f"{year}-{m:02d}-01",
                    end=pd.Timestamp(f"{year}-{m:02d}-01") + pd.offsets.MonthEnd(1),
                    freq="D",
                )
            )

    return [d.strftime("%Y%m%d") for d in dates]


def load_period_stat(dir_data, dates_ymd, loader_func, stat):
    """
    Carga campos diarios para un conjunto de fechas y calcula un estadístico temporal.

    Para cada fecha en `dates_ymd`, usa `loader_func` para cargar el DataArray,
    concatena en la dimensión temporal y calcula el estadístico solicitado.

    Parámetros
    ----------
    dir_data : str
        Directorio donde se encuentran los archivos diarios.
    dates_ymd : list of str
        Lista de fechas en formato 'YYYYMMDD'.
    loader_func : callable
        Función que carga un DataArray dado (dir_data, date_str).
    stat : str
        Estadístico a calcular: 'mean', 'max' o 'min'.

    Retorna
    -------
    xarray.DataArray
        Campo con el estadístico temporal solicitado.
    """
    das = []
    for ymd in dates_ymd:
        da = loader_func(dir_data, ymd)
        da = _rename_coords_latlon(da)
        das.append(da)

    da_stack = xr.concat(das, dim="time")

    if stat == "mean":
        return da_stack.mean("time", skipna=True)
    elif stat == "max":
        return da_stack.max("time", skipna=True)
    elif stat == "min":
        return da_stack.min("time", skipna=True)
    else:
        raise ValueError("stat no soportada")


def load_period_stat_raw(dir_chirts, dates_ymd, prefix_chirts, stat):
    """
    Carga campos diarios de CHIRTS original para un período y calcula un estadístico temporal.

    Para cada fecha en `dates_ymd`, carga el DataArray diario usando
    `load_daily_chirts_raw`, concatena en la dimensión temporal y calcula el
    estadístico solicitado.

    Parámetros
    ----------
    dir_chirts : str
        Directorio con los NetCDF diarios de CHIRTS original.
    dates_ymd : list of str
        Lista de fechas en formato 'YYYYMMDD'.
    prefix_chirts : str
        Prefijo de los archivos diarios de CHIRTS original (ej. 'temp_').
    stat : str
        Estadístico a calcular: 'mean', 'max' o 'min'.

    Retorna
    -------
    xarray.DataArray
        Campo con el estadístico temporal solicitado.
    """
    das = []
    for ymd in dates_ymd:
        da = load_daily_chirts_raw(dir_chirts, ymd, prefix_chirts)
        da = _rename_coords_latlon(da)
        das.append(da)

    da_stack = xr.concat(das, dim="time")
    if stat == "mean":
        return da_stack.mean("time", skipna=True)
    elif stat == "max":
        return da_stack.max("time", skipna=True)
    elif stat == "min":
        return da_stack.min("time", skipna=True)
    else:
        raise ValueError("stat no soportada")


def load_period_stat_corr(dir_merged, dates_ymd, var, stat):
    """
    Carga campos diarios de CHIRTS corregido para un período y calcula un estadístico temporal.

    Para cada fecha en `dates_ymd`, carga el DataArray diario usando
    `load_daily_chirts_corr`, concatena en la dimensión temporal y calcula el
    estadístico solicitado.

    Parámetros
    ----------
    dir_merged : str
        Directorio con los NetCDF diarios de CHIRTS corregido.
    dates_ymd : list of str
        Lista de fechas en formato 'YYYYMMDD'.
    var : str
        Variable base (se mantiene por compatibilidad, no se usa internamente).
    stat : str
        Estadístico a calcular: 'mean', 'max' o 'min'.

    Retorna
    -------
    xarray.DataArray
        Campo con el estadístico temporal solicitado.
    """
    das = []
    for ymd in dates_ymd:
        da = load_daily_chirts_corr(dir_merged, ymd)
        da = _rename_coords_latlon(da)
        das.append(da)

    da_stack = xr.concat(das, dim="time")
    if stat == "mean":
        return da_stack.mean("time", skipna=True)
    elif stat == "max":
        return da_stack.max("time", skipna=True)
    elif stat == "min":
        return da_stack.min("time", skipna=True)
    else:
        raise ValueError("stat no soportada")


def period_station_stat(df_obs_long, dates_ymd, var, stat):
    """
    Calcula un estadístico de observaciones por estación para un período dado.

    Filtra `df_obs_long` a las fechas indicadas en `dates_ymd`, agrupa por
    station_id y calcula el estadístico solicitado sobre la columna
    <var>_station. Devuelve un DataFrame con el valor observado por estación
    y sus metadatos.

    Parámetros
    ----------
    df_obs_long : pandas.DataFrame
        Observaciones en formato largo con columnas que incluyen: date,
        station_id, lon, lat, elev y <var>_station.
    dates_ymd : list of str
        Lista de fechas en formato 'YYYYMMDD' que definen el período.
    var : str
        Variable base (ej. 'tmax' o 'tmin'), usada para seleccionar la columna
        <var>_station.
    stat : str
        Estadístico a calcular: 'mean', 'max' o 'min'.

    Retorna
    -------
    pandas.DataFrame
        DataFrame con columnas: station_id, obs, lon, lat, elev.
    """
    dfp = df_obs_long[df_obs_long["date"].isin(dates_ymd)]

    if stat == "mean":
        s = dfp.groupby("station_id")[f"{var}_station"].mean()
    elif stat == "max":
        s = dfp.groupby("station_id")[f"{var}_station"].max()
    elif stat == "min":
        s = dfp.groupby("station_id")[f"{var}_station"].min()
    else:
        raise ValueError("stat no soportada")

    out = s.reset_index().rename(columns={f"{var}_station": "obs"})
    meta = df_obs_long[["station_id", "lon", "lat", "elev"]].drop_duplicates()
    out = out.merge(meta, on="station_id", how="left")
    return out


def make_period_title(period_type, year, season=None, months=None):
    """
    Construye un título legible en español para un período temporal.

    Soporta dos tipos de período:
    - 'season': usa la definición en SEASONS y genera un título del tipo
      'DJFM 1995 (Dic 1994 – Mar 1995)' para temporadas que cruzan año.
    - 'months': usa una lista explícita de meses y genera un título como
      'Meses 5-7 1995 (May 1995 – Jul 1995)' o 'May 1995' si es un solo mes.

    Parámetros
    ----------
    period_type : str
        Tipo de período: 'season' o 'months'.
    year : int
        Año de referencia del período.
    season : str, opcional
        Clave de temporada en SEASONS (ej. 'DJFM', 'MJJ', etc.), requerida si
        period_type == 'season'.
    months : list of int, opcional
        Lista de meses (1–12), requerida si period_type == 'months'.

    Retorna
    -------
    str
        Título descriptivo del período en español.
    """
    if period_type == "season":
        cfg = SEASONS[season]
        months_list = cfg["months"]
        cross = cfg["cross_year"]

        if cross:
            first_month = months_list[0]
            last_month = months_list[-1]
            start_year = year - 1
            end_year = year
        else:
            first_month = months_list[0]
            last_month = months_list[-1]
            start_year = year
            end_year = year

        start_label = f"{MONTH_NAMES_ES[first_month]} {start_year}"
        end_label = f"{MONTH_NAMES_ES[last_month]} {end_year}"

        return f"{season} {year} ({start_label} – {end_label})"

    elif period_type == "months":
        first_month = months[0]
        last_month = months[-1]

        start_label = f"{MONTH_NAMES_ES[first_month]} {year}"
        end_label = f"{MONTH_NAMES_ES[last_month]} {year}"

        months_str = "-".join(str(m) for m in months)

        if len(months) == 1:
            return f"{MONTH_NAMES_ES[first_month]} {year}"
        else:
            return f"Meses {months_str} {year} ({start_label} – {end_label})"


def build_station_improvement_csv(csv_files, var, stat, out_csv, metric="rmse"):
    """
    Construye un CSV de mejora por estación a partir de archivos de comparación diarios.

    Lee múltiples CSV generados por `export_cmp_csv_next_to_png`, concatena los datos
    y, para cada estación, calcula una métrica agregada para CHIRTS original y
    corregido, así como su mejora:

        delta_metric = metric_raw − metric_corr
        improvement_metric_pct = 100 * (metric_raw − metric_corr) / metric_raw

    donde la métrica puede ser RMSE o MAE.

    Parámetros
    ----------
    csv_files : list of str
        Lista de rutas a archivos CSV de comparación por estación y fecha.
    var : str
        Variable base (ej. 'tmax' o 'tmin').
    stat : str
        Estadístico asociado a la observación (ej. 'mean', 'max', 'min').
    out_csv : str
        Ruta del archivo CSV de salida.
    metric : str, opcional
        Métrica a usar: 'rmse' o 'mae' (por defecto 'rmse').

    Retorna
    -------
    str
        Ruta del archivo CSV generado.
    """
    import pandas as pd
    import numpy as np

    dfs = [pd.read_csv(c) for c in csv_files]
    df_all = pd.concat(dfs, ignore_index=True)

    obs_col = f"{var}_{stat}_obs"
    if obs_col not in df_all.columns:
        raise ValueError(f"No se encontró la columna {obs_col} en los CSV.")

    rows = []
    for (sid, lat, lon), g in df_all.groupby(
        ["station_id", "lat", "lon"], as_index=False
    ):
        obs = g[obs_col].astype(float).values
        raw = g["grid_raw"].astype(float).values
        corr = g["grid_corr"].astype(float).values

        m = np.isfinite(obs) & np.isfinite(raw) & np.isfinite(corr)
        if not np.any(m):
            continue

        obs = obs[m]
        raw = raw[m]
        corr = corr[m]
        err_raw = raw - obs
        err_corr = corr - obs

        if metric.lower() == "rmse":
            met_raw = np.sqrt(np.mean(err_raw**2))
            met_corr = np.sqrt(np.mean(err_corr**2))
            label = "RMSE"
        elif metric.lower() == "mae":
            met_raw = np.mean(np.abs(err_raw))
            met_corr = np.mean(np.abs(err_corr))
            label = "MAE"
        else:
            raise ValueError("metric debe ser 'rmse' o 'mae'")

        delta = met_raw - met_corr

        # Denominador robusto para evitar porcentajes explosivos
        eps = 1e-6
        den = max(met_raw, met_corr, eps)

        if np.isfinite(den):
            improvement_pct = 100.0 * delta / den
        else:
            improvement_pct = np.nan

        rows.append(
            {
                "station_id": sid,
                "lat": lat,
                "lon": lon,
                f"{label}_raw": met_raw,
                f"{label}_corr": met_corr,
                f"delta_{label}": delta,
                # NUEVO: mejora porcentual
                f"improvement_{label}_pct": improvement_pct,
            }
        )

    df_out = pd.DataFrame(rows)
    df_out.to_csv(out_csv, index=False, float_format="%.4f")
    return out_csv


def build_global_station_csv(csv_files, out_csv):
    """
    Construye un CSV global por estación promediando métricas en el tiempo.

    Lee una lista de CSV (anuales o de período), concatena los datos y calcula
    el promedio por estación (station_id, lat, lon) usando únicamente columnas
    numéricas. El resultado se guarda en `out_csv`.

    Parámetros
    ----------
    csv_files : list of str
        Lista de rutas a archivos CSV con métricas por estación.
    out_csv : str
        Ruta del archivo CSV de salida.

    Retorna
    -------
    str
        Ruta del archivo CSV generado.
    """
    import pandas as pd
    import numpy as np

    dfs = [pd.read_csv(c) for c in csv_files]
    df_all = pd.concat(dfs, ignore_index=True)

    grp = df_all.groupby(["station_id", "lat", "lon"], as_index=False).mean(
        numeric_only=True
    )

    grp.to_csv(out_csv, index=False, float_format="%.4f")
    return out_csv


def plot_improvement_at_stations_with_dem(
    stations_df,
    dem,
    out_png,
    title,
    extent=None,
    cmap="RdBu_r",
):
    """
    Genera un mapa de puntos de mejora porcentual de RMSE en estaciones.

    Usa: improvement_pct = 100 * (RMSE_raw − RMSE_corr) / RMSE_raw

    Valores:
      > 0  → mejora
      = 0  → sin cambio
      < 0  → empeora

    Dibuja las estaciones con una escala divergente centrada en cero, superpone
    relieve (hillshade) a partir de un DEM y utiliza un estilo gráfico consistente
    con los mapas lado a lado (coastlines, borders, gridlines y colorbar horizontal
    tipo CHIRPS). Incluye etiquetas numéricas evitando solapamientos.

    Parámetros
    ----------
    stations_df : pandas.DataFrame
        DataFrame con columnas: lat, lon, improvement_pct.
    dem : xarray.DataArray
        Modelo digital de elevación para el sombreado de relieve.
    out_png : str
        Ruta del archivo PNG de salida.
    title : str
        Título del mapa.
    extent : tuple, opcional
        (xmin, xmax, ymin, ymax) para fijar el dominio del mapa.
    cmap : str, opcional
        Colormap a usar (por defecto 'RdBu_r').

    Retorna
    -------
    str
        Ruta del PNG generado.
    """
    proj = ccrs.PlateCarree()

    dem = _rename_coords_latlon(dem)

    lats = stations_df["lat"].values
    lons = stations_df["lon"].values
    values = stations_df["improvement_RMSE_pct"].values.astype(float)

    if extent is None:
        lon_vals = dem["lon"].values
        lat_vals = dem["lat"].values
        xmin = float(np.nanmin(lon_vals))
        xmax = float(np.nanmax(lon_vals))
        ymin = float(np.nanmin(lat_vals))
        ymax = float(np.nanmax(lat_vals))
        dx = (xmax - xmin) * 0.01
        dy = (ymax - ymin) * 0.01
        extent = (xmin - dx, xmax + dx, ymin - dy, ymax + dy)

    vmax = np.nanmax(np.abs(values))
    if not np.isfinite(vmax) or vmax == 0:
        vmax = 10.0  # 10% por defecto si todo es cero/NaN
    vmin = -vmax

    figsize = _figsize_from_extent(extent, base_height=5.5)
    fig = plt.figure(figsize=figsize, dpi=150, constrained_layout=True)

    ax = plt.axes(projection=proj)
    ax.set_extent(extent, crs=proj)

    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.set_xlabel("Longitud", fontsize=9, fontweight="bold")
    ax.set_ylabel("Latitud", fontsize=9, fontweight="bold")

    ax.coastlines(resolution="10m", linewidth=0.6)
    ax.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.6)

    states = cfeature.NaturalEarthFeature(
        category="cultural",
        name="admin_1_states_provinces_lines",
        scale="10m",
        facecolor="none",
        edgecolor="black",
    )
    ax.add_feature(states, linewidth=0.2, alpha=0.6)

    gl = ax.gridlines(
        draw_labels=True, linewidth=0.3, color="gray", alpha=0.5, linestyle="--"
    )
    gl.right_labels = False
    gl.top_labels = False
    gl.xlabel_style = {"size": 8, "weight": "bold"}
    gl.ylabel_style = {"size": 8, "weight": "bold"}

    ls = LightSource(azdeg=315, altdeg=45)
    hs = ls.hillshade(dem.values, vert_exag=1, dx=1, dy=1)
    hs_masked = np.where(dem.values > 0, hs, np.nan)

    ax.imshow(
        hs_masked,
        extent=[
            float(dem.lon.min()),
            float(dem.lon.max()),
            float(dem.lat.min()),
            float(dem.lat.max()),
        ],
        origin="lower",
        transform=proj,
        cmap="gray",
        alpha=0.5,
        zorder=0,
    )

    sc = ax.scatter(
        lons,
        lats,
        c=values,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        s=70,
        edgecolors="k",
        linewidths=0.6,
        transform=proj,
        zorder=3,
    )

    cbar = fig.colorbar(
        sc,
        ax=ax,
        orientation="horizontal",
        fraction=0.05,
        pad=0.08,
    )
    cbar.set_label(
        "Mejora relativa de RMSE [%] (Positivo = mejora, Negativo = empeora)",
        fontsize=9,
        fontweight="bold",
    )
    cbar.ax.tick_params(labelsize=8)

    placed = []
    for _, r in stations_df.iterrows():
        x, y, val = r["lon"], r["lat"], r["improvement_RMSE_pct"]
        if not np.isfinite(val):
            continue
        label = f"{val:+.1f}%"
        _place_text_no_overlap(ax, x, y, label, placed, dx=0.20, dy=0.20, max_tries=15)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=200)
    plt.close(fig)

    return out_png


def plot_boxplot_rmse_by_station(df, var, stat, label, out_png, units="°C"):
    """
    Genera un boxplot comparativo del RMSE por estación para CHIRTS original y corregido,
    con estilo afinado: cajas angostas, bigotes finos, bordes y bigotes del mismo color,
    puntos desplazados a un lado, anotaciones estadísticas extendidas y una línea punteada
    que une las medianas de ambos grupos.

    Parámetros
    ----------
    df : pandas.DataFrame
        DataFrame con columnas: 'RMSE_raw' y 'RMSE_corr' por estación.
    var : str
        Variable base (ej. 'tmax' o 'tmin').
    stat : str
        Estadístico asociado a la observación (ej. 'mean', 'max', 'min').
    label : str
        Etiqueta del período (ej. 'A_1995', 'DJFM_2005', etc.).
    out_png : str
        Ruta del archivo PNG de salida.
    units : str, opcional
        Unidades a mostrar en el eje Y (por defecto '°C').

    Retorna
    -------
    str
        Ruta del PNG generado.
    """
    import os
    import numpy as np
    import matplotlib.pyplot as plt

    # Colores (uno por grupo)
    FILL_RAW = "#fdd0a2"  # pastel naranja
    EDGE_RAW = "#e6550d"
    FILL_CORR = "#9ecae1"  # pastel azul
    EDGE_CORR = "#3182bd"
    GRID_ALPHA = 0.25

    raw = df["RMSE_raw"].astype(float).values
    corr = df["RMSE_corr"].astype(float).values
    raw = raw[np.isfinite(raw)]
    corr = corr[np.isfinite(corr)]

    data = [raw, corr]

    fig, ax = plt.subplots(figsize=(5, 4.2), dpi=150, constrained_layout=True)

    bp = ax.boxplot(
        data,
        labels=["Original", "Corregido"],
        showfliers=False,  # mostramos puntos manualmente
        widths=0.20,  # cajas más angostas
        patch_artist=True,
        medianprops=dict(linewidth=1.2),
        boxprops=dict(linewidth=1.1),
        whiskerprops=dict(linewidth=1.0),
        capprops=dict(linewidth=1.0),
    )

    # Estilo por caja
    fills = [FILL_RAW, FILL_CORR]
    edges = [EDGE_RAW, EDGE_CORR]
    for i, box in enumerate(bp["boxes"]):
        box.set_facecolor(fills[i])
        box.set_edgecolor(edges[i])
        box.set_alpha(0.9)

    # Bigotes y caps del mismo color que su caja
    for i in range(2):
        for w in bp["whiskers"][2 * i : 2 * i + 2]:
            w.set_color(edges[i])
        for c in bp["caps"][2 * i : 2 * i + 2]:
            c.set_color(edges[i])

    # Medianas del mismo color que el borde de su caja
    for i, med in enumerate(bp["medians"]):
        med.set_color(edges[i])
        med.set_linewidth(1.4)

    # Puntos de estaciones a un lado de cada box
    rng = np.random.default_rng(42)
    x_raw = 1.18 + rng.normal(0, 0.015, size=len(raw))
    x_corr = 2.18 + rng.normal(0, 0.015, size=len(corr))

    ax.scatter(
        x_raw, raw, s=20, color=edges[0], alpha=0.65, edgecolors="none", zorder=3
    )
    ax.scatter(
        x_corr, corr, s=20, color=edges[1], alpha=0.65, edgecolors="none", zorder=3
    )

    ax.set_title(
        f"{var.upper()} {stat} — RMSE por estación — {label}",
        fontsize=10,
        fontweight="bold",
    )
    ax.set_ylabel(f"RMSE [{units}]", fontsize=9, fontweight="bold")
    ax.grid(True, axis="y", alpha=GRID_ALPHA)

    # Medianas y línea punteada que las une
    if raw.size and corr.size:
        med_raw = np.nanmedian(raw)
        med_corr = np.nanmedian(corr)
        ax.plot(
            [1, 2],
            [med_raw, med_corr],
            linestyle="--",
            color="#444444",
            linewidth=1.2,
            alpha=0.7,
            zorder=2,
        )

    # Estadísticos para anotación
    def stats_txt(arr, name):
        if arr.size == 0:
            return f"{name}: sin datos"
        p10, p25, p50, p75, p90 = np.nanpercentile(arr, [10, 25, 50, 75, 90])
        mean = np.nanmean(arr)
        n = len(arr)
        return (
            f"{name}\n"
            f"n = {n}\n"
            f"Media = {mean:.2f}\n"
            f"P10 = {p10:.2f}\n"
            f"P25 = {p25:.2f}\n"
            f"Med = {p50:.2f}\n"
            f"P75 = {p75:.2f}\n"
            f"P90 = {p90:.2f}"
        )

    txt = stats_txt(raw, "Original") + "\n\n" + stats_txt(corr, "Corregido")

    ax.text(
        0.98,
        0.95,
        txt,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#999999", alpha=0.85),
    )

    # Ajuste de límites en X para que quepan los puntos desplazados
    ax.set_xlim(0.6, 2.5)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=200)
    plt.close(fig)

    return out_png


def plot_boxplot_improvement_pct_by_station(df, var, stat, label, out_png):
    """
    Genera un boxplot de la mejora relativa de RMSE (%) por estación para un período dado,
    con estilo afinado: caja angosta, bigotes finos, bordes y bigotes del mismo color,
    puntos desplazados a un lado y anotaciones estadísticas extendidas.

    La mejora se define como:
        improvement_% = 100 * (RMSE_raw - RMSE_corr) / RMSE_raw

    Parámetros
    ----------
    df : pandas.DataFrame
        DataFrame con columna: 'improvement_RMSE_pct' por estación.
    var : str
        Variable base (ej. 'tmax' o 'tmin').
    stat : str
        Estadístico asociado a la observación (ej. 'mean', 'max', 'min').
    label : str
        Etiqueta del período (ej. 'A_1995', 'DJFM_2005', etc.).
    out_png : str
        Ruta del archivo PNG de salida.

    Retorna
    -------
    str
        Ruta del PNG generado.
    """
    import os
    import numpy as np
    import matplotlib.pyplot as plt

    # Colores (mismo para bordes, bigotes y extremos)
    FILL = "#9ecae1"  # pastel
    EDGE = "#3182bd"  # acentuado
    GRID_ALPHA = 0.25

    vals = df["improvement_RMSE_pct"].astype(float).values
    vals = vals[np.isfinite(vals)]

    fig, ax = plt.subplots(figsize=(4.5, 4.2), dpi=150, constrained_layout=True)

    bp = ax.boxplot(
        vals,
        labels=["Mejora %"],
        showfliers=False,  # ocultamos outliers porque ya ponemos puntos jitter
        widths=0.175,  # caja más angosta
        patch_artist=True,
        medianprops=dict(color=EDGE, linewidth=1.2),
        boxprops=dict(linewidth=1.1, color=EDGE),
        whiskerprops=dict(linewidth=1.0, color=EDGE),
        capprops=dict(linewidth=1.0, color=EDGE),
    )

    bp["boxes"][0].set_facecolor(FILL)
    bp["boxes"][0].set_edgecolor(EDGE)
    bp["boxes"][0].set_alpha(0.9)

    # Línea de referencia en 0
    ax.axhline(0, color="k", linewidth=0.5, linestyle="--", alpha=0.7)

    # Puntos de estaciones a un lado del box (desplazados a la derecha)
    rng = np.random.default_rng(42)
    # desplazados, no encima
    x_jitter = 1.18 + rng.normal(0, 0.015, size=len(vals))
    ax.scatter(
        x_jitter,
        vals,
        s=20,
        color=EDGE,
        alpha=0.65,
        edgecolors="none",
        zorder=3,
    )

    ax.set_title(
        f"{var.upper()} {stat} — Mejora relativa de RMSE por estación — {label}",
        fontsize=10,
        fontweight="bold",
    )
    ax.set_ylabel("Mejora de RMSE [%]", fontsize=9, fontweight="bold")
    ax.grid(True, axis="y", alpha=GRID_ALPHA)

    # Estadísticos para anotación
    if vals.size:
        p10, p25, p50, p75, p90 = np.nanpercentile(vals, [10, 25, 50, 75, 90])
        mean = np.nanmean(vals)
        n = len(vals)

        stats_txt = (
            f"n = {n}\n"
            f"Media = {mean:.1f}%\n"
            f"P10 = {p10:.1f}%\n"
            f"P25 = {p25:.1f}%\n"
            f"Mediana = {p50:.1f}%\n"
            f"P75 = {p75:.1f}%\n"
            f"P90 = {p90:.1f}%"
        )

        ax.text(
            0.98,
            0.95,
            stats_txt,
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#999999", alpha=0.85),
        )

    # Ajuste de límites en X para que quepan puntos desplazados
    ax.set_xlim(0.6, 1.5)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=200)
    plt.close(fig)

    return out_png


def plot_scatter_rmse_raw_vs_corr(df, var, stat, label, out_png, units="°C"):
    """
    Genera un scatter plot de RMSE original vs RMSE corregido por estación.

    Cada punto representa una estación. El color indica la diferencia:
        ΔRMSE = RMSE_raw − RMSE_corr

    Valores positivos (azules) indican mejora; valores negativos (rojos) indican
    empeoramiento. La línea 1:1 se incluye como referencia.
    """
    import os
    import numpy as np
    import matplotlib.pyplot as plt

    x = df["RMSE_raw"].astype(float).values
    y = df["RMSE_corr"].astype(float).values

    m = np.isfinite(x) & np.isfinite(y)
    x = x[m]
    y = y[m]

    delta = x - y  # positivo = mejora

    fig, ax = plt.subplots(figsize=(5.0, 5.0), dpi=150, constrained_layout=True)

    if delta.size:
        vmax = np.nanmax(np.abs(delta))
        if not np.isfinite(vmax) or vmax == 0:
            vmax = 1.0
        vmin = -vmax
    else:
        vmin, vmax = -1.0, 1.0

    sc = ax.scatter(
        x,
        y,
        c=delta,
        cmap="RdBu_r",
        vmin=vmin,
        vmax=vmax,
        s=46,
        edgecolors="k",
        linewidths=0.6,
        alpha=0.9,
        zorder=3,
    )

    # Límites con padding
    if x.size:
        v0 = min(x.min(), y.min())
        v1 = max(x.max(), y.max())
        rng = v1 - v0
        pad = 0.05 * rng if np.isfinite(rng) and rng > 0 else max(0.1 * v1, 0.1)
        lo = v0 - pad
        hi = v1 + pad

        ax.plot(
            [lo, hi], [lo, hi], color="#444444", linestyle="--", linewidth=1.2, zorder=2
        )
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)

    ax.set_xlabel(f"RMSE Original [{units}]", fontsize=9, fontweight="bold")
    ax.set_ylabel(f"RMSE Corregido [{units}]", fontsize=9, fontweight="bold")
    ax.set_title(
        f"{var.upper()} {stat} — RMSE por estación — {label}",
        fontsize=10,
        fontweight="bold",
    )
    ax.grid(True, alpha=0.25)

    # Colorbar clara
    cb = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label(
        "ΔRMSE = RMSE_raw − RMSE_corr  [" + units + "]\n(>0 = mejora, <0 = empeora)",
        fontsize=8,
    )
    cb.ax.tick_params(labelsize=8)

    ax.text(
        0.02,
        0.95,
        f"n estaciones = {len(x)}",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8,
    )

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=200)
    plt.close(fig)

    return out_png


def plot_scatter_rmse_vs_improvement(df, var, stat, label, out_png):
    """
    Genera un scatter plot de RMSE original vs mejora relativa de RMSE (%) por estación.

    Cada punto representa una estación. El color indica la mejora porcentual. Se incluye:
    - Línea horizontal en 0 (referencia: sin cambio)
    - Línea de regresión lineal (tendencia)
    - Caja con estadísticas: n, r (Pearson), pendiente y mediana de la mejora

    Parámetros
    ----------
    df : pandas.DataFrame
        DataFrame con columnas: 'RMSE_raw' e 'improvement_RMSE_pct' por estación.
    var : str
        Variable base (ej. 'tmax' o 'tmin').
    stat : str
        Estadístico asociado a la observación (ej. 'mean', 'max', 'min').
    label : str
        Etiqueta del período (ej. 'A_1995', 'DJFM_2005', etc.).
    out_png : str
        Ruta del archivo PNG de salida.

    Retorna
    -------
    str
        Ruta del PNG generado.
    """
    import os
    import numpy as np
    import matplotlib.pyplot as plt

    x = df["RMSE_raw"].astype(float).values
    y = df["improvement_RMSE_pct"].astype(float).values

    m = np.isfinite(x) & np.isfinite(y)
    x = x[m]
    y = y[m]

    fig, ax = plt.subplots(figsize=(6.0, 4.2), dpi=150, constrained_layout=True)

    # Colores por mejora %
    if y.size:
        vmax = np.nanmax(np.abs(y))
        if not np.isfinite(vmax) or vmax == 0:
            vmax = 1.0
        vmin = -vmax
    else:
        vmin, vmax = -1.0, 1.0

    sc = ax.scatter(
        x,
        y,
        c=y,
        cmap="coolwarm",
        vmin=vmin,
        vmax=vmax,
        s=46,
        edgecolors="k",
        linewidths=0.6,
        alpha=0.9,
        zorder=3,
    )

    # Línea horizontal en 0 (sin cambio)
    ax.axhline(0, color="#444444", linewidth=1.1, linestyle="--", alpha=0.8, zorder=2)

    # Ajuste de límites en X con padding
    if x.size:
        xmin, xmax = np.nanmin(x), np.nanmax(x)
        rng = xmax - xmin
        pad = 0.05 * rng if np.isfinite(rng) and rng > 0 else max(0.1 * xmax, 0.1)
        ax.set_xlim(xmin - pad, xmax + pad)

    ax.set_xlabel("RMSE Original", fontsize=9, fontweight="bold")
    ax.set_ylabel("Mejora de RMSE [%]", fontsize=9, fontweight="bold")
    ax.set_title(
        f"{var.upper()} {stat} — Mejora vs RMSE original — {label}",
        fontsize=10,
        fontweight="bold",
    )
    ax.grid(True, alpha=0.25)

    # --- Estadísticos y regresión ---
    n = len(x)
    if n > 1:
        # Correlación de Pearson
        r = np.corrcoef(x, y)[0, 1]

        # Regresión lineal y = a*x + b
        a, b = np.polyfit(x, y, 1)

        # Línea de regresión
        xx = np.linspace(ax.get_xlim()[0], ax.get_xlim()[1], 100)
        yy = a * xx + b
        ax.plot(xx, yy, color="#4DA511", linewidth=1.3, alpha=0.8, zorder=2)

        med = np.nanmedian(y)

        stats_txt = (
            f"n = {n}\n"
            f"r = {r:.2f}\n"
            f"pendiente = {a:.2f} % / °C\n"
            f"mediana(mejora) = {med:.1f} %"
        )
    else:
        stats_txt = f"n = {n}\nr = n/a\npendiente = n/a\nmediana = n/a"

    ax.text(
        0.98,
        0.95,
        stats_txt,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#999999", alpha=0.85),
    )

    # Colorbar
    cb = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Mejora de RMSE [%]", fontsize=8)
    cb.ax.tick_params(labelsize=8)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=200)
    plt.close(fig)

    return out_png


def plot_residual_corr_at_stations_with_dem(
    stations_df,
    dem,
    out_png,
    title,
    extent=None,
    cmap="RdBu_r",
    units="°C",
    value_col="residual_corr",
):
    """
    Genera un mapa de puntos del residuo de la grilla corregida en estaciones:
        residual_corr = Grid_corr - Obs

    El valor mostrado corresponde a la estadística agregada según el modo de ejecución
    (daily: valor diario; period/annual: estadística temporal por estación: mean/max/min).

    Dibuja las estaciones con una escala divergente centrada en cero, superpone
    relieve (hillshade) a partir de un DEM y utiliza un estilo gráfico consistente
    con los demás mapas de estaciones (coastlines, borders, gridlines y colorbar horizontal).
    Incluye etiquetas numéricas evitando solapamientos.

    Parámetros
    ----------
    stations_df : pandas.DataFrame
        DataFrame con columnas: 'lat', 'lon' y la columna indicada por `value_col`
        (por defecto 'residual_corr').
    dem : xarray.DataArray
        Modelo digital de elevación para el sombreado de relieve.
    out_png : str
        Ruta del archivo PNG de salida.
    title : str
        Título del mapa.
    extent : tuple, opcional
        (xmin, xmax, ymin, ymax) para fijar el dominio del mapa.
    cmap : str, opcional
        Colormap divergente (por defecto 'RdBu_r').
    units : str, opcional
        Unidades a mostrar en la etiqueta de la barra de colores.
    value_col : str, opcional
        Nombre de la columna con el residuo a graficar (por defecto 'residual_corr').

    Retorna
    -------
    str
        Ruta del PNG generado.
    """
    import os
    import numpy as np
    import matplotlib.pyplot as plt
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    from matplotlib.colors import LightSource

    proj = ccrs.PlateCarree()

    dem = _rename_coords_latlon(dem)

    lats = stations_df["lat"].values
    lons = stations_df["lon"].values
    vals = stations_df[value_col].astype(float).values

    # Extent coherente con el resto (si viene None, usar DEM)
    if extent is None:
        lon_vals = dem["lon"].values
        lat_vals = dem["lat"].values
        xmin = float(np.nanmin(lon_vals))
        xmax = float(np.nanmax(lon_vals))
        ymin = float(np.nanmin(lat_vals))
        ymax = float(np.nanmax(lat_vals))
        dx = (xmax - xmin) * 0.01
        dy = (ymax - ymin) * 0.01
        extent = (xmin - dx, xmax + dx, ymin - dy, ymax + dy)

    # Rango simétrico alrededor de 0
    vmax = np.nanmax(np.abs(vals))
    if not np.isfinite(vmax) or vmax == 0:
        vmax = 1.0
    vmin = -vmax

    figsize = _figsize_from_extent(extent, base_height=5.5)
    fig = plt.figure(figsize=figsize, dpi=150, constrained_layout=True)

    ax = plt.axes(projection=proj)
    ax.set_extent(extent, crs=proj)

    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.set_xlabel("Longitud", fontsize=9, fontweight="bold")
    ax.set_ylabel("Latitud", fontsize=9, fontweight="bold")

    ax.coastlines(resolution="10m", linewidth=0.6)
    ax.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.6)

    states = cfeature.NaturalEarthFeature(
        category="cultural",
        name="admin_1_states_provinces_lines",
        scale="10m",
        facecolor="none",
        edgecolor="black",
    )
    ax.add_feature(states, linewidth=0.2, alpha=0.6)

    gl = ax.gridlines(
        draw_labels=True, linewidth=0.3, color="gray", alpha=0.5, linestyle="--"
    )
    gl.right_labels = False
    gl.top_labels = False
    gl.xlabel_style = {"size": 8, "weight": "bold"}
    gl.ylabel_style = {"size": 8, "weight": "bold"}

    # Hillshade
    ls = LightSource(azdeg=315, altdeg=45)
    hs = ls.hillshade(dem.values, vert_exag=1, dx=1, dy=1)
    hs_masked = np.where(dem.values > 0, hs, np.nan)

    ax.imshow(
        hs_masked,
        extent=[
            float(dem.lon.min()),
            float(dem.lon.max()),
            float(dem.lat.min()),
            float(dem.lat.max()),
        ],
        origin="lower",
        transform=proj,
        cmap="gray",
        alpha=0.5,
        zorder=0,
    )

    sc = ax.scatter(
        lons,
        lats,
        c=vals,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        s=70,
        edgecolors="k",
        linewidths=0.6,
        transform=proj,
        zorder=3,
    )

    cbar = fig.colorbar(
        sc,
        ax=ax,
        orientation="horizontal",
        fraction=0.05,
        pad=0.08,
    )
    cbar.set_label(
        f"Residuo corregido = Grid_corr − Obs [{units}]",
        fontsize=9,
        fontweight="bold",
    )
    cbar.ax.tick_params(labelsize=8)

    # Etiquetas numéricas
    placed = []
    for _, r in stations_df.iterrows():
        x, y, val = r["lon"], r["lat"], r[value_col]
        if not np.isfinite(val):
            continue
        label = f"{val:+.2f}"
        _place_text_no_overlap(ax, x, y, label, placed, dx=0.20, dy=0.20, max_tries=15)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=200)
    plt.close(fig)

    return out_png


def compute_climatology_doy_by_station(
    csv_station,
    var,
    out_csv,
    drop_feb29=True,
):
    """
    Calcula el ciclo anual climatológico diario (DOY) para una estación,
    usando la serie diaria completa (multi-año).

    Para cada día del año (1–365), calcula:
        - mean
        - max
        - min
        - std

    para:
        - Observaciones (obs)
        - CHIRTS original (raw)
        - CHIRTS corregido (corr)

    Parámetros
    ----------
    csv_station : str
        Ruta al CSV diario por estación (daily_timeseries_*_station_XXX.csv).
    var : str
        Variable base ('tmax' o 'tmin'). Se mantiene por consistencia de interfaz.
    out_csv : str
        Ruta del CSV climatológico de salida.
    drop_feb29 : bool, opcional
        Si True, elimina 29 de febrero para mantener 365 días.

    Retorna
    -------
    str
        Ruta del CSV generado.
    """
    import pandas as pd
    import numpy as np
    import os

    df = pd.read_csv(csv_station)

    # Convertir fecha desde YYYYMMDD
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")

    obs_col = "obs"
    raw_col = "raw"
    corr_col = "corr"

    # Verificación de columnas requeridas
    for c in ["date", obs_col, raw_col, corr_col]:
        if c not in df.columns:
            raise ValueError(
                f"Falta columna requerida '{c}' en {csv_station}. Columnas: {list(df.columns)}"
            )

    # Eliminar 29 de febrero si se desea
    if drop_feb29:
        df = df[~((df["date"].dt.month == 2) & (df["date"].dt.day == 29))]

    df["doy"] = df["date"].dt.dayofyear

    rows = []

    for doy, g in df.groupby("doy"):
        row = {"doy": int(doy)}

        for label, col in zip(
            ["obs", "raw", "corr"],
            [obs_col, raw_col, corr_col],
        ):
            vals = g[col].astype(float).values
            vals = vals[np.isfinite(vals)]

            if len(vals) == 0:
                row[f"{label}_mean"] = np.nan
                row[f"{label}_max"] = np.nan
                row[f"{label}_min"] = np.nan
                row[f"{label}_std"] = np.nan
            else:
                row[f"{label}_mean"] = np.nanmean(vals)
                row[f"{label}_max"] = np.nanmax(vals)
                row[f"{label}_min"] = np.nanmin(vals)
                row[f"{label}_std"] = np.nanstd(vals)

        rows.append(row)

    df_out = pd.DataFrame(rows).sort_values("doy")

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    df_out.to_csv(out_csv, index=False, float_format="%.4f")

    return out_csv


def plot_climatology_doy_station_tripanel(
    csv_clim,
    var,
    station_id,
    out_png,
    units="°C",
):
    """
    Grafica el ciclo anual climatológico diario (DOY) para una estación en una figura
    de tres paneles (mean, max, min), comparando OBS, RAW y CORR.

    En el panel de mean se agrega un sombreado ±1σ alrededor del observado.

    Parámetros
    ----------
    csv_clim : str
        CSV generado por compute_climatology_doy_by_station.
    var : str
        Variable base ('tmax' o 'tmin').
    station_id : str o int
        Identificador de estación.
    out_png : str
        Ruta del PNG de salida.
    units : str, opcional
        Unidades (default: '°C').

    Retorna
    -------
    str
        Ruta del PNG generado.
    """
    import pandas as pd
    import matplotlib.pyplot as plt
    import numpy as np
    import os

    df = pd.read_csv(csv_clim)

    if "doy" not in df.columns:
        raise ValueError("El CSV climatológico no contiene la columna 'doy'")

    x = df["doy"].values

    COLORS = {
        # rojos pastel / rojo más fuerte
        "max": {"raw": "#f4a582", "corr": "#ca0020"},
        "mean": {"raw": "#a6dba0", "corr": "#1b7837"},  # verdes
        "min": {"raw": "#92c5de", "corr": "#0571b0"},  # azules
    }

    COL_OBS = "#000000"

    GRID_ALPHA = 0.25

    MONTH_TICKS = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
    MONTH_LABELS = [
        "Ene",
        "Feb",
        "Mar",
        "Abr",
        "May",
        "Jun",
        "Jul",
        "Ago",
        "Sep",
        "Oct",
        "Nov",
        "Dic",
    ]

    fig, axes = plt.subplots(
        nrows=3,
        ncols=1,
        figsize=(9.0, 7.5),
        dpi=150,
        sharex=True,
        constrained_layout=True,
    )

    panels = [
        ("max", "Máximo diario climatológico"),
        ("mean", "Media diaria climatológica"),
        ("min", "Mínimo diario climatológico"),
    ]

    for ax, (stat, subtitle) in zip(axes, panels):
        obs_col = f"obs_{stat}"
        raw_col = f"raw_{stat}"
        corr_col = f"corr_{stat}"

        for c in [obs_col, raw_col, corr_col]:
            if c not in df.columns:
                raise ValueError(f"El CSV climatológico no contiene la columna '{c}'")

        obs = df[obs_col].values
        raw = df[raw_col].values
        corr = df[corr_col].values

        m_obs = np.isfinite(obs)
        m_raw = np.isfinite(raw)
        m_corr = np.isfinite(corr)

        ax.plot(
            x[m_obs],
            obs[m_obs],
            color=COL_OBS,
            linewidth=2.4,
            alpha=0.8,
            label="Observado",
            zorder=4,
        )
        ax.plot(
            x[m_raw],
            raw[m_raw],
            color=COLORS[stat]["raw"],
            linewidth=1.6,
            label="CHIRTS original",
            zorder=2,
        )
        ax.plot(
            x[m_corr],
            corr[m_corr],
            color=COLORS[stat]["corr"],
            linewidth=1.6,
            label="CHIRTS corregido",
            zorder=3,
        )

        # Sombreado ±1σ solo en el panel de mean (observado)
        if stat == "mean" and "obs_std" in df.columns:
            std = df["obs_std"].values
            m = np.isfinite(obs) & np.isfinite(std)
            if np.any(m):
                ax.fill_between(
                    x[m],
                    obs[m] - std[m],
                    obs[m] + std[m],
                    color=COL_OBS,
                    alpha=0.15,
                    linewidth=0,
                    label="±1σ (Obs)",
                    zorder=1,
                )

        ax.set_ylabel(f"{var.upper()} [{units}]", fontsize=9, fontweight="bold")
        ax.set_title(subtitle, fontsize=9, fontweight="bold")

        ax.set_xticks(MONTH_TICKS)
        ax.set_xticklabels(MONTH_LABELS)
        ax.set_xlim(1, 365)

        ax.grid(True, alpha=GRID_ALPHA)
        ax.tick_params(labelsize=8)

    # Título general
    fig.suptitle(
        f"{var.upper()} — Ciclo anual climatológico diario \nEstación {station_id}",
        fontsize=11,
        fontweight="bold",
    )

    axes[-1].set_xlabel("Mes", fontsize=9, fontweight="bold")
    axes[-1].set_xlim(1, 365)

    # Leyenda solo en el primer panel
    axes[0].legend(fontsize=8, loc="upper right", frameon=True)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=200)
    plt.close(fig)

    return out_png


def plot_climatology_doy_station(
    csv_clim,
    var,
    station_id,
    out_png,
    stat="mean",
    units="°C",
):
    """
    Grafica el ciclo anual climatológico diario (DOY) para una estación en un solo panel,
    comparando OBS, RAW y CORR para un estadístico dado (mean, max o min).

    Usa un estilo gráfico consistente con los demás productos:
      - Colores pastel
      - Grilla suave
      - Títulos y etiquetas en negrita
      - (Opcional) sombreado ±1σ para el caso mean si está disponible

    Parámetros
    ----------
    csv_clim : str
        CSV generado por compute_climatology_doy_by_station.
    var : str
        Variable base ('tmax' o 'tmin').
    station_id : str o int
        Identificador de estación.
    out_png : str
        Ruta del PNG de salida.
    stat : str, opcional
        Estadístico a graficar: 'mean', 'max' o 'min' (default: 'mean').
    units : str, opcional
        Unidades (default: '°C').

    Retorna
    -------
    str
        Ruta del PNG generado.
    """

    if stat not in ["mean", "max", "min"]:
        raise ValueError("stat debe ser 'mean', 'max' o 'min'")

    df = pd.read_csv(csv_clim)

    if "doy" not in df.columns:
        raise ValueError("El CSV climatológico no contiene la columna 'doy'")

    x = df["doy"].values

    COLORS = {
        # rojos pastel / rojo más fuerte
        "max": {"raw": "#f4a582", "corr": "#ca0020"},
        "mean": {"raw": "#a6dba0", "corr": "#1b7837"},  # verdes
        "min": {"raw": "#92c5de", "corr": "#0571b0"},  # azules
    }

    COL_OBS = "#000000"

    GRID_ALPHA = 0.25

    MONTH_TICKS = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
    MONTH_LABELS = [
        "Ene",
        "Feb",
        "Mar",
        "Abr",
        "May",
        "Jun",
        "Jul",
        "Ago",
        "Sep",
        "Oct",
        "Nov",
        "Dic",
    ]

    fig, ax = plt.subplots(figsize=(8.5, 4.5), dpi=150, constrained_layout=True)

    # Series
    obs = df[f"obs_{stat}"].values
    raw = df[f"raw_{stat}"].values
    corr = df[f"corr_{stat}"].values

    m_obs = np.isfinite(obs)
    m_raw = np.isfinite(raw)
    m_corr = np.isfinite(corr)

    ax.plot(
        x[m_obs],
        obs[m_obs],
        color=COL_OBS,
        linewidth=2.4,
        alpha=0.8,
        label="Observado",
        zorder=4,
    )
    ax.plot(
        x[m_raw],
        raw[m_raw],
        color=COLORS[stat]["raw"],
        linewidth=1.6,
        label="CHIRTS original",
        zorder=2,
    )
    ax.plot(
        x[m_corr],
        corr[m_corr],
        color=COLORS[stat]["corr"],
        linewidth=1.6,
        label="CHIRTS corregido",
        zorder=3,
    )

    # Sombreado ±1σ solo para mean si existe
    if stat == "mean" and "obs_std" in df.columns:
        std = df["obs_std"].values
        m = np.isfinite(obs) & np.isfinite(std)
        ax.fill_between(
            x[m],
            obs[m] - std[m],
            obs[m] + std[m],
            color=COL_OBS,
            alpha=0.15,
            linewidth=0,
            label="±1σ (Obs)",
            zorder=1,
        )

    # Títulos y etiquetas
    stat_name = {"mean": "Media", "max": "Máximo", "min": "Mínimo"}[stat]

    ax.set_title(
        f"{var.upper()} — {stat_name} diario climatológico\nEstación {station_id}",
        fontsize=10,
        fontweight="bold",
    )

    ax.set_xlabel("Mes", fontsize=9, fontweight="bold")
    ax.set_ylabel(f"{var.upper()} [{units}]", fontsize=9, fontweight="bold")

    ax.set_xticks(MONTH_TICKS)
    ax.set_xticklabels(MONTH_LABELS)
    ax.set_xlim(1, 365)
    ax.grid(True, alpha=GRID_ALPHA)

    ax.tick_params(labelsize=8)

    ax.legend(fontsize=8, loc="upper right", frameon=True)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, dpi=200)
    plt.close(fig)

    return out_png


# ------------------------- Main -------------------------


def main():
    """
    Punto de entrada principal del script de evaluación CHIRTS vs CHIRTS-corregido.

    Este programa permite:
      - Generar mapas comparativos (side-by-side) entre CHIRTS original y corregido.
      - Exportar CSV de comparación en estaciones.
      - Generar productos de diagnóstico: ΔGRID (campo y estaciones), mejoras (ΔRMSE).
      - Ejecutar evaluaciones estadísticas globales y por estación.
      - Operar en distintos modos:
          * annual      : procesamiento anual por año y estadístico
          * daily       : procesamiento de un día específico
          * daily-eval  : evaluación diaria completa en serie temporal
          * period      : procesamiento por temporadas o meses definidos

    Modos principales
    ------------------
    annual:
        Recorre un rango de años (--yini, --yend) y genera:
          - Mapas side-by-side por año y estadístico
          - CSV de comparación por estaciones
          - Mapas ΔGRID por año y un ΔGRID global promedio
        Si se activa --eval, además genera:
          - Boxplots, scatter OBS vs grid, rankings por estación
          - Métricas anuales globales (Bias, MAE, RMSE, R)
          - Mapas de mejora por estación (ΔRMSE)

    daily:
        Procesa una fecha específica (--date):
          - Mapa side-by-side diario
          - CSV de comparación en estaciones
          - Productos de diagnóstico diarios (ΔGRID campo y estaciones)

    daily-eval:
        Construye la serie diaria completa para todos los años disponibles:
          - Serie diaria de obs, raw y corr en estaciones
          - Resúmenes globales y por estación (Bias, MAE, RMSE)

    period:
        Procesa períodos definidos por:
          - Temporadas (--period-type season, --season / --all-seasons)
          - Meses específicos (--period-type months, --months)
        Para cada año, período y estadístico:
          - Genera mapas side-by-side
          - CSV de comparación en estaciones
          - Productos de diagnóstico (ΔGRID, ΔRMSE en estaciones)

    Parámetros de entrada (CLI)
    ---------------------------
    --csv            : Archivo CDT con observaciones en estaciones.
    --dir-chirts     : Directorio con NetCDF diarios/anuales de CHIRTS original.
    --prefix-chirts  : Prefijo de archivos CHIRTS originales (default: "temp_").
    --dir-merged     : Directorio con NetCDF de CHIRTS corregido.
    --var            : Variable a procesar ("tmax" o "tmin").
    --stat           : Estadístico ("mean", "max", "min" o "all").
    --dem            : NetCDF con el modelo digital de elevación (DEM).
    --out            : Directorio base de salida.
    --yini, --yend   : Rango de años para modos annual/period.
    --extent         : Extensión geográfica (xmin xmax ymin ymax).
    --mode           : Modo de operación ("annual", "daily", "daily-eval", "period").
    --period-type    : Tipo de período ("season" o "months") para modo period.
    --season         : Temporada (DJFM, A, MJJ, ASO, N).
    --months         : Lista de meses (ej: "5,6,7") para modo period.
    --all-seasons    : Procesa todas las temporadas definidas.
    --eval           : Activa productos de evaluación estadística.
    --date           : Fecha específica para modo daily (YYYY-MM-DD).

    Flujo general
    -------------
    1) Parseo de argumentos y validación básica.
    2) Lectura del CSV de estaciones y preparación del DataFrame largo.
    3) Carga del DEM.
    4) Enrutamiento según el modo seleccionado:
         - daily-eval
         - daily
         - period
         - annual (por defecto)
    5) Generación de productos operativos (mapas, CSV).
    6) Si --eval está activo, generación de productos de evaluación estadística.
    """

    # ------------------------------------------------------------------
    # 1) Definición de argumentos de línea de comandos
    # ------------------------------------------------------------------
    ap = argparse.ArgumentParser(
        description="Mapas anuales CHIRTS vs CHIRTS-corregido (estilo CHIRPS) con relieve y estaciones."
    )
    ap.add_argument("--csv", required=True)
    ap.add_argument("--dir-chirts", required=True)
    ap.add_argument("--prefix-chirts", default="temp_")
    ap.add_argument("--dir-merged", required=True)
    ap.add_argument("--var", choices=["tmax", "tmin"], required=True)
    ap.add_argument("--stat", choices=["mean", "max", "min", "all"], required=True)
    ap.add_argument("--dem", required=True, help="NetCDF con elevación")
    ap.add_argument("--out", default="./salidas")
    ap.add_argument("--yini", type=int)
    ap.add_argument("--yend", type=int)
    ap.add_argument("--extent", nargs=4, type=float)
    ap.add_argument(
        "--mode", choices=["annual", "daily", "daily-eval", "period"], default="annual"
    )
    ap.add_argument("--period-type", choices=["season", "months"])
    ap.add_argument("--season", choices=list(SEASONS.keys()))
    ap.add_argument("--months", help="Ej: 5,6,7")
    ap.add_argument("--all-seasons", action="store_true")
    ap.add_argument(
        "--eval", action="store_true", help="Genera graficos y tablas de evaluacion"
    )
    ap.add_argument("--date", help="Fecha para modo daily: YYYY-MM-DD")

    args = ap.parse_args()

    # ------------------------------------------------------------------
    # 2) Validaciones básicas y selección de estadísticas a correr
    # ------------------------------------------------------------------
    if args.mode == "daily" and args.date is None:
        ap.error("--date es obligatorio cuando --mode daily")

    if args.stat == "all":
        stats_to_run = ["mean", "max", "min"]
    else:
        stats_to_run = [args.stat]

    # ------------------------------------------------------------------
    # 3) Lectura del CSV de estaciones y preparación del DataFrame largo
    # ------------------------------------------------------------------

    value_name = f"{args.var}_station"
    meta, df_obs_long = parse_cdt_csv(args.csv, value_name)
    df_obs_long["date"] = pd.to_datetime(df_obs_long["date"], format="%Y%m%d")

    # ------------------------------------------------------------------
    # 4) Modo: daily-eval (evaluación diaria completa en serie temporal)
    # ------------------------------------------------------------------
    # MODO: daily-eval
    # Construye la serie diaria completa de estaciones vs rejilla
    # para todos los años disponibles y genera resúmenes estadísticos.
    #
    # Flujo:
    # 1) Identifica los años presentes en el CSV de estaciones.
    # 2) Procesa cada año en paralelo para construir la serie diaria:
    #      - Para cada día y estación: obs, raw y corr.
    # 3) Concatena todos los años en un único DataFrame diario.
    # 4) Guarda la serie diaria completa a disco.
    # 5) Genera:
    #      - Resumen global (Bias, MAE, RMSE) usando todos los datos.
    #      - Resumen por estación (Bias, MAE, RMSE) en toda la serie.
    # 6) Termina la ejecución (no continúa a otros modos).

    if args.mode == "daily-eval":
        print(f"Construyendo evaluación diaria completa para {args.var}...")

        # Años disponibles en el CSV de estaciones
        years = sorted(df_obs_long["year"].unique())

        print(f"Procesando {len(years)} años en paralelo...")

        # Preparar tareas para ejecutar un año por proceso
        from concurrent.futures import ProcessPoolExecutor

        tasks = [
            (
                y,
                df_obs_long,
                args.dir_chirts,
                args.dir_merged,
                args.var,
                args.prefix_chirts,
            )
            for y in years
        ]

        # Ejecutar en paralelo: cada worker construye la serie diaria de un año
        with ProcessPoolExecutor(max_workers=4) as ex:
            dfs = list(ex.map(process_year_worker, tasks))

        # Unir todas las series anuales en una sola serie diaria completa
        df_daily = pd.concat(dfs, ignore_index=True)

        # Directorio de salida para la evaluación diaria
        out_dir = os.path.join(args.out, args.var, "daily_eval")
        os.makedirs(out_dir, exist_ok=True)

        # Guardar la serie diaria completa (útil para análisis posteriores)
        daily_csv = os.path.join(out_dir, f"daily_timeseries_{args.var}_1991_2020.csv")
        df_daily = df_daily.sort_values(["station_id", "date"]).reset_index(drop=True)
        df_daily.to_csv(daily_csv, index=False)
        print(f"✓ Serie diaria guardada: {daily_csv}")

        # --------------------------------------------------
        # Exportar series diarias por estación (archivos pequeños y manejables)
        # --------------------------------------------------
        out_station_dir = os.path.join(out_dir, "by_station")
        os.makedirs(out_station_dir, exist_ok=True)

        print("→ Exportando series diarias por estación...")

        for sid, g in df_daily.groupby("station_id"):
            out_csv_st = os.path.join(
                out_station_dir, f"daily_timeseries_{args.var}_station_{sid}.csv"
            )
            g = g.sort_values("date")
            g.to_csv(out_csv_st, index=False)

        # --------------------------------------------------
        # Construir climatología DOY por estación
        # --------------------------------------------------
        print("→ Construyendo climatología DOY por estación...")

        clim_base_dir = os.path.join(out_dir, "climatology_doy")
        os.makedirs(clim_base_dir, exist_ok=True)

        for fname in os.listdir(out_station_dir):
            if not fname.endswith(".csv"):
                continue

            csv_station = os.path.join(out_station_dir, fname)

            # Extraer station_id del nombre
            station_id = fname.split("_")[-1].replace(".csv", "")

            station_dir = os.path.join(clim_base_dir, f"station_{station_id}")
            os.makedirs(station_dir, exist_ok=True)

            csv_clim = os.path.join(
                station_dir,
                f"clim_doy_{args.var}_station_{station_id}.csv",
            )

            compute_climatology_doy_by_station(
                csv_station,
                args.var,
                csv_clim,
                drop_feb29=True,
            )

            # Graficar mean, max y min
            for stat in ["mean", "max", "min"]:
                out_png = os.path.join(
                    station_dir,
                    f"clim_doy_{args.var}_{stat}_station_{station_id}.png",
                )

                plot_climatology_doy_station(
                    csv_clim,
                    args.var,
                    station_id,
                    out_png,
                    stat=stat,
                )

            out_png = os.path.join(
                station_dir,
                f"clim_doy_{args.var}_tripanel_station_{station_id}.png",
            )

            plot_climatology_doy_station_tripanel(
                csv_clim,
                args.var,
                station_id,
                out_png,
            )

        # ---------------- Resumen global ----------------
        # Métricas agregadas usando todos los días y todas las estaciones
        summary_global = summarize_daily_global(df_daily, args.var)
        summary_global_csv = os.path.join(
            out_dir, f"summary_daily_global_{args.var}.csv"
        )
        summary_global.to_csv(summary_global_csv, index=False)
        print(f"✓ Resumen global diario: {summary_global_csv}")

        # ---------------- Resumen por estación ----------------
        # Métricas calculadas separadamente para cada estación
        summary_station = summarize_daily_by_station(df_daily)
        summary_station_csv = os.path.join(
            out_dir, f"summary_daily_by_station_{args.var}.csv"
        )
        summary_station.to_csv(summary_station_csv, index=False)
        print(f"✓ Resumen por estación: {summary_station_csv}")

        # Salir del main: este modo no continúa con anual/period/daily
        return

    # ------------------------------------------------------------------
    # 5) Carga del DEM (común para los demás modos)
    # ------------------------------------------------------------------

    dem_ds = xr.open_dataset(args.dem)
    dem = _rename_coords_latlon(list(dem_ds.data_vars.values())[0])

    prefix_merged = f"{args.var}_mrg_"

    # ------------------------------------------------------------------
    # 6) Modo: daily (un día específico)
    # ------------------------------------------------------------------
    # MODO: daily
    # Genera productos para UNA fecha específica:
    #
    # Productos principales:
    #  - Mapa side-by-side: CHIRTS original vs CHIRTS corregido
    #  - CSV de comparación en estaciones (obs, raw, corr, errores)
    #
    # Productos de diagnóstico (evaluación diaria):
    #  - Mapa de CAMPO ΔGRID = corr - raw
    #  - Mapa de ΔGRID en estaciones
    #  - Copia del CSV de comparación en carpeta de evaluación
    #
    # Este modo es puntual (una fecha) y termina la ejecución.

    if args.mode == "daily":
        date = args.date  # 'YYYY-MM-DD'

        print(f"Procesando modo DAILY: {args.var} {date}")

        # Extraer observaciones de estaciones para ese día
        stations_obs_day = daily_station_values(df_obs_long, date, value_name)

        # Cargar campos diarios: CHIRTS original y CHIRTS corregido
        da_raw = load_daily_chirts_raw(args.dir_chirts, date, args.prefix_chirts)
        da_corr = load_daily_chirts_corr(args.dir_merged, date)

        # Definir extent común desde la grilla
        extent_plot = (
            tuple(args.extent)
            if args.extent
            else (
                float(da_raw.lon.min()),
                float(da_raw.lon.max()),
                float(da_raw.lat.min()),
                float(da_raw.lat.max()),
            )
        )

        # Directorio de salida para mapas diarios
        out_maps_dir = os.path.join(args.out, args.var, "daily")
        os.makedirs(out_maps_dir, exist_ok=True)

        out_png = os.path.join(out_maps_dir, f"{args.var}_daily_{date}.png")

        # --------- Producto operativo principal: mapa side-by-side ---------
        plot_side_by_side(
            da_left=da_raw,
            da_right=da_corr,
            dem=dem,
            year=date,  # se usa solo en el título
            var=args.var,
            stat="daily",
            stations_obs_year=stations_obs_day,
            out_png=out_png,
            bins=25,
            vmin=0,
            vmax=50,
            cmap="RdYlBu_r",
            extent=extent_plot,
        )

        print(f"✓ Guardado: {out_png}")

        # --------- CSV de comparación en estaciones ---------
        csv_path = export_cmp_csv_next_to_png(
            stations_obs_year=stations_obs_day,
            da_raw=da_raw,
            da_corr=da_corr,
            year=date,
            var=args.var,
            stat="daily",
            out_png=out_png,
        )

        print(f"✓ CSV comparación estaciones: {csv_path}")

        # ====================================================
        # Productos de diagnóstico (evaluación diaria)
        # ====================================================
        eval_daily_dir = os.path.join(args.out, args.var, "eval", "daily", date)
        os.makedirs(eval_daily_dir, exist_ok=True)

        # --------- 1) Mapa de CAMPO ΔGRID = corr - raw ---------
        out_png_delta_field = os.path.join(
            eval_daily_dir, f"delta_grid_field_{args.var}_daily_{date}.png"
        )

        plot_delta_grid_field(
            da_raw=da_raw,
            da_corr=da_corr,
            dem=dem,
            out_png=out_png_delta_field,
            title=f"{args.var.upper()} — Diferencia espacial - CHIRTS (Corregido − Original) — {date}",
            extent=extent_plot,
        )

        print(f"✓ Mapa ΔGRID campo diario: {out_png_delta_field}")

        # --------- 2) Mapa de ΔGRID en estaciones ---------
        df_cmp = pd.read_csv(csv_path)
        print(df_cmp.columns)
        obs_col = f"{args.var}_daily_obs"
        stations_resid_df = pd.DataFrame(
            {
                "lat": df_cmp["lat"],
                "lon": df_cmp["lon"],
                "residual_corr": df_cmp["grid_corr"] - df_cmp[obs_col],
            }
        )

        stations_delta_df = pd.DataFrame(
            {
                "lat": df_cmp["lat"],
                "lon": df_cmp["lon"],
                "delta_grid": df_cmp["grid_corr"] - df_cmp["grid_raw"],
            }
        )

        out_png_delta_st = os.path.join(
            eval_daily_dir, f"delta_grid_stations_{args.var}_daily_{date}.png"
        )

        plot_delta_grid_at_stations(
            stations_df=stations_delta_df,
            dem=dem,
            out_png=out_png_delta_st,
            title=f"{args.var.upper()} — Diferencia en estaciones - CHIRTS (Corregido − Original) — {date}",
            extent=extent_plot,
        )

        print(f"✓ Mapa ΔGRID estaciones diario: {out_png_delta_st}")

        out_png_resid_st = os.path.join(
            eval_daily_dir, f"residual_corr_stations_{args.var}_daily_{date}.png"
        )

        plot_residual_corr_at_stations_with_dem(
            stations_df=stations_resid_df,
            dem=dem,
            out_png=out_png_resid_st,
            title=f"{args.var.upper()} — Residuo (Corr − Obs) en estaciones — {date}",
            extent=extent_plot,
        )

        print(f"✓ Mapa residuo estaciones diario: {out_png_resid_st}")

        # --------- 3) Copiar CSV de comparación a carpeta de evaluación ---------
        import shutil

        shutil.copy(csv_path, eval_daily_dir)
        print(f"✓ CSV copiado a: {eval_daily_dir}")

        # Terminar ejecución: este modo no continúa con anual/period
        return

    # ------------------------------------------------------------------
    # 7) Modo: period (temporadas o meses)
    # ------------------------------------------------------------------
    # MODO: period
    #
    # Genera productos para PERÍODOS definidos por:
    #  - Estaciones climáticas (DJFM, AMJ, etc.)
    #  - O conjuntos de meses (ej: 5,6,7)
    #
    # Para cada año, cada período y cada estadística:
    #  - Calcula el campo agregado (mean/max/min)
    #  - Genera mapa side-by-side (raw vs corregido)
    #  - Genera CSV de comparación en estaciones
    #  - Genera productos de evaluación:
    #       * Mapa ΔGRID (campo)
    #       * Mapa ΔGRID en estaciones
    #       * CSV de mejora por estación (RMSE)
    #       * Mapa ΔRMSE en estaciones
    #
    # Este modo es multi-año y multi-período, y termina la ejecución.

    if args.mode == "period":
        # --- Validaciones obligatorias ---
        if args.period_type is None:
            ap.error("--period-type es obligatorio en modo period")

        # En modo period SIEMPRE se debe indicar rango de años
        if args.yini is None or args.yend is None:
            ap.error("--yini y --yend son obligatorios cuando --mode period")

        # Lista de años a procesar
        years = list(range(args.yini, args.yend + 1))

        # ------------------------------------------------
        # Determinar qué períodos se van a correr
        # ------------------------------------------------
        periods = []

        if args.period_type == "season":
            # Modo estaciones climáticas
            if args.all_seasons:
                # Todas las estaciones definidas en SEASONS
                periods = list(SEASONS.keys())
            else:
                # Solo una estación específica
                if args.season is None:
                    ap.error("--season es obligatorio si no usas --all-seasons")
                periods = [args.season]

        elif args.period_type == "months":
            # Modo meses específicos
            if args.months is None:
                ap.error("--months es obligatorio cuando period-type=months")

            # Convertir "5,6,7" -> [5, 6, 7]
            months = [int(m) for m in args.months.split(",")]
            periods = [months]

        # ------------------------------------------------
        # Bucle principal: por año, por período y por estadística
        # ------------------------------------------------
        for year in years:
            for p in periods:
                # --------------------------------------------
                # Construir las fechas que componen el período
                # --------------------------------------------
                if args.period_type == "season":
                    season = p

                    # Caso especial: DJFM cruza de año (dic del año previo)
                    # Se omite el primer año si no existe diciembre anterior
                    if season == "DJFM" and year == args.yini:
                        print(
                            f"⚠️ Se omite {season}_{year} por falta de diciembre del año anterior"
                        )
                        continue

                    # Generar lista de fechas YYYYMMDD del período
                    dates = get_dates_for_period(
                        year=year,
                        period_type="season",
                        season=season,
                    )

                    # Etiquetas para archivos y títulos
                    label = f"{season}_{year}"
                    title_label = make_period_title(
                        period_type="season", year=year, season=season
                    )

                else:  # period_type == "months"
                    months = p

                    dates = get_dates_for_period(
                        year=year,
                        period_type="months",
                        months=months,
                    )

                    # Construir nombre legible para archivos
                    months_names = [MONTH_NAMES_ES[m].lower() for m in months]

                    if len(months_names) == 1:
                        label = f"{months_names[0]}_{year}"  # ej: marzo_2005
                    else:
                        # ej: mayo-junio-julio_2005
                        label = f"{'-'.join(months_names)}_{year}"

                    title_label = make_period_title(
                        period_type="months", year=year, months=months
                    )

                # Si por alguna razón no hay fechas, se omite
                if len(dates) == 0:
                    print(f"⚠️ Sin fechas para {label}, se omite.")
                    continue

                print(f"Procesando {label} ({len(dates)} días)")

                # ------------------------------------------------
                # Bucle por estadística (mean, max, min)
                # ------------------------------------------------
                for stat in stats_to_run:
                    print(f"  → Estadística: {stat}")

                    # Cargar campos agregados del período
                    da_raw = load_period_stat_raw(
                        args.dir_chirts, dates, args.prefix_chirts, stat
                    )
                    da_corr = load_period_stat_corr(
                        args.dir_merged, dates, args.var, stat
                    )

                    # Definir extent común desde la grilla
                    extent_plot = (
                        tuple(args.extent)
                        if args.extent
                        else (
                            float(da_raw.lon.min()),
                            float(da_raw.lon.max()),
                            float(da_raw.lat.min()),
                            float(da_raw.lat.max()),
                        )
                    )

                    # Calcular estadístico del período en estaciones
                    stations_obs = period_station_stat(
                        df_obs_long, dates, args.var, stat
                    )

                    # ====================================================
                    # Producto operativo principal: mapa side-by-side
                    # ====================================================
                    out_dir = os.path.join(args.out, args.var, "period", stat)
                    os.makedirs(out_dir, exist_ok=True)

                    out_png = os.path.join(out_dir, f"{args.var}_{stat}_{label}.png")

                    plot_side_by_side(
                        da_left=da_raw,
                        da_right=da_corr,
                        dem=dem,
                        year=title_label,
                        var=args.var,
                        stat=stat,
                        stations_obs_year=stations_obs,
                        out_png=out_png,
                        bins=25,
                        vmin=0,
                        vmax=50,
                        cmap="RdYlBu_r",
                        extent=extent_plot,
                    )

                    print(f"✓ Guardado: {out_png}")

                    # ====================================================
                    # CSV de comparación en estaciones
                    # ====================================================
                    csv_path = export_cmp_csv_next_to_png(
                        stations_obs_year=stations_obs,
                        da_raw=da_raw,
                        da_corr=da_corr,
                        year=label,
                        var=args.var,
                        stat=stat,
                        out_png=out_png,
                    )

                    print(f"✓ CSV comparación estaciones: {csv_path}")

                    # ====================================================
                    # Carpeta de evaluación para este período
                    # ====================================================
                    eval_period_dir = os.path.join(
                        args.out, args.var, "eval", "period", stat, label
                    )
                    os.makedirs(eval_period_dir, exist_ok=True)

                    # --------- 1) Mapa de CAMPO ΔGRID ---------
                    out_png_delta_field = os.path.join(
                        eval_period_dir,
                        f"delta_grid_field_{args.var}_{stat}_{label}.png",
                    )

                    plot_delta_grid_field(
                        da_raw=da_raw,
                        da_corr=da_corr,
                        dem=dem,
                        out_png=out_png_delta_field,
                        title=f"{args.var.upper()} {stat} — Diferencia espacial - CHIRTS (Corregido − Original) — {title_label}",
                        extent=extent_plot,
                    )

                    print(f"✓ Mapa ΔGRID campo período: {out_png_delta_field}")

                    # --------- 2) Mapa de ΔGRID en estaciones ---------
                    df_cmp = pd.read_csv(csv_path)

                    # --------- Residuo corr - obs agregado por estación ---------
                    obs_col = f"{args.var}_{stat}_obs"

                    rows_res = []
                    for (sid, lat, lon), g in df_cmp.groupby(
                        ["station_id", "lat", "lon"]
                    ):
                        obs = g[obs_col].astype(float).values
                        corr = g["grid_corr"].astype(float).values

                        m = np.isfinite(obs) & np.isfinite(corr)
                        if not np.any(m):
                            continue

                        obs = obs[m]
                        corr = corr[m]

                        residual_series = corr - obs

                        if stat == "mean":
                            residual_stat = np.nanmean(residual_series)
                        elif stat == "max":
                            residual_stat = np.nanmax(residual_series)
                        elif stat == "min":
                            residual_stat = np.nanmin(residual_series)
                        else:
                            raise ValueError("stat debe ser 'mean', 'max' o 'min'")

                        rows_res.append(
                            {
                                "station_id": sid,
                                "lat": lat,
                                "lon": lon,
                                "residual_corr": residual_stat,
                            }
                        )

                    df_res = pd.DataFrame(rows_res)

                    rows_dg = []
                    for (sid, lat, lon), g in df_cmp.groupby(
                        ["station_id", "lat", "lon"]
                    ):
                        raw = g["grid_raw"].astype(float).values
                        corr = g["grid_corr"].astype(float).values

                        m = np.isfinite(raw) & np.isfinite(corr)
                        if not np.any(m):
                            continue

                        raw = raw[m]
                        corr = corr[m]

                        diff = corr - raw

                        if stat == "mean":
                            delta_stat = np.nanmean(diff)
                        elif stat == "max":
                            delta_stat = np.nanmax(diff)
                        elif stat == "min":
                            delta_stat = np.nanmin(diff)

                        rows_dg.append(
                            {"lat": lat, "lon": lon, "delta_grid": delta_stat}
                        )

                    stations_delta_df = pd.DataFrame(rows_dg)

                    out_png_delta_st = os.path.join(
                        eval_period_dir,
                        f"delta_grid_stations_{args.var}_{stat}_{label}.png",
                    )

                    plot_delta_grid_at_stations(
                        stations_df=stations_delta_df,
                        dem=dem,
                        out_png=out_png_delta_st,
                        title=f"{args.var.upper()} {stat} — Diferencia espacial - CHIRTS (Corregido − Original) en estaciones — {title_label}",
                        extent=extent_plot,
                    )

                    print(f"✓ Mapa ΔGRID en estaciones período: {out_png_delta_st}")

                    # --------- 3) CSV de mejora por estación (RMSE) ---------
                    period_improve_csv = os.path.join(
                        eval_period_dir,
                        f"improvement_stations_{args.var}_{stat}_{label}_RMSE.csv",
                    )

                    build_station_improvement_csv(
                        [csv_path], args.var, stat, period_improve_csv, metric="rmse"
                    )

                    # --------- 4) Mapa de ΔRMSE en estaciones ---------
                    out_map_imp_period = os.path.join(
                        eval_period_dir,
                        f"improvement_RMSEpct_stations_{args.var}_{stat}_{label}.png",
                    )

                    df_imp = pd.read_csv(period_improve_csv)

                    stations_df = pd.DataFrame(
                        {
                            "lat": df_imp["lat"],
                            "lon": df_imp["lon"],
                            "improvement_RMSE_pct": df_imp["improvement_RMSE_pct"],
                        }
                    )

                    plot_improvement_at_stations_with_dem(
                        stations_df=stations_df,
                        dem=dem,
                        out_png=out_map_imp_period,
                        title=f"{args.var.upper()} {stat} — Mejora relativa de RMSE en estaciones (%) — {title_label}",
                        extent=extent_plot,
                    )

                    print(f"✓ Mapa ΔRMSE estaciones período: {out_map_imp_period}")

                    # --------- 5) Boxplots y scatter por estación (period) ---------

                    # Boxplot RMSE raw vs corr
                    out_box_rmse = os.path.join(
                        eval_period_dir,
                        f"boxplot_RMSE_stations_{args.var}_{stat}_{label}.png",
                    )
                    plot_boxplot_rmse_by_station(
                        df_imp, args.var, stat, label, out_box_rmse
                    )

                    # Boxplot mejora %
                    out_box_imp = os.path.join(
                        eval_period_dir,
                        f"boxplot_improvement_RMSEpct_stations_{args.var}_{stat}_{label}.png",
                    )
                    plot_boxplot_improvement_pct_by_station(
                        df_imp, args.var, stat, label, out_box_imp
                    )

                    # Scatter RMSE raw vs corr
                    out_sc_rmse = os.path.join(
                        eval_period_dir,
                        f"scatter_RMSE_raw_vs_corr_{args.var}_{stat}_{label}.png",
                    )
                    plot_scatter_rmse_raw_vs_corr(
                        df_imp, args.var, stat, label, out_sc_rmse
                    )

                    # (Opcional) Scatter RMSE raw vs improvement %
                    out_sc_imp = os.path.join(
                        eval_period_dir,
                        f"scatter_RMSE_raw_vs_improvement_{args.var}_{stat}_{label}.png",
                    )
                    plot_scatter_rmse_vs_improvement(
                        df_imp, args.var, stat, label, out_sc_imp
                    )

                    out_png_resid_st = os.path.join(
                        eval_period_dir,
                        f"residual_corr_stations_{args.var}_{stat}_{label}.png",
                    )

                    plot_residual_corr_at_stations_with_dem(
                        stations_df=df_res,
                        dem=dem,
                        out_png=out_png_resid_st,
                        title=f"{args.var.upper()} {stat} — Residuo (Corr − Obs) en estaciones — {title_label}",
                        extent=extent_plot,
                    )

                    print(f"✓ Mapa residuo estaciones período: {out_png_resid_st}")

                    # --------- 6) Copiar CSV de comparación a carpeta de evaluación ---------
                    import shutil

                    shutil.copy(csv_path, eval_period_dir)
                    print(f"✓ CSV copiado a: {eval_period_dir}")

        # Este modo no continúa con anual
        return

    # ------------------------------------------------------------------
    # 8) Modo: annual (por defecto)
    # ------------------------------------------------------------------
    # MODO ANUAL (por defecto)
    #
    # Para cada estadística (mean/max/min):
    #   - Recorre los años [yini, yend]
    #   - Genera mapas side-by-side (raw vs corregido)
    #   - Genera mapas ΔGRID por año (campo completo)
    #   - Exporta CSV de comparación en estaciones por año
    #   - Acumula ΔGRID para construir un ΔGRID GLOBAL (promedio temporal)
    #
    # Si --eval está activo, además:
    #   - Construye productos de evaluación GLOBAL y por AÑO:
    #       * CSV global por estación
    #       * Mapas ΔGRID en estaciones (global)
    #       * CSV y mapas de mejora (ΔRMSE)
    #       * Métricas anuales (Bias, MAE, RMSE, R)
    #       * Gráficos: RMSE temporal, boxplots, scatter
    #       * Rankings por estación (global y por año)

    for stat in stats_to_run:
        # Lista para acumular campos ΔGRID de cada año
        # (luego se promedia para construir el GLOBAL)
        deltas_for_global = []

        # ------------------------------------------------
        # Preparar carpetas de evaluación anual
        # ------------------------------------------------
        base_eval_dir = os.path.join(args.out, args.var, "eval", "annual", stat)
        global_dir = os.path.join(base_eval_dir, "global")
        by_year_dir = os.path.join(base_eval_dir, "by_year")

        os.makedirs(global_dir, exist_ok=True)
        os.makedirs(by_year_dir, exist_ok=True)

        # Carpeta de mapas operativos (side-by-side) por variable y estadística
        out_maps_dir = os.path.join(args.out, args.var, stat)
        os.makedirs(out_maps_dir, exist_ok=True)

        # ------------------------------------------------
        # Bucle principal por año
        # ------------------------------------------------
        for year in range(args.yini, args.yend + 1):
            print(f"Procesando {args.var} {stat} {year}...")

            # Extraer estadístico anual observado en estaciones
            stations_obs_year = annual_station_stat(df_obs_long, year, stat, value_name)

            # Cargar campos anuales (raw y corregido)
            da_raw = load_annual_temp_stat(
                args.dir_chirts, year, args.prefix_chirts, args.var, stat
            )
            da_corr = load_annual_temp_stat(
                args.dir_merged, year, prefix_merged, args.var, stat
            )

            # Definir extent común desde la grilla
            extent_plot = (
                tuple(args.extent)
                if args.extent
                else (
                    float(da_raw.lon.min()),
                    float(da_raw.lon.max()),
                    float(da_raw.lat.min()),
                    float(da_raw.lat.max()),
                )
            )

            # Calcular ΔGRID del año y guardarlo para el GLOBAL
            delta_year = da_corr - da_raw
            deltas_for_global.append(delta_year)

            # ------------------------------------------------
            # Mapa operativo side-by-side
            # ------------------------------------------------
            out_png = os.path.join(out_maps_dir, f"{args.var}_{stat}_anual_{year}.png")

            plot_side_by_side(
                da_left=da_raw,
                da_right=da_corr,
                dem=dem,
                year=year,
                var=args.var,
                stat=stat,
                stations_obs_year=stations_obs_year,
                out_png=out_png,
                bins=25,
                vmin=0,
                vmax=50,
                cmap="RdYlBu_r",
                extent=extent_plot,
            )

            # ------------------------------------------------
            # Mapa de CAMPO ΔGRID por año
            # ------------------------------------------------
            year_dir = os.path.join(by_year_dir, str(year))
            os.makedirs(year_dir, exist_ok=True)

            out_png_delta_field = os.path.join(
                year_dir, f"delta_grid_field_{args.var}_{stat}_{year}.png"
            )

            plot_delta_grid_field(
                da_raw=da_raw,
                da_corr=da_corr,
                dem=dem,
                out_png=out_png_delta_field,
                title=f"{args.var.upper()} {stat} — Diferencia espacial - CHIRTS (Corregido − Original) — {year}",
                extent=extent_plot,
            )

            print(f"✓ Mapa ΔGRID campo completo {year}: {out_png_delta_field}")
            print(f"✓ Guardado: {out_png}")

            # ------------------------------------------------
            # CSV de comparación en estaciones (raw vs corr vs obs)
            # ------------------------------------------------
            csv_path = export_cmp_csv_next_to_png(
                stations_obs_year=stations_obs_year,
                da_raw=da_raw,
                da_corr=da_corr,
                year=year,
                var=args.var,  # tmax o tmin
                stat=stat,  # mean, max o min
                out_png=out_png,
            )

            print(f"✓ CSV comparación estaciones: {csv_path}")

        # ------------------------------------------------
        # Mapa de CAMPO ΔGRID GLOBAL (promedio temporal)
        # ------------------------------------------------
        if deltas_for_global:
            delta_global = xr.concat(deltas_for_global, dim="time").mean("time")

            out_png_delta_field_global = os.path.join(
                global_dir, f"delta_grid_field_{args.var}_{stat}_GLOBAL.png"
            )

            plot_delta_grid_field(
                da_raw=None,  # no se usan en este caso
                da_corr=None,  # se pasa el delta por override
                dem=dem,
                out_png=out_png_delta_field_global,
                title=f"{args.var.upper()} {stat} — Diferencia espacial - CHIRTS (Corregido − Original) — GLOBAL",
                extent=extent_plot,
                delta_override=delta_global,
            )

            print(f"✓ Mapa ΔGRID campo completo GLOBAL: {out_png_delta_field_global}")

        # ================================================================
        # BLOQUE DE EVALUACIÓN ANUAL (solo si se pasa --eval)
        # ================================================================
        if args.eval:
            print(f"▶ Ejecutando evaluacion anual para {args.var} {stat}...")

            # Buscar todos los CSV anuales generados
            csv_pattern = os.path.join(
                out_maps_dir, f"{args.var}_{stat}_anual*cmp_estaciones*.csv"
            )
            csv_files = sorted(glob.glob(csv_pattern))

            if not csv_files:
                print("⚠️ No se encontraron CSV para evaluacion, se omite.")
            else:
                base_eval_dir = os.path.join(args.out, args.var, "eval", "annual", stat)
                global_dir = os.path.join(base_eval_dir, "global")
                by_year_dir = os.path.join(base_eval_dir, "by_year")

                os.makedirs(global_dir, exist_ok=True)
                os.makedirs(by_year_dir, exist_ok=True)

                # ------------------------------------------------
                # CSV GLOBAL por estación (promedio temporal)
                # ------------------------------------------------
                global_csv = os.path.join(
                    global_dir, f"global_cmp_estaciones_{args.var}_{stat}.csv"
                )
                build_global_station_csv(csv_files, global_csv)

                # ------------------------------------------------
                # Mapa ΔGRID GLOBAL en estaciones
                # ------------------------------------------------
                out_map_global = os.path.join(
                    global_dir, f"delta_grid_stations_{args.var}_{stat}_GLOBAL.png"
                )

                df_cmp = pd.read_csv(global_csv)

                obs_col = f"{args.var}_{stat}_obs"

                rows_res = []
                for (sid, lat, lon), g in df_cmp.groupby(["station_id", "lat", "lon"]):
                    obs = g[obs_col].astype(float).values
                    corr = g["grid_corr"].astype(float).values

                    m = np.isfinite(obs) & np.isfinite(corr)
                    if not np.any(m):
                        continue

                    obs = obs[m]
                    corr = corr[m]

                    residual_series = corr - obs

                    if stat == "mean":
                        residual_stat = np.nanmean(residual_series)
                    elif stat == "max":
                        residual_stat = np.nanmax(residual_series)
                    elif stat == "min":
                        residual_stat = np.nanmin(residual_series)
                    else:
                        raise ValueError("stat debe ser 'mean', 'max' o 'min'")

                    rows_res.append(
                        {
                            "station_id": sid,
                            "lat": lat,
                            "lon": lon,
                            "residual_corr": residual_stat,
                        }
                    )

                df_res_global = pd.DataFrame(rows_res)

                rows_dg = []
                for (sid, lat, lon), g in df_cmp.groupby(["station_id", "lat", "lon"]):
                    raw = g["grid_raw"].astype(float).values
                    corr = g["grid_corr"].astype(float).values

                    m = np.isfinite(raw) & np.isfinite(corr)
                    if not np.any(m):
                        continue

                    diff = corr[m] - raw[m]

                    if stat == "mean":
                        delta_stat = np.nanmean(diff)
                    elif stat == "max":
                        delta_stat = np.nanmax(diff)
                    elif stat == "min":
                        delta_stat = np.nanmin(diff)

                    rows_dg.append({"lat": lat, "lon": lon, "delta_grid": delta_stat})

                stations_delta_df = pd.DataFrame(rows_dg)

                plot_delta_grid_at_stations(
                    stations_df=stations_delta_df,
                    dem=dem,
                    out_png=out_map_global,
                    title=f"{args.var.upper()} {stat} — Diferencia espacial - CHIRTS (Corregido − Original) en estaciones — GLOBAL",
                    extent=extent_plot,
                )
                print(f"✓ Mapa ΔGRID estaciones GLOBAL: {out_map_global}")

                # ------------------------------------------------
                # CSV de mejora GLOBAL por estación (RMSE)
                # ------------------------------------------------
                global_improve_csv = os.path.join(
                    global_dir, f"improvement_stations_{args.var}_{stat}_RMSE.csv"
                )
                build_station_improvement_csv(
                    csv_files, args.var, stat, global_improve_csv, metric="rmse"
                )

                # ------------------------------------------------
                # Mapa ΔRMSE GLOBAL en estaciones
                # ------------------------------------------------
                out_map_imp_global = os.path.join(
                    global_dir,
                    f"improvement_RMSEpct_stations_{args.var}_{stat}_GLOBAL.png",
                )
                df_imp = pd.read_csv(global_improve_csv)

                # Boxplot RMSE raw vs corr (global)
                out_box_rmse = os.path.join(
                    global_dir,
                    f"boxplot_RMSE_stations_{args.var}_{stat}_GLOBAL.png",
                )
                plot_boxplot_rmse_by_station(
                    df_imp, args.var, stat, "GLOBAL", out_box_rmse
                )

                # Boxplot mejora %
                out_box_imp = os.path.join(
                    global_dir,
                    f"boxplot_improvement_RMSEpct_stations_{args.var}_{stat}_GLOBAL.png",
                )
                plot_boxplot_improvement_pct_by_station(
                    df_imp, args.var, stat, "GLOBAL", out_box_imp
                )

                # Scatter RMSE raw vs corr
                out_sc_rmse = os.path.join(
                    global_dir,
                    f"scatter_RMSE_raw_vs_corr_{args.var}_{stat}_GLOBAL.png",
                )
                plot_scatter_rmse_raw_vs_corr(
                    df_imp, args.var, stat, "GLOBAL", out_sc_rmse
                )

                # Scatter RMSE raw vs improvement %
                out_sc_imp = os.path.join(
                    global_dir,
                    f"scatter_RMSE_raw_vs_improvement_{args.var}_{stat}_GLOBAL.png",
                )
                plot_scatter_rmse_vs_improvement(
                    df_imp, args.var, stat, "GLOBAL", out_sc_imp
                )

                stations_df = pd.DataFrame(
                    {
                        "lat": df_imp["lat"],
                        "lon": df_imp["lon"],
                        "improvement_RMSE_pct": df_imp["improvement_RMSE_pct"],
                    }
                )

                plot_improvement_at_stations_with_dem(
                    stations_df=stations_df,
                    dem=dem,
                    out_png=out_map_imp_global,
                    title=f"{args.var.upper()} {stat} — Mejora vs estaciones (ΔRMSE) — GLOBAL",
                    extent=extent_plot,
                )
                print(f"✓ Mapa ΔRMSE estaciones GLOBAL: {out_map_imp_global}")

                # ------------------------------------------------
                # Métricas anuales globales (Bias, MAE, RMSE, R, etc.)
                # ------------------------------------------------
                df_metrics, metrics_csv = compute_annual_metrics_from_csv(
                    csv_files=csv_files,
                    var=args.var,
                    stat=stat,
                    out_dir=global_dir,
                )
                print(f"✓ Tabla de metricas guardada: {metrics_csv}")

                # Gráfico de RMSE anual
                png1 = plot_rmse_bars(df_metrics, args.var, stat, global_dir)
                print(f"✓ Grafico RMSE: {png1}")

                # Boxplot global de errores
                png2 = plot_boxplot_errors(csv_files, args.var, stat, global_dir)
                if png2:
                    print(f"✓ Boxplot global: {png2}")

                # Scatter OBS vs GRID global
                png3 = plot_scatter_obs_vs_grid(csv_files, args.var, stat, global_dir)
                if png3:
                    print(f"✓ Scatter global: {png3}")

                # ------------------------------------------------
                # Ranking GLOBAL por estación
                # ------------------------------------------------
                df_rank_global = compute_station_metrics_global(
                    csv_files, args.var, stat
                )
                rank_global_csv = os.path.join(
                    global_dir, f"ranking_stations_global_{args.var}_{stat}.csv"
                )
                df_rank_global.to_csv(rank_global_csv, index=False, float_format="%.4f")
                print(f"✓ Ranking global por estación: {rank_global_csv}")

                # ------------------------------------------------
                # Productos POR AÑO
                # ------------------------------------------------
                for csv in csv_files:
                    base = os.path.basename(csv)
                    m = re.search(r"(19|20)\d{2}", base)
                    if not m:
                        raise ValueError(
                            f"No se pudo extraer el año del nombre de archivo: {base}"
                        )
                    year = m.group(0)

                    year_dir = os.path.join(by_year_dir, str(year))
                    os.makedirs(year_dir, exist_ok=True)

                    # Boxplot por año
                    p1 = plot_boxplot_errors_single(csv, args.var, stat, year_dir, year)
                    if p1:
                        print(f"  ✓ Boxplot {year}: {p1}")

                    # Scatter por año
                    p2 = plot_scatter_obs_vs_grid_single(
                        csv, args.var, stat, year_dir, year
                    )
                    if p2:
                        print(f"  ✓ Scatter {year}: {p2}")

                    # Ranking por estación para este año
                    df_rank_year = compute_station_metrics_from_csv(csv, args.var, stat)
                    rank_year_csv = os.path.join(
                        year_dir, f"ranking_stations_{year}.csv"
                    )
                    df_rank_year.to_csv(rank_year_csv, index=False, float_format="%.4f")
                    print(f"  ✓ Ranking estaciones {year}: {rank_year_csv}")

                    # CSV de mejora por estación para este año
                    year_improve_csv = os.path.join(
                        year_dir,
                        f"improvement_stations_{args.var}_{stat}_{year}_RMSE.csv",
                    )
                    build_station_improvement_csv(
                        [csv], args.var, stat, year_improve_csv, metric="rmse"
                    )

                    # Mapa ΔRMSE por año
                    out_map_imp_year = os.path.join(
                        year_dir,
                        f"improvement_RMSEpct_stations_{args.var}_{stat}_{year}.png",
                    )

                    df_imp = pd.read_csv(year_improve_csv)

                    # Boxplot RMSE raw vs corr (por año)
                    out_box_rmse = os.path.join(
                        year_dir,
                        f"boxplot_RMSE_stations_{args.var}_{stat}_{year}.png",
                    )
                    plot_boxplot_rmse_by_station(
                        df_imp, args.var, stat, year, out_box_rmse
                    )

                    # Boxplot mejora %
                    out_box_imp = os.path.join(
                        year_dir,
                        f"boxplot_improvement_RMSEpct_stations_{args.var}_{stat}_{year}.png",
                    )
                    plot_boxplot_improvement_pct_by_station(
                        df_imp, args.var, stat, year, out_box_imp
                    )

                    # Scatter RMSE raw vs corr
                    out_sc_rmse = os.path.join(
                        year_dir,
                        f"scatter_RMSE_raw_vs_corr_{args.var}_{stat}_{year}.png",
                    )
                    plot_scatter_rmse_raw_vs_corr(
                        df_imp, args.var, stat, year, out_sc_rmse
                    )

                    # Scatter RMSE raw vs improvement %
                    out_sc_imp = os.path.join(
                        year_dir,
                        f"scatter_RMSE_raw_vs_improvement_{args.var}_{stat}_{year}.png",
                    )
                    plot_scatter_rmse_vs_improvement(
                        df_imp, args.var, stat, year, out_sc_imp
                    )

                    stations_df = pd.DataFrame(
                        {
                            "lat": df_imp["lat"],
                            "lon": df_imp["lon"],
                            "improvement_RMSE_pct": df_imp["improvement_RMSE_pct"],
                        }
                    )

                    plot_improvement_at_stations_with_dem(
                        stations_df=stations_df,
                        dem=dem,
                        out_png=out_map_imp_year,
                        extent=extent_plot,
                        title=f"{args.var.upper()} {stat} — Mejora vs estaciones (ΔRMSE) — {year}",
                    )
                    print(f"  ✓ Mapa ΔRMSE estaciones {year}: {out_map_imp_year}")

                out_map_resid_global = os.path.join(
                    global_dir,
                    f"residual_corr_stations_{args.var}_{stat}_GLOBAL.png",
                )
                plot_residual_corr_at_stations_with_dem(
                    stations_df=df_res_global,
                    dem=dem,
                    out_png=out_map_resid_global,
                    title=f"{args.var.upper()} {stat} — Residuo (Corr − Obs) en estaciones — GLOBAL",
                    extent=extent_plot,
                )

                print(f"✓ Mapa residuo estaciones GLOBAL: {out_map_resid_global}")


# ------------------------- Evaluación estadística -------------------------


def compute_annual_metrics_from_csv(csv_files, var, stat, out_dir):
    """
    Calcula métricas anuales globales a partir de CSV de comparación por estación.

    Lee una lista de CSV (uno por año), extrae el año desde el nombre del archivo,
    y para cada año calcula métricas globales entre observaciones y CHIRTS
    original y corregido:
      - Bias, MAE, RMSE
      - Correlación (R)
      - Mejoras: Delta_RMSE = RMSE_raw − RMSE_corr, Delta_MAE = MAE_raw − MAE_corr

    El resultado se guarda en un CSV con nombre:
        metrics_annual_<var>_<stat>.csv
    dentro de `out_dir`.

    Parámetros
    ----------
    csv_files : list of str
        Lista de rutas a archivos CSV de comparación por estación (uno por año).
        El año se extrae del nombre del archivo (ej. 1995, 2001, etc.).
    var : str
        Variable base (ej. 'tmax' o 'tmin').
    stat : str
        Estadístico asociado (ej. 'mean', 'max', 'min').
    out_dir : str
        Directorio donde se guardará el CSV de métricas anuales.

    Retorna
    -------
    tuple
        (df_metrics, out_csv) donde:
        - df_metrics es un pandas.DataFrame con las métricas por año.
        - out_csv es la ruta del archivo CSV generado.
    """
    rows = []

    for csv in csv_files:
        base = os.path.basename(csv)

        m = re.search(r"(19|20)\d{2}", base)
        if not m:
            raise ValueError(f"No se pudo extraer el año del nombre de archivo: {base}")

        year = int(m.group(0))

        df = pd.read_csv(csv)

        obs_col = f"{var}_{stat}_obs"
        obs = df[obs_col].values
        raw = df["grid_raw"].values
        corr = df["grid_corr"].values

        err_raw = raw - obs
        err_corr = corr - obs

        bias_raw = np.nanmean(err_raw)
        bias_corr = np.nanmean(err_corr)

        mae_raw = np.nanmean(np.abs(err_raw))
        mae_corr = np.nanmean(np.abs(err_corr))

        rmse_raw = np.sqrt(np.nanmean(err_raw**2))
        rmse_corr = np.sqrt(np.nanmean(err_corr**2))

        try:
            r_raw = np.corrcoef(obs, raw)[0, 1]
        except Exception:
            r_raw = np.nan

        try:
            r_corr = np.corrcoef(obs, corr)[0, 1]
        except Exception:
            r_corr = np.nan

        rows.append(
            {
                "year": year,
                "Bias_raw": bias_raw,
                "Bias_corr": bias_corr,
                "MAE_raw": mae_raw,
                "MAE_corr": mae_corr,
                "RMSE_raw": rmse_raw,
                "RMSE_corr": rmse_corr,
                "R_raw": r_raw,
                "R_corr": r_corr,
                "Delta_RMSE": rmse_raw - rmse_corr,
                "Delta_MAE": mae_raw - mae_corr,
            }
        )

    df_metrics = pd.DataFrame(rows).sort_values("year")

    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, f"metrics_annual_{var}_{stat}.csv")
    df_metrics.to_csv(out_csv, index=False, float_format="%.4f")

    return df_metrics, out_csv


def plot_rmse_bars(df_metrics, var, stat, out_dir):
    """
    Genera un gráfico de líneas del RMSE anual para CHIRTS original y corregido.

    A partir de un DataFrame con métricas por año, dibuja dos curvas:
    - RMSE_raw: CHIRTS original
    - RMSE_corr: CHIRTS corregido

    El gráfico se guarda como PNG en `out_dir` con un nombre basado en la
    variable y el estadístico.

    Parámetros
    ----------
    df_metrics : pandas.DataFrame
        DataFrame con columnas que incluyen: year, RMSE_raw, RMSE_corr.
    var : str
        Variable base (ej. 'tmax' o 'tmin').
    stat : str
        Estadístico asociado (ej. 'mean', 'max', 'min').
    out_dir : str
        Directorio donde se guardará la figura PNG.

    Retorna
    -------
    str
        Ruta del archivo PNG generado.
    """
    years = df_metrics["year"].values

    plt.figure(figsize=(10, 5), dpi=150)
    plt.plot(years, df_metrics["RMSE_raw"], marker="o", label="RMSE CHIRTS Original")
    plt.plot(years, df_metrics["RMSE_corr"], marker="o", label="RMSE CHIRTS Corregido")

    plt.xlabel("Año")
    plt.ylabel("RMSE (°C)")
    plt.title(
        f"{var.upper()} {stat} — RMSE anual (CHIRTS Original vs CHIRTS Corregido)"
    )
    plt.legend()
    plt.grid(True, alpha=0.3)

    out_png = os.path.join(out_dir, f"rmse_annual_{var}_{stat}.png")
    plt.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close()

    return out_png


def plot_boxplot_errors(csv_files, var, stat, out_dir):
    """
    Genera un boxplot global del error absoluto en estaciones para CHIRTS original y corregido.

    Lee múltiples CSV de comparación por estación, acumula los errores absolutos
    |grid_raw − obs| y |grid_corr − obs|, y construye un boxplot comparativo
    (original vs corregido). Además:
      - Superpone puntos individuales con jitter horizontal.
      - Anota MAE, RMSE y tamaño de muestra (n) para cada caso.
      - Muestra la diferencia de RMSE (ΔRMSE) y conecta las medianas con una línea.

    El gráfico se guarda como PNG en `out_dir` con un nombre basado en la variable
    y el estadístico.

    Parámetros
    ----------
    csv_files : list of str
        Lista de rutas a archivos CSV de comparación por estación y fecha.
    var : str
        Variable base (ej. 'tmax' o 'tmin').
    stat : str
        Estadístico asociado (ej. 'mean', 'max', 'min').
    out_dir : str
        Directorio donde se guardará la figura PNG.

    Retorna
    -------
    str or None
        Ruta del archivo PNG generado, o None si no hay datos válidos para graficar.
    """
    all_err_raw = []
    all_err_corr = []

    for csv in csv_files:
        df = pd.read_csv(csv)
        obs = df[f"{var}_{stat}_obs"].values.astype(float)
        raw = df["grid_raw"].values.astype(float)
        corr = df["grid_corr"].values.astype(float)

        err_raw = np.abs(raw - obs)
        err_corr = np.abs(corr - obs)

        err_raw = err_raw[np.isfinite(err_raw)]
        err_corr = err_corr[np.isfinite(err_corr)]

        all_err_raw.extend(err_raw.tolist())
        all_err_corr.extend(err_corr.tolist())

    if len(all_err_raw) == 0 or len(all_err_corr) == 0:
        print("⚠️ Boxplot global: no hay datos válidos.")
        return None

    all_err_raw = np.array(all_err_raw)
    all_err_corr = np.array(all_err_corr)

    fill_raw = "#c7dcef"
    edge_raw = "#3b73b9"
    fill_corr = "#cfeee6"
    edge_corr = "#2a8c7a"

    fig, ax = plt.subplots(figsize=(7.5, 5.2), dpi=160)

    bp = ax.boxplot(
        [all_err_raw, all_err_corr],
        positions=[1, 2],
        widths=0.18,
        patch_artist=True,
        showfliers=True,
    )

    boxes = bp["boxes"]
    medians = bp["medians"]
    whiskers = bp["whiskers"]
    caps = bp["caps"]
    fliers = bp["fliers"]

    for box, fill, edge in zip(boxes, [fill_raw, fill_corr], [edge_raw, edge_corr]):
        box.set(facecolor=fill, edgecolor=edge, linewidth=1.3, alpha=0.95)

    for i, edge in enumerate([edge_raw, edge_corr]):
        whiskers[2 * i].set(color=edge, linewidth=1.1)
        whiskers[2 * i + 1].set(color=edge, linewidth=1.1)
        caps[2 * i].set(color=edge, linewidth=1.0)
        caps[2 * i + 1].set(color=edge, linewidth=1.0)

    medians[0].set(color=edge_raw, linewidth=2.2)
    medians[1].set(color=edge_corr, linewidth=2.2)

    for flier, edge in zip(fliers, [edge_raw, edge_corr]):
        flier.set(
            marker="o",
            markerfacecolor="none",
            markeredgecolor=edge,
            markersize=5,
            linestyle="none",
            markeredgewidth=0.9,
        )

    x_raw = np.random.normal(0.78, 0.025, size=len(all_err_raw))
    x_corr = np.random.normal(1.78, 0.025, size=len(all_err_corr))

    ax.scatter(
        x_raw,
        all_err_raw,
        facecolors="none",
        edgecolors=edge_raw,
        s=26,
        linewidths=0.9,
        alpha=0.9,
        zorder=3,
    )
    ax.scatter(
        x_corr,
        all_err_corr,
        facecolors="none",
        edgecolors=edge_corr,
        s=26,
        linewidths=0.9,
        alpha=0.9,
        zorder=3,
    )

    ax.set_xticks([1, 2])
    ax.set_xticklabels(["CHIRTS Original", "CHIRTS Corregido"], fontsize=11)
    ax.set_ylabel("|Error| (°C)", fontsize=11)
    ax.set_title(
        f"{var.upper()} {stat} — Error absoluto en estaciones (Global)",
        fontsize=13,
        fontweight="bold",
    )
    ax.grid(True, axis="y", alpha=0.25)

    mae_o = np.mean(all_err_raw)
    rmse_o = np.sqrt(np.mean(all_err_raw**2))
    n_o = len(all_err_raw)

    mae_c = np.mean(all_err_corr)
    rmse_c = np.sqrt(np.mean(all_err_corr**2))
    n_c = len(all_err_corr)

    delta_rmse = rmse_o - rmse_c

    ymax = max(all_err_raw.max(), all_err_corr.max())
    ax.set_ylim(0, ymax * 1.38)

    ax.text(
        1,
        ymax * 1.08,
        f"MAE={mae_o:.2f}\nRMSE={rmse_o:.2f}\nn={n_o}",
        ha="center",
        va="bottom",
        fontsize=9,
    )
    ax.text(
        2,
        ymax * 1.08,
        f"MAE={mae_c:.2f}\nRMSE={rmse_c:.2f}\nn={n_c}",
        ha="center",
        va="bottom",
        fontsize=9,
    )
    ax.text(
        1.5,
        ymax * 1.22,
        f"ΔRMSE = {delta_rmse:.2f} °C",
        ha="center",
        va="bottom",
        fontsize=10,
        fontweight="bold",
    )

    med_o = np.median(all_err_raw)
    med_c = np.median(all_err_corr)
    ax.plot(
        [1, 2], [med_o, med_c], linestyle="--", color="gray", linewidth=1.2, zorder=5
    )

    ax.text(
        1.12,
        med_o,
        f"Med = {med_o:.2f}",
        color=edge_raw,
        fontsize=9,
        va="center",
        ha="left",
    )
    ax.text(
        2.12,
        med_c,
        f"Med = {med_c:.2f}",
        color=edge_corr,
        fontsize=9,
        va="center",
        ha="left",
    )

    plt.tight_layout()

    out_png = os.path.join(out_dir, f"boxplot_error_global_{var}_{stat}.png")
    plt.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close()

    return out_png


def plot_boxplot_errors_single(csv_file, var, stat, out_dir, year):
    """
    Genera un boxplot del error absoluto en estaciones para un año específico.

    Lee un CSV de comparación por estación, calcula los errores absolutos
    |grid_raw − obs| y |grid_corr − obs| y construye un boxplot comparativo
    (CHIRTS original vs corregido). Además:
      - Superpone puntos individuales con jitter horizontal.
      - Anota MAE, RMSE y tamaño de muestra (n) para cada caso.
      - Muestra la diferencia de RMSE (ΔRMSE) y conecta las medianas con una línea.
      - Añade etiquetas con el valor de las medianas fuera de cada caja.

    El gráfico se guarda como PNG en `out_dir` con un nombre que incluye el año.

    Parámetros
    ----------
    csv_file : str
        Ruta al archivo CSV de comparación por estación para un año.
    var : str
        Variable base (ej. 'tmax' o 'tmin').
    stat : str
        Estadístico asociado (ej. 'mean', 'max', 'min').
    out_dir : str
        Directorio donde se guardará la figura PNG.
    year : int or str
        Año que se mostrará en el título y en el nombre del archivo de salida.

    Retorna
    -------
    str or None
        Ruta del archivo PNG generado, o None si no hay datos válidos para graficar.
    """
    df = pd.read_csv(csv_file)

    obs = df[f"{var}_{stat}_obs"].values.astype(float)
    raw = df["grid_raw"].values.astype(float)
    corr = df["grid_corr"].values.astype(float)

    err_raw = np.abs(raw - obs)
    err_corr = np.abs(corr - obs)

    err_raw = err_raw[np.isfinite(err_raw)]
    err_corr = err_corr[np.isfinite(err_corr)]

    if len(err_raw) == 0 or len(err_corr) == 0:
        print(f"⚠️ Boxplot {year}: no hay datos válidos.")
        return None

    fill_raw = "#c7dcef"
    edge_raw = "#3b73b9"
    fill_corr = "#cfeee6"
    edge_corr = "#2a8c7a"

    fig, ax = plt.subplots(figsize=(7.5, 5.2), dpi=160)

    bp = ax.boxplot(
        [err_raw, err_corr],
        positions=[1, 2],
        widths=0.18,
        patch_artist=True,
        showfliers=True,
    )

    boxes = bp["boxes"]
    medians = bp["medians"]
    whiskers = bp["whiskers"]
    caps = bp["caps"]
    fliers = bp["fliers"]

    for box, fill, edge in zip(boxes, [fill_raw, fill_corr], [edge_raw, edge_corr]):
        box.set(facecolor=fill, edgecolor=edge, linewidth=1.3, alpha=0.95)

    for i, edge in enumerate([edge_raw, edge_corr]):
        whiskers[2 * i].set(color=edge, linewidth=1.1)
        whiskers[2 * i + 1].set(color=edge, linewidth=1.1)
        caps[2 * i].set(color=edge, linewidth=1.0)
        caps[2 * i + 1].set(color=edge, linewidth=1.0)

    medians[0].set(color=edge_raw, linewidth=2.2)
    medians[1].set(color=edge_corr, linewidth=2.2)

    for flier, edge in zip(fliers, [edge_raw, edge_corr]):
        flier.set(
            marker="o",
            markerfacecolor="none",
            markeredgecolor=edge,
            markersize=5,
            linestyle="none",
            markeredgewidth=0.9,
        )

    x_raw = np.random.normal(0.78, 0.025, size=len(err_raw))
    x_corr = np.random.normal(1.78, 0.025, size=len(err_corr))

    ax.scatter(
        x_raw,
        err_raw,
        facecolors="none",
        edgecolors=edge_raw,
        s=26,
        linewidths=0.9,
        alpha=0.9,
        zorder=3,
    )
    ax.scatter(
        x_corr,
        err_corr,
        facecolors="none",
        edgecolors=edge_corr,
        s=26,
        linewidths=0.9,
        alpha=0.9,
        zorder=3,
    )

    ax.set_xticks([1, 2])
    ax.set_xticklabels(["CHIRTS Original", "CHIRTS Corregido"], fontsize=11)
    ax.set_ylabel("|Error| (°C)", fontsize=11)
    ax.set_title(
        f"{var.upper()} {stat} — Error absoluto en estaciones — {year}",
        fontsize=13,
        fontweight="bold",
    )
    ax.grid(True, axis="y", alpha=0.25)

    mae_o = np.mean(err_raw)
    rmse_o = np.sqrt(np.mean(err_raw**2))
    n_o = len(err_raw)

    mae_c = np.mean(err_corr)
    rmse_c = np.sqrt(np.mean(err_corr**2))
    n_c = len(err_corr)

    delta_rmse = rmse_o - rmse_c

    ymax = max(err_raw.max(), err_corr.max())
    ax.set_ylim(0, ymax * 1.38)

    ax.text(
        1,
        ymax * 1.08,
        f"MAE={mae_o:.2f}\nRMSE={rmse_o:.2f}\nn={n_o}",
        ha="center",
        va="bottom",
        fontsize=9,
    )
    ax.text(
        2,
        ymax * 1.08,
        f"MAE={mae_c:.2f}\nRMSE={rmse_c:.2f}\nn={n_c}",
        ha="center",
        va="bottom",
        fontsize=9,
    )
    ax.text(
        1.5,
        ymax * 1.22,
        f"ΔRMSE = {delta_rmse:.2f} °C",
        ha="center",
        va="bottom",
        fontsize=10,
        fontweight="bold",
    )

    med_o = np.median(err_raw)
    med_c = np.median(err_corr)
    ax.plot(
        [1, 2], [med_o, med_c], linestyle="--", color="gray", linewidth=1.2, zorder=5
    )

    ax.text(
        1.12,
        med_o,
        f"Med = {med_o:.2f}",
        color=edge_raw,
        fontsize=9,
        va="center",
        ha="left",
    )
    ax.text(
        2.12,
        med_c,
        f"Med = {med_c:.2f}",
        color=edge_corr,
        fontsize=9,
        va="center",
        ha="left",
    )

    plt.tight_layout()

    out_png = os.path.join(out_dir, f"boxplot_error_{year}.png")
    plt.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close()

    return out_png


def plot_scatter_obs_vs_grid(csv_files, var, stat, out_dir):
    """
    Genera gráficos de dispersión OBS vs REJILLA para CHIRTS original y corregido (global).

    Lee múltiples CSV de comparación por estación y fecha, concatena todos los datos
    y construye dos paneles:
      - Panel izquierdo: Observado vs CHIRTS Original
      - Panel derecho: Observado vs CHIRTS Corregido

    Cada punto se colorea por estación, se incluye la línea 1:1 y se calcula el
    coeficiente de correlación de Pearson (R) para cada caso. El resultado muestra
    el comportamiento global considerando todas las estaciones y todos los años.

    El gráfico se guarda como PNG en `out_dir` con un nombre basado en la variable
    y el estadístico.

    Parámetros
    ----------
    csv_files : list of str
        Lista de rutas a archivos CSV de comparación por estación (posiblemente de
        múltiples años o periodos).
    var : str
        Variable base (ej. 'tmax' o 'tmin').
    stat : str
        Estadístico asociado (ej. 'mean', 'max', 'min').
    out_dir : str
        Directorio donde se guardará la figura PNG.

    Retorna
    -------
    str or None
        Ruta del archivo PNG generado, o None si no hay datos suficientes para graficar.
    """
    # Leer todos los CSV y concatenar
    dfs = []
    for csv in csv_files:
        df = pd.read_csv(csv)
        dfs.append(df)
    df_all = pd.concat(dfs, ignore_index=True)

    obs = df_all[f"{var}_{stat}_obs"].values.astype(float)
    raw = df_all["grid_raw"].values.astype(float)
    corr = df_all["grid_corr"].values.astype(float)
    stations = df_all["station_id"].astype(str).values

    mask_raw = np.isfinite(obs) & np.isfinite(raw)
    mask_corr = np.isfinite(obs) & np.isfinite(corr)

    obs_r, raw_r, st_r = obs[mask_raw], raw[mask_raw], stations[mask_raw]
    obs_c, corr_c, st_c = obs[mask_corr], corr[mask_corr], stations[mask_corr]

    if len(obs_r) < 2 or len(obs_c) < 2:
        print("⚠️ Scatter global: no hay datos suficientes.")
        return None

    r_raw = np.corrcoef(obs_r, raw_r)[0, 1]
    r_corr = np.corrcoef(obs_c, corr_c)[0, 1]

    unique_stations = sorted(set(stations))
    cmaps = [plt.get_cmap("tab20"), plt.get_cmap("tab20b"), plt.get_cmap("tab20c")]
    palette = []
    for cm in cmaps:
        palette.extend([cm(i) for i in range(cm.N)])

    colors = {st: palette[i % len(palette)] for i, st in enumerate(unique_stations)}

    vmin = np.nanmin(np.concatenate([obs_r, obs_c]))
    vmax = np.nanmax(np.concatenate([obs_r, obs_c]))

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=160, sharex=True, sharey=True)

    for st in unique_stations:
        m = st_r == st
        axes[0].scatter(obs_r[m], raw_r[m], s=30, alpha=0.8, color=colors[st], label=st)

    axes[0].plot([vmin, vmax], [vmin, vmax], "--", color="gray", linewidth=1)
    axes[0].set_title(
        f"CHIRTS Original (R = {r_raw:.2f})", fontsize=11, fontweight="bold"
    )
    axes[0].set_xlabel("Observado (°C)", fontsize=10)
    axes[0].set_ylabel("Rejilla (°C)", fontsize=10)
    axes[0].grid(True, alpha=0.3)

    for st in unique_stations:
        m = st_c == st
        axes[1].scatter(
            obs_c[m], corr_c[m], s=30, alpha=0.8, color=colors[st], label=st
        )

    axes[1].plot([vmin, vmax], [vmin, vmax], "--", color="gray", linewidth=1)
    axes[1].set_title(
        f"CHIRTS Corregido (R = {r_corr:.2f})", fontsize=11, fontweight="bold"
    )
    axes[1].set_xlabel("Observado (°C)", fontsize=10)
    axes[1].grid(True, alpha=0.3)

    fig.suptitle(
        f"{var.upper()} {stat} — OBS vs REJILLA (Global, todas las estaciones y años)",
        fontsize=13,
        fontweight="bold",
    )

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="center right",
        title="Estaciones",
        fontsize=8,
        title_fontsize=9,
        frameon=True,
    )

    plt.tight_layout(rect=[0, 0, 0.82, 0.95])

    out_png = os.path.join(out_dir, f"scatter_obs_vs_grid_global_{var}_{stat}.png")
    plt.savefig(out_png, dpi=200)
    plt.close()

    return out_png


def plot_scatter_obs_vs_grid_single(csv_file, var, stat, out_dir, year):
    """
    Genera gráficos de dispersión OBS vs REJILLA para un año específico.

    Lee un CSV de comparación por estación correspondiente a un año, y construye
    dos paneles:
      - Panel izquierdo: Observado vs CHIRTS Original
      - Panel derecho: Observado vs CHIRTS Corregido

    Cada punto se colorea por estación, se incluye la línea 1:1 y se calcula el
    coeficiente de correlación de Pearson (R) para cada caso. El gráfico resume
    el comportamiento de ese año en todas las estaciones disponibles.

    El resultado se guarda como PNG en `out_dir` con un nombre que incluye el año.

    Parámetros
    ----------
    csv_file : str
        Ruta al archivo CSV de comparación por estación para un año.
    var : str
        Variable base (ej. 'tmax' o 'tmin').
    stat : str
        Estadístico asociado (ej. 'mean', 'max', 'min').
    out_dir : str
        Directorio donde se guardará la figura PNG.
    year : int or str
        Año que se mostrará en el título y en el nombre del archivo de salida.

    Retorna
    -------
    str or None
        Ruta del archivo PNG generado, o None si no hay datos suficientes para graficar.
    """
    df = pd.read_csv(csv_file)

    obs = df[f"{var}_{stat}_obs"].values.astype(float)
    raw = df["grid_raw"].values.astype(float)
    corr = df["grid_corr"].values.astype(float)
    stations = df["station_id"].astype(str).values

    mask_raw = np.isfinite(obs) & np.isfinite(raw)
    mask_corr = np.isfinite(obs) & np.isfinite(corr)

    obs_r, raw_r, st_r = obs[mask_raw], raw[mask_raw], stations[mask_raw]
    obs_c, corr_c, st_c = obs[mask_corr], corr[mask_corr], stations[mask_corr]

    if len(obs_r) < 2 or len(obs_c) < 2:
        print(f"⚠️ Scatter {year}: no hay datos suficientes.")
        return None

    r_raw = np.corrcoef(obs_r, raw_r)[0, 1]
    r_corr = np.corrcoef(obs_c, corr_c)[0, 1]

    unique_stations = sorted(set(stations))
    cmaps = [plt.get_cmap("tab20"), plt.get_cmap("tab20b"), plt.get_cmap("tab20c")]
    palette = []
    for cm in cmaps:
        palette.extend([cm(i) for i in range(cm.N)])

    colors = {st: palette[i % len(palette)] for i, st in enumerate(unique_stations)}

    vmin = np.nanmin(np.concatenate([obs_r, obs_c]))
    vmax = np.nanmax(np.concatenate([obs_r, obs_c]))

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=160, sharex=True, sharey=True)

    for st in unique_stations:
        m = st_r == st
        axes[0].scatter(
            obs_r[m], raw_r[m], s=35, alpha=0.85, color=colors[st], label=st
        )

    axes[0].plot([vmin, vmax], [vmin, vmax], "--", color="gray", linewidth=1)
    axes[0].set_title(
        f"CHIRTS Original (R = {r_raw:.2f})", fontsize=11, fontweight="bold"
    )
    axes[0].set_xlabel("Observado (°C)", fontsize=10)
    axes[0].set_ylabel("Rejilla (°C)", fontsize=10)
    axes[0].grid(True, alpha=0.3)

    for st in unique_stations:
        m = st_c == st
        axes[1].scatter(
            obs_c[m], corr_c[m], s=35, alpha=0.85, color=colors[st], label=st
        )

    axes[1].plot([vmin, vmax], [vmin, vmax], "--", color="gray", linewidth=1)
    axes[1].set_title(
        f"CHIRTS Corregido (R = {r_corr:.2f})", fontsize=11, fontweight="bold"
    )
    axes[1].set_xlabel("Observado (°C)", fontsize=10)
    axes[1].grid(True, alpha=0.3)

    fig.suptitle(
        f"{var.upper()} {stat} — OBS vs REJILLA — {year}",
        fontsize=13,
        fontweight="bold",
    )

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="center right",
        title="Estaciones",
        fontsize=8,
        title_fontsize=9,
        frameon=True,
    )

    plt.tight_layout(rect=[0, 0, 0.82, 0.95])

    out_png = os.path.join(out_dir, f"scatter_obs_vs_grid_{year}.png")
    plt.savefig(out_png, dpi=200)
    plt.close()

    return out_png


def compute_station_metrics_from_csv(csv_file, var, stat):
    """
    Calcula métricas de desempeño por estación a partir de un CSV de comparación.

    Lee un archivo CSV que contiene, por estación y fecha, las columnas:
    - observación: <var>_<stat>_obs
    - rejilla original: grid_raw
    - rejilla corregida: grid_corr

    Para cada estación calcula:
      - Bias, MAE y RMSE para CHIRTS original y corregido
      - Mejoras: Delta_MAE = MAE_raw − MAE_corr, Delta_RMSE = RMSE_raw − RMSE_corr
      - n: número de pares válidos (obs, grid) usados en el cálculo

    Las estaciones con datos insuficientes se omiten. El resultado se ordena
    por mayor mejora en RMSE (Delta_RMSE descendente).

    Parámetros
    ----------
    csv_file : str
        Ruta al archivo CSV de comparación por estación (puede contener múltiples fechas).
    var : str
        Variable base (ej. 'tmax' o 'tmin').
    stat : str
        Estadístico asociado (ej. 'mean', 'max', 'min').

    Retorna
    -------
    pandas.DataFrame
        DataFrame con una fila por estación y las columnas:
        station_id, n, Bias_raw, Bias_corr, MAE_raw, MAE_corr,
        RMSE_raw, RMSE_corr, Delta_MAE, Delta_RMSE,
        ordenado por Delta_RMSE de mayor a menor.
    """
    df = pd.read_csv(csv_file)

    obs = df[f"{var}_{stat}_obs"].values.astype(float)
    raw = df["grid_raw"].values.astype(float)
    corr = df["grid_corr"].values.astype(float)
    stations = df["station_id"].astype(str).values

    rows = []

    for st in sorted(set(stations)):
        m = stations == st

        o = obs[m]
        r = raw[m]
        c = corr[m]

        mask_r = np.isfinite(o) & np.isfinite(r)
        mask_c = np.isfinite(o) & np.isfinite(c)

        o_r, r_r = o[mask_r], r[mask_r]
        o_c, c_c = o[mask_c], c[mask_c]

        if len(o_r) < 1 or len(o_c) < 1:
            continue

        err_raw = r_r - o_r
        err_corr = c_c - o_c

        bias_raw = np.nanmean(err_raw)
        bias_corr = np.nanmean(err_corr)

        mae_raw = np.nanmean(np.abs(err_raw))
        mae_corr = np.nanmean(np.abs(err_corr))

        rmse_raw = np.sqrt(np.nanmean(err_raw**2))
        rmse_corr = np.sqrt(np.nanmean(err_corr**2))

        rows.append(
            {
                "station_id": st,
                "n": len(o_r),
                "Bias_raw": bias_raw,
                "Bias_corr": bias_corr,
                "MAE_raw": mae_raw,
                "MAE_corr": mae_corr,
                "RMSE_raw": rmse_raw,
                "RMSE_corr": rmse_corr,
                "Delta_MAE": mae_raw - mae_corr,
                "Delta_RMSE": rmse_raw - rmse_corr,
            }
        )

    df_out = pd.DataFrame(rows)
    df_out = df_out.sort_values("Delta_RMSE", ascending=False)

    return df_out


def compute_station_metrics_global(csv_files, var, stat):
    """
    Calcula métricas de desempeño por estación a nivel global combinando múltiples CSV.

    Lee y concatena una lista de archivos CSV de comparación por estación (posiblemente
    de varios años o periodos) y, para cada estación, calcula métricas entre
    observaciones y CHIRTS original y corregido:
      - Bias, MAE y RMSE para cada caso
      - Mejoras: Delta_MAE = MAE_raw − MAE_corr, Delta_RMSE = RMSE_raw − RMSE_corr
      - n: número de pares válidos usados en el cálculo

    Las estaciones con datos insuficientes se omiten. El resultado se ordena por
    mayor mejora en RMSE (Delta_RMSE descendente).

    Parámetros
    ----------
    csv_files : list of str
        Lista de rutas a archivos CSV de comparación por estación (pueden corresponder
        a distintos años o periodos).
    var : str
        Variable base (ej. 'tmax' o 'tmin').
    stat : str
        Estadístico asociado (ej. 'mean', 'max', 'min').

    Retorna
    -------
    pandas.DataFrame
        DataFrame con una fila por estación y las columnas:
        station_id, n, Bias_raw, Bias_corr, MAE_raw, MAE_corr,
        RMSE_raw, RMSE_corr, Delta_MAE, Delta_RMSE,
        ordenado por Delta_RMSE de mayor a menor.
    """
    dfs = []
    for csv in csv_files:
        dfs.append(pd.read_csv(csv))
    df_all = pd.concat(dfs, ignore_index=True)

    obs = df_all[f"{var}_{stat}_obs"].values.astype(float)
    raw = df_all["grid_raw"].values.astype(float)
    corr = df_all["grid_corr"].values.astype(float)
    stations = df_all["station_id"].astype(str).values

    rows = []

    for st in sorted(set(stations)):
        m = stations == st

        o = obs[m]
        r = raw[m]
        c = corr[m]

        mask_r = np.isfinite(o) & np.isfinite(r)
        mask_c = np.isfinite(o) & np.isfinite(c)

        o_r, r_r = o[mask_r], r[mask_r]
        o_c, c_c = o[mask_c], c[mask_c]

        if len(o_r) < 1 or len(o_c) < 1:
            continue

        err_raw = r_r - o_r
        err_corr = c_c - o_c

        bias_raw = np.nanmean(err_raw)
        bias_corr = np.nanmean(err_corr)

        mae_raw = np.nanmean(np.abs(err_raw))
        mae_corr = np.nanmean(np.abs(err_corr))

        rmse_raw = np.sqrt(np.nanmean(err_raw**2))
        rmse_corr = np.sqrt(np.nanmean(err_corr**2))

        rows.append(
            {
                "station_id": st,
                "n": len(o_r),
                "Bias_raw": bias_raw,
                "Bias_corr": bias_corr,
                "MAE_raw": mae_raw,
                "MAE_corr": mae_corr,
                "RMSE_raw": rmse_raw,
                "RMSE_corr": rmse_corr,
                "Delta_MAE": mae_raw - mae_corr,
                "Delta_RMSE": rmse_raw - rmse_corr,
            }
        )

    df_out = pd.DataFrame(rows).sort_values("Delta_RMSE", ascending=False)
    return df_out


if __name__ == "__main__":
    main()
