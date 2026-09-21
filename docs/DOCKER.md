# Manual de Operación con Docker

**Plataforma de Evaluación y Corrección Climatológica (GridCorr)**  
*Ministerio de Medio Ambiente y Recursos Naturales (MARN) — El Salvador*

---

## 1. Introducción

El entorno en Docker proporciona aislamiento completo, portabilidad entre servidores del MARN y encapsulación de las dependencias geoespaciales complejas (GEOS, PROJ, NetCDF, Cartopy).

---

## 2. Construcción de la Imagen

Desde la raíz del repositorio:

```bash
docker build -t gridcorr:1.0.0 .
```

La imagen base `python:3.10-slim` compila de manera reproducible todas las extensiones requeridas sin dejar capas innecesarias gracias al `.dockerignore`.

---

## 3. Ejecución del Contenedor

### 3.1 Interfaz Web (Streamlit)
```bash
docker run -d \
    --name gridcorr_app \
    -p 8501:8501 \
    -v $(pwd)/DATA:/app/DATA:ro \
    -v $(pwd)/salidas:/app/salidas:rw \
    gridcorr:1.0.0
```

Acceder desde el navegador: `http://localhost:8501`

### 3.2 Modo Línea de Comandos (CLI) dentro de Docker
Es posible ejecutar análisis por lotes directamente dentro del contenedor sin abrir la interfaz gráfica:

```bash
# Ejecutar análisis CHIRPS
docker run --rm \
    -v $(pwd)/DATA:/app/DATA:ro \
    -v $(pwd)/salidas:/app/salidas:rw \
    gridcorr:1.0.0 \
    python -m src.cli chirps \
    --raw DATA/el_salvador/CHIRPS_raw \
    --corr DATA/el_salvador/CHIRPS_merged \
    --cdt DATA/el_salvador/precip_diaria_el_salvador.csv \
    --dem DATA/el_salvador/dem/dem_esa_1km.nc \
    --out salidas/docker_chirps
```

---

## 4. Uso con Docker Compose

El archivo `compose.yaml` permite levantar y gestionar la plataforma con un solo comando:

```bash
# Iniciar servicios
docker compose up -d

# Consultar estado de salud (healthcheck)
docker compose ps

# Ver registros de ejecución
docker compose logs -f

# Detener el contenedor
docker compose down
```
