# Manual de Usuario y Documentación Científica: GridCorr / CHIRTS & CHIRPS Evaluation Toolkit

**Autor**: William Abarca  
**Afiliación**: Gerencia de Meteorología, Observatorio de Amenazas y Recursos Naturales, Ministerio de Medio Ambiente y Recursos Naturales (MARN), El Salvador  
**Contacto**: abarca.will@gmail.com  

---

## 1. Introducción y Marco General

La plataforma **GridCorr / CHIRTS & CHIRPS Evaluation Toolkit** es una solución científica integral desarrollada para meteorólogos, climatólogos, hidrólogos y analistas geoespaciales. Su propósito central es **evaluar, comparar, validar y diagnosticar el valor agregado de los productos grillados corregidos mediante la herramienta CDT (Climate Data Tool)** frente a los productos satelitales y de reanálisis originales (CHIRPSv2 para precipitación y CHIRTS-daily para temperatura máxima y mínima) y las observaciones in-situ de estaciones meteorológicas terrestres.

---

## 2. Manual de Instalación y Requisitos del Sistema

### 2.1. Requisitos Previos del Sistema
- **Sistemas Operativos:** Linux (Ubuntu 20.04+, Debian 11+, RHEL/CentOS 8+), Windows 10/11 (nativo o WSL2), macOS 12+.
- **Python:** Versiones 3.10, 3.11 o 3.12 (Se recomienda Miniforge / Conda para gestión de binarios geoespaciales C/C++).
- **Memoria RAM:** 4 GB mínimo (8 GB o más recomendado para procesamiento de series diarias multianuales).
- **Espacio en Disco:** ~1 GB para el entorno y dependencias.

### 2.2. Métodos de Instalación

#### Opción A: Vía Conda / Mamba (Recomendada para Windows y Escritorio)
```bash
# 1. Clonar el repositorio
git clone https://github.com/wabarca/gridcorr-evaluation.git
cd gridcorr-evaluation

# 2. Crear y activar el entorno
conda env create -f environment.yml
conda activate chirpts-evaluation

# 3. Instalar paquete en modo desarrollo
pip install -e ".[dev]"
```

#### Opción B: Vía Python `venv` y `pip` (Estándar en Linux / Servidores)
```bash
# 1. Instalar librerías C/C++ del sistema
sudo apt-get update && sudo apt-get install -y \
    python3-venv python3-pip \
    libgeos-dev libproj-dev proj-data proj-bin libnetcdf-dev libhdf5-dev

# 2. Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 3. Instalar dependencias
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -e ".[dev]"
```

#### Opción C: Vía Docker
```bash
docker compose up -d --build
```
Acceso web directo en `http://localhost:8501`.

### 2.3. Verificación de la Suite de Pruebas
```bash
pytest -v
```

---

## 3. Manual de Utilización y Flujo de Trabajo (GUI & CLI)

### 3.1. Iniciar la Interfaz Gráfica Web (GUI)
```bash
streamlit run app.py
```
O ejecutando directamente:
```bash
python app.py
```

### 3.2. Configuración en el Panel Lateral (Sidebar)
1. **Producto Climático:**
   - `CHIRPS (Precipitación)`: Acumulados anuales, días lluviosos, extremos diarios ($\text{Rx1day}$) y detección categórica.
   - `CHIRTS (Temperatura)`: Temperatura máxima (`tmax`) o mínima (`tmin`), promedios anuales, extremos y residuales térmicos con relieve DEM.
2. **Selector de Rutas con Explorador Integrado:**
   - Utilice el botón **"📂 Explorar"** para seleccionar visualmente las rutas del sistema:
     - *Directorio Original (Raw)*
     - *Directorio Corregido (Merged / CDT)*
     - *Archivo CSV de Estaciones*
     - *DEM Topográfico (NetCDF opcional)*
     - *Directorio de Salida*
3. **Período Temporal:** Año individual (ej. `1991`) o rango multianual (ej. `1991-2020`).
4. **Dominio Geográfico y Reglas de Etiquetado:**
   - *Regional (Centroamérica y Caribe, amplitud $> 5^\circ$):* Puntos limpios coloreados según la paleta para evitar saturación.
   - *Nacional (El Salvador, Guatemala, Honduras, amplitud $\le 5^\circ$):* Etiquetas numéricas no superpuestas con líneas conectoras.

