# proyecto_seminario

**Production-Grade ETL Pipeline for Economic Indicators**

Una pipeline de data engineering profesional que implementa arquitectura medallion (BRONZE → SILVER → GOLD) para procesar indicadores económicos del DANE. Incluye gobernanza de datos, validación de calidad, trazabilidad completa, y reportes automatizados.

---

## Características Principales

✨ **Medallion Architecture** (BRONZE/SILVER/GOLD layers)
📊 **Rich Data Quality Checks** (schema, uniqueness, time consistency, outliers)
📝 **Complete Traceability** (execution manifests, file hashes, logging)
🔧 **CLI Orchestrator** (run individual stages or complete pipeline)
📈 **YAML Configuration** (sources, schemas, transformations)
✅ **Unit Tests** (pytest with coverage)

---

## Estructura del Proyecto

```
proyecto_seminario/
├── config/
│   ├── sources.yaml           # Definición de fuentes de datos
│   └── schema.yaml            # Esquemas esperados y reglas de validación
│
├── data/
│   ├── raw/                   # BRONZE: Archivos Excel originales
│   ├── silver/                # SILVER: Datos estandarizados (parquet)
│   ├── gold/                  # GOLD: Tablas analíticas (parquet)
│   ├── processed/             # LEGACY: Salidas compatibles con v1
│   └── data_dictionary.md     # Metadatos de variables
│
├── logs/
│   └── pipeline.log           # Log consolidado de la pipeline
│
├── reports/
│   ├── run_manifest.json      # Manifiesto ejecutado (timestamps, hashes, etc.)
│   ├── quality_report.md      # Informe de calidad de datos (rich Markdown)
│   ├── quality_checks.csv     # Resultados de validaciones (CSV)
│   ├── raw_manifest.csv       # Catálogo de archivos raw
│   ├── dashboard_prototype.html
│   ├── duplicates_rows.csv
│
├── src/
│   ├── __init__.py
│   ├── pipeline.py            # Orchestrador con CLI
│   └── etl/
│       ├── __init__.py
│       ├── utils.py           # Utilities: hashing, IO, logging, etc.
│       ├── ingest.py          # BRONZE: Descubrimiento de archivos
│       ├── clean.py           # SILVER: Limpieza y estandarización
│       ├── quality.py         # Validación de calidad
│       ├── quality_new.py     # (Refactored - usar este después de migrar)
│       ├── find_duplicates.py # Análisis de duplicados
│       └── inspect_raw.py     # Inspección de layouts
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Fixtures de pytest
│   ├── test_quality.py        # Tests para validación
│   └── test_ingest.py         # Tests para ingesta
│
├── notebooks/
│   └── dashboard_prototype.ipynb
│
├── requirements.txt
└── README.md
```

---

## Instalación y Configuración

### 1. Crear entorno virtual

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 2. Instalar dependencias

```powershell
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install matplotlib seaborn jupyter nbconvert   # Para dashboard
```

### 3. Verificar instalación

```powershell
python -c "import pandas, pyarrow, yaml; print('✅ OK')"
```

---

## Uso de la Pipeline

### Opción 1: CLI (Recomendado)

```powershell
# Ejecutar pipeline completa
python -m src.pipeline run --stage all

# Ejecutar solo BRONZE (descubrir archivos)
python -m src.pipeline run --stage bronze

# Ejecutar solo SILVER (limpiar datos)
python -m src.pipeline run --stage silver

# Ejecutar solo GOLD (analítica)
python -m src.pipeline run --stage gold

# Validar calidad de datos
python -m src.pipeline validate

# Generar todos los reportes
python -m src.pipeline build-report
```

### Opción 2: Scripts individuales (Legacy)

```powershell
python src/etl/ingest.py       # Descubrir y catalogar
python src/etl/clean.py        # Limpiar y estandarizar
python src/etl/find_duplicates.py   # Análisis de duplicados
python src/etl/quality.py      # Validación básica (viejo)
```

### Opción 3: Python directo

```python
from src.etl import ingest, clean, quality_new

# Ingesta
ingest.main()

# Limpieza
df = clean.main()

# Validación
quality_new.main()
```

---

## Arquitectura de Datos

### BRONZE (data/raw)
- **Naturaleza**: Datos crudos sin transformar
- **Contenido**: Archivos Excel originales del DANE (FBCF, GEIH, IIOC)
- **Gobernanza**: Inmutables, con hash SHA256 registrado en `raw_manifest.csv`

### SILVER (data/silver)
- **Naturaleza**: Datos limpios y estandarizados
- **Contenido**: `indicators_tidy.parquet` en formato long (tidy)
- **Gobernanza**: Una fila = (date, indicator), sin duplicados
- **Validación**: Schema, missingness, uniqueness

