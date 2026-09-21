# Plan de Implementación por Fases: CHIRPS & CHIRTS Platform

**Proyecto**: CHIRPS & CHIRTS Evaluation & Visualization Platform  
**Autor**: William Abarca  
**Afiliación**: Gerencia de Meteorología, Observatorio de Amenazas y Recursos Naturales, MARN  

---

## Resumen de Fases

| Fase | Título | Estado | Entregables Principales |
|---|---|---|---|
| **FASE 0** | Auditoría y Diseño de Arquitectura | Completado | `docs/REPOSITORY_AUDIT.md`, `docs/ARCHITECTURE.md` |
| **FASE 1** | Refactorización de Scientific Core, IO y Viz | En Progreso | `src/config/`, `src/io/`, `src/core/`, `src/visualization/` |
| **FASE 2** | Construcción de Application Layer | Pendiente | `src/application/models.py`, `validators.py`, `services.py` |
| **FASE 3** | Desarrollo de Interfaz Gráfica (Streamlit) | Pendiente | `src/gui/app.py`, componentes interactivos, `app.py` |
| **FASE 4** | Integración y Wrappers CLI | Pendiente | Compatibilidad de scripts originales y `src/cli.py` |
| **FASE 5** | Suite de Tests y Validación Científica | Pendiente | Pruebas unitarias y de regresión numérica estricta |
| **FASE 6** | Documentación de Usuario y Despliegue | Pendiente | `README.md`, `docs/USER_GUIDE.md`, `environment.yml` |

---

## Detalle de Actividades

### FASE 1: Scientific Core, IO y Visualization
1. `src/config/constants.py`: Definición centralizada de temporadas (`SEASONS`), meses en español, paletas de colores (`RdYlBu_r`, `RdBu_r`, `YlGnBu`), fuentes tipográficas con fallback seguro, niveles de corte y valores de relleno (`FILL_VALUE = -99.0`).
2. `src/io/cdt_parser.py`: Extracción pura de la función `parse_cdt_csv` con soporte para metadatos (`station_id`, `lon`, `lat`, `elev`), conversión a DataFrame largo (*tidy format*) y reemplazo seguro de nulos.
3. `src/io/netcdf_loader.py`: Funciones de carga de NetCDFs (`load_daily_chirts_raw`, `load_daily_chirts_corr`, `load_dem_dataset`) con normalización de coordenadas (`_rename_coords_latlon`).
4. `src/io/exporters.py`: Funciones de exportación de tablas de comparación, resúmenes globales y rankings.
5. `src/core/metrics.py`: Implementación pura y vectorizada de `compute_metrics` (Bias, MAE, RMSE), cálculo de correlación de Pearson $R$, rankings globales y por año.
6. `src/core/spatial.py`: Extracción de observaciones y grillas por vecino más cercano, sumas acumuladas de precipitación anual, medias/máximos/mínimos temporales y sombreado DEM (*hillshade*).
7. `src/core/climatology.py`: Generación de fechas de períodos/temporadas climáticas (`DJFM`, `A`, `MJJ`, `ASO`, `N`, meses específicos) y ciclo diario climatológico DOY (1–365) por estación (`mean`, `max`, `min`, `std`).
8. `src/visualization/maps.py`: Renderizado modular de mapas cartográficos (`plot_side_by_side`, `plot_delta_grid_field`, `plot_delta_grid_at_stations`, `plot_residual_corr_at_stations_with_dem`, `plot_improvement_at_stations_with_dem`).
9. `src/visualization/plots.py`: Generación de figuras estadísticas (`plot_rmse_bars`, `plot_boxplot_errors`, `plot_boxplot_rmse_by_station`, `plot_boxplot_improvement_pct_by_station`, `plot_scatter_obs_vs_grid`, `plot_scatter_rmse_raw_vs_corr`, `plot_scatter_rmse_vs_improvement`, `plot_climatology_doy_station_tripanel`, `plot_climatology_doy_station`).

### FASE 2: Application Layer
1. `src/application/models.py`: Modelos fuertemente tipados con `dataclasses` y `Enums`:
   - `AnalysisRequest` (producto, variable, modo, rutas, fechas, parámetros).
   - `AnalysisResult` (éxito, mensajes, lista de mapas generados, tablas de métricas, dataframes cargados).
   - `ValidationResult` (validez, lista de errores, advertencias).
2. `src/application/validators.py`: Validadores pre-ejecución que verifican existencia de archivos, compatibilidad de columnas en CSVs, validez de fechas y parámetros numéricos.
3. `src/application/services.py`:
   - `ChirpsService`: Servicio para análisis de precipitación acumulada.
   - `ChirtsService`: Servicio para análisis de temperatura (anual, diario, serie completa `daily-eval`, períodos/temporadas) con soporte para callbacks de progreso `(progress_pct, status_text)`.

### FASE 3: Interfaz Gráfica (Streamlit)
1. `src/gui/app.py` & `app.py`:
   - Interfaz con diseño profesional enfocado en el dominio climatológico.
   - Panel lateral con presets automáticos para probar con datos de ejemplo del repositorio o seleccionar rutas personalizadas.
   - Validación interactiva previa antes del procesamiento.
   - Visualización del progreso en tiempo real.
   - Pestañas organizadas para visualización de mapas, estaciones, gráficos DOY, métricas y descarga de resultados (individual o paquete ZIP).

### FASE 4: Wrappers CLI y Compatibilidad
1. Refactorización de `mapas_acumulados_chirps_anuales.py` y `mapas_acumulados_chirts_anuales.py` para invocar la `Application Layer`, manteniendo 100% de retrocompatibilidad con la terminal.
2. Creación de `src/cli.py` como CLI unificado.

### FASE 5: Tests y Validación Numérica
1. Pruebas unitarias de parsers, loaders y métricas.
2. Pruebas de validación de entradas.
3. Pruebas de regresión científica comparando salidas numéricas con tolerancias estrictas (`1e-6`).

### FASE 6: Documentación y Despliegue
1. Actualización de `README.md`.
2. Redacción de `docs/USER_GUIDE.md`.
3. Actualización de `requirements.txt` y `environment.yml`.
