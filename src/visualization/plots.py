# -*- coding: utf-8 -*-
"""
Statistical charts, boxplots, scatter plots, KGE components, and DOY climatology curves.
Applies soft pastel aesthetics (#2D3748 Obs, #E57373 Raw, #4DB6AC Corrected)
and ensures exact visual matching with explanatory documentation.
"""

import os
from typing import List, Optional, Dict, Any, Union, Tuple
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from ..config.constants import (
    MONTH_NAMES_ES,
    DOY_MONTH_TICKS,
    DOY_MONTH_LABELS,
)

# Paleta Pastel Estándar
COLOR_OBS = "#0F172A"    # Carbón Intenso / Pizarra Oscuro (Observaciones in-situ)
COLOR_RAW = "#EF4444"    # Coral / Rojo (Satélite Original / Raw)
COLOR_CORR = "#3B82F6"   # Azul CDT / Pastel Suave (Satélite Corregido / Merged)
COLOR_ENV = "#93C5FD"    # Azul Celeste Pastel translúcido para envolvente ±1σ
COLOR_PURPLE = "#BA68C8" # Orquídea / Púrpura pastel para diferencias
COLOR_GRID = "#E2E8F0"   # Gris muy tenue para grillas


def _apply_boxed_spines(ax: plt.Axes, color: str = "#CBD5E1", linewidth: float = 0.9) -> None:
    """Aplica estilo boxed completo con bordes superior, derecho, inferior e izquierdo visibles."""
    for s in ["top", "right", "bottom", "left"]:
        ax.spines[s].set_visible(True)
        ax.spines[s].set_color(color)
        ax.spines[s].set_linewidth(linewidth)


def plot_rmse_bars(df_metrics: pd.DataFrame, var: str, stat: str, out_dir: str) -> str:
    """
    Genera un gráfico de evolución temporal del RMSE anual para producto original y corregido.
    """
    years = df_metrics["year"].values
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)

    ax.plot(years, df_metrics["RMSE_raw"], marker="o", markersize=6, label="RMSE Original (Raw)", color=COLOR_RAW, linewidth=2.2)
    ax.plot(years, df_metrics["RMSE_corr"], marker="s", markersize=6, label="RMSE Corregido (CDT)", color=COLOR_CORR, linewidth=2.2)

    if "Delta_RMSE" in df_metrics.columns:
        ax.bar(years, df_metrics["Delta_RMSE"], alpha=0.25, color=COLOR_CORR, label="Reducción de Error (ΔRMSE)", width=0.6)

    unit = "mm" if "precip" in var.lower() else "°C"
    ax.set_xlabel("Año", fontweight="bold", fontsize=11, color=COLOR_OBS)
    ax.set_ylabel(f"RMSE ({unit})", fontweight="bold", fontsize=11, color=COLOR_OBS)
    ax.set_title(f"{var.upper()} {stat} — Evolución Temporal del RMSE (Original vs Corregido)", fontweight="bold", fontsize=12, pad=12)
    ax.legend(frameon=True, facecolor="white", edgecolor=COLOR_GRID, fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.4, color="#CBD5E1")
    _apply_boxed_spines(ax)

    os.makedirs(out_dir, exist_ok=True)
    out_png = os.path.join(out_dir, f"rmse_annual_{var}_{stat}.png")
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close()
    return out_png


def plot_kge_components(df_metrics: pd.DataFrame, var: str, stat: str, out_dir: str) -> Optional[str]:
    """
    Genera un panel cuádruple de evolución de KGE y sus tres componentes (r, alpha, beta).
    """
    if "KGE_raw" not in df_metrics.columns or "KGE_corr" not in df_metrics.columns:
        return None

    years = df_metrics["year"].values
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=300, sharex=True)
    fig.suptitle(f"{var.upper()} {stat} — Descomposición de Eficiencia Kling-Gupta (KGE)", fontsize=13, fontweight="bold", y=0.98)

    # 1. KGE Global
    ax1 = axes[0, 0]
    ax1.plot(years, df_metrics["KGE_raw"], marker="o", color=COLOR_RAW, label="KGE Original", linewidth=2)
    ax1.plot(years, df_metrics["KGE_corr"], marker="s", color=COLOR_CORR, label="KGE Corregido", linewidth=2)
    ax1.axhline(1.0, color="#718096", linestyle=":", label="Óptimo (1.0)")
    ax1.set_title("KGE Global (1 - Distancia Euclídea)", fontweight="bold", fontsize=10)
    ax1.set_ylabel("KGE", fontweight="bold")
    ax1.legend(fontsize=8)
    ax1.grid(True, linestyle="--", alpha=0.3)

    # 2. Correlación r
    ax2 = axes[0, 1]
    if "R_raw" in df_metrics.columns:
        ax2.plot(years, df_metrics["R_raw"], marker="o", color=COLOR_RAW, label="r Original", linewidth=2)
        ax2.plot(years, df_metrics["R_corr"], marker="s", color=COLOR_CORR, label="r Corregido", linewidth=2)
    ax2.axhline(1.0, color="#718096", linestyle=":")
    ax2.set_title("Coeficiente de Correlación (r)", fontweight="bold", fontsize=10)
    ax2.set_ylabel("Pearson r", fontweight="bold")
    ax2.legend(fontsize=8)
    ax2.grid(True, linestyle="--", alpha=0.3)

    # 3. Ratio de Variabilidad Alpha (sigma_sim / sigma_obs)
    ax3 = axes[1, 0]
    if "Alpha_raw" in df_metrics.columns:
        ax3.plot(years, df_metrics["Alpha_raw"], marker="o", color=COLOR_RAW, label="α Original", linewidth=2)
        ax3.plot(years, df_metrics["Alpha_corr"], marker="s", color=COLOR_CORR, label="α Corregido", linewidth=2)
    ax3.axhline(1.0, color="#718096", linestyle=":", label="Óptimo (1.0)")
    ax3.set_title("Ratio de Variabilidad (α = σ_grid / σ_obs)", fontweight="bold", fontsize=10)
    ax3.set_xlabel("Año", fontweight="bold")
    ax3.set_ylabel("α (Variabilidad)", fontweight="bold")
    ax3.legend(fontsize=8)
    ax3.grid(True, linestyle="--", alpha=0.3)

    # 4. Ratio de Sesgo Beta (mu_sim / mu_obs)
    ax4 = axes[1, 1]
    if "Beta_raw" in df_metrics.columns:
        ax4.plot(years, df_metrics["Beta_raw"], marker="o", color=COLOR_RAW, label="β Original", linewidth=2)
        ax4.plot(years, df_metrics["Beta_corr"], marker="s", color=COLOR_CORR, label="β Corregido", linewidth=2)
    ax4.axhline(1.0, color="#718096", linestyle=":", label="Óptimo (1.0)")
    ax4.set_title("Ratio de Sesgo en la Media (β = μ_grid / μ_obs)", fontweight="bold", fontsize=10)
    ax4.set_xlabel("Año", fontweight="bold")
    ax4.set_ylabel("β (Sesgo)", fontweight="bold")
    ax4.legend(fontsize=8)
    ax4.grid(True, linestyle="--", alpha=0.3)

    for ax in axes.flat:
        _apply_boxed_spines(ax)

    plt.tight_layout()
    os.makedirs(out_dir, exist_ok=True)
    out_png = os.path.join(out_dir, f"kge_components_{var}_{stat}.png")
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close()
    return out_png


