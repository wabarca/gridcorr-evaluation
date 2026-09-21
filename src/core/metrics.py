# -*- coding: utf-8 -*-
"""
Scientific metrics and statistical evaluation module.
Implements standard error metrics, hydrological efficiency (KGE, NSE),
agreement indices (Willmott d1), precipitation detection (POD, FAR, CSI, FBI),
and extreme quantile diagnostics.
"""

import os
import re
from typing import List, Tuple, Optional, Dict, Any, Union
import numpy as np
import pandas as pd


# ==============================================================================
# 1. MÉTRICAS BÁSICAS Y DE EFICIENCIA CONTINUA
# ==============================================================================

def compute_metrics(obs: np.ndarray, grid: np.ndarray) -> Tuple[float, float, float]:
    """
    Calcula métricas básicas de error entre observaciones y valores en rejilla.

    Fórmulas:
    - Bias = mean(grid - obs)
    - MAE  = mean(|grid - obs|)
    - RMSE = sqrt(mean((grid - obs)^2))
    """
    obs = np.asarray(obs, dtype=float)
    grid = np.asarray(grid, dtype=float)
    mask = np.isfinite(obs) & np.isfinite(grid)
    if not np.any(mask):
        return np.nan, np.nan, np.nan

    diff = grid[mask] - obs[mask]
    bias = float(np.mean(diff))
    mae = float(np.mean(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(diff**2)))
    return bias, mae, rmse


def compute_pbias(obs: np.ndarray, grid: np.ndarray) -> float:
    """
    Calcula el Sesgo Porcentual Relativo (PBIAS).
    PBIAS = 100 * sum(grid - obs) / sum(obs)
    """
    obs = np.asarray(obs, dtype=float)
    grid = np.asarray(grid, dtype=float)
    mask = np.isfinite(obs) & np.isfinite(grid)
    if not np.any(mask):
        return np.nan

    sum_obs = np.sum(obs[mask])
    if abs(sum_obs) < 1e-9:
        return 0.0
    return float(100.0 * np.sum(grid[mask] - obs[mask]) / sum_obs)


def compute_nse(obs: np.ndarray, grid: np.ndarray, min_valid_samples: int = 3) -> float:
    """
    Calcula la Eficiencia de Nash-Sutcliffe (NSE).
    NSE = 1 - sum((grid - obs)^2) / sum((obs - mean(obs))^2)
    """
    obs = np.asarray(obs, dtype=float)
    grid = np.asarray(grid, dtype=float)
    mask = np.isfinite(obs) & np.isfinite(grid)
    if np.sum(mask) < min_valid_samples:
        return np.nan

    o, g = obs[mask], grid[mask]
    denom = np.sum((o - np.mean(o)) ** 2)
    if denom < 1e-9:
        return np.nan
    num = np.sum((g - o) ** 2)
    return float(1.0 - (num / denom))


def compute_willmott_d1(obs: np.ndarray, grid: np.ndarray, min_valid_samples: int = 3) -> float:
    """
    Calcula el Índice de Concordancia Modificado de Willmott (d1, Willmott et al., 2012).
    d1 = 1 - sum(|grid - obs|) / sum(|grid - mean(obs)| + |obs - mean(obs)|)
    Rango: [0, 1], Óptimo = 1.0.
    """
    obs = np.asarray(obs, dtype=float)
    grid = np.asarray(grid, dtype=float)
    mask = np.isfinite(obs) & np.isfinite(grid)
    if np.sum(mask) < min_valid_samples:
        return np.nan

    o, g = obs[mask], grid[mask]
    mean_o = np.mean(o)
    num = np.sum(np.abs(g - o))
    denom = np.sum(np.abs(g - mean_o) + np.abs(o - mean_o))
    if denom < 1e-9:
        return 1.0 if num < 1e-9 else 0.0
    return float(1.0 - (num / denom))


