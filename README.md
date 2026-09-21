# CHIRTS & CHIRPS Evaluation & Visualization Platform

#### ✍️ Autor y Desarrollador:
- **William Abarca**
- **Afiliación**: Gerencia de Meteorología, Observatorio de Amenazas y Recursos Naturales, Ministerio de Medio Ambiente y Recursos Naturales (MARN), El Salvador
- **Contacto**: abarca.will@gmail.com

---

Plataforma integral en Python para la **evaluación, comparación, diagnóstico y visualización** de productos grillados climatológicos (**CHIRTS** para temperatura y **CHIRPS** para precipitación) en su versión original vs. versión corregida mediante la metodología CDT (*Climate Data Tool*), utilizando observaciones meteorológicas terrestres.

La plataforma cuenta con una **interfaz gráfica web moderna e interactiva en Streamlit** y una **interfaz de línea de comandos (CLI)** retrocompatible sobre una arquitectura modular por capas.

---

## 📌 Características Principales

- **Interfaz Gráfica Web Interactiva**:
  - Configuración visual de parámetros, variables y fechas.
  - Preajustes (*presets*) de datos de ejemplo locales para pruebas rápidas.
  - Validación previa inteligente de rutas y compatibilidad de archivos.
  - Barra de progreso con logs en tiempo real.
  - Visores interactivos de mapas cartográficos lado a lado con relieve DEM (*hillshade*).
  - Explorador dinámico de ciclos climatológicos diarios (**DOY 1–365**) por estación en panel simple y tri-panel ($\text{max} / \text{mean} / \text{min}$) con envolventes $\pm 1\sigma$.
  - Tablas de métricas y rankings ordenados por mejora en error cuadrático medio ($\Delta\text{RMSE}$).
  - Centro de descargas para imágenes individuales, tablas CSV y paquetes ZIP completos.
- **Preservación Científica**:
  - Cálculos matemáticos vectorizados y estrictos de *Bias*, *MAE*, *RMSE*, *Pearson $R$*, $\Delta\text{RMSE}$ y porcentaje de mejora ($\%\text{ Mejora}$).
  - Manejo riguroso de datos faltantes (`-99`, `NA`, `NaN`) y conteo de días válidos.
  - Extracción en coordenadas de estaciones mediante vecino más cercano (*nearest-neighbor*).
- **Múltiples Modos de Operación**:
  - `annual`: Mapas y estadísticas anuales con diagnóstico global y por año.
  - `daily`: Mapa y comparación para una fecha específica (`YYYY-MM-DD`).
  - `daily-eval`: Construcción paralela de series diarias completas multianuales y climatología DOY.
  - `period`: Análisis por temporadas climáticas del Foro del Clima Centroamericano (`DJFM`, `A`, `MJJ`, `ASO`, `N`) o meses específicos.

---

## 🏛️ Arquitectura del Sistema

```
┌────────────────────────────────────────────────────────┐
│                   GUI (Streamlit)                      │
│        (app.py / src/gui/components/...)               │
└───────────────────────────┬────────────────────────────┘
                            │ (AnalysisRequest)
                            ▼
┌────────────────────────────────────────────────────────┐
│                  Application Layer                     │
│    (src/application/models.py, validators.py, services)│
└───────────┬───────────────────────────────┬────────────┘
            │                               │
            ▼                               ▼
┌──────────────────────────┐    ┌────────────────────────┐
│     Scientific Core      │    │     Data / IO Layer    │
│  - src/core/metrics.py   │    │  - src/io/cdt_parser.py│
│  - src/core/spatial.py   │    │  - src/io/netcdf_loader│
│  - src/core/climatology  │    │  - src/io/exporters.py │
└───────────┬──────────────┘    └────────────────────────┘
            ▼
┌──────────────────────────┐
│   Visualization Layer    │
│  - src/visualization/maps│
│  - src/visualization/plot│
└──────────────────────────┘
```

---

## ⚙️ Guía Rápida de Instalación