def plot_boxplot_errors(csv_files: List[str], var: str, stat: str, out_dir: str) -> Optional[str]:
    """
    Genera un boxplot global del error absoluto en estaciones con estética pastel.
    """
    all_err_raw, all_err_corr = [], []

    for csv in csv_files:
        df = pd.read_csv(csv)
        obs_col = f"{var}_{stat}_obs"
        if obs_col not in df.columns:
            candidates = [c for c in df.columns if c.endswith("_obs") or c == "obs"]
            if candidates:
                obs_col = candidates[0]
            else:
                continue

        raw_col = "grid_raw" if "grid_raw" in df.columns else ("raw" if "raw" in df.columns else None)
        corr_col = "grid_corr" if "grid_corr" in df.columns else ("corr" if "corr" in df.columns else None)
        if raw_col is None or corr_col is None:
            continue

        obs = df[obs_col].values.astype(float)
        raw = df[raw_col].values.astype(float)
        corr = df[corr_col].values.astype(float)

        err_raw = np.abs(raw - obs)
        err_corr = np.abs(corr - obs)

        all_err_raw.extend(err_raw[np.isfinite(err_raw)].tolist())
        all_err_corr.extend(err_corr[np.isfinite(err_corr)].tolist())

    if len(all_err_raw) == 0 or len(all_err_corr) == 0:
        return None

    all_err_raw = np.array(all_err_raw)
    all_err_corr = np.array(all_err_corr)

    fill_raw, edge_raw = "#FFCDD2", COLOR_RAW      # Rojo/Coral pastel
    fill_corr, edge_corr = "#BFDBFE", COLOR_CORR   # Azul Pastel Suave (CDT)

    fig, ax = plt.subplots(figsize=(7.5, 5.2), dpi=160)
    bp = ax.boxplot([all_err_raw, all_err_corr], positions=[1, 2], widths=0.22, patch_artist=True, showfliers=True)

    for box, fill, edge in zip(bp["boxes"], [fill_raw, fill_corr], [edge_raw, edge_corr]):
        box.set(facecolor=fill, edgecolor=edge, linewidth=1.5, alpha=0.9)

    for i, edge in enumerate([edge_raw, edge_corr]):
        bp["whiskers"][2 * i].set(color=edge, linewidth=1.2)
        bp["whiskers"][2 * i + 1].set(color=edge, linewidth=1.2)
        bp["caps"][2 * i].set(color=edge, linewidth=1.2)
        bp["caps"][2 * i + 1].set(color=edge, linewidth=1.2)

    bp["medians"][0].set(color="#C62828", linewidth=2.2)
    bp["medians"][1].set(color="#1D4ED8", linewidth=2.2)

    # Conectar las medianas con una línea punteada sutil y armónica
    med_raw = float(np.median(all_err_raw))
    med_corr = float(np.median(all_err_corr))
    ax.plot(
        [1, 2],
        [med_raw, med_corr],
        linestyle=(0, (4, 3)),
        color="#546E7A",
        linewidth=0.95,
        marker="o",
        markersize=3.2,
        markerfacecolor="#ECEFF1",
        markeredgecolor="#455A64",
        markeredgewidth=0.8,
        zorder=6,
        label=f"Tendencia Mediana ({med_raw:.2f} → {med_corr:.2f})"
    )

    for flier, edge in zip(bp["fliers"], [edge_raw, edge_corr]):
        flier.set(marker="o", markerfacecolor="none", markeredgecolor=edge, markersize=5, linestyle="none", markeredgewidth=0.8, alpha=0.6)

    # Jitter puntos individuales
    x_raw = np.random.normal(0.78, 0.025, size=len(all_err_raw))
    x_corr = np.random.normal(1.78, 0.025, size=len(all_err_corr))

    ax.scatter(x_raw, all_err_raw, facecolors="none", edgecolors=edge_raw, s=24, linewidths=0.8, alpha=0.7, zorder=3)
    ax.scatter(x_corr, all_err_corr, facecolors="none", edgecolors=edge_corr, s=24, linewidths=0.8, alpha=0.7, zorder=3)

    unit = "mm" if "precip" in var.lower() else "°C"
    ax.set_xticks([1, 2])
    ax.set_xticklabels(["Original (Raw)", "Corregido (CDT)"], fontsize=11, fontweight="bold", color=COLOR_OBS)
    ax.set_ylabel(f"|Error Absoluto| ({unit})", fontsize=11, fontweight="bold", color=COLOR_OBS)
    ax.set_title(f"{var.upper()} {stat} — Distribución del Error Absoluto en Estaciones", fontsize=12, fontweight="bold", pad=12)
    ax.legend(loc="upper right", fontsize=9, framealpha=0.85)
    ax.grid(True, axis="y", linestyle="--", alpha=0.3, color="#CBD5E1")
    _apply_boxed_spines(ax)

    mae_o = np.mean(all_err_raw)
    rmse_o = np.sqrt(np.mean(all_err_raw**2))
    mae_c = np.mean(all_err_corr)
    rmse_c = np.sqrt(np.mean(all_err_corr**2))

    ymax = max(all_err_raw.max(), all_err_corr.max())
    ax.set_ylim(0, ymax * 1.35)

    ax.text(1, ymax * 1.08, f"MAE={mae_o:.2f} {unit}\nRMSE={rmse_o:.2f} {unit}", ha="center", va="bottom", fontsize=9, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=edge_raw, alpha=0.8))
    ax.text(2, ymax * 1.08, f"MAE={mae_c:.2f} {unit}\nRMSE={rmse_c:.2f} {unit}", ha="center", va="bottom", fontsize=9, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=edge_corr, alpha=0.8))

    os.makedirs(out_dir, exist_ok=True)
    out_png = os.path.join(out_dir, f"boxplot_errors_{var}_{stat}.png")
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close()
    return out_png


