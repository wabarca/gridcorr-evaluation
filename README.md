# CHIRTS Evaluation & Visualization Toolkit

#### ✍️ Autor:

- William Abarca
- Contacto: abarca.will@gmail.com

---

Herramienta en Python para la **evaluación, comparación y visualización** de rejillas CHIRTS original vs CHIRTS corregido usando datos diarios de observación.

El flujo permite:

- Generar mapas climatológicos y diarios.
- Calcular métricas de desempeño (Bias, MAE, RMSE).
- Analizar mejoras espaciales y por estación.
- Construir series diarias completas y climatologías DOY (día del año).
- Producir gráficos comparativos consistentes y listos para informes técnicos.

---

## 📌 Características principales

- Comparación **lado a lado**: CHIRTS original vs CHIRTS corregido.
- Mapas de:
  - Campo ΔGRID = Corregido − Original
  - ΔGRID en estaciones
  - Mejora por estación
- Evaluación diaria completa:
  - Serie temporal por estación
  - Resúmenes globales y por estación
- Climatología DOY (dia del año) por estación:
  - Media, máximo y mínimo diario climatológico
  - Panel simple y 3-panel (max / mean / min)
- Estilo gráfico:
  - Relieve (hillshade) desde DEM
- Soporte de periodos:
  - Anual
  - Diario
  - Estaciones climáticas (DJFM, A, MJJ, ASO, N)
  - Meses específicos

---

## 📂 Estructura de entradas

### 1) CSV de estaciones (formato CDT)

- Fila 1: IDs de estaciones
- Fila 2: Longitudes
- Fila 3: Latitudes
- Fila 4: Elevaciones
- Filas siguientes:
  `YYYYMMDD, val_est1, val_est2, ...`

Ejemplo de columnas internas tras parseo:

- `date` (YYYYMMDD)
- `station_id`
- `lon`, `lat`, `elev`
- `<var>_station` (ej. `tmax_station`)

---

### 2) CHIRTS original (NetCDF diarios)

Archivos tipo:

`{prefix}_YYYYMMDD.nc`

Ejemplo:

`temp_19910101.nc`

---

### 3) CHIRTS corregido (NetCDF diarios)

Archivos tipo:

`*_mrg_YYYYMMDD.nc`

Ejemplo:

`tmax_mrg_19910101.nc`, `tmin_mrg_19910101.nc`, `temp_mrg_19910101.nc`

---

### 4) DEM (NetCDF)

- Un campo de elevación con coordenadas lat/lon
- Usado para generar hillshade en los mapas

---

## ⚙️ Instalación del entorno

### Opción A: conda / mamba (recomendado)

```bash
conda create -n chirpts-evaluation python=3.10
conda activate chirpts-evaluation
pip install -r requirements.txt
```

O con `mamba`:

```bash
mamba create -n chirpts-evaluation python=3.10
mamba activate chirpts-evaluation
pip install -r requirements.txt
```

### Opción B: environment.yml

```bash
conda env create -f environment.yml
conda activate chirpts-evaluation
```

---

## ▶️ Modos de ejecución

Ejecuta:

```bash
python mapas_acumulados_chirts_anuales.py --help
```

para ver todas las opciones:

```bash
    Parámetros de entrada (CLI)
    ---------------------------
    --csv            : Archivo CDT con observaciones en estaciones.
    --dir-chirts     : Directorio con NetCDF diarios/anuales de CHIRTS original.
    --prefix-chirts  : Prefijo de archivos CHIRTS originales (default: "temp_").
    --dir-merged     : Directorio con NetCDF de CHIRTS corregido.
    --var            : Variable a procesar ("tmax" o "tmin").
    --stat           : Estadístico ("mean", "max", "min" o "all").
    --dem            : NetCDF con el modelo digital de elevación (DEM).
    --out            : Directorio base de salida.
    --yini, --yend   : Rango de años para modos annual/period.
    --extent         : Extensión geográfica (xmin xmax ymin ymax).
    --mode           : Modo de operación ("annual", "daily", "daily-eval", "period").
    --period-type    : Tipo de período ("season" o "months") para modo period.
    --season         : Temporada (DJFM, A, MJJ, ASO, N).
    --months         : Lista de meses (ej: "5,6,7") para modo period.
    --all-seasons    : Procesa todas las temporadas definidas.
    --eval           : (opcional) Activa productos de evaluación estadística.
    --date           : Fecha específica para modo daily (YYYY-MM-DD).
```

**Flujo general**

1. Parseo de argumentos y validación básica.
2. Lectura del CSV de estaciones y preparación del DataFrame largo.
3. Carga del DEM.
4. Enrutamiento según el modo seleccionado:
   - `daily-eval`
   - `daily`
   - `period`
   - `annual` (por defecto)