Para instrucciones completas y detalladas por sistema operativo, consulte [docs/INSTALLATION.md](file:///docs/INSTALLATION.md).

### 1. Requisitos Previos

- **Python**: Versión 3.10, 3.11 o 3.12.
- **Git**: Para clonar el repositorio.

---

### 2. Métodos de Instalación

#### Opción A: Con Conda o Mamba (Recomendado para Windows / Escritorio)

Conda gestiona de forma automática las bibliotecas binarias C/C++ de Cartopy, GEOS y PROJ:

```bash
# 1. Clonar el repositorio
git clone https://github.com/wabarca/gridcorr-evaluation.git
cd gridcorr-evaluation

# 2. Crear y activar el entorno virtual
conda env create -f environment.yml
conda activate chirpts-evaluation

# 3. Instalar el paquete en modo editable con herramientas de desarrollo
pip install -e ".[dev]"
```

*Nota: Con `mamba` el proceso de resolución de paquetes es más rápido:*
```bash
mamba env create -f environment.yml
mamba activate chirpts-evaluation
pip install -e ".[dev]"
```

---

#### Opción B: Con Python `venv` y `pip` (Linux / macOS / WSL)

**Paso previo en Ubuntu / Debian**: Instalar bibliotecas de sistema requeridas para Cartopy y NetCDF:
```bash
sudo apt-get update && sudo apt-get install -y \
    python3-venv python3-pip \
    libgeos-dev libproj-dev proj-data proj-bin libnetcdf-dev libhdf5-dev
```

**Instalación del entorno Python**:
```bash
# 1. Crear el entorno virtual
python3 -m venv .venv

# 2. Activar el entorno
# En Linux/macOS:
source .venv/bin/activate
# En Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# 3. Actualizar herramientas base
pip install --upgrade pip setuptools wheel

# 4. Instalar dependencias del proyecto
pip install -r requirements.txt
pip install -e ".[dev]"
```

---

#### Opción C: Con Docker y Docker Compose (Sin configurar dependencias locales)

Si cuenta con Docker Desktop o Docker Engine:

```bash
# 1. Clonar el repositorio
git clone https://github.com/wabarca/gridcorr-evaluation.git
cd gridcorr-evaluation

# 2. Levantar la aplicación web con Docker Compose
docker compose up -d --build
```
La aplicación web estará disponible inmediatamente en `http://localhost:8501`.

---

### 3. Verificación de la Instalación

Compruebe que la instalación fue exitosa ejecutando las pruebas automatizadas y el comando CLI:

```bash
# Ejecutar suite de pruebas unitarias y científicas (12 tests)
pytest -v

# Verificar la CLI del sistema
gridcorr --help
```


---

## ▶️ Ejecución

### 1. Interfaz Gráfica (Streamlit)

Para iniciar el dashboard interactivo en su navegador web:

```bash
streamlit run app.py
```

Acceda a `http://localhost:8501`. Desde el panel lateral izquierdo puede seleccionar los datos de prueba o ingresar sus propias rutas, validar los datos y ejecutar el análisis.

---

### 2. Línea de Comandos (CLI)

Los scripts originales continúan funcionando exactamente igual sobre la nueva arquitectura modular:

#### A) Evaluación de CHIRPS (Precipitación acumulada anual)
```bash
python mapas_acumulados_chirps_anuales.py \
  --csv DATA/centroamerica/datos/station_data/lluvia_formato_cdt_elsalvador.csv \
  --dir-chirps DATA/centroamerica/cdt_original_data/CHIRPSv2_CDT_NetCDF_Format \
  --dir-merged DATA/centroamerica/cdt_corrected_data/CHIRPSv2_pr_MERGED_RAIN_Data_1ene1991_31dic2020/DATA \
  --yini 1991 \
  --yend 2020 \
  --out ./salidas_chirps \
  --export-csv
```

#### B) Evaluación de CHIRTS (Temperatura: Anual con Evaluación Estadística)
```bash
python mapas_acumulados_chirts_anuales.py \
  --csv DATA/centroamerica/datos/station_data/tmax_formato_cdt_elsalvador.csv \
  --dir-chirts DATA/centroamerica/cdt_original_data/CHIRTS_TMax_CDT_NetCDF_Format \
  --dir-merged DATA/centroamerica/cdt_corrected_data/CHIRTS_tmax_MERGED_TEMP_Data_1ene1991_31dic2020/DATA \
  --var tmax \
  --stat mean \
  --dem DATA/centroamerica/datos/dem/gebco_2024_el_salvador.nc \
  --mode annual \
  --yini 1991 \
  --yend 2020 \
  --out ./salidas_chirts \
  --eval
```

#### C) Evaluación de CHIRTS Diaria Puntual (`daily`)
```bash
python mapas_acumulados_chirts_anuales.py \
  --csv DATA/centroamerica/datos/station_data/tmax_formato_cdt_elsalvador.csv \
  --dir-chirts DATA/centroamerica/cdt_original_data/CHIRTS_TMax_CDT_NetCDF_Format \
  --dir-merged DATA/centroamerica/cdt_corrected_data/CHIRTS_tmax_MERGED_TEMP_Data_1ene1991_31dic2020/DATA \
  --var tmax \
  --stat daily \
  --dem DATA/centroamerica/datos/dem/gebco_2024_el_salvador.nc \
  --mode daily \
  --date 1991-01-01 \
  --out ./salidas_chirts_daily
```

#### D) Evaluación CHIRTS Serie Completa y DOY Climatología (`daily-eval`)
```bash
python mapas_acumulados_chirts_anuales.py \
  --csv DATA/centroamerica/datos/station_data/tmax_formato_cdt_elsalvador.csv \
  --dir-chirts DATA/centroamerica/cdt_original_data/CHIRTS_TMax_CDT_NetCDF_Format \
  --dir-merged DATA/centroamerica/cdt_corrected_data/CHIRTS_tmax_MERGED_TEMP_Data_1ene1991_31dic2020/DATA \
  --var tmax \
  --mode daily-eval \
  --out ./salidas_daily_eval
```

#### E) Evaluación CHIRTS por Temporadas Climáticas o Meses (`period`)
```bash
# Por temporada (ej. DJFM):
python mapas_acumulados_chirts_anuales.py \
  --csv DATA/centroamerica/datos/station_data/tmax_formato_cdt_elsalvador.csv \
  --dir-chirts DATA/centroamerica/cdt_original_data/CHIRTS_TMax_CDT_NetCDF_Format \
  --dir-merged DATA/centroamerica/cdt_corrected_data/CHIRTS_tmax_MERGED_TEMP_Data_1ene1991_31dic2020/DATA \
  --var tmax \
  --stat mean \
  --dem DATA/centroamerica/datos/dem/gebco_2024_el_salvador.nc \
  --mode period \
  --period-type season \
  --season DJFM \
  --yini 1991 \
  --yend 2020 \
  --out ./salidas_period \
  --eval

# Por meses específicos (ej. mayo, junio, julio):
python mapas_acumulados_chirts_anuales.py \
  --csv DATA/centroamerica/datos/station_data/tmax_formato_cdt_elsalvador.csv \
  --dir-chirts DATA/centroamerica/cdt_original_data/CHIRTS_TMax_CDT_NetCDF_Format \
  --dir-merged DATA/centroamerica/cdt_corrected_data/CHIRTS_tmax_MERGED_TEMP_Data_1ene1991_31dic2020/DATA \
  --var tmax \
  --stat mean \
  --dem DATA/centroamerica/datos/dem/gebco_2024_el_salvador.nc \
  --mode period \
  --period-type months \
  --months 5,6,7 \
  --yini 1991 \
  --yend 2020 \
  --out ./salidas_period \
  --eval
```

#### F) CLI Unificado
```bash
python -m src.cli chirts --help
python -m src.cli chirps --help
```

---

## 📊 Métricas Estadísticas Implementadas

Sea $o_i$ el valor observado en estación y $g_i$ el valor en rejilla para el día o período $i$:

- **Sesgo (*Bias*)**:
  $$\text{Bias} = \frac{1}{N} \sum_{i=1}^{N} (g_i - o_i)$$
- **Error Absoluto Medio (*MAE*)**:
  $$\text{MAE} = \frac{1}{N} \sum_{i=1}^{N} |g_i - o_i|$$
- **Raíz del Error Cuadrático Medio (*RMSE*)**:
  $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} (g_i - o_i)^2}$$
