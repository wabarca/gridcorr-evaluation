# Guía de Instalación

**Plataforma de Evaluación y Corrección Climatológica (GridCorr)**  
*Ministerio de Medio Ambiente y Recursos Naturales (MARN) — El Salvador*

---

## 1. Requisitos Previos del Sistema

- **Sistema Operativo**: Linux (Ubuntu 20.04+, Debian 11+, RHEL/CentOS 8+), Windows 10/11 (nativo o WSL2), macOS 12+.
- **Python**: Versión 3.10, 3.11 o 3.12.
- **Memoria RAM**: 4 GB mínimo (8 GB recomendado para procesar periodos largos de datos diarios).
- **Almacenamiento**: ~500 MB para entorno y dependencias; espacio adicional según el volumen de archivos NetCDF históricos.

---

## 2. Métodos de Instalación

Puedes instalar la plataforma mediante tres vías:

### Opción A: Vía Conda / Mamba (Recomendada para Usuarios de Escritorio / Windows)

Conda gestiona de forma automática la compilación de bibliotecas espaciales C/C++ (`GEOS`, `PROJ`, `Cartopy`):

```bash
# 1. Clonar el repositorio
git clone https://github.com/wabarca/gridcorr-evaluation.git
cd gridcorr-evaluation

# 2. Crear y activar el entorno Conda
conda env create -f environment.yml
conda activate chirpts-evaluation

# 3. Instalar el paquete en modo editable con herramientas de desarrollo
pip install -e ".[dev]"
```

Si utilizas `mamba`:
```bash
mamba env create -f environment.yml
mamba activate chirpts-evaluation
pip install -e ".[dev]"
```

---

### Opción B: Vía Python `venv` y `pip` (Estándar en Linux / Servidores)

En entornos Linux Debian/Ubuntu, es indispensable instalar previamente las bibliotecas de sistema C/C++:
```bash
sudo apt-get update && sudo apt-get install -y \
    python3-venv python3-pip \
    libgeos-dev libproj-dev proj-data proj-bin libnetcdf-dev libhdf5-dev
```

Luego procede con la instalación del entorno Python:
```bash
# 1. Crear el entorno virtual
python3 -m venv .venv
source .venv/bin/activate  # En Windows: .\.venv\Scripts\Activate.ps1

# 2. Actualizar pip y setuptools
pip install --upgrade pip setuptools wheel

# 3. Instalar requerimientos y paquete local
pip install -r requirements.txt
pip install -e ".[dev]"
```

---

### Opción C: Vía Docker (Sin necesidad de configurar dependencias locales)

Si dispones de Docker instalado:
```bash
# 1. Clonar el repositorio
git clone https://github.com/wabarca/gridcorr-evaluation.git
cd gridcorr-evaluation

# 2. Levantar la aplicación con Docker Compose
docker compose up -d --build
```
La aplicación web estará disponible inmediatamente en `http://localhost:8501`.

---

## 3. Comprobación de la Instalación

Comprueba que los puntos de entrada (CLI y GUI) están disponibles y funcionales:

```bash
# Verificar ayuda de la CLI del sistema
gridcorr --help

# O usando el módulo directamente
python -m src.cli --help

# Ejecutar la suite completa de pruebas unitarias y de regresión científica
pytest -v
```

Si los 12 tests pasan exitosamente (`12 passed`), la instalación ha concluido con total éxito.

---

## 4. Solución de Problemas Frecuentes (Troubleshooting)

### ❌ Error al compilar `cartopy` o `shapely` con `pip` en Windows
- **Causa**: Falta el compilador C++ de Microsoft Visual C++ Build Tools o las librerías binarias GEOS/PROJ.
- **Solución**: Utilice **Conda / Mamba** con `environment.yml` (Opción A), la cual descarga los binarios precompilados automáticamente sin necesidad de compiladores locales.

### ❌ Error de puerto ocupado en Streamlit (`Port 8501 is already in use`)
- **Solución**: Especifique un puerto alternativo:
  ```bash
  streamlit run app.py --server.port 8502
  ```

### ❌ Error `ModuleNotFoundError: No module named 'src'`
- **Solución**: Asegúrese de haber instalado el paquete en modo desarrollo con `pip install -e .` desde la raíz del proyecto, o ejecute agregando el directorio actual a `PYTHONPATH`:
  ```bash
  python -m src.cli --help
  ```