def plot_boxplot_errors_single(csv_path_or_df: Union[str, pd.DataFrame], var: str, stat: str, out_png: str) -> str:
    """
    Genera un boxplot de error para un único archivo o DataFrame.
    """
    if isinstance(csv_path_or_df, str):
        df = pd.read_csv(csv_path_or_df)
    else:
        df = csv_path_or_df.copy()

    obs_col = f"{var}_{stat}_obs"
    if obs_col not in df.columns:
        candidates = [c for c in df.columns if c.endswith("_obs") or c == "obs"]
        obs_col = candidates[0] if candidates else None

    if obs_col is None:
        raise ValueError("No se encontró columna de observación en el dataframe.")

    raw_col = "grid_raw" if "grid_raw" in df.columns else ("raw" if "raw" in df.columns else None)
    corr_col = "grid_corr" if "grid_corr" in df.columns else ("corr" if "corr" in df.columns else None)

    if raw_col is None or corr_col is None:
        raise ValueError("No se encontraron columnas de valores crudos (raw) y corregidos (corr).")

    obs = df[obs_col].values.astype(float)
    raw = df[raw_col].values.astype(float)
    corr = df[corr_col].values.astype(float)

    err_raw = np.abs(raw - obs)
    err_corr = np.abs(corr - obs)
    mask = np.isfinite(err_raw) & np.isfinite(err_corr)
    err_raw = err_raw[mask]
    err_corr = err_corr[mask]

    if len(err_raw) == 0 or len(err_corr) == 0:
        fig, ax = plt.subplots(figsize=(7, 5), dpi=160)
        ax.text(0.5, 0.5, "No hay suficientes datos válidos para generar boxplot", ha="center", va="center", fontsize=11)
        _apply_boxed_spines(ax)
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        plt.savefig(out_png, dpi=300, bbox_inches="tight")
        plt.close()
        return out_png

    fig, ax = plt.subplots(figsize=(7, 5), dpi=160)
    bp = ax.boxplot([err_raw, err_corr], positions=[1, 2], widths=0.25, patch_artist=True)
    bp["boxes"][0].set(facecolor="#FFCDD2", edgecolor=COLOR_RAW, linewidth=1.5)
    bp["boxes"][1].set(facecolor="#BFDBFE", edgecolor=COLOR_CORR, linewidth=1.5)
    bp["medians"][0].set(color="#C62828", linewidth=2.2)
    bp["medians"][1].set(color="#1D4ED8", linewidth=2.2)

    # Jitter puntos individuales
    np.random.seed(42)
    x_raw = np.random.normal(0.82, 0.025, size=len(err_raw))
    x_corr = np.random.normal(1.82, 0.025, size=len(err_corr))
    ax.scatter(x_raw, err_raw, facecolors="none", edgecolors=COLOR_RAW, s=28, linewidths=0.8, alpha=0.75, zorder=4)
    ax.scatter(x_corr, err_corr, facecolors="none", edgecolors=COLOR_CORR, s=28, linewidths=0.8, alpha=0.75, zorder=4)

    # Conectar medianas
    med_raw = float(np.median(err_raw))
    med_corr = float(np.median(err_corr))
    ax.plot(
        [1, 2],
        [med_raw, med_corr],
        linestyle=(0, (4, 3)),
        color="#546E7A",
        linewidth=0.95,
        marker="o",
        markersize=3.2,
        markerfacecolor="#ECEFF1",
        markeredgecolor="#455A64",
        markeredgewidth=0.8,
        zorder=6,
        label=f"Tendencia Mediana ({med_raw:.2f} → {med_corr:.2f})"
    )

    unit = "mm" if "precip" in var.lower() else "°C"
    ax.set_xticks([1, 2])
    ax.set_xticklabels(["Original (Raw)", "Corregido (CDT)"], fontsize=10, fontweight="bold")
    ax.set_ylabel(f"|Error Absoluto| ({unit})", fontsize=10, fontweight="bold")
    ax.set_title(f"{var.upper()} {stat} — Error Absoluto", fontsize=11, fontweight="bold")
    ax.legend(loc="upper right", fontsize=9, framealpha=0.85)
    ax.grid(True, axis="y", linestyle="--", alpha=0.3)
    _apply_boxed_spines(ax)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close()
    return out_png


def plot_boxplot_rmse_by_station(df_imp: pd.DataFrame, var: str, stat: str, label: str, out_png: str) -> str:
    """
    Genera un boxplot comparativo del RMSE entre estaciones para Original vs Corregido.
    """
    raw_col = "RMSE_raw" if "RMSE_raw" in df_imp.columns else ([c for c in df_imp.columns if "raw" in c.lower()][0] if any("raw" in c.lower() for c in df_imp.columns) else df_imp.columns[3])
    corr_col = "RMSE_corr" if "RMSE_corr" in df_imp.columns else ([c for c in df_imp.columns if "corr" in c.lower() or "mrg" in c.lower()][0] if any("corr" in c.lower() or "mrg" in c.lower() for c in df_imp.columns) else df_imp.columns[4])
    rmse_raw = df_imp[raw_col].dropna().values
    rmse_corr = df_imp[corr_col].dropna().values

    if len(rmse_raw) == 0 or len(rmse_corr) == 0:
        fig, ax = plt.subplots(figsize=(6.5, 5), dpi=160)
        ax.text(0.5, 0.5, "No hay suficientes estaciones con datos válidos", ha="center", va="center", fontsize=11)
        _apply_boxed_spines(ax)
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        plt.savefig(out_png, dpi=300, bbox_inches="tight")
        plt.close()
        return out_png

    fig, ax = plt.subplots(figsize=(6.5, 5), dpi=160)
    bp = ax.boxplot([rmse_raw, rmse_corr], positions=[1, 2], widths=0.3, patch_artist=True)
    bp["boxes"][0].set(facecolor="#FFCDD2", edgecolor=COLOR_RAW, linewidth=1.5)
    bp["boxes"][1].set(facecolor="#BFDBFE", edgecolor=COLOR_CORR, linewidth=1.5)
    bp["medians"][0].set(color="#C62828", linewidth=2.0)
    bp["medians"][1].set(color="#1D4ED8", linewidth=2.0)

    # Jitter puntos individuales por estación
    np.random.seed(42)
    x_raw = np.random.normal(0.82, 0.025, size=len(rmse_raw))
    x_corr = np.random.normal(1.82, 0.025, size=len(rmse_corr))
    ax.scatter(x_raw, rmse_raw, facecolors="none", edgecolors=COLOR_RAW, s=28, linewidths=0.8, alpha=0.75, zorder=4)
    ax.scatter(x_corr, rmse_corr, facecolors="none", edgecolors=COLOR_CORR, s=28, linewidths=0.8, alpha=0.75, zorder=4)

    # Conectar medianas
    med_raw = float(np.median(rmse_raw))
    med_corr = float(np.median(rmse_corr))
    ax.plot(
        [1, 2],
        [med_raw, med_corr],
        linestyle=(0, (4, 3)),
        color="#546E7A",
        linewidth=0.95,
        marker="o",
        markersize=3.2,
        markerfacecolor="#ECEFF1",
        markeredgecolor="#455A64",
        markeredgewidth=0.8,
        zorder=6,
        label=f"Tendencia Mediana ({med_raw:.2f} → {med_corr:.2f})"
    )

    unit = "mm" if "precip" in var.lower() else "°C"
    ax.set_xticks([1, 2])
    ax.set_xticklabels(["Original (Raw)", "Corregido (CDT)"], fontsize=10, fontweight="bold")
    ax.set_ylabel(f"RMSE ({unit})", fontsize=10, fontweight="bold")
    ax.set_title(f"{var.upper()} {stat} — Distribución de RMSE en Estaciones ({label})", fontsize=11, fontweight="bold")
    ax.legend(loc="upper right", fontsize=9, framealpha=0.85)
    ax.grid(True, axis="y", linestyle="--", alpha=0.3)
    _apply_boxed_spines(ax)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close()
    return out_png