def compute_kge(
    obs: np.ndarray, grid: np.ndarray, modified: bool = False, min_valid_samples: int = 3
) -> Tuple[float, float, float, float]:
    """
    Calcula la Eficiencia de Kling-Gupta (KGE) y sus 3 componentes descompuestos:
    KGE = 1 - sqrt((r - 1)^2 + (alpha_or_gamma - 1)^2 + (beta - 1)^2)

    donde:
    - r: correlación de Pearson
    - alpha = std(grid) / std(obs) (KGE 2009) o gamma = CV(grid) / CV(obs) (KGE 2012 modificado)
    - beta = mean(grid) / mean(obs)

    Retorna
    -------
    (kge, r, alpha_or_gamma, beta)
    """
    obs = np.asarray(obs, dtype=float)
    grid = np.asarray(grid, dtype=float)
    mask = np.isfinite(obs) & np.isfinite(grid)
    if np.sum(mask) < min_valid_samples:
        return np.nan, np.nan, np.nan, np.nan

    o, g = obs[mask], grid[mask]
    std_o = np.std(o, ddof=1)
    std_g = np.std(g, ddof=1)
    mean_o = np.mean(o)
    mean_g = np.mean(g)

    # Correlación r
    if std_o < 1e-9 or std_g < 1e-9:
        r = 0.0
    else:
        denom_r = np.sqrt(np.sum((o - mean_o) ** 2) * np.sum((g - mean_g) ** 2))
        r = float(np.clip(np.sum((o - mean_o) * (g - mean_g)) / denom_r, -1.0, 1.0)) if denom_r > 1e-9 else 0.0

    # Ratio de sesgo beta
    if abs(mean_o) < 1e-9:
        beta = 1.0 if abs(mean_g) < 1e-9 else float(mean_g)
    else:
        beta = float(mean_g / mean_o)

    # Ratio de dispersión alpha o gamma
    if modified:
        cv_o = std_o / mean_o if abs(mean_o) > 1e-9 else 1.0
        cv_g = std_g / mean_g if abs(mean_g) > 1e-9 else 1.0
        alpha_val = float(cv_g / cv_o) if abs(cv_o) > 1e-9 else 1.0
    else:
        alpha_val = float(std_g / std_o) if std_o > 1e-9 else 1.0

    kge = float(1.0 - np.sqrt((r - 1.0) ** 2 + (alpha_val - 1.0) ** 2 + (beta - 1.0) ** 2))
    return kge, r, alpha_val, beta


# ==============================================================================
# 2. MÉTRICAS CATEGÓRICAS DE DETECCIÓN DE LLUVIA (CHIRPS)
# ==============================================================================

def compute_rain_detection_metrics(
    obs: np.ndarray, grid: np.ndarray, threshold: float = 1.0
) -> Dict[str, float]:
    """
    Calcula la tabla de contingencia y métricas categóricas de detección de lluvia:
    - Hits (H): obs >= th y grid >= th
    - False Alarms (F): obs < th y grid >= th
    - Misses (M): obs >= th y grid < th
    - Correct Negatives (C): obs < th y grid < th

    Métricas derivadas:
    - POD (Probability of Detection / Hit Rate) = H / (H + M)
    - FAR (False Alarm Ratio) = F / (H + F)
    - CSI (Critical Success Index / Threat Score) = H / (H + M + F)
    - FBI (Frequency Bias Index) = (H + F) / (H + M)
    - ETS (Equitable Threat Score)
    - Accuracy = (H + C) / (H + F + M + C)
    """
    obs = np.asarray(obs, dtype=float)
    grid = np.asarray(grid, dtype=float)
    mask = np.isfinite(obs) & np.isfinite(grid)
    if not np.any(mask):
        return {
            "POD": np.nan, "FAR": np.nan, "CSI": np.nan, "FBI": np.nan,
            "ETS": np.nan, "Accuracy": np.nan, "Hits": 0, "FalseAlarms": 0,
            "Misses": 0, "CorrectNegatives": 0, "Threshold": threshold
        }

    o, g = obs[mask], grid[mask]
    obs_rain = o >= threshold
    grid_rain = g >= threshold

    h = int(np.sum(obs_rain & grid_rain))
    f = int(np.sum(~obs_rain & grid_rain))
    m = int(np.sum(obs_rain & ~grid_rain))
    c = int(np.sum(~obs_rain & ~grid_rain))
    total = h + f + m + c

    pod = float(h / (h + m)) if (h + m) > 0 else np.nan
    far = float(f / (h + f)) if (h + f) > 0 else np.nan
    csi = float(h / (h + m + f)) if (h + m + f) > 0 else np.nan
    fbi = float((h + f) / (h + m)) if (h + m) > 0 else np.nan
    acc = float((h + c) / total) if total > 0 else np.nan

    # ETS (Equitable Threat Score)
    hits_random = float((h + m) * (h + f) / total) if total > 0 else 0.0
    denom_ets = (h + m + f - hits_random)
    ets = float((h - hits_random) / denom_ets) if denom_ets > 0 else np.nan

    return {
        "POD": pod,
        "FAR": far,
        "CSI": csi,
        "FBI": fbi,
        "ETS": ets,
        "Accuracy": acc,
        "Hits": h,
        "FalseAlarms": f,
        "Misses": m,
        "CorrectNegatives": c,
        "Threshold": threshold,
    }


