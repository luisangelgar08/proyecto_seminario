# proyecto_seminario

Este repositorio contiene un proyecto desarrollado como parte del hito numero 2.

El objetivo es construir un pipeline ETL que tome datos en bruto (Excel del DANE) y produzca un conjunto de datos tidy listo para análisis, junto con un prototipo de dashboard para visualizar indicadores económicos.

---

## Estructura del proyecto

```
README.md
requirements.txt

data/
  raw/                    # Excels originales (input)
  processed/              # Salidas del pipeline (CSV/Parquet)

notebooks/
  dashboard_prototype.ipynb  # Notebook con explorarión y gráficas

reports/
  dashboard_prototype.html  # HTML resultante del notebook
  duplicates_rows.csv        # Hallazgos de duplicados
  quality_report.md          # Informe de calidad de los datos

src/
  etl/
    ingest.py           # registra archivos raw y crea un manifiesto
    clean.py            # parsea y limpia cada Excel, genera indicators_tidy
    find_duplicates.py  # identifica filas duplicadas en el dataset tidy
    quality.py          # genera métricas básicas de calidad
```

---

## Requisitos y configuración

El proyecto usa Python 3 (con venv). Las dependencias principales se listan en `requirements.txt` y se instalan con pip.

```powershell
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt matplotlib seaborn jupyter nbconvert
```

## Uso

1. Coloque los archivos Excel originales dentro de `data/raw/`.
2. Ejecute el pipeline completo:
   ```powershell
   .venv\Scripts\python.exe src/etl/ingest.py
   .venv\Scripts\python.exe src/etl/clean.py
   .venv\Scripts\python.exe src/etl/find_duplicates.py
   .venv\Scripts\python.exe src/etl/quality.py
   ```
3. Revise las salidas en `reports/` y el dataset final en `data/processed/`.
4. Para explorar los datos y visualizar los indicadores, abra el notebook o su versión HTML:
   ```powershell
   # opción rápida: servir carpeta reports y abrir en navegador
   cd reports
   .\..\ .venv\Scripts\python.exe -m http.server 8000
   # luego visita http://localhost:8000/dashboard_prototype.html
   ```

## ¿Qué hace cada componente?

- **ingest.py**: construye un manifiesto con hashes y tamaños de todos los archivos raw, útil para auditoría.
- **clean.py**: procesa los Excel según la lógica interna de cada serie y unifica los datos en formato tidy. Agrega columna `year` y guarda CSV/Parquet.
- **find_duplicates.py**: genera reporte con duplicados (si hay) en `date`+`indicator`.
- **quality.py**: crea un pequeño informe (`quality_report.md`) con conteos de nulos, duplicados, min/max de fechas y número de indicadores.
- **dashboard_prototype.ipynb**: notebook de prototipo que importa el dataset limpio y genera visualizaciones de evolución temporal y comparación de indicadores.

## Notas

- Los datos provienen de DANE: Cuentas Nacionales, GEIH, IIOC.
- El dataset final (`indicators_tidy.csv`) contiene columnas: `date`,`value`,`indicator`,`source`,`unit`,`frequency`,`year`.
- Actualmente no hay duplicados en el dataset y el rango de fechas va de 1999 a 2023.

---

Cualquier duda adicional sobre la estructura o el funcionamiento puede consultarse directamente en los scripts dentro de `src/etl/` o en el notebook.