5. Generación de productos operativos (mapas, CSV).
6. Si `--eval` está activo, generación de productos de evaluación estadística.

### A) Modo ANUAL (default)

Para cada estadística (mean/max/min):

- Recorre los años `[yini, yend]`
- Genera mapas side-by-side (raw vs corregido)
- Genera mapas ΔGRID por año (campo completo)
- Exporta CSV de comparación en estaciones por año
- Acumula ΔGRID para construir un ΔGRID GLOBAL (promedio temporal)

Si `--eval` está activo, además:

- Construye productos de evaluación GLOBAL y por AÑO:
- CSV global por estación
- Mapas ΔGRID en estaciones (global)
- CSV y mapas de mejora (ΔRMSE)
- Métricas anuales (Bias, MAE, RMSE, R)
- Gráficos: RMSE temporal, boxplots, scatter
- Rankings por estación (global y por año)

**Ejecución:**

En la terminal **(en Windows puede ser necesario escribir todo en una sola línea, sin \\ )** ejecuta:

```bash
python mapas_acumulados_chirts_anuales.py \
  --csv estaciones_tmax_formato_cdt.csv \
  --dir-chirts /datos/CHIRTS/CDT_NetCDF_Format/ \
  --dir-merged /datos/CHIRTS/MERGED_TEMP_Data_1Jan1991_31Dec2020/DATA/ \
  --var tmax \
  --stat max | mean | min | all \
  --mode annual \
  --dem dem.nc \
  --yini 1991 \
  --yend 2020 \
  --out ./salidas
  --eval (opcional)
```

### B) Modo DIARIO (mapa para una fecha específica, es obligatorio el parámetro --date YYYY-MM-DD):

Genera productos para UNA fecha específica `YYYY-MM-DD`:
Productos principales:

- Mapa side-by-side: CHIRTS original vs CHIRTS corregido
- CSV de comparación en estaciones (obs, raw, corr, errores)
  Productos de diagnóstico (evaluación diaria):
- Mapa de CAMPO `ΔGRID = corr - raw`
- Mapa de `ΔGRID` en estaciones
- Copia del CSV de comparación en carpeta de evaluación
- **Este modo es puntual (una fecha) y termina la ejecución.**

**Ejecución:**

En la terminal **(en Windows puede ser necesario escribir todo en una sola línea, sin \\ )** ejecuta:

```bash

python mapas_acumulados_chirts_anuales.py \
  --csv estaciones_tmax_formato_cdt.csv \
  --dir-chirts /datos/CHIRTS/CDT_NetCDF_Format/ \
  --dir-merged /datos/CHIRTS/MERGED_TEMP_Data_1Jan1991_31Dec2020/DATA/ \
  --var tmax \
  --stat max | mean | min | all \
  --mode daily \
  --dem elevacion.nc \
  --date 1991-01-01 \
  --out ./salidas
  --eval (opcional)
```

### C) Modo `daily-eval` (evaluación diaria completa en serie temporal):

Construye la serie diaria completa de estaciones vs rejilla
para todos los años disponibles y genera resúmenes estadísticos.
Flujo:

1. Identifica los años presentes en el CSV de estaciones.
2. Procesa cada año en paralelo para construir la serie diaria:
   - Para cada día y estación: `obs`, `raw` y `corr`.
3. Concatena todos los años en un único DataFrame diario.
4. Guarda la serie diaria completa a disco completa y por estaciones.
5. Genera:
   - Resumen global (Bias, MAE, RMSE) usando todos los datos.
   - Resumen por estación (Bias, MAE, RMSE) en toda la serie.
   - Gráficas de las series temporales de climatología de día del año (DOY)
6. Termina la ejecución (no continúa a otros modos).

**Ejecución:**

En la terminal **(en Windows puede ser necesario escribir todo en una sola línea, sin \\ )** ejecuta:

```bash
python mapas_acumulados_chirts_anuales.py \
  --csv estaciones_tmax_formato_cdt.csv \
  --dir-chirts /datos/CHIRTS/CDT_NetCDF_Format/ \
  --dir-merged /datos/CHIRTS/MERGED_TEMP_Data_1Jan1991_31Dec2020/DATA/ \
  --var tmax \
  --mode daily-eval \
  --out ./salidas
  --eval (opcional)
```

### D) Modo PERIODO (Estación climática: `DJFM`, `A`, `MJJ`, `ASO`, `N` | mes: 7 o meses especificos: 4,5,6 ):

Genera productos para PERÍODOS definidos por cualquiera de estas opciones:

- Estaciones climáticas definidas por el Foro del Clima Centroamericano (`DJFM`, `A`, `MJJ`, `ASO`, `N`)
- Mes (ej: `7`) o conjunto de meses (ej: `5,6,7,8,9,10`)