### 3.3. Control de Ejecución
- **🔍 Validar Configuración:** Comprueba la existencia y compatibilidad de archivos antes del cálculo.
- **🚀 Ejecutar Análisis:** Procesa el análisis con barra de progreso y consola de eventos en tiempo real.
- **🛑 Detener Cálculo:** Cancela de forma segura un proceso en curso.
- **📂 Visualizar Resultados Existentes:** Carga instantáneamente salidas previas detectadas en el directorio de salida.
- **🗑️ Limpiar y Recalcular:** Elimina salidas anteriores y recalcula desde cero.

### 3.4. Uso por Línea de Comandos (CLI)
```bash
# Modo CHIRPS Precipitación Anual
python -m src.cli chirps --csv DATA/stations.csv --dir-raw DATA/chirps_raw --dir-corr DATA/chirps_mrg --yini 1991 --yend 2020 --out ./salidas_chirps

# Modo CHIRTS Temperatura con DEM
python -m src.cli chirts --csv DATA/stations.csv --dir-raw DATA/tmax_raw --dir-corr DATA/tmax_mrg --var tmax --stat mean --dem DATA/dem.nc --yini 1991 --yend 2020 --out ./salidas_chirts
```

---

## 4. Especificación de los Productos de Entrada

1. **Rejillas NetCDF (Originales y Corregidas por CDT):**
   - Archivos diarios estructurados como `precip_<YYYYMMDD>.nc`, `tmax_mrg_<YYYYMMDD>.nc`, etc.
   - Coordenadas espaciales estándar: `lon` (o `longitude`), `lat` (o `latitude`).
   - Unidades: $\text{mm}$ para precipitación, $^\circ\text{C}$ para temperatura.
   - Valores nulos codificados como `NaN` o `_FillValue = -9999.0`.

2. **Archivo CSV de Observaciones en Estaciones:**
   - Columnas requeridas: `station_id`, `lon`, `lat`, `elev`, `date` (o `year`, `month`, `day`), `value` (o `obs`).
   - Soporte automático para códigos de datos faltantes CDT (`-99`, `-999`, `NA`).

3. **Modelo Digital de Elevación (DEM NetCDF, Opcional):**
   - Rejilla de altitud en metros para sombreado topográfico (*hillshade*) y gradientes térmicos.

---

## 5. Productos y Métricas Calculadas e Interpretación

### 5.1. Métricas de Error Continuo
- **Sesgo Medio ($\text{Bias}$) y Sesgo Porcentual ($\text{PBIAS}$):**
  $$\text{Bias} = \frac{1}{N}\sum_{i=1}^N (S_i - O_i) \qquad \text{PBIAS} = \frac{\sum_{i=1}^N (S_i - O_i)}{\sum_{i=1}^N O_i} \times 100\%$$
  *Interpretación:* Cuantifica la tendencia global a sobrestimar ($>0$) o subestimar ($<0$). $|\text{PBIAS}| < 10\%$ indica calidad excelente en precipitación y $<5\%$ en temperatura.
- **Error Absoluto Medio ($\text{MAE}$):**
  $$\text{MAE} = \frac{1}{N}\sum_{i=1}^N |S_i - O_i|$$
  *Interpretación:* Magnitud promedio lineal del error físico sin sobreponderar valores atípicos.
- **Raíz del Error Cuadrático Medio ($\text{RMSE}$):**
  $$\text{RMSE} = \sqrt{\frac{1}{N}\sum_{i=1}^N (S_i - O_i)^2}$$
  *Interpretación:* Penaliza severamente las grandes discrepancias puntuales y eventos extremos.
- **Mejora Relativa de RMSE ($\%\Delta\text{RMSE}$):**
  $$\text{Mejora \%} = \frac{\text{RMSE}_{\text{original}} - \text{RMSE}_{\text{corregido}}}{\text{RMSE}_{\text{original}}} \times 100\%$$
  *Interpretación:* Porcentaje de error eliminado gracias a la corrección CDT. Valores positivos indican ganancia de precisión.

### 5.2. Métricas de Eficiencia y Concordancia
- **Kling-Gupta Efficiency ($\text{KGE}$ - Gupta et al., 2009; Kling et al., 2012):**
  $$\text{KGE} = 1 - \sqrt{(r - 1)^2 + (\beta - 1)^2 + (\gamma - 1)^2}$$
  Descompone el error en:
  1. Correlación lineal de Pearson ($r$, sincronía temporal).
  2. Razón de sesgo ($\beta = \mu_S / \mu_O$, balance de volumen/media).
  3. Razón de variabilidad ($\gamma = \text{CV}_S / \text{CV}_O$, dispersión relativa).
  *Interpretación:* $\text{KGE} = 1.0$ (Óptimo), $\ge 0.75$ (Excelente), $\ge 0.50$ (Bueno), $> -0.41$ (Mejor que la media observada).
