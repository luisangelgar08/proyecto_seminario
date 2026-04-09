"""
QUALITY CHECKS & DATA VALIDATION

Comprehensive data quality assessment with rich reporting.
- Schema validation
- Uniqueness checks
- Time consistency analysis
- Missingness analysis
- Outlier detection (IQR method)
- Generates quality_checks.csv and rich Markdown report
"""

from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import pandas as pd
import numpy as np
import logging
from datetime import datetime

from .utils import setup_logging, write_csv, detect_outliers_iqr, create_run_manifest, save_run_manifest


def validate_schema(
    df: pd.DataFrame,
    required_columns: List[str],
    column_dtypes: Dict[str, str] = None,
    logger: logging.Logger = None
) -> Tuple[bool, List[str]]:
    """
    Validate DataFrame schema against expected columns and dtypes.
    
    Args:
        df: DataFrame to validate
        required_columns: List of required column names
        column_dtypes: Dict of column name -> expected dtype string
        logger: Logger instance
        
    Returns:
        Tuple of (passed_bool, errors_list)
    """
    errors = []
    
    # Check required columns
    missing_cols = [c for c in required_columns if c not in df.columns]
    if missing_cols:
        msg = f"Missing required columns: {missing_cols}"
        errors.append(msg)
        if logger:
            logger.error(msg)
    
    # Check dtypes if specified
    if column_dtypes:
        for col, expected_dtype in column_dtypes.items():
            if col in df.columns:
                actual = str(df[col].dtype)
                if expected_dtype not in actual:
                    msg = f"Column {col}: expected {expected_dtype}, got {actual}"
                    errors.append(msg)
                    if logger:
                        logger.warning(msg)
    
    return len(errors) == 0, errors


