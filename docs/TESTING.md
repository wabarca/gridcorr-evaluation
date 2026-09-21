# Estrategia y Protocolo de Pruebas

**Plataforma de Evaluación y Corrección Climatológica (GridCorr)**  
*Ministerio de Medio Ambiente y Recursos Naturales (MARN) — El Salvador*

---

## 1. Objetivos del Sistema de Pruebas

El conjunto de pruebas garantiza que:
1. **La lógica científica es 100% fiel y exacta**: Fórmulas matemáticas de RMSE, Bias, Correlación de Pearson, $\Delta\text{RMSE}$ y Porcentaje de Mejora coinciden con la formulación estándar y los scripts originales.
2. **El manejo de valores faltantes es riguroso**: Los códigos de no-dato (`-99`, `NA`, `NaN`) son omitidos correctamente sin sesgar las estadísticas ni las sumas acumuladas.
3. **El parser CDT es tolerante a fallos**: Archivos con cabeceras incompletas, columnas corruptas o caracteres inesperados arrojan excepciones claras en lugar de fallos silenciosos.
4. **Validación previa de insumos**: Se detectan incompatibilidades de fechas, mallas espaciales o variables antes de consumir tiempo de cómputo.

---

## 2. Estructura del Directorio de Pruebas (`tests/`)

```
tests/
├── conftest.py                   # Fixtures compartidas y generación de datos sintéticos
├── test_cdt_parser.py            # Pruebas del parser de estaciones CDT (3 filas cabecera)
├── test_metrics.py               # Pruebas de formulaciones estadísticas y métricas de error
├── test_validators.py            # Pruebas de validación de archivos, rutas y fechas
└── test_scientific_regression.py # Pruebas de regresión científica contra los algoritmos base
```

---

## 3. Ejecución de las Pruebas

### 3.1 Ejecución Estándar con Pytest
```bash
pytest
```

### 3.2 Reporte Detallado de Cobertura
```bash
pytest --cov=src --cov-report=term-missing tests/
```

### 3.3 Ejecutar una Suite Específica
```bash
# Probar únicamente el cálculo de métricas científicas
pytest tests/test_metrics.py -v

# Probar la validación de archivos CDT
pytest tests/test_cdt_parser.py -v
```

---

## 4. Pruebas de Regresión Científica

La suite incluye pruebas que comparan directamente el cálculo de las métricas vectorizadas contra una implementación manual no-vectorizada paso a paso:

```python
def test_metric_exactness_vs_manual_reference():
    obs = np.array([10.0, 20.0, -99.0, 40.0, 50.0])
    sim = np.array([12.0, 18.0, 25.0, 44.0, 48.0])
    # Validación con filtro estricto de valores válidos
    ...
```

Esto asegura que futuras refactorizaciones del código fuente nunca alteren los resultados numéricos entregados al usuario.