Para cada año, cada período y cada estadística:

- Calcula el campo agregado (`mean`/`max`/`min`)
- Genera mapa side-by-side (`raw` vs `corregido`)
- Genera CSV de comparación en estaciones
- Genera productos de evaluación:
  - Mapa `ΔGRID` (campo)
  - Mapa `ΔGRID` en estaciones
  - CSV de mejora por estación (`RMSE`)
  - Mapa `ΔRMSE` en estaciones
    Este modo es multi-año y multi-período, y termina la ejecución.

**Ejecución:**

En la terminal **(en Windows puede ser necesario escribir todo en una sola línea, sin \\ )** ejecuta:

**Para estación climática:**

```bash
python mapas_acumulados_chirts_anuales.py \
  --csv estaciones_tmax_formato_cdt.csv \
  --dir-chirts /datos/CHIRTS/CDT_NetCDF_Format/ \
  --dir-merged /datos/CHIRTS/MERGED_TEMP_Data_1Jan1991_31Dec2020/DATA/ \
  --var tmax \
  --stat max | mean | min | all \
  --mode period \
  --period-type season \
  --season DJFM | A | MJJ | ASO | N | --all-seasons \
  --yini 1991 \
  --yend 2020 \
  --dem elevacion.nc \
  --out ./salidas
  --eval (opcional)
```

**Para mes o meses específicos:**

```bash
python mapas_acumulados_chirts_anuales.py \
  --csv estaciones_tmax_formato_cdt.csv \
  --dir-chirts /datos/CHIRTS/CDT_NetCDF_Format/ \
  --dir-merged /datos/CHIRTS/MERGED_TEMP_Data_1Jan1991_31Dec2020/DATA/ \
  --var tmax \
  --stat max | mean | min | all \
  --mode period \
  --period-type months \
  --months 5,6,7 \ (obligatorio en modo months)
  --yini 1991 \
  --yend 2020 \
  --dem elevacion.nc \
  --out ./salidas
  --eval (opcional)
```

---

## 📊 Definición de métricas estadísticas

Sea:

- $( o_i )$ el valor observado en la estación para el día $( i )$
- $( g_i )$ el valor del producto en rejilla (raw o corregido) para el mismo día
- $( N )$ el número total de pares válidos $(o_i, g_i)$

Definimos el **error** como:

$$
e_i = g_i - o_i
$$

### 1) Bias (Sesgo)

El **Bias** mide el error medio con signo:

$$
\text{Bias} = \frac{1}{N} \sum_{i=1}^{N} (g_i - o_i) = \frac{1}{N} \sum_{i=1}^{N} e_i
$$

**Interpretación:**

- Bias > 0 → el producto **sobreestima** en promedio.
- Bias < 0 → el producto **subestima** en promedio.
- Bias ≈ 0 → no hay sesgo sistemático, pero puede haber errores compensados.

---

### 2) MAE (Mean Absolute Error)

El **MAE** mide la magnitud media del error, sin considerar el signo:

$$
\text{MAE} = \frac{1}{N} \sum_{i=1}^{N} | g_i - o_i | = \frac{1}{N} \sum_{i=1}^{N} | e_i |
$$

**Propiedades:**

- Siempre es ≥ 0.
- Penaliza todos los errores de forma lineal.
- Es más **robusto** que el RMSE frente a valores extremos.

---

### 3) RMSE (Root Mean Square Error)

El **RMSE** penaliza más fuertemente los errores grandes:

$$
\text{RMSE} = \sqrt{ \frac{1}{N} \sum_{i=1}^{N} (g_i - o_i)^2 } = \sqrt{ \frac{1}{N} \sum_{i=1}^{N} e_i^2 }
$$

**Propiedades:**

- Siempre es ≥ 0.
- Da más peso a errores grandes (outliers).
- Muy usado en verificación meteorológica y climatológica.
- Sensible a eventos extremos (lo cual es deseable en muchos análisis climáticos).

---

### 4) Diferencia de RMSE (ΔRMSE)

Para comparar el producto **original (raw)** y el **corregido (corr)**:

Sea:

- $(\text{RMSE}\_{\text{raw}}$ ) el RMSE del producto original
- $(\text{RMSE}\_{\text{corr}}$ ) el RMSE del producto corregido

Definimos:

$$
\Delta \text{RMSE} = \text{RMSE}_{\text{raw}} - \text{RMSE}_{\text{corr}}
$$

**Interpretación:**

- $(\Delta \text{RMSE} > 0)$ → la corrección **mejora** el producto (reduce el error).
- $(\Delta \text{RMSE} < 0)$ → la corrección **empeora** el producto.
- $(\Delta \text{RMSE} = 0)$ → no hay cambio en el error cuadrático medio.