def plot_boxplot_improvement_pct_by_station(df_imp: pd.DataFrame, var: str, stat: str, label: str, out_png: str) -> str:
    """
    Genera un gráfico del porcentaje de mejora de RMSE por estación con línea de referencia en 0%.
    """
    col = (
        "improvement_pct"
        if "improvement_pct" in df_imp.columns
        else (
            "improvement_RMSE_pct"
            if "improvement_RMSE_pct" in df_imp.columns
            else (
                "Improvement_RMSE_pct"
                if "Improvement_RMSE_pct" in df_imp.columns
                else (
                    [c for c in df_imp.columns if "improv" in c.lower()][0]
                    if any("improv" in c.lower() for c in df_imp.columns)
                    else df_imp.columns[-1]
                )
            )
        )
    )
    imp_pct = df_imp[col].dropna().values

    if len(imp_pct) == 0:
        fig, ax = plt.subplots(figsize=(6.5, 5), dpi=160)
        ax.text(0.5, 0.5, "No hay suficientes estaciones con datos válidos", ha="center", va="center", fontsize=11)
        _apply_boxed_spines(ax)
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        plt.savefig(out_png, dpi=300, bbox_inches="tight")
        plt.close()
        return out_png

    fig, ax = plt.subplots(figsize=(6.5, 5), dpi=160)
    bp = ax.boxplot([imp_pct], positions=[1], widths=0.3, patch_artist=True)
    bp["boxes"][0].set(facecolor="#C8E6C9", edgecolor="#43A047", linewidth=1.5)
    bp["medians"][0].set(color="#1B5E20", linewidth=2.0)

    # Jitter puntos individuales por estación
    np.random.seed(42)
    x_pts = np.random.normal(0.82, 0.025, size=len(imp_pct))
    ax.scatter(x_pts, imp_pct, facecolors="none", edgecolors="#2E7D32", s=28, linewidths=0.8, alpha=0.75, zorder=4)

    ax.axhline(0, color="#E53935", linestyle="--", linewidth=1.2, label="Sin Cambio (0%)")
    ax.set_xticks([1])
    ax.set_xticklabels(["Estaciones Evaluadas"], fontsize=10, fontweight="bold")
    ax.set_ylabel("Mejora en RMSE (%)", fontsize=10, fontweight="bold")
    ax.set_title(f"{var.upper()} {stat} — Porcentaje de Reducción de Error ({label})", fontsize=11, fontweight="bold")
    ax.grid(True, axis="y", linestyle="--", alpha=0.3)
    ax.legend(fontsize=9)
    _apply_boxed_spines(ax)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close()
    return out_png


def plot_scatter_obs_vs_grid(
    csv_files: List[str], var: str, stat: str, out_dir: str, title: Optional[str] = None
) -> Optional[str]:
    """
    Genera un diagrama de dispersión Observado vs Rejilla (Original y Corregido) con línea 1:1,
    coloreando cada estación meteorológica con su propio tono distintivo de la paleta original
    y con líneas de regresión claramente diferenciadas de la línea 1:1.
    """
    dfs = []
    for csv in csv_files:
        df_temp = pd.read_csv(csv)
        obs_col = f"{var}_{stat}_obs"
        if obs_col not in df_temp.columns:
            candidates = [c for c in df_temp.columns if c.endswith("_obs") or c == "obs"]
            if candidates:
                obs_col = candidates[0]
            else:
                continue

        raw_col = "grid_raw" if "grid_raw" in df_temp.columns else ("raw" if "raw" in df_temp.columns else None)
        corr_col = "grid_corr" if "grid_corr" in df_temp.columns else ("corr" if "corr" in df_temp.columns else None)
        if raw_col is None or corr_col is None:
            continue

        st_col = "station_id" if "station_id" in df_temp.columns else ("id" if "id" in df_temp.columns else None)
        sub = pd.DataFrame({
            "obs": df_temp[obs_col].values.astype(float),
            "raw": df_temp[raw_col].values.astype(float),
            "corr": df_temp[corr_col].values.astype(float),
            "station": df_temp[st_col].astype(str) if st_col else [f"Est_{i}" for i in range(len(df_temp))]
        })
        mask = np.isfinite(sub["obs"]) & np.isfinite(sub["raw"]) & np.isfinite(sub["corr"])
        dfs.append(sub[mask])

    if not dfs:
        return None

    df_all = pd.concat(dfs, ignore_index=True)
    if df_all.empty:
        return None

    obs_arr = df_all["obs"].values
    raw_arr = df_all["raw"].values
    corr_arr = df_all["corr"].values
    stations = df_all["station"].values

    unique_stations = sorted(list(set(stations)))
    # Paleta original extendida (tab20 + tab20b + tab20c) para distinguir todas las estaciones
    cmaps = [plt.get_cmap("tab20"), plt.get_cmap("tab20b"), plt.get_cmap("tab20c")]
    palette = []
    for cm in cmaps:
        palette.extend([cm(i) for i in range(cm.N)])
    station_color_map = {sid: palette[i % len(palette)] for i, sid in enumerate(unique_stations)}
    point_colors = [station_color_map[sid] for sid in stations]

    fig, axes = plt.subplots(1, 2, figsize=(14.0, 6.5), dpi=300, sharex=True, sharey=True)
    unit = "mm" if "precip" in var.lower() else "°C"

    # Límite común
    val_min = min(float(obs_arr.min()), float(raw_arr.min()), float(corr_arr.min()))
    val_max = max(float(obs_arr.max()), float(raw_arr.max()), float(corr_arr.max()))
    margin = (val_max - val_min) * 0.05 if val_max > val_min else 1.0
    axis_min = val_min - margin
    axis_max = val_max + margin

    # Colores de regresión llamativos y diferenciados de la línea 1:1
    reg_colors = ["#2563EB", "#DC2626"]  # Azul Zafiro (Raw) y Rojo Carmesí (Corr)

    for ax, sim_arr, panel_label, reg_color in zip(
        axes,
        [raw_arr, corr_arr],
        ["Original (Raw Satélite)", "Corregido (CDT Merged)"],
        reg_colors
    ):
        # Puntos de estaciones con círculos más grandes y colores distintivos
        ax.scatter(
            obs_arr,
            sim_arr,
            c=point_colors,
            s=80,
            edgecolors="#0F172A",
            linewidths=0.75,
            alpha=0.88,
            zorder=4
        )

        # Línea 1:1 Ideal (gris punteada sutil)
        ax.plot([axis_min, axis_max], [axis_min, axis_max], linestyle="--", color="#64748B", linewidth=1.4, label="Línea 1:1 Ideal (Sin Error)", zorder=2)

        # Regresión Lineal OLS con color vibrante distintivo y trazo sólido
        if len(obs_arr) >= 2 and np.var(obs_arr) > 1e-9:
            try:
                p = np.polyfit(obs_arr, sim_arr, 1)
                x_fit = np.linspace(axis_min, axis_max, 100)
                y_fit = np.polyval(p, x_fit)
                ax.plot(x_fit, y_fit, color=reg_color, linestyle="-", linewidth=2.4, label=f"Regresión OLS: $y = {p[0]:.2f}x + {p[1]:.2f}$", zorder=5)
            except Exception:
                pass

        try:
            r = np.corrcoef(obs_arr, sim_arr)[0, 1] if (np.var(obs_arr) > 1e-9 and np.var(sim_arr) > 1e-9) else np.nan
        except Exception:
            r = np.nan
        bias = float(np.mean(sim_arr - obs_arr))
        rmse = float(np.sqrt(np.mean((sim_arr - obs_arr)**2)))
        r_str = f"R = {r:.3f}" if np.isfinite(r) else "R = N/A"

        ax.set_xlim(axis_min, axis_max)
        ax.set_ylim(axis_min, axis_max)
        ax.set_xlabel(f"Observado en Estaciones ({unit})", fontweight="bold", fontsize=11, color=COLOR_OBS)
        ax.set_title(f"{panel_label}\n{r_str} | Bias = {bias:+.2f} {unit} | RMSE = {rmse:.2f} {unit}", fontweight="bold", fontsize=12, color=COLOR_OBS, pad=8)
        ax.legend(loc="upper left", fontsize=9.5, framealpha=0.92, facecolor="white", edgecolor="#CBD5E1")
        ax.grid(True, linestyle="--", alpha=0.35, color="#CBD5E1")
        _apply_boxed_spines(ax)

    axes[0].set_ylabel(f"Valor Rejilla Satelital ({unit})", fontweight="bold", fontsize=11, color=COLOR_OBS)
    var_pretty = "CHIRPS Precipitación" if "precip" in var.lower() else f"CHIRTS {var.upper()}"
    stat_pretty = "Acumulada" if stat == "accum" else ("Promedio" if stat == "mean" else ("Máxima" if stat == "max" else ("Mínima" if stat == "min" else stat)))
    main_title = title or f"{var_pretty} ({stat_pretty}) — Comparación Observado vs Rejilla Satelital (Puntos por estación)"
    fig.suptitle(main_title, fontsize=13.5, fontweight="bold", y=0.99)

    plt.tight_layout()
    os.makedirs(out_dir, exist_ok=True)
    out_png = os.path.join(out_dir, f"scatter_obs_vs_grid_{var}_{stat}.png")
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close()
    return out_png