# ==============================================================================
# 3. MÉTRICAS DE CUANTILES Y EXTREMOS
# ==============================================================================

def compute_quantiles_metrics(
    obs: np.ndarray, grid: np.ndarray, quantiles: Tuple[float, ...] = (0.90, 0.95, 0.99)
) -> Dict[str, float]:
    """
    Calcula diferencias en cuantiles extremos entre observaciones y rejilla.
    """
    obs = np.asarray(obs, dtype=float)
    grid = np.asarray(grid, dtype=float)
    mask = np.isfinite(obs) & np.isfinite(grid)
    out = {}
    if np.sum(mask) < 5:
        for q in quantiles:
            pct_label = int(q * 100)
            out[f"P{pct_label}_obs"] = np.nan
            out[f"P{pct_label}_grid"] = np.nan
            out[f"Delta_P{pct_label}"] = np.nan
        return out

    o, g = obs[mask], grid[mask]
    for q in quantiles:
        pct_label = int(q * 100)
        p_o = float(np.percentile(o, pct_label))
        p_g = float(np.percentile(g, pct_label))
        out[f"P{pct_label}_obs"] = p_o
        out[f"P{pct_label}_grid"] = p_g
        out[f"Delta_P{pct_label}"] = p_g - p_o

    return out


# ==============================================================================
# 4. RESÚMENES GLOBALES Y POR ESTACIÓN CON MÉTRICAS COMPLETAS
# ==============================================================================