- **Eficiencia de Nash-Sutcliffe ($\text{NSE}$ - Nash & Sutcliffe, 1970):**
  $$\text{NSE} = 1 - \frac{\sum (O_i - S_i)^2}{\sum (O_i - \mu_O)^2}$$
- **Índice de Concordancia Modificado de Willmott ($d_1$ - Willmott et al., 2012):**
  $$d_1 = 1 - \frac{\sum |S_i - O_i|}{2 \sum |O_i - \mu_O|}$$
  *Interpretación:* Índice lineal acotado en $[0, 1]$, robusto ante extremos.

### 5.3. Métricas Categóricas de Detección de Lluvia (CHIRPS)
- **POD (Probability of Detection):** Fracción de días de lluvia real detectados por el satélite (Óptimo = 1.0).
- **FAR (False Alarm Ratio):** Fracción de días de lluvia pronosticados que fueron secos en tierra (Óptimo = 0.0).
- **CSI (Critical Success Index / Threat Score):** Exactitud balanceada de eventos (Óptimo = 1.0).
- **FBI (Frequency Bias Index):** Razón entre eventos pronosticados y eventos reales (Óptimo = 1.0).
- **ETS (Equitable Threat Score):** Habilidad descontando aciertos aleatorios.

---

## 6. Catálogo de Imágenes Generadas y Guía de Interpretación

1. **Mapa Comparativo Lado a Lado (Original vs Corregido en 4K UHD):**
   - *Panel Izquierdo:* Rejilla Original; *Panel Derecho:* Rejilla Corregida; *Puntos:* Estaciones observadas.
   - *Interpretación:* Permite evaluar cómo la corrección CDT redistribuye espacialmente la variable, ajustando sesgos orográficos y homogeneizando valles y montañas.
2. **Mapa de Diferencia Espacial ($\Delta\text{GRID} = \text{Grid}_{\text{corr}} - \text{Grid}_{\text{raw}}$):**
   - Superficie continua divergente (azul = disminución, rojo = incremento) sobre relieve DEM.
   - Etiquetas flotantes muestran el ajuste exacto en estaciones con signo ($+$, $-$).
3. **Mapa de $\Delta\text{GRID}$ en Estaciones sobre DEM:**
   - Muestra la distribución altitudinal de los ajustes puntuales.
4. **Mapa de Residuos en Estaciones ($\text{Residuo} = \text{Grid}_{\text{corr}} - \text{Obs}$):**
   - Diagnóstico del error remanente post-calibración.
5. **Mapa de Mejora Relativa de RMSE ($\%\Delta\text{RMSE}$):**
   - Puntos verdes/azules identifican estaciones con reducción efectiva del error.
6. **Gráficos Estadísticos:** Scatter plots con línea $1:1$, Boxplots de error, y curvas climatológicas de día del año (DOY).

---

## 7. Referencias Bibliográficas Comentadas