- **Diferencia de RMSE ($\Delta\text{RMSE}$)**:
  $$\Delta\text{RMSE} = \text{RMSE}_{\text{raw}} - \text{RMSE}_{\text{corr}}$$
  *(Valores positivos indican que la corrección redujo el error).*
- **Mejora Relativa Porcentual ($\%\text{ Mejora}$)**:
  $$\%\text{ Mejora} = 100 \times \frac{\text{RMSE}_{\text{raw}} - \text{RMSE}_{\text{corr}}}{\text{RMSE}_{\text{raw}}}$$
- **Coeficiente de Correlación de Pearson ($R$)**:
  $$R = \frac{\sum (o_i - \bar{o})(g_i - \bar{g})}{\sqrt{\sum (o_i - \bar{o})^2 \sum (g_i - \bar{g})^2}}$$

---

## 🧪 Pruebas Automatizadas

Para ejecutar la suite completa de pruebas unitarias y de regresión científica:

```bash
pytest -v tests/
```

Las pruebas validan:
- Parseo correcto de metadatos y series temporales en formato CDT.
- Cálculo exacto de métricas analíticas.
- Generación y cruce de fechas de temporadas climáticas.
- Validadores de parámetros de entrada.
- Equivalencia numérica estricta entre el nuevo *Scientific Core* y las fórmulas científicas originales.

