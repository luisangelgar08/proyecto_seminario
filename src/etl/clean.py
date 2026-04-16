"""
SILVER LAYER: Data Cleaning & Standardization

Transforms raw Excel files into standardized, long-format (tidy) datasets.
- Parses complex Excel layouts using config
- Normalizes time index into year and quarter
- Standardizes units and numeric formats
- Harmonizes indicator names into indicator_id taxonomy
- Outputs SILVER tables per source + unified data/silver/indicators_tidy.parquet
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from sklearn import logger
import yaml

from .utils import setup_logging, write_parquet, create_run_manifest, save_run_manifest


# ============================================================================
# Directory Paths
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW = BASE_DIR / "data" / "raw"
OUT = BASE_DIR / "data" / "processed"
SILVER = BASE_DIR / "data" / "silver"
CONFIG = BASE_DIR / "config"
LOGS = BASE_DIR / "logs"

# Ensure directories exist
OUT.mkdir(parents=True, exist_ok=True)
SILVER.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Indicator Taxonomy Mapping
# ============================================================================

INDICATOR_TAXONOMY = {
    "fbcf_investment": "inv_pib",
    "geih_construction_employment": "empleo_const",
    "iioc_construction_cost_index": "iioc",
    "fiscal_spending_constants": "gasto_const",
    "logistics_performance_index": "logistics_lpi",
    "infrastructure_investment_projects": "inv_proyectos",
    "construction_production_value": "pib_const"
}

MONTH_MAP = {
    "enero": 1, "ene": 1,
    "febrero": 2, "feb": 2,
    "marzo": 3, "mar": 3,
    "abril": 4, "abr": 4,
    "mayo": 5, "may": 5,
    "junio": 6, "jun": 6,
    "julio": 7, "jul": 7,
    "agosto": 8, "ago": 8,
    "septiembre": 9, "sep": 9, "setiembre": 9, "set": 9,
    "octubre": 10, "oct": 10,
    "noviembre": 11, "nov": 11,
    "diciembre": 12, "dic": 12,
}

QUARTER_MAP = {
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "i": 1,
    "ii": 2,
    "iii": 3,
    "iv": 4,
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "t1": 1,
    "t2": 2,
    "t3": 3,
    "t4": 4,
    "trimestre 1": 1,
    "trimestre 2": 2,
    "trimestre 3": 3,
    "trimestre 4": 4,
}
# ============================================================================
# Helper Functions
# ============================================================================

def load_sources_config() -> List[Dict]:
    """Load sources configuration from YAML."""
    config_path = CONFIG / "sources.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data['sources']


def standardize_time(df: pd.DataFrame, frequency: str) -> pd.DataFrame:
    """Add year and quarter columns based on frequency."""
    if frequency.lower() == "annual":
        if 'year' not in df.columns:
            df['year'] = pd.to_datetime(df.get('date', df.get('year')), errors='coerce').dt.year
        df['quarter'] = None
    elif frequency.lower() == "quarterly":
        if 'year' not in df.columns or 'quarter' not in df.columns:
            # Assume date column or infer
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df['year'] = df['date'].dt.year
                df['quarter'] = df['date'].dt.quarter
            else:
                # Assume year and quarter present
                pass
    elif frequency.lower() == "monthly":
        if 'year' not in df.columns or 'month' not in df.columns:
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df['year'] = df['date'].dt.year
                df['month'] = df['date'].dt.month
        df['quarter'] = np.ceil(df['month'] / 3).astype('Int64')
    return df


def harmonize_indicator_names(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """Add indicator_id column using taxonomy."""
    df['indicator_id'] = INDICATOR_TAXONOMY.get(source_name, source_name)
    return df

## funcion nueva
def parse_ipoc_quarterly(file_path, logger):
    logger.info(f"Parsing IPOC quarterly data from {file_path.name}")

    df = pd.read_excel(file_path, sheet_name="Sheet1")

    # limpiar nombres de columnas
    df.columns = [str(c).strip() for c in df.columns]

    required_cols = ["Año", "Trimestre"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas en IPOC: {missing}")

    value_cols = [c for c in df.columns if c not in ["Año", "Trimestre"]]
    if not value_cols:
        raise ValueError("No se encontraron columnas de valores en IPOC")

    tidy = df.melt(
        id_vars=["Año", "Trimestre"],
        value_vars=value_cols,
        var_name="indicator",
        value_name="value"
    )

    tidy = tidy.rename(columns={
        "Año": "year",
        "Trimestre": "quarter"
    })

    tidy["year"] = pd.to_numeric(tidy["year"], errors="coerce")
    tidy["quarter"] = pd.to_numeric(tidy["quarter"], errors="coerce")
    tidy["value"] = pd.to_numeric(tidy["value"], errors="coerce")

    tidy = tidy.dropna(subset=["year", "quarter", "value"]).copy()

    tidy["year"] = tidy["year"].astype(int)
    tidy["quarter"] = tidy["quarter"].astype(int)

    # fecha trimestral
    tidy["date"] = pd.PeriodIndex(
        tidy["year"].astype(int).astype(str) + "Q" + tidy["quarter"].astype(int).astype(str),
        freq="Q"
    ).to_timestamp(how="end")

    tidy["indicator"] = (
        tidy["indicator"]
            .astype(str)
            .str.strip()
            .str.lower()
            .str.replace(" ", "_", regex=False)
    )

    tidy["source"] = "IPOC"
    tidy["unit"] = "Índice"
    tidy["frequency"] = "Trimestral"
    tidy["indicator_id"] = tidy["indicator"]

    tidy = tidy[
        ["date", "year", "quarter", "indicator", "value", "source", "unit", "frequency", "indicator_id"]
    ].sort_values(["date", "indicator"]).reset_index(drop=True)
    print("IPOC columns:", tidy.columns.tolist())
    print(tidy.head(5).to_string())
    print(tidy["indicator_id"].value_counts(dropna=False)) 
 
    return tidy

##---------------------------------

def parse_source(source: Dict, logger: logging.Logger) -> pd.DataFrame:
    """Parse a single source based on config."""
    file_path = RAW / source['file_path']
    if source["name"] == "ipoc_quarterly":
        return parse_ipoc_quarterly(file_path, logger)
    if not file_path.exists():
        logger.warning(f"File {file_path} not found, skipping {source['name']}")
        return pd.DataFrame()
    
    # Use specific parsers for known complex files
    if source['name'] == 'fbcf_investment':
        return parse_fbcf_an112_other_buildings(file_path, logger)
    elif source['name'] == 'geih_construction_employment':
        return parse_geih_ocupados_construccion(file_path, logger)
    elif source['name'] == 'iioc_construction_cost_index':
        return parse_iioc_anexo_a3(file_path, logger)
    elif source['name'] == 'fiscal_spending_constants':
        # Placeholder: assume similar to fbcf but different sheet
        try:
            df = pd.read_excel(file_path, sheet_name=source['sheet_name'], header=None)
            # Simple parsing: assume year, quarter, value in columns
            # This is placeholder; adjust as needed
            logger.warning(f"Using placeholder parser for {source['name']}")
            return pd.DataFrame()  # Return empty for now
        except Exception as e:
            logger.error(f"Failed to parse {source['name']}: {e}")
            return pd.DataFrame()
    else:
        # Generic parser for simple files
        try:
            df = pd.read_excel(file_path, sheet_name=source['sheet_name'], usecols=source.get('usecols'))
            if source.get('rename_map'):
                df = df.rename(columns=source['rename_map'])
            
            # Assume columns are as per keys + value
            keys = source['keys']
            if 'value' not in df.columns:
                df = df.rename(columns={df.columns[-1]: 'value'})
            
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna(subset=keys + ['value'])
            
            # Add metadata
            df['source'] = source['name']
            df['unit'] = source['units']
            df['frequency'] = source['frequency']
            
            # Standardize time
            df = standardize_time(df, source['frequency'])
            
            # Harmonize indicator
            df = harmonize_indicator_names(df, source['name'])
            
            # Create date if not present
            if 'date' not in df.columns:
                if 'quarter' in df.columns and df['quarter'].notna().any():
                    df['date'] = pd.PeriodIndex(df['year'].astype(str) + 'Q' + df['quarter'].astype(str), freq='Q').to_timestamp()
                elif 'month' in df.columns:
                    df['date'] = pd.to_datetime(df[['year', 'month']].assign(day=1))
                else:
                    df['date'] = pd.to_datetime(df['year'], format='%Y')
            
            logger.info(f"Parsed {source['name']}: {len(df)} rows")
            return df
        except Exception as e:
            logger.error(f"Failed to parse {source['name']}: {e}")
            return pd.DataFrame()


def parse_fbcf_an112_other_buildings(file_path: Path, logger: logging.Logger) -> pd.DataFrame:
    """Parse FBCF (Fixed Capital Formation) - AN112 asset class."""
    logger.info(f"Parsing FBCF AN112 from {file_path.name}")
    df = pd.read_excel(file_path, sheet_name="Sheet1", header=None)
    def is_year_header_row(i: int) -> bool:
        c0 = str(df.iat[i, 0]).strip()
        c1 = str(df.iat[i, 1]).strip()
        c2 = df.iat[i, 2]
        return (c0 == "Clasificación Cuentas Nacionales" and c1 == "Concepto" and pd.notna(pd.to_numeric(c2, errors="coerce")))
    year_row_candidates = [i for i in range(min(80, len(df))) if is_year_header_row(i)]
    if not year_row_candidates:
        raise ValueError("Could not find year header row in Cuadro 5")
    year_row = year_row_candidates[0]
    q_row = year_row + 1
    years = pd.to_numeric(df.iloc[year_row, 2:], errors="coerce").ffill()
    quarters = df.iloc[q_row, 2:].astype(str).str.strip().map(QUARTER_MAP)
    start = year_row + 2
    end_candidates = df.index[(df.index > start) & (df.iloc[:, 0].astype(str).str.strip() == "Clasificación Cuentas Nacionales")]
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
    tmp = pd.DataFrame({"year": years.values, "q": quarters.values, "value": values.values, "colpos": range(len(values))}).dropna(subset=["year", "q", "value"])
    tmp = tmp.sort_values("colpos").drop_duplicates(subset=["year", "q"], keep="first")
    tmp["period"] = tmp["year"].astype(int).astype(str) + "Q" + tmp["q"].astype(int).astype(str)
    dates = pd.PeriodIndex(tmp["period"], freq="Q").to_timestamp(how="end").normalize()
    df_out = pd.DataFrame({
        "date": dates,
        "value": tmp["value"].values,
        "year": tmp["year"].astype(int),
        "quarter": tmp["q"].astype(int),
        "indicator_id": "inv_pib",
        "source": "fbcf_investment",
        "unit": "Millones de pesos constantes",
        "frequency": "Trimestral"
    })
    return df_out


def parse_geih_ocupados_construccion(file_path: Path, logger: logging.Logger) -> pd.DataFrame:
    """Parse GEIH (Labor Force Survey) - Construction Employment."""
    logger.info(f"Parsing GEIH from {file_path.name}")
    xls = pd.ExcelFile(file_path)
    candidate_sheets = [
        "ocup ramas mes tnal CIIU 4",
        "ocup ramas mes total CIIU 4",
        "ocup ramas mes tnal",
        "ocup ramas mes total",
    ]

    sh = None
    for s in candidate_sheets:
        if s in xls.sheet_names:
            sh = s
            break

    if sh is None:
        sh = xls.sheet_names[0]
        logger.warning(f"No se encontró hoja GEIH esperada; usando {sh}")

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
    months = df.iloc[month_row, 1:].astype(str).str.strip().str.lower()
    month_num = months.map(MONTH_MAP)

    valid = years.notna() & month_num.notna()
    years_v = years[valid].astype(int).tolist()
    months_v = month_num[valid].astype(int).tolist()
    col_idx = (np.where(valid.values)[0] + 1).tolist()

    data = df.iloc[data_start:, [0] + col_idx].copy()
    data = data[data.iloc[:, 0].notna()]

    concept = data.iloc[:, 0].astype(str).str.strip().str.lower()
    row = data.loc[concept.str.contains("constru", na=False)]

    if row.empty:
        logger.warning("Construcción row not found in GEIH")
        return pd.DataFrame()

    row = row.iloc[0]
    values = pd.to_numeric(row.iloc[1:].values, errors="coerce")

    df_out = pd.DataFrame({
        "date": [pd.Timestamp(year=y, month=m, day=1) for y, m in zip(years_v, months_v)],
        "value": values,
        "year": years_v,
        "month": months_v,
        "quarter": pd.Series(months_v).apply(lambda m: (m - 1) // 3 + 1).astype(int),
        "indicator": "empleo_construccion",
        "indicator_id": "empleo_const",
        "source": "geih_construction_employment",
        "unit": "Miles de personas",
        "frequency": "Mensual"
    })

    df_out = df_out.dropna(subset=["date", "value"]).reset_index(drop=True)

    logger.info(f"GEIH parsed rows: {len(df_out)}")
    logger.info(f"GEIH hoja usada: {sh}")
    logger.info(f"GEIH year_row: {year_row}, month_row: {month_row}")
    logger.info(f"GEIH months sample: {months.head(12).tolist()}")
    logger.info(f"GEIH month_num sample: {month_num.head(12).tolist()}")
    logger.info(f"GEIH valid columns: {int(valid.sum())}")
    logger.info(f"GEIH data shape: {data.shape}")
    logger.info(f"GEIH concept sample: {concept.head(10).tolist()}")
    logger.info(f"GEIH constru matches: {int(concept.str.contains('constru', na=False).sum())}")
    return df_out


def parse_iioc_anexo_a3(file_path: Path, logger: logging.Logger) -> pd.DataFrame:
    """Parse IIOC Anexo A3."""
    logger.info(f"Parsing IIOC Anexo A3 from {file_path.name}")
    sh = "Anexo A3"
    df = pd.read_excel(file_path, sheet_name=sh, header=None)

    col1 = df.iloc[:, 1].astype(str).str.strip()
    col2 = df.iloc[:, 2].astype(str).str.strip()
    header_candidates = df.index[(col1 == "Año") & (col2 == "Trimestre")].tolist()
    if not header_candidates:
        raise ValueError("No encontré header Año/Trimestre en IIOC Anexo A3.")
    header_row = header_candidates[0]
    label_row = header_row + 1
    data_start = header_row + 2

    sub = df.iloc[data_start:, 1:9].copy()
    sub.columns = ["year", "quarter", "iioc_total", "c4001", "c4002", "c4003", "c4004", "c4008"]

    sub["year"] = pd.to_numeric(sub["year"], errors="coerce").ffill()
    sub["quarter"] = sub["quarter"].astype(str).str.strip().map(QUARTER_MAP)

    for c in ["iioc_total", "c4001", "c4002", "c4003", "c4004", "c4008"]:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")

    sub = sub.dropna(subset=["year", "quarter"])
    sub["period"] = sub["year"].astype(int).astype(str) + "Q" + sub["quarter"].astype(int).astype(str)
    dates = pd.PeriodIndex(sub["period"], freq="Q").to_timestamp(how="end").normalize()

    # Only take total for now
    df_out = pd.DataFrame({
        "date": dates,
        "value": sub["iioc_total"].values,
        "year": sub["year"].astype(int),
        "quarter": sub["quarter"].astype(int),
        "indicator": "iioc_total",
        "indicator_id": "iioc",
        "source": "iioc_construction_cost_index",
        "unit": "Índice (base 2018=100)",
        "frequency": "Trimestral"
    })
    return df_out


def main():
    logger = setup_logging(LOGS / "clean.log", name="clean")
    logger.info("SILVER STAGE: Cleaning and standardizing data")
    
    sources = load_sources_config()
    all_dfs = []
    
    for source in sources:
        df = parse_source(source, logger)
        if not df.empty:
            # Save per source
            out_path = SILVER / f"{source['name']}.parquet"
            df.to_parquet(out_path, index=False)
            logger.info(f"Saved {source['name']} to {out_path}")
            all_dfs.append(df)
    
    if all_dfs:
        tidy = pd.concat(all_dfs, ignore_index=True)
        
        # Ensure backward compatibility
        out_csv = OUT / "indicators_tidy.csv"
        out_parq = OUT / "indicators_tidy.parquet"
        silver_parq = SILVER / "indicators_tidy.parquet"
        
        tidy.to_csv(out_csv, index=False)
        tidy.to_parquet(out_parq, index=False)
        tidy.to_parquet(silver_parq, index=False)
        
        logger.info(f"✅ Unified tidy saved to {silver_parq}")
        logger.info(f"Indicators: {tidy['indicator'].nunique()}")
        logger.info(f"Date range: {tidy['date'].min()} to {tidy['date'].max()}")
        
        return tidy
    else:
        logger.warning("No data parsed")
        return pd.DataFrame()


if __name__ == "__main__":
    main()