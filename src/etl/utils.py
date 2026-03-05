"""
Utility functions for ETL pipeline

- File I/O handlers
- Hashing and integrity checks
- Logging configuration
- Date and time utilities
- Manifest generation
"""

import hashlib
import logging
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import pandas as pd
import subprocess
import time
import shutil
from enum import Enum


# ============================================================================
# Logging Configuration
# ============================================================================

class LogLevel(str, Enum):
    """Log level enumeration"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def setup_logging(
    log_file: Path,
    level: str = "INFO",
    name: str = "pipeline"
) -> logging.Logger:
    """
    Configure logging to file and console.
    
    Args:
        log_file: Path to log file
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        name: Logger name
        
    Returns:
        Configured logger instance
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))
    
    # File handler
    fh = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    fh.setLevel(getattr(logging, level))
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(getattr(logging, level))
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger


# ============================================================================
# File Hashing & Integrity
# ============================================================================

def hash_file(file_path: Path, algorithm: str = "sha256") -> str:
    """
    Compute hash of a file for integrity checking.
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm (md5, sha1, sha256, etc.)
        
    Returns:
        Hex digest of file hash
    """
    h = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_data_hash(df: pd.DataFrame) -> str:
    """
    Compute hash of a DataFrame for reproducibility checks.
    
    Args:
        df: DataFrame to hash
        
    Returns:
        Hash of DataFrame content
    """
    content = pd.util.hash_pandas_object(df, index=True).values
    return hashlib.sha256(content.tobytes()).hexdigest()


# ============================================================================
# File I/O Utilities
# ============================================================================

def read_parquet(path: Path) -> pd.DataFrame:
    """
    Read parquet file with error handling.
    
    Args:
        path: Path to parquet file
        
    Returns:
        DataFrame
    """
    try:
        return pd.read_parquet(path)
    except Exception as e:
        raise IOError(f"Failed to read parquet {path}: {e}")


def write_parquet(df: pd.DataFrame, path: Path, **kwargs) -> Path:
    """
    Write DataFrame to parquet with auto directory creation.
    
    Args:
        df: DataFrame to write
        path: Output path
        **kwargs: Additional arguments to to_parquet()
        
    Returns:
        Path to written file
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, **kwargs)
    return path


def write_csv(df: pd.DataFrame, path: Path, **kwargs) -> Path:
    """
    Write DataFrame to CSV with auto directory creation.
    
    Args:
        df: DataFrame to write
        path: Output path
        **kwargs: Additional arguments to to_csv()
        
    Returns:
        Path to written file
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, **kwargs)
    return path


# ============================================================================
# Manifest & Traceability
# ============================================================================

def get_git_commit_hash() -> Optional[str]:
    """
    Get current git commit hash if repo is initialized.
    
    Returns:
        Commit hash or None if not a git repo
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def create_run_manifest(
    stage: str,
    input_files: Dict[str, Path],
    output_files: Dict[str, Path],
    input_rows: Dict[str, int] = None,
    output_rows: Dict[str, int] = None,
    warnings: List[str] = None,
    errors: List[str] = None,
) -> Dict[str, Any]:
    """
    Create execution manifest for reproducibility.
    
    Args:
        stage: Pipeline stage name (bronze, silver, gold, etc.)
        input_files: Dict of input file names and paths
        output_files: Dict of output file names and paths
        input_rows: Dict of input dataset row counts
        output_rows: Dict of output dataset row counts
        warnings: List of warning messages
        errors: List of error messages
        
    Returns:
        Manifest dictionary
    """
    manifest = {
        "timestamp": datetime.now().isoformat(),
        "stage": stage,
        "git_commit": get_git_commit_hash(),
        "input_files": {k: str(v.as_posix()) for k, v in (input_files or {}).items()},
        "output_files": {k: str(v.as_posix()) for k, v in (output_files or {}).items()},
        "input_file_hashes": {
            k: hash_file(v) for k, v in (input_files or {}).items()
        },
        "input_rows": input_rows or {},
        "output_rows": output_rows or {},
        "warnings": warnings or [],
        "errors": errors or [],
    }
    return manifest


def save_run_manifest(manifest: Dict[str, Any], path: Path) -> Path:
    """
    Save execution manifest to JSON file.
    
    Args:
        manifest: Manifest dictionary
        path: Output path
        
    Returns:
        Path to written file
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return path


# ============================================================================
# Data Quality Utilities
# ============================================================================