def plot_scatter_obs_vs_grid_single(
    csv_path_or_df: Union[str, pd.DataFrame], var: str, stat: str, out_png: str, title: Optional[str] = None
) -> str:
    """
    Genera un scatter plot Observado vs Rejilla (Raw y Corregido lado a lado) para un único archivo o DataFrame,
    con puntos coloreados por estación meteorológica, línea 1:1 y regresiones OLS.
    """
    if isinstance(csv_path_or_df, str):
        df = pd.read_csv(csv_path_or_df)
    else:
        df = csv_path_or_df.copy()

    obs_col = f"{var}_{stat}_obs"
    if obs_col not in df.columns:
        candidates = [c for c in df.columns if c.endswith("_obs") or c == "obs"]
        obs_col = candidates[0] if candidates else None

    if obs_col is None:
        raise ValueError("No se encontró columna de observación en el dataframe.")

    raw_col = "grid_raw" if "grid_raw" in df.columns else ("raw" if "raw" in df.columns else None)
    corr_col = "grid_corr" if "grid_corr" in df.columns else ("corr" if "corr" in df.columns else None)

    if raw_col is None or corr_col is None:
        raise ValueError("No se encontraron columnas de valores crudos (raw) y corregidos (corr).")

    st_col = "station_id" if "station_id" in df.columns else ("id" if "id" in df.columns else None)
    stations = df[st_col].astype(str).values if st_col else np.array([f"Est_{i}" for i in range(len(df))])

    obs_arr = df[obs_col].values.astype(float)
    raw_arr = df[raw_col].values.astype(float)
    corr_arr = df[corr_col].values.astype(float)

    mask = np.isfinite(obs_arr) & np.isfinite(raw_arr) & np.isfinite(corr_arr)
    obs_arr = obs_arr[mask]
    raw_arr = raw_arr[mask]
    corr_arr = corr_arr[mask]
    stations = stations[mask]

    if len(obs_arr) == 0:
        fig, ax = plt.subplots(figsize=(7, 6.5), dpi=300)
        ax.text(0.5, 0.5, "No hay suficientes observaciones para diagrama de dispersión", ha="center", va="center", fontsize=11)
        _apply_boxed_spines(ax)
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        plt.savefig(out_png, dpi=300, bbox_inches="tight")
        plt.close()
        return out_png

    unique_stations = sorted(list(set(stations)))
    cmaps = [plt.get_cmap("tab20"), plt.get_cmap("tab20b"), plt.get_cmap("tab20c")]
    palette = []
    for cm in cmaps:
        palette.extend([cm(i) for i in range(cm.N)])
    station_color_map = {sid: palette[i % len(palette)] for i, sid in enumerate(unique_stations)}
    point_colors = [station_color_map[sid] for sid in stations]

    fig, axes = plt.subplots(1, 2, figsize=(14.0, 6.5), dpi=300, sharex=True, sharey=True)
    unit = "mm" if "precip" in var.lower() else "°C"

    val_min = min(float(obs_arr.min()), float(raw_arr.min()), float(corr_arr.min()))
    val_max = max(float(obs_arr.max()), float(raw_arr.max()), float(corr_arr.max()))
    margin = (val_max - val_min) * 0.05 if val_max > val_min else 1.0
    axis_min = val_min - margin
    axis_max = val_max + margin

    reg_colors = ["#2563EB", "#DC2626"]

    for ax, sim_arr, panel_label, reg_color in zip(
        axes,
        [raw_arr, corr_arr],
        ["Original (Raw Satélite)", "Corregido (CDT Merged)"],
        reg_colors
    ):
        ax.scatter(
            obs_arr,
            sim_arr,
            c=point_colors,
            s=80,
            edgecolors="#0F172A",
            linewidths=0.75,
            alpha=0.88,
            zorder=4
        )

        ax.plot([axis_min, axis_max], [axis_min, axis_max], linestyle="--", color="#64748B", linewidth=1.4, label="Línea 1:1 Ideal (Sin Error)", zorder=2)

        if len(obs_arr) >= 2 and np.var(obs_arr) > 1e-9:
            try:
                p = np.polyfit(obs_arr, sim_arr, 1)
                x_fit = np.linspace(axis_min, axis_max, 100)
                y_fit = np.polyval(p, x_fit)
                ax.plot(x_fit, y_fit, color=reg_color, linestyle="-", linewidth=2.4, label=f"Regresión OLS: $y = {p[0]:.2f}x + {p[1]:.2f}$", zorder=5)
            except Exception:
                pass

        try:
            r = np.corrcoef(obs_arr, sim_arr)[0, 1] if (np.var(obs_arr) > 1e-9 and np.var(sim_arr) > 1e-9) else np.nan
        except Exception:
            r = np.nan
        bias = float(np.mean(sim_arr - obs_arr))
        rmse = float(np.sqrt(np.mean((sim_arr - obs_arr)**2)))
        r_str = f"R = {r:.3f}" if np.isfinite(r) else "R = N/A"

        ax.set_xlim(axis_min, axis_max)
        ax.set_ylim(axis_min, axis_max)
        ax.set_xlabel(f"Observado en Estaciones ({unit})", fontweight="bold", fontsize=11, color=COLOR_OBS)
        ax.set_title(f"{panel_label}\n{r_str} | Bias = {bias:+.2f} {unit} | RMSE = {rmse:.2f} {unit}", fontweight="bold", fontsize=12, color=COLOR_OBS, pad=8)
        ax.legend(loc="upper left", fontsize=9.5, framealpha=0.92, facecolor="white", edgecolor="#CBD5E1")
        ax.grid(True, linestyle="--", alpha=0.35, color="#CBD5E1")
        _apply_boxed_spines(ax)

    axes[0].set_ylabel(f"Valor Rejilla Satelital ({unit})", fontweight="bold", fontsize=11, color=COLOR_OBS)
    var_pretty = "CHIRPS Precipitación" if "precip" in var.lower() else f"CHIRTS {var.upper()}"
    stat_pretty = "Acumulada" if stat == "accum" else ("Promedio" if stat == "mean" else ("Máxima" if stat == "max" else ("Mínima" if stat == "min" else stat)))
    main_title = title or f"{var_pretty} ({stat_pretty}) — Comparación Observado vs Rejilla Satelital (Puntos por estación)"
    fig.suptitle(main_title, fontsize=13.5, fontweight="bold", y=0.99)

    plt.tight_layout()
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close()
    return out_png