---

### 5) Mejora relativa porcentual de RMSE

Para expresar la mejora en términos relativos:

$$
\text{Mejora} = 100 \times \frac{\text{RMSE}_{\text{raw}} - \text{RMSE}_{\text{corr}}}{\text{RMSE}_{\text{raw}}}
$$

Es decir:

$$
\text{Mejora} = 100 \times \frac{\Delta \text{RMSE}}{\text{RMSE}_{\text{raw}}}
$$

**Interpretación:**

- Valor positivo → reducción porcentual del error gracias a la corrección.
- Valor negativo → aumento porcentual del error.
- Ejemplo:
  - Si $( \text{RMSE}_{\text{raw}} = 4.0 )$ y $( \text{RMSE}_{\text{corr}} = 3.0 )$:
    $$
    \text{Mejora} = 100 \times \frac{4.0 - 3.0}{4.0} = 25(\%)
    $$

---

## 📈 Métricas en distintos contextos

### A) Serie diaria completa (modo `daily-eval`)

Se usan **todos los días y todas las estaciones**:

- Bias, MAE, RMSE globales:

$$
  \text{RMSE}_{\text{global}} = \sqrt{ \frac{1}{N_{\text{total}}} \sum_{i=1}^{N_{\text{total}}} (g_i - o_i)^2 }
$$

- Por estación:
  Si una estación ( s ) tiene ( N_s ) datos:

$$
\text{RMSE}_s = \sqrt{ \frac{1}{N_s} \sum_{i=1}^{N_s} (g_{s,i} - o_{s,i})^2 }
$$

Esto permite:

- Detectar estaciones problemáticas
- Construir rankings por desempeño
- Evaluar espacialmente la calidad del producto

---

### B) Períodos (meses o estaciones climáticas)

Para un período $( P )$ (ej. DJFM, MJJ, o meses 5-6-7):

1. Primero se construyen series restringidas al período.
2. Luego se calculan las métricas exactamente igual que antes, pero usando solo los datos del período:

$$
\text{RMSE}_{s,P} = \sqrt{ \frac{1}{N_{s,P}} \sum_{i=1}^{N_{s,P}} (g_{s,i} - o_{s,i})^2 }
$$

Y la mejora porcentual:

$$
\text{Mejora}_{s, P} = 100 \times \frac{\text{RMSE}_{s,P}^{\text{raw}} - \text{RMSE}_{s,P}^{\text{corr}}}{\text{RMSE}_{s,P}^{\text{raw}}}
$$

---

### C) Climatología DOY (día del año)

Para cada día del año $( d \in [1,365] )$ y una estación $( s )$:

Sea $( x\_{s,d,y} )$ el valor en el año $( y )$.

Se define:

**Media climatológica diaria:**

$$
\mu_{s,d} = \frac{1}{N_y} \sum_{y=1}^{N_y} x_{s,d,y}
$$

**Máximo climatológico diario:**

$$
x^{\max}_{s,d} = \max_{y}(x_{s,d,y})
$$

**Mínimo climatológico diario:**

$$
x^{\min}_{s,d} = \min_{y}(x_{s,d,y})
$$

**Desviación estándar (variabilidad interanual):**

$$
\sigma_{s,d} = \sqrt{ \frac{1}{N_y} \sum_{y=1}^{N_y} (x_{s,d,y} - \mu_{s,d})^2 }
$$

En los gráficos:

- La **línea negra** es el observado.
- Las líneas de color son raw y corregido.
- El **sombreado ±1σ** muestra la variabilidad interanual del observado.

---

## 🗺️ Interpretación de los mapas

### 1) Mapa ΔGRID = Corregido − Original

En cada punto de la rejilla:

$$
\Delta G(x,y) = G_{\text{corr}}(x,y) - G_{\text{raw}}(x,y)
$$

- Valores positivos: la corrección incrementa el campo.
- Valores negativos: la corrección lo reduce.
- El colormap divergente centrado en 0 permite ver fácilmente dónde y cuánto cambia.

---

### 2) Mapa de residuo en estaciones (Corr − Obs)

Para cada estación:

$$
R_s = G_{\text{corr}, s} - O_s
$$

- Si $( R_s > 0 )$: el producto corregido sobreestima en esa estación.
- Si $( R_s < 0 )$: subestima.
- Permite ver **patrones espaciales de error residual** tras la corrección.

---

## 📦 Entorno de ejecución

Se proveen:

- `requirements.txt` para `pip`
- `environment.yml` para `conda/mamba`

Nombre sugerido del entorno:

```bash
chirpts-evaluation
```

---
