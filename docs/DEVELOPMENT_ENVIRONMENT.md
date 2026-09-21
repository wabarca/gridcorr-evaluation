# Configuración del Entorno de Desarrollo

**Plataforma de Evaluación y Corrección Climatológica (GridCorr)**  
*Ministerio de Medio Ambiente y Recursos Naturales (MARN) — El Salvador*

---

## 1. Visión General del Stack Tecnológico

El proyecto combina computación científica en Python con procesamiento geoespacial raster/vectorial y visualización de datos climatológicos.

| Componente | Herramienta / Librería | Propósito |
| :--- | :--- | :--- |
| **Lenguaje Base** | Python >= 3.10 | Tipado estricto, dataclasses y soporte moderno. |
| **Cálculo Numérico** | NumPy, SciPy | Métricas vectorizadas (RMSE, Bias, Pearson $R$, MAE). |
| **Series Temporales** | Pandas | Manejo de metadatos de estaciones y agregaciones temporales. |
| **Manejo Geoespacial Raster** | NetCDF4, xarray | Lectura y extracción de mallas NetCDF CF-compliant. |
| **Cartografía & SIG** | Cartopy, Matplotlib | Proyecciones geográficas (`PlateCarree`), sombreado de relieve (hillshade). |
| **Evitación de Colisiones** | adjustText | Dispersión visual iterativa de etiquetas de estaciones. |
| **Interfaz Gráfica** | Streamlit | Dashboard interactivo local y desplegable en web. |
| **Testing** | Pytest, Pytest-cov | Pruebas unitarias, de integración y regresión científica. |

---

## 2. Dependencias de Sistema (C/C++ Geospatial Libraries)

`Cartopy` y `NetCDF4` dependen de bibliotecas compiladas C/C++:
- **GEOS** (Geometry Engine Open Source)
- **PROJ** (Cartographic Projections Library)
- **HDF5 / NetCDF-C**

### En Ubuntu / Debian / WSL2:
```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    libgeos-dev \
    libproj-dev \
    proj-data \
    proj-bin \
    libnetcdf-dev \
    libhdf5-dev
```

### En Windows:
La forma recomendada en Windows para evitar compilar C/C++ es usar **Conda / Mamba** o instalar ruedas binarias precompiladas (`wheels`) de GDAL/Cartopy:
```powershell
# Usando Conda/Mamba (Recomendado para Windows):
conda env create -f environment.yml
conda activate gridcorr-env
```

---

## 3. Configuración del Entorno Virtual con Conda (Recomendado)

El archivo `environment.yml` provisto en la raíz del proyecto automatiza la resolución de todas las dependencias geoespaciales:

```bash
# 1. Clonar el repositorio
git clone https://github.com/wabarca/gridcorr-evaluation.git
cd gridcorr-evaluation

# 2. Crear entorno conda
conda env create -f environment.yml

# 3. Activar el entorno
conda activate gridcorr-env

# 4. Instalar el paquete en modo editable con herramientas de desarrollo
pip install -e ".[dev]"
```

---

## 4. Configuración del Entorno Virtual con `venv` y `pip`

Si trabajas en Linux, macOS o WSL2:

```bash
# 1. Crear entorno virtual
python3 -m venv .venv

# 2. Activar entorno
source .venv/bin/activate  # En Windows: .venv\Scripts\Activate.ps1

# 3. Actualizar pip y setuptools
pip install --upgrade pip setuptools wheel

# 4. Instalar dependencias
pip install -r requirements.txt
pip install -e ".[dev]"
```

---

## 5. Variables de Entorno

Copia la plantilla `.env.example` a `.env` para personalizar rutas y configuraciones locales:

```bash
cp .env.example .env
```

Variables disponibles:
- `CHIRPTS_DATA_DIR`: Ruta base predeterminada hacia los datos (por defecto `./DATA`).
- `CHIRPTS_OUT_DIR`: Directorio predeterminado donde se guardarán mapas, gráficos y CSVs (por defecto `./salidas`).
- `CHIRPTS_MAX_WORKERS`: Número de hilos para operaciones paralelas (por defecto `4`).
- `CHIRPTS_DPI_MAPS`: Resolución de exportación en pulgadas de figuras cartográficas (por defecto `300`).
- `STREAMLIT_SERVER_PORT`: Puerto para la interfaz Streamlit (por defecto `8501`).

---

## 6. Verificación del Entorno

Ejecuta el conjunto de pruebas para validar que todas las librerías científicas y geoespaciales funcionen correctamente:

```bash
pytest tests/
```

Para verificar que la CLI responda:
```bash
python -m src.cli --help
```