def plot_scatter_rmse_raw_vs_corr(df_imp: pd.DataFrame, var: str, stat: str, label: str, out_png: str) -> str:
    """
    Genera un scatter plot de RMSE Original vs RMSE Corregido con línea 1:1.
    Puntos bajo la línea 1:1 demuestran mejora por parte de CDT.
    """
    raw_col = "RMSE_raw" if "RMSE_raw" in df_imp.columns else ([c for c in df_imp.columns if "raw" in c.lower()][0] if any("raw" in c.lower() for c in df_imp.columns) else df_imp.columns[3])
    corr_col = "RMSE_corr" if "RMSE_corr" in df_imp.columns else ([c for c in df_imp.columns if "corr" in c.lower() or "mrg" in c.lower()][0] if any("corr" in c.lower() or "mrg" in c.lower() for c in df_imp.columns) else df_imp.columns[4])
    r_raw = df_imp[raw_col].dropna().values
    r_corr = df_imp[corr_col].dropna().values

    if len(r_raw) == 0 or len(r_corr) == 0:
        fig, ax = plt.subplots(figsize=(6.5, 6), dpi=300)
        ax.text(0.5, 0.5, "No hay suficientes estaciones con datos válidos", ha="center", va="center", fontsize=11)
        _apply_boxed_spines(ax)
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        plt.savefig(out_png, dpi=300, bbox_inches="tight")
        plt.close()
        return out_png

    fig, ax = plt.subplots(figsize=(6.5, 6), dpi=300)
    ax.scatter(r_raw, r_corr, color=COLOR_CORR, edgecolors=COLOR_OBS, s=55, alpha=0.85, label="Estaciones")

    vmin = min(r_raw.min(), r_corr.min())
    vmax = max(r_raw.max(), r_corr.max())
    margin = (vmax - vmin) * 0.05 if vmax > vmin else 1.0
    ax.plot([vmin - margin, vmax + margin], [vmin - margin, vmax + margin], "--", color="#64748B", linewidth=1.3, label="Línea 1:1 (Sin mejora)")

    unit = "mm" if "precip" in var.lower() else "°C"
    ax.set_xlabel(f"RMSE Original ({unit})", fontweight="bold", fontsize=10.5)
    ax.set_ylabel(f"RMSE Corregido ({unit})", fontweight="bold", fontsize=10.5)
    ax.set_title(f"{var.upper()} {stat} — RMSE Original vs Corregido ({label})", fontweight="bold", fontsize=11.5, pad=10)
    ax.legend(fontsize=9, framealpha=0.9)
    ax.grid(True, linestyle="--", alpha=0.35, color="#CBD5E1")
    _apply_boxed_spines(ax)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close()
    return out_png


