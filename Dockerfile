# ==============================================================================
# Dockerfile para la Plataforma de Evaluación Climatológica CHIRPS/CHIRTS
# Gerencia de Meteorología - Observatorio de Amenazas y Recursos Naturales (MARN)
# ==============================================================================

FROM python:3.10-slim AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Instalar dependencias del sistema requeridas para Cartopy, NetCDF y Matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libgeos-dev \
    libproj-dev \
    proj-data \
    proj-bin \
    libnetcdf-dev \
    libhdf5-dev \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Copiar requerimientos e instalar dependencias Python
COPY requirements.txt pyproject.toml ./
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Copiar el código fuente del proyecto
COPY . .

# Instalar el paquete en modo editable/estándar
RUN pip install -e .

# Exponer el puerto de Streamlit
EXPOSE 8501

# Healthcheck para verificar el estado del servicio web
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Comando de inicio predeterminado (GUI Streamlit)
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