def compute_all_station_metrics(
    obs: np.ndarray,
    raw: np.ndarray,
    corr: np.ndarray,
    rain_threshold: float = 1.0,
    is_precip: bool = False,
    min_valid_samples: int = 3,
) -> Dict[str, Any]:
    """
    Calcula el catálogo completo de métricas continuas, de eficiencia y categóricas
    comparando las observaciones contra el producto crudo y el corregido.
    """
    bias_r, mae_r, rmse_r = compute_metrics(obs, raw)
    bias_c, mae_c, rmse_c = compute_metrics(obs, corr)

    kge_r, r_r, alpha_r, beta_r = compute_kge(obs, raw, min_valid_samples=min_valid_samples)
    kge_c, r_c, alpha_c, beta_c = compute_kge(obs, corr, min_valid_samples=min_valid_samples)

    nse_r = compute_nse(obs, raw, min_valid_samples=min_valid_samples)
    nse_c = compute_nse(obs, corr, min_valid_samples=min_valid_samples)

    d1_r = compute_willmott_d1(obs, raw, min_valid_samples=min_valid_samples)
    d1_c = compute_willmott_d1(obs, corr, min_valid_samples=min_valid_samples)

    pbias_r = compute_pbias(obs, raw)
    pbias_c = compute_pbias(obs, corr)

    delta_rmse = rmse_r - rmse_c if (np.isfinite(rmse_r) and np.isfinite(rmse_c)) else np.nan
    imp_rmse_pct = (100.0 * delta_rmse / rmse_r) if (rmse_r > 0 and np.isfinite(rmse_r)) else np.nan
    delta_kge = kge_c - kge_r if (np.isfinite(kge_c) and np.isfinite(kge_r)) else np.nan
    delta_nse = nse_c - nse_r if (np.isfinite(nse_c) and np.isfinite(nse_r)) else np.nan

    metrics = {
        "Bias_raw": bias_r, "Bias_corr": bias_c, "Delta_Bias": abs(bias_r) - abs(bias_c),
        "MAE_raw": mae_r, "MAE_corr": mae_c, "Delta_MAE": mae_r - mae_c,
        "RMSE_raw": rmse_r, "RMSE_corr": rmse_c, "Delta_RMSE": delta_rmse,
        "Improvement_RMSE_pct": imp_rmse_pct,
        "R_raw": r_r, "R_corr": r_c, "Delta_R": r_c - r_r,
        "KGE_raw": kge_r, "KGE_corr": kge_c, "Delta_KGE": delta_kge,
        "NSE_raw": nse_r, "NSE_corr": nse_c, "Delta_NSE": delta_nse,
        "Willmott_d1_raw": d1_r, "Willmott_d1_corr": d1_c, "Delta_d1": d1_c - d1_r,
        "PBIAS_raw": pbias_r, "PBIAS_corr": pbias_c,
        "Alpha_raw": alpha_r, "Alpha_corr": alpha_c,
        "Beta_raw": beta_r, "Beta_corr": beta_c,
    }

    if is_precip:
        cat_r = compute_rain_detection_metrics(obs, raw, threshold=rain_threshold)
        cat_c = compute_rain_detection_metrics(obs, corr, threshold=rain_threshold)
        metrics.update({
            "POD_raw": cat_r["POD"], "POD_corr": cat_c["POD"], "Delta_POD": cat_c["POD"] - cat_r["POD"],
            "FAR_raw": cat_r["FAR"], "FAR_corr": cat_c["FAR"], "Delta_FAR": cat_r["FAR"] - cat_c["FAR"],
            "CSI_raw": cat_r["CSI"], "CSI_corr": cat_c["CSI"], "Delta_CSI": cat_c["CSI"] - cat_r["CSI"],
            "FBI_raw": cat_r["FBI"], "FBI_corr": cat_c["FBI"],
        })

    return metrics


def summarize_daily_global(df_daily: pd.DataFrame, var: str, rain_threshold: float = 1.0) -> pd.DataFrame:
    """
    Calcula métricas globales diarias de desempeño extendidas para producto original y corregido.
    """
    is_precip = "precip" in var.lower() or "lluvia" in var.lower()
    res_dict = compute_all_station_metrics(
        df_daily["obs"].values, df_daily["raw"].values, df_daily["corr"].values,
        rain_threshold=rain_threshold, is_precip=is_precip
    )
    res_dict["var"] = var
    return pd.DataFrame([res_dict])


def summarize_daily_by_station(df_daily: pd.DataFrame, var: str = "tmax", rain_threshold: float = 1.0) -> pd.DataFrame:
    """
    Calcula métricas diarias de desempeño completas agrupadas por estación.
    """
    is_precip = "precip" in var.lower() or "lluvia" in var.lower()
    rows = []
    for sid, g in df_daily.groupby("station_id"):
        m = compute_all_station_metrics(
            g["obs"].values, g["raw"].values, g["corr"].values,
            rain_threshold=rain_threshold, is_precip=is_precip
        )
        m["station_id"] = sid
        m["n"] = len(g)
        rows.append(m)

    df_out = pd.DataFrame(rows)
    if not df_out.empty and "Delta_RMSE" in df_out.columns:
        df_out = df_out.sort_values("Delta_RMSE", ascending=False).reset_index(drop=True)
    return df_out