def plot_scatter_rmse_vs_improvement(df_imp: pd.DataFrame, var: str, stat: str, label: str, out_png: str) -> str:
    """
    Genera un scatter plot de RMSE Original vs % de Mejora.
    """
    raw_col = "RMSE_raw" if "RMSE_raw" in df_imp.columns else ([c for c in df_imp.columns if "raw" in c.lower()][0] if any("raw" in c.lower() for c in df_imp.columns) else df_imp.columns[3])
    imp_col = (
        "improvement_pct"
        if "improvement_pct" in df_imp.columns
        else (
            "improvement_RMSE_pct"
            if "improvement_RMSE_pct" in df_imp.columns
            else (
                "Improvement_RMSE_pct"
                if "Improvement_RMSE_pct" in df_imp.columns
                else (
                    [c for c in df_imp.columns if "improv" in c.lower()][0]
                    if any("improv" in c.lower() for c in df_imp.columns)
                    else df_imp.columns[-1]
                )
            )
        )
    )
    r_raw = df_imp[raw_col].dropna().values
    imp_pct = df_imp[imp_col].dropna().values

    if len(r_raw) == 0 or len(imp_pct) == 0:
        fig, ax = plt.subplots(figsize=(6.5, 5.5), dpi=300)
        ax.text(0.5, 0.5, "No hay suficientes estaciones con datos válidos", ha="center", va="center", fontsize=11)
        _apply_boxed_spines(ax)
        os.makedirs(os.path.dirname(out_png), exist_ok=True)
        plt.savefig(out_png, dpi=300, bbox_inches="tight")
        plt.close()
        return out_png

    fig, ax = plt.subplots(figsize=(6.5, 5.5), dpi=300)
    ax.scatter(r_raw, imp_pct, color=COLOR_CORR, edgecolors=COLOR_OBS, s=50, alpha=0.85)
    ax.axhline(0, color="#E53935", linestyle="--", linewidth=1.2, label="0% Mejora")

    unit = "mm" if "precip" in var.lower() else "°C"
    ax.set_xlabel(f"RMSE Original ({unit})", fontweight="bold", fontsize=10.5)
    ax.set_ylabel("Mejora en RMSE (%)", fontweight="bold", fontsize=10.5)
    ax.set_title(f"{var.upper()} {stat} — Error Inicial vs % Mejora ({label})", fontweight="bold", fontsize=11.5, pad=10)
    ax.legend(fontsize=9, framealpha=0.9)
    ax.grid(True, linestyle="--", alpha=0.35, color="#CBD5E1")
    _apply_boxed_spines(ax)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close()
    return out_png


def _get_doy_axis_config(df_doy: pd.DataFrame) -> Tuple[Tuple[float, float], List[int], List[str], str, Optional[str]]:
    """
    Determina los límites, ticks, etiquetas y nombre de mes para el eje temporal de gráficos DOY.
    """
    n_days = len(df_doy)
    if "month" in df_doy.columns:
        # Preservar orden cronológico de meses presentes
        months_seq = list(dict.fromkeys(df_doy["month"].values))
        if len(months_seq) == 1 and n_days <= 31:
            # Mes individual (ej. Mayo, 31 días)
            m = int(months_seq[0])
            m_name = MONTH_NAMES_ES.get(m, f"Mes {m}")
            xlim = (1, n_days)
            if n_days == 31:
                ticks = [1, 5, 10, 15, 20, 25, 30, 31]
            elif n_days == 30:
                ticks = [1, 5, 10, 15, 20, 25, 30]
            else:
                ticks = [1, 5, 10, 15, 20, 25, n_days]
            labels = [str(t) for t in ticks]
            xlabel = f"Día de {m_name}"
            return xlim, ticks, labels, xlabel, m_name
        elif 1 < len(months_seq) < 12 and n_days < 365:
            # Temporada o agrupación de meses (ej. ASO, DJFM, MJJ)
            ticks = []
            labels = []
            is_cross_year = (months_seq[0] == 12 and any(m < 12 for m in months_seq[1:]))
            for m in months_seq:
                locs = np.where(df_doy["month"].values == m)[0]
                if len(locs) > 0:
                    first_idx = int(locs[0]) + 1
                    ticks.append(first_idx)
                    m_short = MONTH_NAMES_ES.get(int(m), str(m))[:3].capitalize()
                    if is_cross_year and m == 12:
                        labels.append("Dic (año ant.)")
                    else:
                        labels.append(m_short)
            xlim = (1, n_days)
            first_name = MONTH_NAMES_ES.get(int(months_seq[0]), '')[:3].capitalize()
            last_name = MONTH_NAMES_ES.get(int(months_seq[-1]), '')[:3].capitalize()
            if is_cross_year:
                xlabel = f"Días del período: {first_name} (año anterior) → Ene–{last_name} (año evaluado)"
                period_label = f"{first_name} (año ant.) – {last_name} (año eval.)"
            else:
                xlabel = "Mes / Día del Período"
                period_label = f"{first_name}–{last_name}"
            return xlim, ticks, labels, xlabel, period_label

    # Serie anual completa o fallback por defecto
    return (1, 365), DOY_MONTH_TICKS, DOY_MONTH_LABELS, "Mes / Día del Año (DOY)", None


def plot_climatology_doy_station(
    data_or_csv: Union[str, pd.DataFrame],
    arg2: str,
    arg3: str,
    out_png: str,
    stat_col: str = "mean",
    stat: Optional[str] = None,
    title: Optional[str] = None,
) -> str:
    """
    Genera la curva del ciclo climatológico diario para una estación con colores pastel.
    Soporta acumulado progresivo (accum), promedio diario (mean), máximo (max) y mínimo (min).
    Acepta (df, station_id, var, out_png) o (csv_path, var, station_id, out_png).
    """
    if isinstance(data_or_csv, str):
        df_doy = pd.read_csv(data_or_csv)
    else:
        df_doy = data_or_csv

    target_stat = stat or stat_col

    known_vars = ["tmax", "tmin", "precip", "tmean"]
    if arg2.lower() in known_vars:
        var = arg2
        station_id = arg3
    elif arg3.lower() in known_vars:
        var = arg3
        station_id = arg2
    else:
        var = arg2
        station_id = arg3

    doy = df_doy["doy"].values
    xlim, ticks, tick_labels, xlabel, sub_name = _get_doy_axis_config(df_doy)

    fig, ax = plt.subplots(figsize=(11, 5.2), dpi=300)

    obs_col = f"obs_{target_stat}" if f"obs_{target_stat}" in df_doy.columns else "obs"
    raw_col = f"raw_{target_stat}" if f"raw_{target_stat}" in df_doy.columns else "raw"
    corr_col = f"corr_{target_stat}" if f"corr_{target_stat}" in df_doy.columns else "corr"

    # Curva Observada (Estación in-situ con marcadores para visibilidad)
    ax.plot(doy, df_doy[obs_col], color=COLOR_OBS, linewidth=2.5, marker="o", markersize=3.0, label="Observado (Estación in-situ)", zorder=3)

    # Curva Corregida (CDT Merged - sobre la curva de observado)
    ax.plot(doy, df_doy[corr_col], color=COLOR_CORR, linewidth=2.0, label="Corregido (CDT Merged)", zorder=4)

    # Curva Original (Raw Satélite)
    ax.plot(doy, df_doy[raw_col], color=COLOR_RAW, linewidth=1.8, linestyle="--", label="Original (Raw Satélite)", zorder=2)

    is_precip = "precip" in var.lower()

    # Envolvente ±1 sigma de observaciones si existe y no es accum
    if target_stat != "accum" and "obs_std" in df_doy.columns:
        mean_v = df_doy[obs_col].values
        std_v = df_doy["obs_std"].values
        lower_v = np.maximum(0.0, mean_v - std_v) if is_precip else (mean_v - std_v)
        ax.fill_between(doy, lower_v, mean_v + std_v, color=COLOR_ENV, alpha=0.3, label="Variabilidad Obs. (±1σ)", zorder=1)

    if target_stat == "accum":
        unit = "mm" if is_precip else "°C"
        ylabel_str = f"Acumulado ({unit})"
    elif is_precip:
        unit = "mm/día"
        ylabel_str = f"Precipitación ({unit})"
    else:
        unit = "°C"
        ylabel_str = f"{var.upper()} ({unit})"

    if is_precip and target_stat in ["accum", "mean", "max"]:
        ax.set_ylim(bottom=0.0)

    ax.set_xticks(ticks)
    ax.set_xticklabels(tick_labels, fontsize=10, fontweight="bold", color=COLOR_OBS)
    ax.set_xlim(xlim[0], xlim[1])
    ax.set_xlabel(xlabel, fontweight="bold", fontsize=11, color=COLOR_OBS)
    ax.set_ylabel(ylabel_str, fontweight="bold", fontsize=11, color=COLOR_OBS)

    stat_tag_map = {
        "accum": "Acumulado Progresivo",
        "mean": "Promedio Diario",
        "max": "Máximo Diario",
        "min": "Mínimo Diario",
    }
    stat_tag = stat_tag_map.get(target_stat, target_stat.upper())

    if title:
        plot_title = title
    elif sub_name:
        plot_title = f"Ciclo Diario — Estación: {station_id} — {sub_name} ({stat_tag})"
    else:
        plot_title = f"Ciclo Climatológico Diario — Estación: {station_id} ({stat_tag})"

    ax.set_title(plot_title, fontweight="bold", fontsize=12, pad=12)
    ax.legend(loc="upper right", framealpha=0.9, facecolor="white", edgecolor=COLOR_GRID, fontsize=9.5)
    ax.grid(True, linestyle="--", alpha=0.35, color="#CBD5E1")
    _apply_boxed_spines(ax)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close()
    return out_png