def detect_outliers_iqr(
    series: pd.Series,
    threshold: float = 1.5
) -> Tuple[pd.Series, Dict[str, Any]]:
    """
    Detect outliers using Interquartile Range (IQR) method.
    
    Args:
        series: Data series
        threshold: IQR multiplier (1.5 = standard, 3.0 = extreme)
        
    Returns:
        Tuple of (boolean mask of outliers, stats dict)
    """
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - threshold * iqr
    upper_bound = q3 + threshold * iqr
    
    outliers = (series < lower_bound) | (series > upper_bound)
    
    stats = {
        "q1": float(q1),
        "q3": float(q3),
        "iqr": float(iqr),
        "lower_bound": float(lower_bound),
        "upper_bound": float(upper_bound),
        "n_outliers": int(outliers.sum()),
        "pct_outliers": float(100 * outliers.sum() / len(series)),
    }
    
    return outliers, stats


# ============================================================================
# Date & Time Utilities
# ============================================================================

def parse_period_key(year: int, period: Optional[int], frequency: str) -> pd.Timestamp:
    """
    Convert year + period to timestamp based on frequency.
    
    Args:
        year: Year
        period: Quarter (1-4), Month (1-12), or None for yearly
        frequency: "yearly", "quarterly", "monthly"
        
    Returns:
        Timestamp (end of period)
    """
    if frequency.lower() == "yearly":
        return pd.Timestamp(year=year, month=12, day=31)
    elif frequency.lower() == "quarterly":
        if not 1 <= period <= 4:
            raise ValueError(f"Invalid quarter: {period}")
        month = period * 3
        return pd.Timestamp(year=year, month=month, day=1) + pd.DateOffset(months=1) - pd.DateOffset(days=1)
    elif frequency.lower() == "monthly":
        if not 1 <= period <= 12:
            raise ValueError(f"Invalid month: {period}")
        return pd.Timestamp(year=year, month=period, day=1) + pd.DateOffset(months=1) - pd.DateOffset(days=1)
    else:
        raise ValueError(f"Unknown frequency: {frequency}")


def get_frequency_from_dates(dates: pd.Series) -> str:
    """
    Infer frequency from a date series.
    
    Args:
        dates: Series of timestamps
        
    Returns:
        Inferred frequency ("D", "M", "Q", "Y")
    """


def safe_read_parquet(path: Path, retries: int = 3, delay: float = 1.0, logger: Optional[logging.Logger] = None) -> pd.DataFrame:
    """Read a parquet file with retry/backoff on failure.

    Args:
        path: Path to parquet file
        retries: number of attempts
        delay: base delay between attempts (seconds)
        logger: optional logger for messages

    Returns:
        DataFrame loaded from file
    """
    for attempt in range(1, retries + 1):
        try:
            return pd.read_parquet(path)
        except Exception as e:
            if logger:
                logger.warning(f"Attempt {attempt} failed reading {path}: {e}")
            if attempt == retries:
                if logger:
                    logger.error(f"All {retries} attempts failed for {path}")
                raise
            time.sleep(delay * attempt)


def move_to_quarantine(file_path: Path, quarantine_dir: Path) -> Path:
    """Move a problematic file into a quarantine directory.

    Returns new path in quarantine.
    """
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    dest = quarantine_dir / file_path.name
    shutil.move(str(file_path), str(dest))
    return dest
    if len(dates) < 2:
        return "U"  # Unknown
    
    diffs = dates.diff().dropna().dt.days
    median_diff = diffs.median()
    
    if 27 <= median_diff <= 31:
        return "M"
    elif 88 <= median_diff <= 93:
        return "Q"
    elif 360 <= median_diff <= 366:
        return "Y"
    else:
        return "U"


# ============================================================================
# DataFrame Utilities
# ============================================================================

def validate_required_columns(df: pd.DataFrame, required_cols: List[str]) -> Tuple[bool, List[str]]:
    """
    Check if DataFrame has all required columns.
    
    Args:
        df: DataFrame
        required_cols: List of required column names
        
    Returns:
        Tuple of (all_present_bool, missing_cols_list)
    """
    missing = [col for col in required_cols if col not in df.columns]
    return len(missing) == 0, missing


def get_dataframe_profile(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Generate quick profile of a DataFrame.
    
    Args:
        df: DataFrame
        
    Returns:
        Profile dictionary with shape, dtypes, nulls, etc.
    """
    return {
        "shape": df.shape,
        "columns": df.columns.tolist(),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "nulls": {col: int(df[col].isna().sum()) for col in df.columns},
        "nulls_pct": {col: float(100 * df[col].isna().sum() / len(df)) for col in df.columns},
        "memory_mb": float(df.memory_usage(deep=True).sum() / 1024 / 1024),
    }