def compute_annual_metrics_from_csv(
    csv_files: List[str], var: str, stat: str, out_dir: Optional[str] = None
) -> Tuple[pd.DataFrame, Optional[str]]:
    """
    Calcula métricas anuales globales extendidas a partir de CSVs de comparación por estación.
    """
    rows = []
    is_precip = "precip" in var.lower() or "lluvia" in var.lower()

    for csv in csv_files:
        base = os.path.basename(csv)
        m = re.search(r"(19|20)\d{2}", base)
        if not m:
            continue

        year = int(m.group(0))
        df = pd.read_csv(csv)

        obs_col = f"{var}_{stat}_obs"
        if obs_col not in df.columns:
            candidates = [c for c in df.columns if c.endswith("_obs")]
            if candidates:
                obs_col = candidates[0]
            else:
                continue

        obs = df[obs_col].values.astype(float)
        raw = df["grid_raw"].values.astype(float)
        corr = df["grid_corr"].values.astype(float)

        metrics = compute_all_station_metrics(obs, raw, corr, is_precip=is_precip)
        metrics["year"] = int(year)
        rows.append(metrics)

    df_metrics = pd.DataFrame(rows)
    if not df_metrics.empty:
        if "year" in df_metrics.columns:
            cols = ["year"] + [c for c in df_metrics.columns if c != "year"]
            df_metrics = df_metrics[cols]
        df_metrics = df_metrics.sort_values("year").reset_index(drop=True)

    out_csv = None
    if out_dir is not None and not df_metrics.empty:
        os.makedirs(out_dir, exist_ok=True)
        out_csv = os.path.join(out_dir, f"metrics_annual_{var}_{stat}.csv")
        df_metrics.to_csv(out_csv, index=False, float_format="%.4f")

    return df_metrics, out_csv


def compute_station_metrics_from_csv(
    csv_file: str, var: str, stat: str
) -> pd.DataFrame:
    """
    Calcula métricas de desempeño por estación a partir de un CSV individual.
    """
    df = pd.read_csv(csv_file)
    obs_col = f"{var}_{stat}_obs"
    if obs_col not in df.columns:
        candidates = [c for c in df.columns if c.endswith("_obs")]
        if candidates:
            obs_col = candidates[0]
        else:
            raise KeyError(f"No se encontró columna de observación en {csv_file}")

    obs = df[obs_col].values.astype(float)
    raw = df["grid_raw"].values.astype(float)
    corr = df["grid_corr"].values.astype(float)
    stations = df["station_id"].astype(str).values
    is_precip = "precip" in var.lower()

    rows = []
    for st in sorted(set(stations)):
        m = stations == st
        o, r, c = obs[m], raw[m], corr[m]
        res = compute_all_station_metrics(o, r, c, is_precip=is_precip)
        res["station_id"] = st
        res["n"] = int(np.sum(np.isfinite(o) & np.isfinite(r)))
        rows.append(res)

    df_out = pd.DataFrame(rows)
    if not df_out.empty and "Delta_RMSE" in df_out.columns:
        df_out = df_out.sort_values("Delta_RMSE", ascending=False).reset_index(drop=True)
    return df_out


def compute_station_metrics_global(
    csv_files: List[str], var: str, stat: str
) -> pd.DataFrame:
    """
    Calcula métricas de desempeño por estación a nivel global combinando múltiples CSVs anuales.
    """
    dfs = [pd.read_csv(c) for c in csv_files]
    df_all = pd.concat(dfs, ignore_index=True)

    obs_col = f"{var}_{stat}_obs"
    if obs_col not in df_all.columns:
        candidates = [c for c in df_all.columns if c.endswith("_obs")]
        if candidates:
            obs_col = candidates[0]
        else:
            raise KeyError("No se encontró columna de observación en los CSVs.")

    obs = df_all[obs_col].values.astype(float)
    raw = df_all["grid_raw"].values.astype(float)
    corr = df_all["grid_corr"].values.astype(float)
    stations = df_all["station_id"].astype(str).values
    is_precip = "precip" in var.lower()

    rows = []
    for st in sorted(set(stations)):
        m = stations == st
        o, r, c = obs[m], raw[m], corr[m]
        res = compute_all_station_metrics(o, r, c, is_precip=is_precip)
        res["station_id"] = st
        res["n"] = int(np.sum(np.isfinite(o) & np.isfinite(r)))
        rows.append(res)

    df_out = pd.DataFrame(rows)
    if not df_out.empty and "Delta_RMSE" in df_out.columns:
        df_out = df_out.sort_values("Delta_RMSE", ascending=False).reset_index(drop=True)
    return df_out
