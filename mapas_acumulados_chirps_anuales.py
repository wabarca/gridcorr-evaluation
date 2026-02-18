# -*- coding: utf-8 -*-
"""
Mapas de acumulados anuales: CHIRPS vs CHIRPS corregido (lado a lado) con
puntos de estaciones (VALORES OBSERVADOS desde el CSV) y escala de colores global.

- Escala discreta fija 0–2000 mm (10/20 intervalos).
- Salida: guarda las figuras en <out>/mapas_anuales/acumulado_anual_YYYY.png
"""

import os
import re
import glob
import argparse
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm

os.environ["CARTOPY_DATA_DIR"] = os.path.join(os.path.dirname(__file__), "cartopy_data")
import cartopy.crs as ccrs
import cartopy.feature as cfeature

try:
    from adjustText import adjust_text
except ImportError:
    adjust_text = None


# ------------------------- Lectura CSV CDT -------------------------


def parse_cdt_csv(csv_path: str):
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
                    # 👇 nuevo: faltantes en CSV
                    if v == -99:
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
        id_vars="date", var_name="station_id", value_name="precip_station"
    )
    df_obs_long = df_obs_long.merge(meta, on="station_id", how="left")
    df_obs_long["year"] = df_obs_long["date"].str.slice(0, 4).astype(int)

    return meta, df_obs_long


# ------------------------- Utilidades NetCDF -------------------------


def _rename_coords_latlon(da: xr.DataArray) -> xr.DataArray:
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


def load_daily_sum_for_year(
    data_dir: str, year: int, pattern_prefix: str, varname: str = "precip"
) -> xr.DataArray:
    glob_pat = os.path.join(data_dir, f"{pattern_prefix}{year}*.nc")
    files = sorted(glob.glob(glob_pat))
    if not files:
        raise FileNotFoundError(f"No se encontraron archivos: {glob_pat}")

    annual_sum = None
    valid_count = None  # contador de días válidos por celda

    for fp in files:
        ds = xr.open_dataset(fp)
        v = (
            varname
            if varname in ds
            else (list(ds.data_vars)[0] if ds.data_vars else None)
        )
        if v is None:
            ds.close()
            continue

        da = _rename_coords_latlon(ds[v])

        # Si tiene time (1), squeeze
        try:
            if "time" in da.coords and getattr(da["time"], "size", 0) == 1:
                da = da.squeeze("time", drop=True)
        except Exception:
            pass

        # Tratar -99 como faltante:
        da = da.where(da != -99)

        # Contador de días válidos (1 si no NaN, 0 si NaN)
        day_valid = xr.where(xr.ufuncs.isnan(da), 0, 1)

        if annual_sum is None:
            annual_sum = da.fillna(0)  # primer día
            valid_count = day_valid
        else:
            # Alinear por si hay pequeñas diferencias de grilla
            annual_sum, da_al = xr.align(annual_sum, da, join="outer")
            valid_count, day_valid_al = xr.align(valid_count, day_valid, join="outer")

            annual_sum = annual_sum.fillna(0) + da_al.fillna(0)
            valid_count = valid_count.fillna(0) + day_valid_al.fillna(0)

        ds.close()

    if annual_sum is None:
        raise RuntimeError(f"No se pudo construir suma anual en {data_dir} ({year}).")

    # Colocar NaN donde N días válidos == 0
    annual_sum = annual_sum.where(valid_count > 0)

    return annual_sum


# ------------------------- Acumulados de estaciones (CSV) -------------------------


def annual_station_accum(df_obs_long: pd.DataFrame, year: int) -> pd.DataFrame:
    sub = df_obs_long[df_obs_long["year"] == year].copy()
    acc = sub.groupby("station_id", as_index=False)["precip_station"].sum(min_count=1)
    acc = acc.rename(columns={"precip_station": "accum_obs"})
    st = sub[["station_id", "lon", "lat", "elev"]].drop_duplicates()
    out = acc.merge(st, on="station_id", how="left")
    return out[["station_id", "lon", "lat", "elev", "accum_obs"]]


