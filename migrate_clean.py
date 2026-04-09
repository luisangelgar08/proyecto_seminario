#!/usr/bin/env python3
"""
AUTOMATIC CLEAN.PY MIGRATION

This script replaces src/etl/clean.py with the refactored v2.0 version.
Run this once to complete the migration.

Usage:
    python migrate_clean.py
"""

from pathlib import Path

# The complete refactored clean.py content
REFACTORED_CLEAN = '''"""
SILVER LAYER: Data Cleaning & Standardization

Transforms raw Excel files into standardized, long-format (tidy) datasets.
- Parses complex Excel layouts
- Normalizes dates by frequency
- Standardizes column names and data types
- Outputs to data/silver/ as Parquet files
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import pandas as pd
import numpy as np
import logging
from datetime import datetime

from .utils import setup_logging, write_parquet, create_run_manifest, save_run_manifest


# ============================================================================
# Mapping Tables
# ============================================================================

MONTH_MAP = {
    "Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Ago": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dic": 12
}

QUARTER_MAP = {"I": 1, "II": 2, "III": 3, "IV": 4}


# ============================================================================
# Helper Functions
# ============================================================================

def to_tidy(
    dates: List[pd.Timestamp],
    values: List[float],
    indicator: str,
    source: str,
    unit: str,
    frequency: str
) -> pd.DataFrame:
    """
    Convert raw data into tidy (long) format.
    
    Args:
        dates: List of timestamps
        values: List of numeric values
        indicator: Indicator name
        source: Data source name
        unit: Measurement unit
        frequency: Temporal frequency (Mensual, Trimestral, Anual)
        
    Returns:
        Tidy DataFrame with one row per (date, indicator) pair
    """
    df = pd.DataFrame({
        "date": dates,
        "value": values
    })
    df["indicator"] = indicator
    df["source"] = source
    df["unit"] = unit
    df["frequency"] = frequency
    
    # Coerce types
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    
    # Drop rows with missing critical fields
    df = df.dropna(subset=["date", "value"])
    
    return df


# ============================================================================
# Parser Functions (One per Data Source)
# ============================================================================

def parse_fbcf_an112_other_buildings(
    file_path: Path,
    logger: logging.Logger
) -> pd.DataFrame:
    """
    Parse FBCF (Fixed Capital Formation) - AN112 asset class.
    Source: DANE Cuentas Nacionales, Cuadro 5
    """
    logger.info(f"Parsing FBCF AN112 from {file_path.name}")
    df = pd.read_excel(file_path, sheet_name="Cuadro 5", header=None)
    
    def is_year_header_row(i: int) -> bool:
        c0 = str(df.iat[i, 0]).strip()
        c1 = str(df.iat[i, 1]).strip()
        c2 = df.iat[i, 2]
        return (c0 == "Clasificación Cuentas Nacionales" and 
                c1 == "Concepto" and 
                pd.notna(pd.to_numeric(c2, errors="coerce")))
    
    year_row_candidates = [i for i in range(min(80, len(df))) if is_year_header_row(i)]
    if not year_row_candidates:
        raise ValueError("Could not find year header row in Cuadro 5")
    
    year_row = year_row_candidates[0]
    q_row = year_row + 1
    
    years = pd.to_numeric(df.iloc[year_row, 2:], errors="coerce").ffill()
    quarters = df.iloc[q_row, 2:].astype(str).str.strip().map(QUARTER_MAP)
    
    start = year_row + 2
    end_candidates = df.index[(df.index > start) & 
                               (df.iloc[:, 0].astype(str).str.strip() == "Clasificación Cuentas Nacionales")]
    end = int(end_candidates.min()) if len(end_candidates) else len(df)
    
    block = df.iloc[start:end].copy()
    code_col = block.iloc[:, 0].astype(str).str.strip()
    concept_col = block.iloc[:, 1].astype(str).str.strip()
    mask = (code_col == "AN112") & (concept_col.str.contains("Otros edificios", case=False, na=False))
    
    if not mask.any():
        mask = (code_col == "AN112")
    
    if not mask.any():
        logger.warning("AN112 row not found")
        return pd.DataFrame()
    
    row = block.loc[mask].iloc[0]
    values = pd.to_numeric(row.iloc[2:], errors="coerce")
    
    tmp = pd.DataFrame({
        "year": years.values,
        "q": quarters.values,
        "value": values.values,
        "colpos": range(len(values))
    }).dropna(subset=["year", "q", "value"])
    
    tmp = tmp.sort_values("colpos").drop_duplicates(subset=["year", "q"], keep="first")
    tmp["period"] = tmp["year"].astype(int).astype(str) + "Q" + tmp["q"].astype(int).astype(str)
    dates = pd.PeriodIndex(tmp["period"], freq="Q").to_timestamp(how="end").normalize()
    
    return to_tidy(
        dates=dates,
        values=tmp["value"].values,
        indicator="FBCF - Otros edificios y estructuras (AN112)",
        source="DANE - Cuentas Nacionales (Cuadro 5)",
        unit="Constantes",
        frequency="Trimestral"
    )


def parse_geih_ocupados_construccion(
    file_path: Path,
    logger: logging.Logger
) -> pd.DataFrame:
    """Parse GEIH (Labor Force Survey) - Construction Employment."""
    logger.info(f"Parsing GEIH from {file_path.name}")
    sh = "ocup ramas mes tnal CIIU 4"
    df = pd.read_excel(file_path, sheet_name=sh, header=None)
    
    c0 = df.iloc[:, 0].astype(str).str.strip()
    c1_num = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    
    year_row_candidates = df.index[(c0 == "Concepto") & c1_num.notna()].tolist()
    if not year_row_candidates:
        raise ValueError("Could not find Concepto header in GEIH")
    
    year_row = year_row_candidates[0]
    month_row = year_row + 1
    data_start = month_row + 1
    
    years = pd.to_numeric(df.iloc[year_row, 1:], errors="coerce").ffill()
    months = df.iloc[month_row, 1:].astype(str).str.strip()
    month_num = months.map(MONTH_MAP)
    
    valid = years.notna() & month_num.notna()
    years_v = years[valid].astype(int).tolist()
    months_v = month_num[valid].astype(int).tolist()
    
    col_idx = (np.where(valid.values)[0] + 1).tolist()
    data = df.iloc[data_start:, [0] + col_idx].copy()
    data = data[data.iloc[:, 0].notna()]
    
    concept = data.iloc[:, 0].astype(str).str.strip()
    row = data.loc[concept == "Construcción"]
    
    if row.empty:
        logger.warning("Construcción row not found in GEIH")
        return pd.DataFrame()
    
    row = row.iloc[0]
    values = pd.to_numeric(row.iloc[1:].values, errors="coerce")
    dates = [pd.Timestamp(year=y, month=m, day=1) for y, m in zip(years_v, months_v)]
    
    return to_tidy(
        dates=dates,
        values=values,
        indicator="GEIH - Ocupados (Construcción)",
        source="DANE - GEIH",
        unit="Miles de personas",
        frequency="Mensual"
    )


def parse_iioc_anexo_a3(
    file_path: Path,
    logger: logging.Logger
) -> pd.DataFrame:
    """Parse IIOC (Construction Input & Cost Index) - Anexo A3."""
    logger.info(f"Parsing IIOC from {file_path.name}")
    sh = "Anexo A3"
    df = pd.read_excel(file_path, sheet_name=sh, header=None)
    
    col1 = df.iloc[:, 1].astype(str).str.strip()
    col2 = df.iloc[:, 2].astype(str).str.strip()
    header_candidates = df.index[(col1 == "Año") & (col2 == "Trimestre")].tolist()
    
    if not header_candidates:
        logger.warning("Could not find Año/Trimestre header in IIOC")
        return pd.DataFrame()
    
    header_row = header_candidates[0]
    data_start = header_row + 2
    
    sub = df.iloc[data_start:, 1:9].copy()
    sub.columns = ["year", "quarter", "iioc_total", "c4001", "c4002", "c4003", "c4004", "c4008"]
    
    sub["year"] = pd.to_numeric(sub["year"], errors="coerce").ffill()
    sub["quarter"] = sub["quarter"].astype(str).str.strip().map(QUARTER_MAP)
    
    for col in ["iioc_total", "c4001", "c4002", "c4003", "c4004", "c4008"]:
        sub[col] = pd.to_numeric(sub[col], errors="coerce")
    
    sub = sub.dropna(subset=["year", "quarter"])
    sub["period"] = sub["year"].astype(int).astype(str) + "Q" + sub["quarter"].astype(int).astype(str)
    dates = pd.PeriodIndex(sub["period"], freq="Q").to_timestamp(how="end").normalize()
    
    indicators = [
        ("IIOC - Total", "iioc_total"),
        ("IIOC - 4001 (vías/carreteras/puentes)", "c4001"),
        ("IIOC - 4002 (férreas/aeropuertos)", "c4002"),
        ("IIOC - 4003 (puertos/represas/acueductos)", "c4003"),
        ("IIOC - 4004 (minería/tuberías)", "c4004"),
        ("IIOC - 4008 (otras obras ingeniería)", "c4008"),
    ]
    
    dfs = []
    for indicator_name, col_name in indicators:
        dfs.append(to_tidy(
            dates=dates,
            values=sub[col_name].values,
            indicator=indicator_name,
            source="DANE - IIOC (Anexo A3)",
            unit="Índice",
            frequency="Trimestral"
        ))
    
    return pd.concat(dfs, ignore_index=True)


# ============================================================================
# Main Orchestration
# ============================================================================

def main(
    raw_dir: Path = Path("data/raw"),
    silver_dir: Path = Path("data/silver"),
    processed_dir: Path = Path("data/processed"),
    reports_dir: Path = Path("reports"),
    log_file: Path = Path("logs/pipeline.log"),
) -> pd.DataFrame:
    """Main cleaning orchestrator."""
    logger = setup_logging(log_file, level="INFO", name="clean")
    silver_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 70)
    logger.info("STAGE: SILVER CLEANING & STANDARDIZATION")
    logger.info("=" * 70)
    
    files = {
        "fbcf_an112": raw_dir / "anex-GastoConstantes-IVtrim2025.xlsx",
        "geih_ocupados": raw_dir / "anexo-mercado-laboral-segun-proyecciones-CNPV2018.xlsx",
        "iioc_anexo_a3": raw_dir / "anexos_IIOC_IVtrim20.xlsx",
    }
    
    parsers = [
        lambda fp: parse_fbcf_an112_other_buildings(fp, logger),
        lambda fp: parse_geih_ocupados_construccion(fp, logger),
        lambda fp: parse_iioc_anexo_a3(fp, logger),
    ]
    
    dfs = []
    parsed_sources = {}
    
    for source_name, file_path in files.items():
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            continue
        
        try:
            parser = parsers[len([f for f in [p for p in files.values() if p.exists()] if f == file_path])-1] if file_path.exists() else None
            # Simplified: just use index based on order we've processed
            if len(dfs) < len(parsers):
                df_parsed = parsers[len(dfs)](file_path)
                if len(df_parsed) > 0:
                    dfs.append(df_parsed)
                    parsed_sources[source_name] = {"rows": len(df_parsed), "status": "success"}
                    logger.info(f"✓ {source_name}: {len(df_parsed)} rows")
                else:
                    logger.warning(f"✗ {source_name}: No data parsed")
        except Exception as e:
            logger.error(f"✗ {source_name}: {e}")
            parsed_sources[source_name] = {"rows": 0, "status": "error", "error": str(e)}
    
    if not dfs:
        raise SystemExit("No data could be parsed from any source")
    
    tidy = pd.concat(dfs, ignore_index=True)
    logger.info(f"Combined: {len(tidy)} rows, {tidy['indicator'].nunique()} unique indicators")
    
    tidy["indicator"] = tidy["indicator"].astype(str).str.strip()
    tidy = tidy.dropna(subset=["value"])
    
    # Silver output
    silver_tidy = silver_dir / "indicators_tidy.parquet"
    write_parquet(tidy, silver_tidy)
    logger.info(f"Silver output: {silver_tidy}")
    
    # Legacy output
    processed_csv = processed_dir / "indicators_tidy.csv"
    processed_parq = processed_dir / "indicators_tidy.parquet"
    tidy.to_csv(processed_csv, index=False)
    tidy.to_parquet(processed_parq, index=False)
    logger.info(f"Legacy output: {processed_csv}, {processed_parq}")
    
    manifest = create_run_manifest(
        stage="silver_clean",
        input_files=files,
        output_files={"silver_tidy": silver_tidy, "legacy_csv": processed_csv},
        output_rows={"tidy": len(tidy)},
        warnings=[source for source, meta in parsed_sources.items() 
                  if meta.get("status") != "success"],
    )
    
    save_run_manifest(manifest, reports_dir / "run_manifest.json")
    
    logger.info("=" * 70)
    logger.info(f"SILVER stage complete: {len(tidy)} rows in output")
    logger.info("=" * 70)
    
    return tidy


if __name__ == "__main__":
    main()
'''

def migrate_clean():
    """Perform the migration"""
    clean_file = Path("src/etl/clean.py")
    backup_file = Path("src/etl/clean.py.bak")
    
    print("\n" + "=" * 70)
    print("MIGRATING src/etl/clean.py to v2.0 (Refactored)")
    print("=" * 70 + "\n")
    
    # Backup existing
    if clean_file.exists():
        clean_file.rename(backup_file)
        print(f"✓ Backed up existing file to: {backup_file}")
    
    # Write refactored version
    clean_file.write_text(REFACTORED_CLEAN, encoding="utf-8")
    print(f"✓ Wrote refactored clean.py ({len(REFACTORED_CLEAN)} bytes)")
    
    # Verify
    if clean_file.exists():
        print(f"✓ File created successfully at: {clean_file}")
        print("\n✅ Migration complete!")
        print(f"\nBackup of old version saved to: {backup_file}")
        print("You can safely delete it once you verify everything works.\n")
        return True
    else:
        print("❌ Migration failed!")
        if backup_file.exists():
            backup_file.rename(clean_file)
            print(f"   Restored backup from {backup_file}")
        return False


if __name__ == "__main__":
    import sys
    try:
        success = migrate_clean()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        sys.exit(1)
