"""
QUALITY & VALIDATION: Advanced Data Quality Checks

- Schema validation per source from config/schema.yaml
- Missingness thresholds per indicator
- Duplicate key checks
- Time continuity checks (detect gaps)
- Outlier detection (IQR) and flagging
- Consistency checks across related indicators
"""

from pathlib import Path
import pandas as pd
import numpy as np
import yaml
import logging
from typing import Dict, List

from .utils import setup_logging


# ============================================================================
# Directory Paths
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SILVER = BASE_DIR / "data" / "silver"
CONFIG = BASE_DIR / "config"
REPORTS = BASE_DIR / "reports"
LOGS = BASE_DIR / "logs"


def load_schema_config() -> Dict:
    """Load schema configuration."""
    schema_path = CONFIG / "schema.yaml"
    with open(schema_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)['schemas']


def validate_schema(df: pd.DataFrame, schema: Dict) -> Dict[str, bool]:
    """Validate DataFrame against schema."""
    results = {}
    for col, rules in schema.get('columns', {}).items():
        if col in df.columns:
            dtype_ok = df[col].dtype == rules.get('dtype', df[col].dtype)
            null_ok = df[col].isna().mean() <= rules.get('null_threshold', 1.0)
            results[f"{col}_dtype"] = dtype_ok
            results[f"{col}_nulls"] = null_ok
        else:
            results[f"{col}_missing"] = False
    return results


def check_missingness(df: pd.DataFrame, threshold: float) -> Dict:
    """Check missingness per indicator."""
    missing = df.groupby('indicator_id')['value'].apply(lambda x: x.isna().mean())
    failed = missing[missing > threshold]
    return {
        'passed': len(failed) == 0,
        'details': failed.to_dict()
    }


def check_duplicates(df: pd.DataFrame, keys: List[str]) -> Dict:
    """Check for duplicate keys."""
    dups = df.duplicated(subset=keys).sum()
    return {
        'passed': dups == 0,
        'count': dups
    }


def check_time_continuity(df: pd.DataFrame) -> Dict:
    """Check for gaps in time series per indicator."""
    gaps = {}
    for ind, group in df.groupby('indicator_id'):
        if 'date' in group.columns:
            group = group.sort_values('date')
            expected_freq = 'Q' if group['frequency'].iloc[0] == 'Trimestral' else 'M' if group['frequency'].iloc[0] == 'Mensual' else 'Y'
            full_range = pd.date_range(start=group['date'].min(), end=group['date'].max(), freq=expected_freq)
            missing_dates = set(full_range) - set(group['date'])
            gaps[ind] = len(missing_dates)
    total_gaps = sum(gaps.values())
    return {
        'passed': total_gaps == 0,
        'total_gaps': total_gaps,
        'details': gaps
    }


def detect_outliers(df: pd.DataFrame) -> Dict:
    """Detect outliers using IQR."""
    outliers = {}
    for ind, group in df.groupby('indicator_id'):
        if len(group) > 4:
            Q1 = group['value'].quantile(0.25)
            Q3 = group['value'].quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            out_count = ((group['value'] < lower) | (group['value'] > upper)).sum()
            outliers[ind] = out_count
    total_outliers = sum(outliers.values())
    return {
        'total_outliers': total_outliers,
        'details': outliers
    }


def check_consistency(df: pd.DataFrame) -> Dict:
    """Check consistency across indicators."""
    issues = []
    # Example: if inv_pib YoY > 20%, check if iioc changed significantly
    if 'inv_pib' in df['indicator_id'].values and 'iioc' in df['indicator_id'].values:
        inv = df[df['indicator_id'] == 'inv_pib'].set_index('date')['value']
        iioc = df[df['indicator_id'] == 'iioc'].set_index('date')['value']
        inv_yoy = inv.pct_change(4) * 100
        spikes = inv_yoy[inv_yoy > 20]
        for date, val in spikes.items():
            iioc_change = iioc.pct_change().loc[date] if date in iioc.index else 0
            if abs(iioc_change) < 5:  # If iioc didn't change much, flag
                issues.append(f"High inv_pib growth at {date} but low iioc change")
    return {
        'issues': issues
    }


def generate_quality_report(results: Dict, logger: logging.Logger):
    """Generate markdown report."""
    lines = ["# Advanced Quality Report\n"]
    
    for source, checks in results.items():
        lines.append(f"## {source}\n")
        for check, result in checks.items():
            if isinstance(result, dict):
                lines.append(f"- {check}: {result.get('passed', 'N/A')}")
                if 'details' in result:
                    for k, v in result['details'].items():
                        lines.append(f"  - {k}: {v}")
            else:
                lines.append(f"- {check}: {result}")
        lines.append("")
    
    report_path = REPORTS / "quality_report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    logger.info(f"Quality report saved to {report_path}")


def main():
    logger = setup_logging(LOGS / "quality.log", name="quality")
    logger.info("QUALITY STAGE: Running advanced checks")
    
    schemas = load_schema_config()
    results = {}
    
    for source_file in SILVER.glob("*.parquet"):
        source_name = source_file.stem
        if source_name == "indicators_tidy":
            continue
        df = pd.read_parquet(source_file)
        
        checks = {}
        if source_name in schemas:
            checks['schema_validation'] = validate_schema(df, schemas[source_name])
        
        threshold = schemas.get(source_name, {}).get('missing_threshold', 0.05)
        checks['missingness'] = check_missingness(df, threshold)
        
        keys = ['year', 'quarter'] if 'quarter' in df.columns else ['year']
        checks['duplicates'] = check_duplicates(df, keys)
        
        checks['time_continuity'] = check_time_continuity(df)
        checks['outliers'] = detect_outliers(df)
        
        results[source_name] = checks
    
    # Overall consistency
    tidy_df = pd.read_parquet(SILVER / "indicators_tidy.parquet")
    results['overall_consistency'] = check_consistency(tidy_df)
    
    generate_quality_report(results, logger)
    logger.info("✅ Quality checks completed")


if __name__ == "__main__":
    main()