# ------------------------- Plotting -------------------------
def _place_text_no_overlap(ax, x, y, text, placed, dx=0.08, dy=0.08, max_tries=10):
    """Fallback simple: desplaza la etiqueta alrededor del punto para evitar solapes."""
    t = ax.text(
        x,
        y,
        text,
        transform=ax.transData,
        fontsize=7,
        ha="left",
        va="bottom",
        color="black",
        bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.6),
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
    year: int,
    stations_obs_year: pd.DataFrame,  # station_id, lon, lat, elev, accum_obs
    out_png: str,
    bins: int = 30,  # 10 o 20
    max_mm: float = 3000.0,  # tope de la escala discreta
    cmap: str = "YlGnBu",
    extent: Optional[Tuple[float, float, float, float]] = None,
):
    # Asegurar coords
    da_left = _rename_coords_latlon(da_left)
    da_right = _rename_coords_latlon(da_right)

    proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(14, 6), dpi=150, constrained_layout=True)

    # Extent desde el grid CHIRPS + 1%
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

    # Escala discreta
    levels = np.linspace(0, max_mm, bins + 1)
    norm = BoundaryNorm(levels, ncolors=plt.get_cmap(cmap).N, clip=False)

    # ----- Panel izquierdo -----
    ax1 = plt.subplot(1, 2, 1, projection=proj)
    ax1.set_title(f"CHIRPSv2 — Acumulado anual {year}", fontsize=10)
    ax1.coastlines(resolution="10m", linewidth=0.6)
    ax1.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.4)
    ax1.add_feature(
        cfeature.LAKES.with_scale("10m"), linewidth=0.2, edgecolor="k", facecolor="none"
    )
    ax1.add_feature(cfeature.RIVERS.with_scale("10m"), linewidth=0.2)
    ax1.set_extent(extent, crs=proj)
    gl1 = ax1.gridlines(
        draw_labels=True, linewidth=0.3, color="gray", alpha=0.5, linestyle="--"
    )
    gl1.right_labels = False
    gl1.top_labels = False

    lonL = da_left["lon"].values
    latL = da_left["lat"].values
    mesh1 = ax1.pcolormesh(
        lonL, latL, da_left.values, transform=proj, cmap=cmap, norm=norm, shading="auto"
    )

    texts_left, pts_left = [], []
    for _, r in stations_obs_year.iterrows():
        (pt,) = ax1.plot(
            r["lon"],
            r["lat"],
            marker="o",
            markersize=3.5,
            markeredgecolor="k",
            markerfacecolor="white",
            transform=proj,
            zorder=5,
        )
        pts_left.append(pt)
        if pd.notna(r["accum_obs"]):
            if adjust_text is None:
                if not hasattr(ax1, "_placed_left"):
                    ax1._placed_left = []
                _place_text_no_overlap(
                    ax1, r["lon"], r["lat"], f"{r['accum_obs']:.0f}", ax1._placed_left
                )
            else:
                t = ax1.text(
                    r["lon"],
                    r["lat"],
                    f"{r['accum_obs']:.0f}",
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

    # ----- Panel derecho -----
    ax2 = plt.subplot(1, 2, 2, projection=proj)
    ax2.set_title(f"CHIRPSv2-Corregido — Acumulado anual {year}", fontsize=10)
    ax2.coastlines(resolution="10m", linewidth=0.6)
    ax2.add_feature(cfeature.BORDERS.with_scale("10m"), linewidth=0.4)
    ax2.add_feature(
        cfeature.LAKES.with_scale("10m"), linewidth=0.2, edgecolor="k", facecolor="none"
    )
    ax2.add_feature(cfeature.RIVERS.with_scale("10m"), linewidth=0.2)
    ax2.set_extent(extent, crs=proj)
    gl2 = ax2.gridlines(
        draw_labels=True, linewidth=0.3, color="gray", alpha=0.5, linestyle="--"
    )
    gl2.right_labels = True
    gl2.top_labels = False
    gl2.left_labels = False

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
    )

    texts_right, pts_right = [], []
    for _, r in stations_obs_year.iterrows():
        (pt,) = ax2.plot(
            r["lon"],
            r["lat"],
            marker="o",
            markersize=3.5,
            markeredgecolor="k",
            markerfacecolor="white",
            transform=proj,
            zorder=5,
        )
        pts_right.append(pt)
        if pd.notna(r["accum_obs"]):
            if adjust_text is None:
                if not hasattr(ax2, "_placed_right"):
                    ax2._placed_right = []
                _place_text_no_overlap(
                    ax2, r["lon"], r["lat"], f"{r['accum_obs']:.0f}", ax2._placed_right
                )
            else:
                t = ax2.text(
                    r["lon"],
                    r["lat"],
                    f"{r['accum_obs']:.0f}",
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

    # Ajuste automático de etiquetas (si hay adjustText)
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

    # Colorbar común, rectangular y discreta
    cbar = fig.colorbar(
        mesh2,
        ax=[ax1, ax2],
        orientation="horizontal",
        fraction=0.06,
        pad=0.08,
        boundaries=levels,
        spacing="proportional",
    )
    tick_step = 200 if bins in (10, 20) else max_mm / 10
    cbar.set_ticks(np.arange(0, max_mm + 1e-6, tick_step))
    cbar.set_label("Precipitación acumulada anual (mm)")

    fig.suptitle(
        "Comparación CHIRPS vs CHIRPS-Corregido\nPuntos: acumulado anual OBSERVADO (estaciones)",
        fontsize=12,
        y=0.98,
    )
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.subplots_adjust(top=0.92)
    fig.savefig(out_png, dpi=200)
    plt.close(fig)


# ------------------------- Main -------------------------


def main():
    ap = argparse.ArgumentParser(
        description="Mapas anuales CHIRPS vs CHIRPS-corregido con puntos observados (CSV) y escala global."
    )
    ap.add_argument(
        "--csv", required=True, help="Ruta al CSV CDT (estaciones y datos diarios)."
    )
    ap.add_argument(
        "--dir-chirps",
        required=True,
        help="Carpeta NetCDF CHIRPS (precip_YYYYMMDD.nc).",
    )
    ap.add_argument(
        "--dir-merged",
        required=True,
        help="Carpeta NetCDF CHIRPS corregido (precip_mrg_YYYYMMDD.nc).",
    )
    ap.add_argument(
        "--out",
        default="./salidas",
        help="Carpeta base de salida (se usará <out>/mapas_anuales).",
    )
    ap.add_argument("--yini", type=int, default=1991, help="Año inicial (incluido).")
    ap.add_argument("--yend", type=int, default=2020, help="Año final (incluido).")
    ap.add_argument(
        "--extent",
        nargs=4,
        type=float,
        metavar=("xmin", "xmax", "ymin", "ymax"),
        help="Extensión del mapa (lon_min lon_max lat_min lat_max).",
    )
    ap.add_argument(
        "--export-csv",
        action="store_true",
        help="Exporta CSV con acumulados observados por estación (por año).",
    )
    args = ap.parse_args()

    # ---- Lectura CSV
    meta, df_obs_long = parse_cdt_csv(args.csv)

    # Carpeta de salida definitiva
    out_maps_dir = os.path.join(args.out, "mapas_anuales")
    os.makedirs(out_maps_dir, exist_ok=True)

    # ---- Paso 2: generar mapas usando la escala global
    for year in range(args.yini, args.yend + 1):
        print(f"Procesando año {year}...")

        # Acumulado anual OBSERVADO por estación (desde CSV)
        obs_year = df_obs_long[df_obs_long["year"] == year].copy()
        acc = obs_year.groupby("station_id", as_index=False)["precip_station"].sum(
            min_count=1
        )
        acc = acc.rename(columns={"precip_station": "accum_obs"})
        st = obs_year[["station_id", "lon", "lat", "elev"]].drop_duplicates()
        stations_obs_year = acc.merge(st, on="station_id", how="left")[
            ["station_id", "lon", "lat", "elev", "accum_obs"]
        ]

        # Campos anuales
        da_chirps = load_daily_sum_for_year(args.dir_chirps, year, "precip_", "precip")
        da_merged = load_daily_sum_for_year(
            args.dir_merged, year, "precip_mrg_", "precip"
        )

        out_png = os.path.join(out_maps_dir, f"acumulado_anual_{year}.png")
        plot_side_by_side(
            da_left=da_chirps,
            da_right=da_merged,
            year=year,
            stations_obs_year=stations_obs_year,
            out_png=out_png,
            bins=30,  # pon 10 si prefieres 10 intervalos
            max_mm=3000.0,  # tope de la escala discreta
            cmap="YlGnBu",
            extent=(
                tuple(args.extent) if args.extent else None
            ),  # si pasas --extent, se respeta; si no, se deriva del grid CHIRPS +5%
        )

        print(f"✓ Guardado: {out_png}")

        if args.export_csv:
            out_csv = os.path.join(
                out_maps_dir, f"acumulado_observado_estaciones_{year}.csv"
            )
            stations_obs_year.to_csv(out_csv, index=False)
            print(f"  ↳ CSV acumulados observado: {out_csv}")


if __name__ == "__main__":
    main()