def plot_climatology_doy_station_tripanel(
    data_or_csv: Union[str, pd.DataFrame],
    arg2: str,
    arg3: str,
    out_png: str,
    title: Optional[str] = None,
) -> str:
    """
    Genera el panel multi-curva DOY (Acumulado, Máximo, Media, Mínimo) para una estación con colores pastel.
    Soporta modo anual (DOY 1–365), temporadas climáticas y meses individuales.
    Acepta (df, station_id, var, out_png) o (csv_path, var, station_id, out_png).
    """
    if isinstance(data_or_csv, str):
        df_doy = pd.read_csv(data_or_csv)
    else:
        df_doy = data_or_csv

    known_vars = ["tmax", "tmin", "precip", "tmean"]
    if arg2.lower() in known_vars:
        var = arg2
        station_id = arg3
    elif arg3.lower() in known_vars:
        var = arg3
        station_id = arg2
    else:
        var = arg2
        station_id = arg3

    doy = df_doy["doy"].values
    is_precip = "precip" in var.lower()
    xlim, ticks, tick_labels, xlabel, sub_name = _get_doy_axis_config(df_doy)

    if is_precip:
        if "obs_accum" in df_doy.columns:
            stats_labels = [
                ("accum", "Acumulado Progresivo de Precipitación", "mm"),
                ("max", "Máximo Diario Climatológico", "mm/día"),
                ("mean", "Promedio Diario Climatológico", "mm/día"),
            ]
            fig, axes = plt.subplots(3, 1, figsize=(11, 10), dpi=300, sharex=True)
        else:
            stats_labels = [
                ("max", "Máximo Diario Climatológico", "mm/día"),
                ("mean", "Promedio Diario Climatológico", "mm/día"),
            ]
            fig, axes = plt.subplots(2, 1, figsize=(11, 7.5), dpi=300, sharex=True)
    else:
        # Temperatura: siempre 3 paneles (Máximo, Media, Mínimo)
        stats_labels = [
            ("max", "Máximo Diario Climatológico", "°C"),
            ("mean", "Media Diaria Climatológica", "°C"),
            ("min", "Mínimo Diario Climatológico", "°C"),
        ]
        fig, axes = plt.subplots(3, 1, figsize=(11, 10), dpi=300, sharex=True)

    if not isinstance(axes, (list, np.ndarray)):
        axes = [axes]

    for ax, (sc, title_sub, unit_sc) in zip(axes, stats_labels):
        obs_col = f"obs_{sc}" if f"obs_{sc}" in df_doy.columns else "obs"
        raw_col = f"raw_{sc}" if f"raw_{sc}" in df_doy.columns else "raw"
        corr_col = f"corr_{sc}" if f"corr_{sc}" in df_doy.columns else "corr"

        ax.plot(doy, df_doy[obs_col], color=COLOR_OBS, linewidth=2.5, marker="o", markersize=3.0, label="Observado (Estación)", zorder=3)
        ax.plot(doy, df_doy[corr_col], color=COLOR_CORR, linewidth=2.0, label="Corregido (CDT)", zorder=4)
        ax.plot(doy, df_doy[raw_col], color=COLOR_RAW, linewidth=1.8, linestyle="--", label="Original (Raw)", zorder=2)

        if sc == "mean" and "obs_std" in df_doy.columns:
            mean_v = df_doy["obs_mean"].values if "obs_mean" in df_doy.columns else df_doy[obs_col].values
            std_v = df_doy["obs_std"].values
            lower_v = np.maximum(0.0, mean_v - std_v) if is_precip else (mean_v - std_v)
            ax.fill_between(doy, lower_v, mean_v + std_v, color=COLOR_ENV, alpha=0.3, label="Variabilidad ±1σ")

        if is_precip and sc in ["accum", "max", "mean"]:
            ax.set_ylim(bottom=0.0)

        ax.set_ylabel(f"{var.upper()} ({unit_sc})", fontweight="bold", fontsize=9.5, color=COLOR_OBS)
        ax.set_title(f"{title_sub}", fontweight="bold", fontsize=10.5, loc="left", color=COLOR_OBS)
        ax.grid(True, linestyle="--", alpha=0.3, color="#CBD5E1")
        ax.legend(loc="upper right", fontsize=8.5, framealpha=0.85)
        _apply_boxed_spines(ax)

    axes[-1].set_xticks(ticks)
    axes[-1].set_xticklabels(tick_labels, fontsize=10, fontweight="bold", color=COLOR_OBS)
    axes[-1].set_xlim(xlim[0], xlim[1])
    axes[-1].set_xlabel(xlabel, fontweight="bold", fontsize=11, color=COLOR_OBS)

    if title:
        plot_title = title
    elif sub_name:
        plot_title = f"Ciclo Diario — Estación: {station_id} — {sub_name}"
    else:
        plot_title = f"Ciclo Climatológico Diario Multianual (DOY 1–365) — Estación: {station_id}"

    fig.suptitle(plot_title, fontsize=13.5, fontweight="bold", y=0.995)
    plt.tight_layout()

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close()
    return out_png