def check_missingness(
    df: pd.DataFrame,
    null_threshold_pct: float = 10.0,
    logger: logging.Logger = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check missingness levels per column.
    
    Args:
        df: DataFrame
        null_threshold_pct: Threshold percentage (fail if exceeded)
        logger: Logger instance
        
    Returns:
        Tuple of (passed_bool, stats_dict)
    """
    stats = {}
    for col in df.columns:
        null_count = df[col].isna().sum()
        null_pct = 100 * null_count / len(df)
        stats[col] = {
            "null_count": int(null_count),
            "null_pct": float(null_pct),
            "exceeded_threshold": null_pct > null_threshold_pct
        }
        if null_pct > null_threshold_pct and logger:
            logger.warning(f"{col}: {null_pct:.1f}% missing (threshold: {null_threshold_pct}%)")
    
    passed = not any(s["exceeded_threshold"] for s in stats.values())
    return passed, stats


def check_uniqueness(
    df: pd.DataFrame,
    key_columns: List[str],
    logger: logging.Logger = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check uniqueness constraints.
    
    Args:
        df: DataFrame
        key_columns: Columns that should form unique rows
        logger: Logger instance
        
    Returns:
        Tuple of (passed_bool, stats_dict)
    """
    stats = {
        "key_columns": key_columns,
        "total_rows": len(df),
        "unique_rows": len(df.drop_duplicates(subset=key_columns)),
    }
    
    duplicates = df[df.duplicated(subset=key_columns, keep=False)]
    stats["n_duplicates"] = len(duplicates)
    stats["failed"] = stats["n_duplicates"] > 0
    
    if stats["failed"] and logger:
        logger.warning(f"Found {stats['n_duplicates']} duplicate rows on {key_columns}")
    
    return not stats["failed"], stats


def check_time_consistency(
    df: pd.DataFrame,
    date_col: str = "date",
    logger: logging.Logger = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check temporal consistency (monotonicity, gaps, etc).
    
    Args:
        df: DataFrame
        date_col: Name of date column
        logger: Logger instance
        
    Returns:
        Tuple of (passed_bool, stats_dict)
    """
    stats = {}
    
    if date_col not in df.columns:
        msg = f"Date column '{date_col}' not found"
        if logger:
            logger.error(msg)
        return False, {"error": msg}
    
    # parse dates once
    dates_parsed = pd.to_datetime(df[date_col], errors="coerce")
    dates_sorted = dates_parsed.sort_values()
    
    stats["min_date"] = str(dates_sorted.min())
    stats["max_date"] = str(dates_sorted.max())
    stats["n_rows"] = len(df)
    
    # Check for nulls in date
    null_dates = dates_parsed.isna().sum()
    stats["null_dates"] = int(null_dates)
    
    # Check monotonicity using original order
    if len(dates_parsed) > 1:
        diffs = dates_parsed.diff().dt.days
        stats["min_gap_days"] = int(diffs.min())
        stats["max_gap_days"] = int(diffs.max())
        stats["negative_gaps"] = int((diffs < 0).sum())
    
    stats["failed"] = stats.get("null_dates", 0) > 0 or stats.get("negative_gaps", 0) > 0
    
    if stats["failed"] and logger:
        logger.warning(f"Time consistency check failed: {stats}")
    
    return not stats["failed"], stats


def check_value_ranges(
    df: pd.DataFrame,
    column: str,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    allow_negative: bool = True,
    logger: logging.Logger = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Check value ranges for a column.
    
    Args:
        df: DataFrame
        column: Column name
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        allow_negative: Whether negative values are allowed
        logger: Logger instance
        
    Returns:
        Tuple of (passed_bool, stats_dict)
    """
    stats = {"column": column}
    
    if column not in df.columns:
        msg = f"Column '{column}' not found"
        if logger:
            logger.error(msg)
        return False, {"error": msg}
    
    values = pd.to_numeric(df[column], errors="coerce")
    stats["non_numeric"] = int(values.isna().sum())
    stats["min"] = float(values.min()) if len(values) > 0 else None
    stats["max"] = float(values.max()) if len(values) > 0 else None
    
    violations = []
    
    if min_val is not None and stats["min"] < min_val:
        violations.append(f"Values < {min_val}: {(values < min_val).sum()}")
    
    if max_val is not None and stats["max"] > max_val:
        violations.append(f"Values > {max_val}: {(values > max_val).sum()}")
    
    if not allow_negative and (values < 0).any():
        violations.append(f"Negative values: {(values < 0).sum()}")
    
    stats["violations"] = violations
    stats["failed"] = len(violations) > 0
    
    if stats["failed"] and logger:
        logger.warning(f"{column} range check: {violations}")
    
    return not stats["failed"], stats


def check_outliers(
    df: pd.DataFrame,
    column: str,
    threshold: float = 1.5,
    logger: logging.Logger = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Detect outliers using IQR method. Issues warning but does not fail.
    
    Args:
        df: DataFrame
        column: Numeric column to check
        threshold: IQR multiplier
        logger: Logger instance
        
    Returns:
        Tuple of (always_true, stats_dict) - outliers don't cause failure
    """
    stats = {"column": column, "method": "IQR"}
    
    if column not in df.columns:
        return True, {"error": f"Column '{column}' not found"}
    
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    
    if len(values) < 4:
        stats["result"] = "insufficient data"
        return True, stats
    
    outliers, iqr_stats = detect_outliers_iqr(values, threshold=threshold)
    
    stats.update(iqr_stats)
    
    if logger and iqr_stats["n_outliers"] > 0:
        logger.info(f"{column} outliers: {iqr_stats['n_outliers']} ({iqr_stats['pct_outliers']:.1f}%) detected")
    
    return True, stats


def main(
    tidy_file: Path = Path("data/silver/indicators_tidy.parquet"),
    reports_dir: Path = Path("reports"),
    log_file: Path = Path("logs/pipeline.log"),
) -> Dict[str, Any]:
    """
    Main quality check orchestrator.
    
    Args:
        tidy_file: Path to tidy dataset
        reports_dir: Path to reports directory
        log_file: Path to log file
        
    Returns:
        Dictionary with all quality check results
    """
    logger = setup_logging(log_file, level="INFO", name="quality")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 70)
    logger.info("STAGE: DATA QUALITY CHECKS")
    logger.info("=" * 70)
    
    # Load data
    try:
        df = pd.read_parquet(tidy_file)
        logger.info(f"Loaded {len(df)} rows from {tidy_file}")
    except Exception as e:
        logger.error(f"Failed to load {tidy_file}: {e}")
        raise
    
    # Run all checks
    all_results = []
    
    # 1. Schema validation
    logger.info("→ Schema validation...")
    passed, errors = validate_schema(
        df,
        required_columns=["date", "indicator", "value", "source", "unit", "frequency"],
        logger=logger
    )
    all_results.append({
        "check": "schema_validation",
        "passed": passed,
        "details": ";".join(errors) if errors else "OK"
    })
    
    # 2. Missingness
    logger.info("→ Missingness check...")
    passed, miss_stats = check_missingness(df, null_threshold_pct=10.0, logger=logger)
    all_results.append({
        "check": "missingness",
        "passed": passed,
        "details": str(miss_stats)
    })
    
    # 3. Uniqueness: (date, indicator) pairs
    logger.info("→ Uniqueness check...")
    passed, uniq_stats = check_uniqueness(
        df,
        key_columns=["date", "indicator"],
        logger=logger
    )
    all_results.append({
        "check": "uniqueness_date_indicator",
        "passed": passed,
        "details": str(uniq_stats)
    })
    
    # 4. Time consistency
    logger.info("→ Time consistency check...")
    passed, time_stats = check_time_consistency(df, date_col="date", logger=logger)
    all_results.append({
        "check": "time_consistency",
        "passed": passed,
        "details": str(time_stats)
    })
    
    # 5. Value ranges (non-negative, reasonable bounds)
    logger.info("→ Value range checks...")
    passed, range_stats = check_value_ranges(
        df,
        column="value",
        min_val=0,
        max_val=1000000,
        allow_negative=False,
        logger=logger
    )
    all_results.append({
        "check": "value_ranges",
        "passed": passed,
        "details": str(range_stats)
    })
    
    # 6. Outlier detection (does not fail, only reports)
    logger.info("→ Outlier detection...")
    _, outlier_stats = check_outliers(df, column="value", threshold=1.5, logger=logger)
    all_results.append({
        "check": "outliers",
        "passed": True,
        "details": str(outlier_stats)
    })
    
    # Save results to CSV
    results_df = pd.DataFrame(all_results)
    results_csv = reports_dir / "quality_checks.csv"
    write_csv(results_df, results_csv)
    logger.info(f"Quality check results: {results_csv}")
    
    # Generate Markdown report
    markdown_lines = []
    markdown_lines.append("# Data Quality Report")
    markdown_lines.append(f"\n**Generated**: {datetime.now().isoformat()}")
    markdown_lines.append(f"\n**Dataset**: {tidy_file}")
    markdown_lines.append(f"**Rows**: {len(df):,} | **Columns**: {len(df.columns)} | **Indicators**: {df['indicator'].nunique() if 'indicator' in df.columns else 'N/A'}")
    
    markdown_lines.append("\n## Check Results\n")
    for result in all_results:
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        markdown_lines.append(f"### {result['check']} {status}")
        markdown_lines.append(f"```\n{result['details']}\n```\n")
    
    # Summary
    passed_count = sum(1 for r in all_results if r["passed"])
    markdown_lines.append(f"\n## Summary\n")
    markdown_lines.append(f"- Checks passed: **{passed_count}/{len(all_results)}**")
    markdown_lines.append(f"- Overall status: **{'✅ All checks passed' if passed_count == len(all_results) else '⚠️ Some checks failed'}**")
    
    report_md = reports_dir / "quality_report.md"
    report_md.write_text("\n".join(markdown_lines), encoding="utf-8")
    logger.info(f"Markdown report: {report_md}")
    
    # Save run manifest
    manifest = create_run_manifest(
        stage="quality_checks",
        input_files={"tidy": tidy_file},
        output_files={"csv": results_csv, "markdown": report_md},
        output_rows={"checked_rows": len(df)},
    )
    save_run_manifest(manifest, reports_dir / "run_manifest.json")
    
    logger.info("=" * 70)
    logger.info(f"Quality checks complete: {passed_count}/{len(all_results)} passed")
    logger.info("=" * 70)
    
    return {
        "all_results": all_results,
        "passed": passed_count == len(all_results),
        "report_csv": str(results_csv),
        "report_md": str(report_md),
    }


if __name__ == "__main__":
    main()