### GOLD (data/gold)
- **Naturaleza**: Tablas analíticas de negocio
- **Contenido**:
  - `national_panel.parquet`: Un año per row con agregados por fuente
  - `metrics_summary.parquet`: Tasas de cambio, promedios móviles, lags

---

## Robustez y tolerancia a fallos

- **Safe Parquet reads**: `utils.safe_read_parquet()` reintenta lecturas con backoff y registra advertencias.
- **Cuartentena automática**: durante la ingesta, si un archivo no puede ser hasheado se mueve a
  `data/quarantine/` para inspección manual y se omite del manifiesto.
- **Patrones configurables**: `discover_raw_files()` puede cargar `file_pattern` desde
  `config/sources.yaml`, lo que permite filtrar archivos sin cambiar el código.
- **Pruebas incluidas**: la suite de `pytest` ahora verifica el comportamiento de reintentos
y el manejo de cuarentena.

## Configuración (YAML)

### config/sources.yaml
Define cada fuente de datos: archivo, sheet, frequencia, mapeo de columnas.

```yaml
sources:
  fbcf_an112:
    name: "FBCF - Otros edificios"
    file_pattern: "anex-GastoConstantes*.xlsx"
    sheet: "Cuadro 5"
    frequency: "quarterly"
    join_key: ["year", "quarter"]
```

### config/schema.yaml
Define esquemas esperados, tipos de datos, reglas de validación y umbrales de calidad.

```yaml
schemas:
  silver_tidy:
    columns:
      date:
        dtype: "datetime64[ns]"
        required: true
        null_threshold: 0.0
      value:
        dtype: "float64"
        required: true
        null_threshold: 0.05
        validation:
          non_negative: true
          range: [0, 10000]
```

---

## Gobernanza y Trazabilidad

### Run Manifest (reports/run_manifest.json)
Captura metadatos de cada ejecución:
```json
{
  "timestamp": "2024-03-05T10:30:45",
  "stage": "silver_clean",
  "git_commit": "abc123...",
  "input_files": {...},
  "input_file_hashes": {"file1.xlsx": "sha256_hash"},
  "output_rows": {"tidy": 1250},
  "warnings": [],
  "errors": []
}
```

### Logging (logs/pipeline.log)
Registro continuo con INFO / WARNING / ERROR para cada etapa.

### Data Dictionary (data/data_dictionary.md)
Documentación automática de variables, fuentes, unidades, transformaciones.

---

## Validación de Calidad

El modulo `quality_new.py` ejecuta:

1. **Schema Validation**: Columnas requeridas y tipos de datos
2. **Missingness Check**: % de nulos por columna (threshold: 10%)
3. **Uniqueness**: Clave (date, indicator) sin duplicados
4. **Time Consistency**: Fechas monótonas, sin gaps anómalos
5. **Value Ranges**: No negativos, dentro de límites [0, 1M]
6. **Outlier Detection**: IQR method (solo reporte, sin drop)

Generan reportes en:
- `reports/quality_report.md` (Rich Markdown)
- `reports/quality_checks.csv` (Detallado por check)

---

## Testing

```powershell
# Correr todos los tests
pytest tests/ -v

# Con cobertura
pytest tests/ --cov=src --cov-report=html

# Tests específicos
pytest tests/test_quality.py -v
pytest tests/test_ingest.py -v
```

---

## Troubleshooting

### Error: "No Excel files found in data/raw"
- Verificar que Excel files (`*.xlsx`, `*.xls`) están en `data/raw/`
- Revisar nombres de sheets en los archivos (ver inspect_raw.py)

### Quality checks failing
- Revisar `reports/quality_report.md`
- Ajustar thresholds en `config/schema.yaml` si es necesario
- Ver logs en `logs/pipeline.log`

### Import errors
- Reinstalar dependencias: `pip install -r requirements.txt --force-reinstall`
- Verificar Python >= 3.8: `python --version`

---

## Notas de Migración (v1 → v2)

- ✅ Outputs legacy mantenidos en `data/processed/` (CSV + Parquet)
- ✅ Scripts individuales aún funcionan
- 📝 Usar CLI `python -m src.pipeline` para nuevos workflows
- 📝 Nueva refactorización en `quality_new.py` (reemplazar quality.py cuando listo)

---

## Recursos

- **DANE**: https://www.dane.gov.co/
- **Pandas Docs**: https://pandas.pydata.org/docs/
- **PyArrow**: https://arrow.apache.org/docs/python/
- **Pytest**: https://docs.pytest.org/

---

## Autor

Desarrollo de ética e integridad. Parte del seminario de data engineering.

---

**Última actualización**: 2024-03-05 | **Versión**: 2.0.0 | **Status**: Production-ready ✅