1. **Funk, C., et al. (2015).** *The climate hazards group infrared precipitation with stations—a new environmental record for monitoring extremes.* Scientific Data, 2(1), 150066. [DOI: 10.1038/sdata.2015.66](https://doi.org/10.1038/sdata.2015.66)  
   - **¿Por qué es importante?:** Documenta el desarrollo, calibración y archivo del producto CHIRPSv2, combinando nubes frías (CCD), CHPclim y estaciones terrestres.  
   - **Aporte a la herramienta:** Fundamenta la rejilla de precipitación cruda (Raw) evaluada, fijando la resolución espacial estándar de $0.05^\circ$ (~5.5 km).

2. **Funk, C., et al. (2019).** *A high-resolution 1983–2016 Tmax climate data record based on infrared temperatures, stations, and reanalysis data.* Scientific Data, 6(1), 248. [DOI: 10.1038/s41597-019-0252-0](https://doi.org/10.1038/s41597-019-0252-0)  
   - **¿Por qué es importante?:** Presenta el producto térmico satelital global CHIRTS-daily a partir de LST, reanálisis ERA5 y estaciones.  
   - **Aporte a la herramienta:** Define las características base del producto térmico procesado en el módulo de temperatura.

3. **Gupta, H. V., et al. (2009).** *Decomposition of the mean squared error and NSE performance criteria: Implications for improving hydrological modelling.* Journal of Hydrology, 377(1-2), 80–91. [DOI: 10.1016/j.jhydrol.2009.08.003](https://doi.org/10.1016/j.jhydrol.2009.08.003)  
   - **¿Por qué es importante?:** Demuestra que el NSE subestima la variabilidad temporal y propone el coeficiente KGE descomponiendo el error en correlación, sesgo y variabilidad.  
   - **Aporte a la herramienta:** Constituye la métrica principal de eficiencia climática e hidrológica utilizada en la plataforma.

4. **Kling, H., Fuchs, M., & Paulin, M. (2012).** *Runoff conditions in the upper Danube basin under an ensemble of climate change scenarios.* Journal of Hydrology, 424–425, 264–277. [DOI: 10.1016/j.jhydrol.2012.04.011](https://doi.org/10.1016/j.jhydrol.2012.04.011)  
   - **¿Por qué es importante?:** Modifica el KGE original para que el término de variabilidad ($\gamma$) use el coeficiente de variación ($\text{CV}$), eliminando interacciones indeseadas con el sesgo medio.  
   - **Aporte a la herramienta:** Es la formulación refinada de KGE implementada en el código para series de lluvia y temperatura.

5. **Dinku, T., et al. (2018).** *Enhancing National Climate Services (ENACTS) through transforming climate data, products, and services.* Bulletin of the American Meteorological Society, 99(7), S1–S10. [DOI: 10.1175/BAMS-D-16-0158.1](https://doi.org/10.1175/BAMS-D-16-0158.1)  
   - **¿Por qué es importante?:** Presenta el marco metodológico ENACTS / IRI de la Universidad de Columbia, base operativa del software CDT.  
   - **Aporte a la herramienta:** Justifica la metodología de validación cruzada y comparación directa 'Original vs Corregido por CDT'.

6. **Willmott, C. J., Robeson, S. M., & Matsuura, K. (2012).** *A refined index of model performance.* International Journal of Climatology, 32(13), 2088–2094. [DOI: 10.1002/joc.2419](https://doi.org/10.1002/joc.2419)  
   - **¿Por qué es importante?:** Desarrolla el índice modificado lineal $d_1$, robusto frente a valores atípicos severos en comparación con el índice cuadrático $d$ (1981).  
   - **Aporte a la herramienta:** Incorporado para evaluar la concordancia en estaciones con eventos extremos o distribuciones fuertemente asimétricas.

7. **Wilks, D. S. (2011).** *Statistical Methods in the Atmospheric Sciences.* Academic Press (Elsevier), 3rd Edition, 676 pp. [DOI: 10.1016/C2009-0-00031-0](https://doi.org/10.1016/C2009-0-00031-0)  
   - **¿Por qué es importante?:** Texto de referencia mundial para la verificación de pronósticos meteorológicos y campos climatológicos.  
   - **Aporte a la herramienta:** Sustenta el cálculo de la matriz de contingencia $2\times 2$ y las métricas categóricas: POD, FAR, CSI, FBI y ETS.

8. **Moriasi, D. N., et al. (2007).** *Model evaluation guidelines for systematic quantification of accuracy in watershed simulations.* Transactions of the ASABE, 50(3), 885–900. [DOI: 10.13031/2013.23153](https://doi.org/10.13031/2013.23153)  
   - **¿Por qué es importante?:** Establece directrices y rangos cuantitativos de desempeño (Muy Bueno, Bueno, Satisfactorio, No Satisfactorio) para PBIAS, RMSE y NSE.  
   - **Aporte a la herramienta:** Proporciona los umbrales de semaforización y clasificación de calidad de las métricas en la interfaz y tablas resumen.

9. **Nash, J. E., & Sutcliffe, J. V. (1970).** *River flow forecasting through conceptual models part I—A discussion of principles.* Journal of Hydrology, 10(3), 282–290. [DOI: 10.1016/0022-1694(70)90255-6](https://doi.org/10.1016/0022-1694(70)90255-6)  
   - **¿Por qué es importante?:** Introduce el clásico coeficiente de eficiencia NSE.  
   - **Aporte a la herramienta:** Mantiene la comparabilidad histórica con estudios hidrológicos previos.

10. **IRI - International Research Institute for Climate and Society (2020).** *Climate Data Tool (CDT) User Guide and Training Manual.* Columbia University. [Enlace](https://iri.columbia.edu/resources/enacts/cdt-guide/)  
    - **¿Por qué es importante?:** Manual de referencia oficial de la herramienta CDT.  
    - **Aporte a la herramienta:** Sustenta la compatibilidad directa con los esquemas de archivos, convenciones y códigos de datos nulos generados por CDT.

