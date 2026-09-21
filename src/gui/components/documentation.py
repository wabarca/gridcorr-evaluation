# -*- coding: utf-8 -*-
"""
Interactive Scientific Documentation, User Manual, and Statistical Justification Component.
Provides complete guides for installation, usage, input data formats, computed metrics,
generated maps interpretation, and an annotated scientific bibliography.
"""

import streamlit as st


def render_scientific_documentation() -> None:
    """
    Renderiza la sección completa e interactiva de documentación científica, manual de usuario
    y justificación de métricas estadísticas en la plataforma Streamlit.
    """
    st.markdown("## 📚 Manual de Usuario, Metodología y Documentación Científica")
    st.markdown(
        """
        Esta sección constituye el compendio técnico y científico integral de la plataforma **GridCorr / CHIRTS & CHIRPS Evaluation Toolkit**.
        Aquí encontrará el manual de instalación, la guía de operación, los formatos de datos requeridos,
        la formulación matemática de los estadísticos calculados, la guía de interpretación de los mapas generados
        y la fundamentación bibliográfica comentada que sustenta cada decisión metodológica.
        """
    )

    doc_tab1, doc_tab2, doc_tab3, doc_tab4, doc_tab5, doc_tab6 = st.tabs([
        "💻 1. Manual de Instalación",
        "🚀 2. Manual de Utilización",
        "📥 3. Productos de Entrada",
        "🧮 4. Productos y Métricas Calculadas",
        "🗺️ 5. Catálogo de Imágenes e Interpretación",
        "📖 6. Referencias Bibliográficas Justificadas",
    ])

    # =========================================================================
    # TAB 1: MANUAL DE INSTALACIÓN
    # =========================================================================
    with doc_tab1:
        st.markdown("### 💻 1. Manual de Instalación y Configuración del Entorno")
        st.markdown(
            r"""
            La plataforma está construida sobre Python 3.10+ y utiliza bibliotecas de procesamiento geoespacial de alto rendimiento
            (`Xarray`, `NetCDF4`, `Cartopy`, `Shapely`, `Matplotlib`, `Streamlit`). A continuación se detallan los requisitos del sistema
            y los métodos de instalación soportados.

            ---

            #### 1.1. Requisitos Previos del Sistema
            - **Sistemas Operativos Soportados:** Linux (Ubuntu 20.04+, Debian 11+, RHEL/CentOS 8+), Windows 10/11 (64 bits nativo o WSL2), macOS 12+ (Apple Silicon o Intel).
            - **Versión de Python:** Python 3.10, 3.11 o 3.12 (Recomendado: Miniforge / Conda para gestión automática de binarios geoespaciales C/C++).
            - **Memoria RAM:** 4 GB mínimo (8 GB o más recomendado para series diarias multianuales).
            - **Almacenamiento en Disco:** ~1 GB para el entorno virtual y dependencias; espacio adicional en función del volumen de archivos NetCDF históricos a procesar.

            ---

            #### 1.2. Métodos de Instalación Paso a Paso

            ##### Opción A: Vía Conda / Mamba (Recomendada para Windows y Escritorio)
            Conda resuelve y compila automáticamente las dependencias binarias geoespaciales (`GEOS`, `PROJ`, `GDAL`, `Cartopy`):

            ```bash
            # 1. Clonar el repositorio del proyecto
            git clone https://github.com/wabarca/gridcorr-evaluation.git
            cd gridcorr-evaluation

            # 2. Crear y activar el entorno virtual con Conda o Mamba
            conda env create -f environment.yml
            conda activate chirpts-evaluation

            # 3. Instalar el paquete en modo editable para desarrollo
            pip install -e ".[dev]"
            ```

            ##### Opción B: Vía Python `venv` y `pip` (Estándar en Servidores Linux)
            En distribuciones Linux Debian/Ubuntu, es indispensable instalar primero las bibliotecas del sistema:

            ```bash
            # 1. Instalar librerías de sistema C/C++ para soporte geoespacial
            sudo apt-get update && sudo apt-get install -y \
                python3-venv python3-pip \
                libgeos-dev libproj-dev proj-data proj-bin libnetcdf-dev libhdf5-dev

            # 2. Crear y activar el entorno virtual
            python3 -m venv .venv
            source .venv/bin/activate

            # 3. Actualizar herramientas base de empaquetado
            pip install --upgrade pip setuptools wheel

            # 4. Instalar dependencias del proyecto
            pip install -r requirements.txt
            pip install -e ".[dev]"
            ```

            ##### Opción C: Vía Docker (Despliegue Aislado sin dependencias locales)
            Si cuenta con Docker y Docker Compose:

            ```bash
            docker compose up -d --build
            ```
            La aplicación web estará disponible inmediatamente en `http://localhost:8501`.

            ---

            #### 1.3. Verificación de la Instalación
            Para corroborar que todos los módulos y algoritmos científicos están funcionando correctamente, ejecute la suite de pruebas unitarias:

            ```bash
            # Ejecutar todas las pruebas con pytest
            pytest -v

            # Ejecutar la aplicación web Streamlit
            streamlit run app.py
            ```
            """
        )

    # =========================================================================
    # TAB 2: MANUAL DE UTILIZACIÓN
    # =========================================================================
    with doc_tab2:
        st.markdown("### 🚀 2. Manual de Utilización y Flujo de Trabajo")
        st.markdown(
            r"""
            La plataforma está diseñada con una arquitectura modular orientada a flujos de trabajo claros e intuitivos.
            Puede operarse tanto desde la **Interfaz Gráfica Web (Streamlit)** como desde la **Línea de Comandos (CLI)**.

            ---

            #### 2.1. Flujo de Trabajo Operativo (Workflow)

            ```
            ┌──────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
            │  1. Carga de Datos   │ ───> │  2. Validación Previa   │ ───> │  3. Ejecución & Cálculo │
            │  (NetCDF & CSV Obs)  │      │  (Estructura y Coorden) │      │  (Métricas & Mapas 4K)  │
            └──────────────────────┘      └─────────────────────────┘      └─────────────────────────┘
                                                                                        │
                                                                                        ▼
            ┌──────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
            │ 6. Exportación ZIP   │ <─── │ 5. Diagnóstico Estación │ <─── │ 4. Visualización Mapas  │
            │ (Datos, Mapas, CSV)  │      │ (Scatter, DOY, Series)  │      │ (Lado a Lado, ΔGRID)    │
            └──────────────────────┘      └─────────────────────────┘      └─────────────────────────┘
            ```

            ---

            #### 2.2. Configuración en el Panel Lateral (Sidebar)

            1. **Selección del Producto Climático:**
               - **CHIRPS (Precipitación):** Procesa archivos diarios de lluvia (`precip_*.nc` o `chirps_*.nc`), calcula acumulados anuales, días lluviosos, máximos diarios anuales y métricas categóricas de detección.
               - **CHIRTS (Temperatura):** Procesa archivos diarios de temperatura máxima (`tmax`) o mínima (`tmin`), calcula promedios anuales, extremos máximos/mínimos y residuales térmicos.
            2. **Rutas de Datos y Explorador Integrado:**
               - Cada campo cuenta con un botón **"📂 Explorar"** que abre un cuadro de diálogo para navegar por el árbol de carpetas del sistema.
               - *Directorio Original (Raw):* Carpeta con los archivos NetCDF satelitales sin corregir.
               - *Directorio Corregido (Merged / CDT):* Carpeta con los archivos NetCDF corregidos con la herramienta CDT.
               - *Archivo de Observaciones (CSV):* Archivo con las mediciones in-situ de estaciones meteorológicas terrestres.
               - *Modelo Digital de Elevación (DEM NetCDF, opcional):* Rejilla topográfica para sombreado de relieve (*hillshade*).
               - *Directorio de Salida:* Carpeta donde se guardarán todos los mapas, tablas CSV y gráficos generados.
            3. **Años a Procesar:**
               - Especifique un año único (ej. `1991`) o un rango continuo (ej. `1991-2020`).
            4. **Dominio Geográfico y Reglas de Etiquetado:**
               - **Regional (Centroamérica y Caribe):** Para dominios con amplitud geográfica $> 5.0^\circ$, la herramienta muestra únicamente puntos limpios coloreados según la paleta del producto para evitar saturación visual.
               - **Nacional / Local (El Salvador, Guatemala, Honduras, etc.):** Para dominios $\le 5.0^\circ$, la herramienta despliega etiquetas numéricas con líneas conectoras armónicas y algoritmo de no solapamiento.

            ---

            #### 2.3. Botones de Acción y Control
            - **🔍 Validar Configuración:** Revisa la existencia de carpetas, formato de archivos NetCDF y coincidencia de coordenadas antes de iniciar el cálculo.
            - **🚀 Ejecutar Análisis:** Inicia el procesamiento científico con barra de progreso y registro de eventos en tiempo real.
            - **🛑 Detener Cálculo:** Permite cancelar de forma segura un procesamiento largo sin corromper archivos existentes.
            - **📂 Visualizar Resultados Existentes:** Si el directorio de salida ya contiene productos calculados previamente, permite cargarlos al instante sin recalcular.
            - **🗑️ Limpiar y Recalcular:** Elimina las salidas previas y recalcula todos los productos desde cero.
            """
        )

    # =========================================================================
    # TAB 3: PRODUCTOS DE ENTRADA
    # =========================================================================
    with doc_tab3:
        st.markdown("### 📥 3. Formatos y Especificaciones de los Productos de Entrada")
        st.markdown(
            r"""
            Para garantizar la correcta ejecución del sistema, los archivos de entrada deben cumplir con las siguientes especificaciones estándar:

            ---

            #### 3.1. Rejillas NetCDF (Datos Originales y Corregidos por CDT)
            - **Formato:** NetCDF-3 / NetCDF-4 clásico (`.nc`).
            - **Estructura Temporal:** Un archivo por día.
            - **Patrón de Nomenclatura Estándar:**
              - *Precipitación Original:* `chirps-v2.0.<YYYY>.<MM>.<DD>.nc` o `precip_<YYYYMMDD>.nc`
              - *Precipitación Corregida (CDT):* `precip_mrg_<YYYYMMDD>.nc` o `chirps_mrg_<YYYYMMDD>.nc`
              - *Temperatura Original:* `tmax_<YYYYMMDD>.nc` o `tmin_<YYYYMMDD>.nc`
              - *Temperatura Corregida (CDT):* `tmax_mrg_<YYYYMMDD>.nc` o `tmin_mrg_<YYYYMMDD>.nc`
            - **Dimensiones Requeridas:**
              - Coordenada longitudinal: `lon` o `longitude` (grados decimales, ej. $-90.5$ a $-87.5$).
              - Coordenada latitudinal: `lat` o `latitude` (grados decimales, ej. $13.0$ a $14.5$).
              - Coordenada temporal (opcional): `time` (dimensión de tamaño 1 que es automáticamente reducida).
            - **Unidades Físicas:**
              - Precipitación: $\text{mm}$ o $\text{mm/día}$.
              - Temperatura: $^\circ\text{C}$.
            - **Valores Nulos / Máscaras:** Valores no válidos deben estar codificados como `NaN` o utilizar el atributo `_FillValue = -9999.0`.

            ---

            #### 3.2. Archivo CSV de Observaciones en Estaciones Meteorológicas
            El archivo CSV de estaciones terrestres debe contener datos diarios o registros tabulares con las siguientes columnas (se aceptan minúsculas o mayúsculas):

            | Nombre Columna | Alias Aceptados | Tipo | Descripción | Ejemplo |
            | :--- | :--- | :--- | :--- | :--- |
            | `station_id` | `id`, `estacion`, `code` | Texto | Identificador único de la estación | `ST_01`, `99001` |
            | `lon` | `longitude`, `long`, `x` | Numérico | Longitud geográfica en grados decimales | `-89.214` |
            | `lat` | `latitude`, `latitud`, `y` | Numérico | Latitud geográfica en grados decimales | `13.702` |
            | `elev` | `elevation`, `altitud`, `z` | Numérico | Elevación sobre el nivel del mar en metros | `625.0` |
            | `date` | `fecha`, `time`, `year/month/day` | Fecha/Texto | Fecha del registro (`YYYY-MM-DD` o columnas `year`, `month`, `day`) | `1991-05-18` |
            | `value` | `precip_station`, `temp_station`, `obs` | Numérico | Valor observado diario de la variable ($\text{mm}$ o $^\circ\text{C}$) | `14.5` |

            > [!NOTE]
            > **Manejo de Datos Faltantes CDT:** Los códigos habituales generados por la herramienta CDT para días sin dato (`-99.0`, `-999.0`, `NA`, `null`) son detectados y excluidos automáticamente de los cálculos estadísticos.

            ---

            #### 3.3. Modelo Digital de Elevación (DEM NetCDF, Opcional)
            - **Formato:** Archivo NetCDF con la topografía de la región en metros de altitud (`elev`, `z`, `dem` o `Band1`).
            - **Uso:** Generación de sombreado de relieve (*hillshade*) en mapas cartográficos y soporte para análisis de gradiente altotérmico.
            """
        )

    # =========================================================================
    # TAB 4: PRODUCTOS Y MÉTRICAS CALCULADAS
    # =========================================================================
    with doc_tab4:
        st.markdown("### 🧮 4. Productos y Estadísticos Calculados e Interpretación")
        st.markdown(
            r"""
            La plataforma computa un conjunto riguroso de estadísticos continuos, de eficiencia hidrológica y categóricos,
            diseñados para cuantificar con precisión el **valor agregado** del ajuste CDT sobre los datos satelitales originales.

            ---

            #### 4.1. Métricas de Error Continuo

            ##### A. Sesgo Medio (Mean Bias) y Sesgo Relativo Porcentual (PBIAS)
            $$\text{Bias} = \frac{1}{N}\sum_{i=1}^N (S_i - O_i) \qquad \text{PBIAS} = \frac{\sum_{i=1}^N (S_i - O_i)}{\sum_{i=1}^N O_i} \times 100\%$$
            - **Definición de Variables:** $S_i$ es el valor estimado por la rejilla satelital/corregida en la celda correspondiente, $O_i$ es el valor observado en la estación terrestre, y $N$ es el número de observaciones válidas.
            - **Interpretación:**
              - $\text{Bias} > 0$ / $\text{PBIAS} > 0$: **Sobrestimación sistemática** del producto grillado respecto a las estaciones.
              - $\text{Bias} < 0$ / $\text{PBIAS} < 0$: **Subestimación sistemática** del producto grillado.
              - $\text{Bias} = 0$: Ausencia de sesgo en el acumulado o promedio global.
            - **Rangos de Calidad Óptima:** $|\text{PBIAS}| < 10\%$ (Excelente en precipitación), $|\text{PBIAS}| < 5\%$ (Excelente en temperatura).

            ##### B. Error Absoluto Medio (MAE)
            $$\text{MAE} = \frac{1}{N}\sum_{i=1}^N |S_i - O_i|$$
            - **Interpretación:** Magnitud media lineal del error en las unidades físicas de la variable ($\text{mm}$ o $^\circ\text{C}$). Al no elevar las diferencias al cuadrado, ofrece una estimación robusta que no se ve distorsionada por valores atípicos aislados.

            ##### C. Raíz del Error Cuadrático Medio (RMSE)
            $$\text{RMSE} = \sqrt{\frac{1}{N}\sum_{i=1}^N (S_i - O_i)^2}$$
            - **Interpretación:** Magnitud del error que penaliza fuertemente las grandes discrepancias puntuales y eventos extremos. Un valor bajo indica alta fidelidad en toda la serie.

            ##### D. Mejora Relativa Porcentual de RMSE ($\%\Delta\text{RMSE}$)
            $$\text{Mejora \%} = \frac{\text{RMSE}_{\text{original}} - \text{RMSE}_{\text{corregido}}}{\text{RMSE}_{\text{original}}} \times 100\%$$
            - **Interpretación:**
              - $\text{Mejora \%} > 0$: El producto corregido por CDT redujo el error cuadrático (ganancia positiva de exactitud).
              - $\text{Mejora \%} < 0$: El producto corregido incrementó el error (empeoramiento local).

            ---

            #### 4.2. Métricas de Eficiencia Hidrológica y Climatológica

            ##### A. Kling-Gupta Efficiency (KGE - Gupta et al., 2009; Kling et al., 2012)
            $$\text{KGE} = 1 - \sqrt{(r - 1)^2 + (\beta - 1)^2 + (\gamma - 1)^2}$$
            El KGE descompone el desempeño en tres ejes independientes y complementarios:
            1. **Correlación lineal de Pearson ($r$):** Coincidencia en la sincronía temporal y patrones de variación ($r \in [-1, 1]$, óptimo $= 1.0$).
            2. **Razón de Sesgo ($\beta = \mu_S / \mu_O$):** Balance de la media del producto frente a la media observada ($\beta > 1$ sobrestima, $\beta < 1$ subestima, óptimo $= 1.0$).
            3. **Razón de Variabilidad ($\gamma = \text{CV}_S / \text{CV}_O = \frac{\sigma_S / \mu_S}{\sigma_O / \mu_O}$):** Capacidad del producto para reproducir la dispersión relativa de la serie (óptimo $= 1.0$).
            - **Criterio de Evaluación:** $\text{KGE} = 1.0$ (Ajuste perfecto); $\text{KGE} \ge 0.75$ (Excelente); $0.50 \le \text{KGE} < 0.75$ (Bueno); $\text{KGE} > -0.41$ (Mejor estimador que la media climatológica observada).

            ##### B. Eficiencia de Nash-Sutcliffe (NSE - Nash & Sutcliffe, 1970)
            $$\text{NSE} = 1 - \frac{\sum_{i=1}^N (O_i - S_i)^2}{\sum_{i=1}^N (O_i - \mu_O)^2}$$
            - Compara la varianza del error del modelo con la varianza natural de los datos observados. $\text{NSE} = 1$ indica correspondencia perfecta; $\text{NSE} > 0.5$ indica habilidad aceptable.

            ##### C. Índice de Concordancia Modificado de Willmott ($d_1$ - Willmott et al., 2012)
            $$d_1 = 1 - \frac{\sum_{i=1}^N |S_i - O_i|}{2 \sum_{i=1}^N |O_i - \mu_O|}$$
            - Índice adimensional acotado estrictamente entre $[0, 1]$ que cuantifica la proporción en la que las estimaciones del modelo están libres de error, con menor sensibilidad a valores atípicos que el índice cuadrático original.

            ---

            #### 4.3. Métricas Categóricas de Detección de Lluvia (CHIRPS) y Umbral Diario ($\tau$)
            
            ##### A. Rol e Importancia del Umbral de Precipitación Diaria ($\tau$)
            En el análisis de precipitación diaria satelital (CHIRPS), una proporción significativa de los días registra valores cercanos a cero (lloviznas inapreciables, ruido instrumental o evaporación antes de tocar el suelo). Para evaluar rigurosamente la capacidad del producto satelital y su corrección para discriminar entre días secos y eventos efectivos de precipitación, se define un **Umbral de Corte ($\tau$)** expresado en $\text{mm/día}$ (por defecto $\tau = 1.0\,\text{mm/día}$, ajustable mediante el deslizador en la barra lateral entre $0.1$ y $25.0\,\text{mm}$).
            
            Un día se clasifica formalmente como:
            - **Evento de Lluvia (Día Lluvioso):** $P \ge \tau$
            - **No-Evento (Día Seco):** $P < \tau$

            ##### B. Matriz de Contingencia Dicotómica ($2 \times 2$)
            A partir de este umbral $\tau$, cada par de observación en estación ($O_i$) y estimación grillada ($S_i$) en el tiempo se clasifica en una tabla de contingencia $2 \times 2$:

            | | Lluvia Observada in-situ ($O \ge \tau$) | Sin Lluvia Observada ($O < \tau$) | Total Estimado |
            | :--- | :---: | :---: | :---: |
            | **Lluvia Estimada Satélite ($S \ge \tau$)** | **Aciertos ($a$ / Hits)** | **Falsas Alarmas ($b$ / False Alarms)** | $a + b$ |
            | **Sin Lluvia Estimada ($S < \tau$)** | **Fallos ($c$ / Misses)** | **No-Eventos Correctos ($d$ / Correct Negatives)** | $c + d$ |
            | **Total Observado** | $a + c$ | $b + d$ | $N = a + b + c + d$ |

            ##### C. Fórmulas de Estadísticos Categóricos y Rango Óptimo
            1. **POD (Probability of Detection / Hit Rate):**
               $$\text{POD} = \frac{a}{a+c} \in [0, 1] \qquad (\text{Óptimo} = 1.0)$$
               Fracción de los días lluviosos observados que fueron detectados exitosamente por la rejilla satelital. Un valor cercano a 1 indica excelente sensibilidad.
            2. **FAR (False Alarm Ratio):**
               $$\text{FAR} = \frac{b}{a+b} \in [0, 1] \qquad (\text{Óptimo} = 0.0)$$
               Proporción de eventos de lluvia pronosticados/estimados por el satélite que no ocurrieron en la estación. Valores bajos indican alta confiabilidad.
            3. **CSI (Critical Success Index / Threat Score):**
               $$\text{CSI} = \frac{a}{a+b+c} \in [0, 1] \qquad (\text{Óptimo} = 1.0)$$
               Métrica balanceada que evalúa la exactitud conjunta considerando aciertos, falsas alarmas y fallos, sin verse inflada por los días secos comunes ($d$).
            4. **FBI (Frequency Bias Index):**
               $$\text{FBI} = \frac{a+b}{a+c} \in [0, \infty) \qquad (\text{Óptimo} = 1.0)$$
               Compara la frecuencia total con la que el satélite estima lluvia respecto a la frecuencia real observada.
               - $\text{FBI} > 1$: Sobrestimación sistemática en la frecuencia de días lluviosos (lluvia simulada con demasiada frecuencia).
               - $\text{FBI} < 1$: Subestimación en la frecuencia de eventos de precipitación.
            5. **ETS (Equitable Threat Score / Gilbert Skill Score):**
               $$\text{ETS} = \frac{a - a_r}{a + b + c - a_r} \in \left[-\frac{1}{3}, 1\right] \qquad (\text{Óptimo} = 1.0)$$
               Donde $a_r = \frac{(a+b)(a+c)}{N}$ representa el número esperado de aciertos por simple azar. $\text{ETS} > 0$ indica habilidad real de discriminación más allá del azar fortuito.
            6. **HSS (Heidke Skill Score):**
               $$\text{HSS} = \frac{2(ad - bc)}{(a+c)(c+d) + (a+b)(b+d)} \in [-1, 1] \qquad (\text{Óptimo} = 1.0)$$
               Evalúa la exactitud global de la clasificación categórica en comparación con una estimación puramente aleatoria. $\text{HSS} = 1$ indica ajuste perfecto, $\text{HSS} = 0$ indica ausencia de habilidad (equivalente al azar), y $\text{HSS} < 0$ indica peor desempeño que el azar.

            ---

            #### 5.2. Mapa de Campo de Anomalías $\Delta\text{GRID}$ ($\Delta\text{GRID} = \text{Grid}_{\text{corr}} - \text{Grid}_{\text{raw}}$)
            - **Estructura:**
              - Superficie continua calculada celda a celda como la resta directa entre el producto corregido y el original.
              - Paleta divergente centrada en cero (`RdBu_r` o `PiYG`).
              - Fondo con sombreado de relieve topográfico (*hillshade DEM*).
              - Marcadores de estaciones con etiquetas numéricas firmadas ($+$, $-$).
            - **Cómo Interpretar:**
              - **Zonas Rojas / Positivas ($+$):** Áreas donde el ajuste CDT aumentó el valor respecto al satélite original (ej. $+150\,\text{mm}$ o $+1.2\,^\circ\text{C}$), corrigiendo una subestimación previa del satélite.
              - **Zonas Azules / Negativas ($-$):** Áreas donde el ajuste CDT redujo el valor (ej. $-200\,\text{mm}$ o $-0.8\,^\circ\text{C}$), corrigiendo una sobrestimación previa del satélite.
              - **Zonas Blancas / Neutras ($0$):** Áreas donde el producto original ya presentaba concordancia o donde la densidad de estaciones no introdujo modificaciones sustanciales.
              - **Etiquetas de Estaciones:** Muestran el ajuste puntual exacto en cada estación meteorológica con signo explícito (ej. `+1.02`, `-2.44`), evitando confusiones con los valores crudos de temperatura o lluvia.

            ---

            #### 5.3. Mapa de $\Delta\text{GRID}$ en Estaciones sobre Relieve Topográfico
            - **Estructura:** Puntos circulares ubicados sobre el mapa de relieve sombreado (DEM), coloreados según la magnitud de la diferencia $(\text{Grid}_{\text{corr}} - \text{Grid}_{\text{raw}})$ en la estación.
            - **Cómo Interpretar:** Permite identificar la correlación entre la corrección realizada y la altitud del terreno. Por ejemplo, en zonas montañosas es común observar incrementos térmicos o reducciones de lluvia orográfica mal modelada por el satélite.

            ---

            #### 5.4. Mapa de Residuos en Estaciones ($\text{Residuo} = \text{Grid}_{\text{corr}} - \text{Obs}$)
            - **Estructura:** Puntos circulares en estaciones coloreados por el residuo final de calibración.
            - **Cómo Interpretar:** Un valor cercano a $0.0$ indica que la superficie corregida reproduce con exactitud la medición de la estación (calibración óptima). Valores residuales apreciables pueden indicar microclimas muy locales no capturables a la resolución de la rejilla ($0.05^\circ \approx 5.5\,\text{km}$).

            ---

            #### 5.5. Mapa de Mejora Relativa de RMSE ($\%\Delta\text{RMSE}$)
            - **Estructura:** Puntos en estaciones coloreados con paleta de mejora: valores verdes/azules indican porcentaje de reducción del error ($\text{Mejora} > 0\%$), mientras que valores rojos indicarían aumento del error.
            - **Cómo Interpretar:** Valida globalmente el éxito del proceso de mezcla CDT en la red de monitoreo nacional.

            ---

            #### 5.6. Gráficos Estadísticos y de Dispersión
            - **Scatter Plot (Original vs Obs y Corregido vs Obs):**
              - Gráfico de dispersión con línea diagonal $1:1$ de ajuste perfecto y recta de regresión lineal por mínimos cuadrados ordinarios (OLS).
              - **Interpretación:** La nube de puntos del producto corregido (verde menta) debe agruparse más estrechamente alrededor de la línea $1:1$ y presentar un $R^2$ mayor que el producto original (coral).
            - **Climatología Diaria DOY (Day of Year):**
              - Curva anual diaria ($1 \dots 365$) que compara el ciclo estacional medio observado frente a las rejillas original y corregida.
              - **Interpretación:** Permite evaluar la capacidad del producto para capturar el inicio de la estación lluviosa, la canícula (*veranillo* o *mid-summer drought*) y el pico de precipitaciones en septiembre/octubre.
            """
        )

    # =========================================================================
    # TAB 6: REFERENCIAS BIBLIOGRÁFICAS JUSTIFICADAS
    # =========================================================================
    with doc_tab6:
        st.markdown("### 📖 6. Referencias Bibliográficas y Aporte Científico a la Herramienta")
        st.markdown(
            """
            Cada una de las métricas y metodologías implementadas en esta plataforma ha sido seleccionada con base en
            estándares internacionales establecidos por la Organización Meteorológica Mundial (OMM/WMO) y la literatura
            científica climatológica revisada por pares. A continuación se presenta cada referencia con su justificación técnica
            y su aporte específico a la herramienta:
            """
        )

        references = [
            {
                "title": "Funk, C., Peterson, P., Landsfeld, M., Pedreros, D., Verdin, J., Shukla, S., Husak, G., Rowland, J., Harrison, L., Hoell, A., & Michaelsen, J. (2015).",
                "journal": "The climate hazards group infrared precipitation with stations—a new environmental record for monitoring extremes. Scientific Data, 2(1), 150066.",
                "doi": "https://doi.org/10.1038/sdata.2015.66",
                "importance": (
                    "Es el artículo fundacional que documenta el desarrollo, calibración y archivo del producto de precipitación CHIRPSv2. "
                    "Explica cómo se combinan las imágenes satelitales infrarrojas de temperatura de brillo de nubes (Cold Cloud Duration - CCD) "
                    "con la climatología de alta resolución CHPclim y las observaciones in-situ de estaciones para producir una serie temporal continua desde 1981."
                ),
                "contribution": (
                    "Proporciona la base física y matemática de la rejilla de precipitación original (Raw) que la plataforma evalúa. "
                    "Define la resolución espacial estándar de 0.05° (~5.5 km) y las convenciones de unidades (mm) y días de acumulación que utiliza la herramienta."
                )
            },
            {
                "title": "Funk, C., Peterson, P., Peterson, S., Shukla, S., Davenport, F., Michaelsen, J., Rowland, J., Husak, G., Pedreros, D., & Verdin, J. (2019).",
                "journal": "A high-resolution 1983–2016 Tmax climate data record based on infrared temperatures, stations, and reanalysis data. Scientific Data, 6(1), 248.",
                "doi": "https://doi.org/10.1038/s41597-019-0252-0",
                "importance": (
                    "Documenta el producto térmico satelital CHIRTS-daily, detallando la fusión de temperaturas superficiales terrestres (LST), "
                    "re-análisis ERA5 y estaciones para modelar la temperatura máxima y mínima diaria a escala global."
                ),
                "contribution": (
                    "Establece las características del producto de temperatura base que se procesa en el módulo térmico, incluyendo el modelado de extremos "
                    "y las limitaciones orográficas que el ajuste CDT corrige mediante regresión con el Modelo Digital de Elevación (DEM)."
                )
            },
            {
                "title": "Gupta, H. V., Kling, H., Yilmaz, K. K., & Martinez, G. F. (2009).",
                "journal": "Decomposition of the mean squared error and NSE performance criteria: Implications for improving hydrological modelling. Journal of Hydrology, 377(1-2), 80–91.",
                "doi": "https://doi.org/10.1016/j.jhydrol.2009.08.003",
                "importance": (
                    "Demuestra formalmente que el clásico coeficiente de Nash-Sutcliffe (NSE) y el error cuadrático medio (MSE) subestiman sistemáticamente "
                    "la variabilidad temporal en series hidrológicas y climáticas. Introduce el coeficiente Kling-Gupta Efficiency (KGE) como una formulación "
                    "multicriterio que equilibra correlación lineal, sesgo de media y razón de variabilidad."
                ),
                "contribution": (
                    "Aporta la métrica principal de eficiencia hidrológica y climática (KGE) utilizada en la plataforma. Permite descomponer el desempeño "
                    "en los componentes independientes r, beta y gamma, facilitando el diagnóstico exacto de por qué un producto satelital gana o pierde precisión."
                )
            },
            {
                "title": "Kling, H., Fuchs, M., & Paulin, M. (2012).",
                "journal": "Runoff conditions in the upper Danube basin under an ensemble of climate change scenarios. Journal of Hydrology, 424–425, 264–277.",
                "doi": "https://doi.org/10.1016/j.jhydrol.2012.04.011",
                "importance": (
                    "Propone una revisión fundamental al KGE original (KGE') para garantizar que el término de variabilidad (gamma) sea completamente "
                    "independiente del sesgo en la media (beta), utilizando el coeficiente de variación (CV = sigma / mu) en lugar de la desviación estándar simple."
                ),
                "contribution": (
                    "La plataforma implementa la formulación refinada KGE (2012), evitando interacciones espurias entre el sesgo de volumen y la dispersión "
                    "en series de precipitación diaria y acumulados anuales."
                )
            },
            {
                "title": "Dinku, T., Thomson, M. C., Cousin, R., del Corral, J., Ceccato, P., Hansen, J., & Connor, S. J. (2018).",
                "journal": "Enhancing National Climate Services (ENACTS) through transforming climate data, products, and services. Bulletin of the American Meteorological Society, 99(7), S1–S10.",
                "doi": "https://doi.org/10.1175/BAMS-D-16-0158.1",
                "importance": (
                    "Presenta el marco metodológico de la iniciativa ENACTS desarrollada por el International Research Institute for Climate and Society (IRI) "
                    "de la Universidad de Columbia, base operativa del software Climate Data Tool (CDT). Sustenta la necesidad de fusionar observaciones locales con productos satelitales."
                ),
                "contribution": (
                    "Justifica conceptualmente la arquitectura de validación y la comparación directa 'Original vs Corregido por CDT'. Provee las directrices "
                    "de control de calidad y validación cruzada adoptadas en este software."
                )
            },
            {
                "title": "Willmott, C. J., Robeson, S. M., & Matsuura, K. (2012).",
                "journal": "A refined index of model performance. International Journal of Climatology, 32(13), 2088–2094.",
                "doi": "https://doi.org/10.1002/joc.2419",
                "importance": (
                    "Desarrolla el índice de concordancia modificado y refinado (d1), superando las limitaciones del índice cuadrático d de Willmott (1981), "
                    "el cual era excesivamente sensible a unos pocos valores atípicos severos."
                ),
                "contribution": (
                    "Se incorpora en la plataforma como métrica no paramétrica lineal acotada entre [0, 1], permitiendo evaluar la bondad de ajuste en estaciones "
                    "con distribuciones altamente asimétricas o eventos extremos de precipitación sin sesgos inducidos por outliers."
                )
            },
            {
                "title": "Wilks, D. S. (2011).",
                "journal": "Statistical Methods in the Atmospheric Sciences. Academic Press (Elsevier), 3rd Edition, 676 pp.",
                "doi": "https://doi.org/10.1016/C2009-0-00031-0",
                "importance": (
                    "Es el texto de referencia estándar mundial para la verificación estadística de pronósticos, productos meteorológicos y campos climáticos. "
                    "Detalla la formulación rigurosa de matrices de contingencia 2x2 y métricas de habilidad dicotómica."
                ),
                "contribution": (
                    "Fundamenta las fórmulas de verificación categórica de lluvia diaria calculadas por la herramienta: Probability of Detection (POD), "
                    "False Alarm Ratio (FAR), Critical Success Index (CSI), Frequency Bias Index (FBI) y Equitable Threat Score (ETS)."
                )
            },
            {
                "title": "Moriasi, D. N., Arnold, J. G., Van Liew, M. W., Bingner, R. L., Harmel, R. D., & Veith, T. L. (2007).",
                "journal": "Model evaluation guidelines for systematic quantification of accuracy in watershed simulations. Transactions of the ASABE, 50(3), 885–900.",
                "doi": "https://doi.org/10.13031/2013.23153",
                "importance": (
                    "Establece umbrales de rendimiento y directrices cuantitativas estandarizadas para clasificar la precisión de modelos climáticos e hidrológicos "
                    "en categorías cualitativas (Muy Bueno, Bueno, Satisfactorio, No Satisfactorio) a partir de PBIAS, RMSE y NSE."
                ),
                "contribution": (
                    "Aporta los rangos de semaforización y clasificación de calidad utilizados en las tarjetas resumen de métricas y tablas de ranking de la aplicación."
                )
            },
            {
                "title": "Nash, J. E., & Sutcliffe, J. V. (1970).",
                "journal": "River flow forecasting through conceptual models part I—A discussion of principles. Journal of Hydrology, 10(3), 282–290.",
                "doi": "https://doi.org/10.1016/0022-1694(70)90255-6",
                "importance": (
                    "Artículo clásico fundamental que introdujo el coeficiente de eficiencia de Nash-Sutcliffe (NSE), métrica histórica universal "
                    "para contrastar el desempeño de un modelo contra la media observada."
                ),
                "contribution": (
                    "Se incluye en la plataforma para mantener compatibilidad con estudios históricos y permitir la comparación directa con literatura hidrológica previa."
                )
            },
            {
                "title": "IRI - International Research Institute for Climate and Society (2020).",
                "journal": "Climate Data Tool (CDT) User Guide and Training Manual. Earth Institute, Columbia University, New York, USA.",
                "doi": "https://iri.columbia.edu/resources/enacts/cdt-guide/",
                "importance": (
                    "Manual oficial y guía de referencia del software CDT, describiendo los algoritmos de homogeneización, control de calidad, "
                    "regresión orográfica con DEM y técnicas de interpolación espacial de residuales (Kriging e IDW)."
                ),
                "contribution": (
                    "Sustenta la compatibilidad directa de la plataforma con los formatos de salida generados por CDT (nombres de archivos, códigos de datos nulos "
                    "como -99/-999 y estructuras de carpetas de datos combinados)."
                )
            }
        ]

        for i, ref in enumerate(references, start=1):
            with st.expander(f"📚 {i}. {ref['title']}", expanded=(i == 1)):
                st.markdown(f"**Referencia:** *{ref['title']}* {ref['journal']} [DOI / Enlace]({ref['doi']})")
                st.markdown(f"**¿Por qué es importante?**  \n{ref['importance']}")
                st.markdown(f"**¿Qué aporta específicamente a esta herramienta?**  \n{ref['contribution']}")