---

## 🚀 Despliegue (Deployment)

### Despliegue Local o en Servidor Institucional

1. **Configuración de Puerto y Acceso**:
   Puede configurar el puerto y la visibilidad de red mediante el archivo `.streamlit/config.toml` o por argumentos:
   ```bash
   streamlit run app.py --server.port 8501 --server.address 0.0.0.0
   ```

2. **Variables de Entorno Opcionales**:
   - `CHIRPTS_OUT_DIR`: Directorio base predeterminado para guardar salidas.
   - `CHIRPTS_MAX_WORKERS`: Número de procesos paralelos para evaluación multianual (default: 4).
   - `CHIRPTS_DPI_MAPS`: Resolución DPI para mapas (default: 200).
   - `CHIRPTS_DPI_PLOTS`: Resolución DPI para gráficos estadísticos (default: 160).

---

## 📖 Documentación Completa

- [Auditoría del Repositorio](file:///docs/REPOSITORY_AUDIT.md): Análisis detallado del código original, entradas, dependencias y deuda técnica resuelta.
- [Especificación de Arquitectura](file:///docs/ARCHITECTURE.md): Diagrama y especificación de capas de software (GUI, Application, Scientific Core, Data/IO, Visualization).
- [Plan de Implementación](file:///docs/IMPLEMENTATION_PLAN.md): Fases del proyecto, decisiones técnicas y criterios de calidad.
- [Guía de Usuario](file:///docs/USER_GUIDE.md): Manual paso a paso con flujos de trabajo detallados para la interfaz gráfica y la CLI.
- [Entorno de Desarrollo](file:///docs/DEVELOPMENT_ENVIRONMENT.md): Configuración de herramientas, dependencias C/C++ geoespaciales y variables de entorno.
- [Guía de Instalación](file:///docs/INSTALLATION.md): Procedimientos de instalación detallados para Conda, venv/pip y Docker.
- [Guía de Despliegue](file:///docs/DEPLOYMENT.md): Opciones para servidores Linux, Systemd, Nginx reverse proxy y entornos de producción.
- [Manual de Docker](file:///docs/DOCKER.md): Instrucciones para construcción y operación de contenedores con Docker y Docker Compose.
- [Estrategia de Pruebas](file:///docs/TESTING.md): Protocolo de testing, suites unitarias y validación de regresión científica.
