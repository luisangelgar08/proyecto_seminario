"""
BRONZE INGESTION

Discovers and catalogs raw data files from data/raw/.
Generates raw_manifest.csv with file metadata and integrity hashes.
"""

from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import pandas as pd
import logging

from .utils import setup_logging, hash_file, save_run_manifest


def discover_raw_files(raw_dir: Path, patterns: List[str] = None, logger: logging.Logger = None) -> List[Path]:
    """
    Discover raw data files in directory, optionally driven by config.
    
    Args:
        raw_dir: Path to raw data directory
        patterns: List of glob patterns (default: ["*.xlsx", "*.xls"] or read from config)
        logger: optional logger for debug
        
    Returns:
        Sorted list of file paths
    """
    # attempt to load patterns from config if not provided
    if patterns is None:
        cfg = {}
        try:
            import yaml
            cfg = yaml.safe_load(Path("config/sources.yaml").read_text()) or {}
        except Exception:
            # config missing or unreadable, fallback
            if logger:
                logger.warning("Could not load config/sources.yaml; using default patterns")
        if isinstance(cfg, dict) and cfg.get("sources"):
            # assume each entry may have a file_pattern element
            patterns = []
            for src in cfg["sources"]:
                pat = src.get("file_pattern")
                if pat:
                    patterns.append(pat)
            if not patterns:
                patterns = ["*.xlsx", "*.xls"]
        else:
            patterns = ["*.xlsx", "*.xls"]
    
    files: List[Path] = []
    for pattern in patterns:
        files.extend(raw_dir.glob(pattern))
    
    unique_files = sorted(set(files))
    # if patterns were loaded from config and no files found, fallback to defaults
    if not unique_files and patterns and not any(pat in ["*.xlsx","*.xls"] for pat in patterns):
        if logger:
            logger.warning("No files found with config patterns; falling back to default Excel patterns")
        patterns = ["*.xlsx","*.xls"]
        files = []
        for pattern in patterns:
            files.extend(raw_dir.glob(pattern))
        unique_files = sorted(set(files))
    if logger:
        logger.info(f"discover_raw_files found {len(unique_files)} files using patterns {patterns}")
    return unique_files


def create_file_manifest(files: List[Path], logger: logging.Logger) -> pd.DataFrame:
    """
    Create manifest of raw files with metadata and hashes.
    
    Args:
        files: List of file paths
        logger: Logger instance
        
    Returns:
        DataFrame with file metadata
    """
    rows = []
    
    # compute quarantine directory relative to the first raw file (or default to data/quarantine)
    if files:
        quarantine = files[0].parent.parent / "quarantine"
    else:
        quarantine = Path("data") / "quarantine"
    for filepath in files:
        try:
            sha = hash_file(filepath)
        except Exception as e:
            logger.error(f"Hashing failed for {filepath.name}: {e}; moving to quarantine")
            dest = __import__("src.etl.utils", fromlist=["move_to_quarantine"]).move_to_quarantine(filepath, quarantine)
            logger.info(f"Moved {filepath.name} to quarantine: {dest}")
            continue
        try:
            row = {
                "file": filepath.name,
                "path": str(filepath.as_posix()),
                "size_bytes": filepath.stat().st_size,
                "sha256": sha,
                "ingested_at": datetime.now().isoformat(timespec="seconds"),
            }
            rows.append(row)
            logger.info(f"Cataloged: {filepath.name} ({row['size_bytes']:,} bytes)")
        except Exception as e:
            logger.error(f"Failed to catalog {filepath.name}: {e}")
    
    return pd.DataFrame(rows)


def main(
    raw_dir: Path = Path("data/raw"),
    reports_dir: Path = Path("reports"),
    log_file: Path = Path("logs/pipeline.log"),
) -> Dict[str, Any]:
    """
    Main ingestion orchestrator.
    
    Args:
        raw_dir: Path to raw data directory
        reports_dir: Path to reports directory
        log_file: Path to log file
        
    Returns:
        Manifest dictionary with execution details
    """
    # Setup
    logger = setup_logging(log_file, level="INFO", name="ingest")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 70)
    logger.info("STAGE: BRONZE INGESTION")
    logger.info("=" * 70)
    
    # Discover files (patterns may come from config/sources.yaml)
    files = discover_raw_files(raw_dir, logger=logger)
    
    if not files:
        logger.error(f"No Excel files found in {raw_dir}")
        raise SystemExit("No Excel files in data/raw/")
    
    logger.info(f"Found {len(files)} raw data files")
    
    # Create manifest
    manifest_df = create_file_manifest(files, logger)
    
    # Save manifest
    manifest_path = reports_dir / "raw_manifest.csv"
    manifest_df.to_csv(manifest_path, index=False)
    logger.info(f"Manifest saved: {manifest_path}")
    
    # Create run manifest
    run_manifest = save_run_manifest(
        manifest={
            "timestamp": datetime.now().isoformat(),
            "stage": "bronze_ingest",
            "files_discovered": len(files),
            "manifest_file": str(manifest_path.as_posix()),
        },
        path=reports_dir / "run_manifest.json"
    )
    
    logger.info(f"Ingestion complete: {len(files)} files cataloged")
    logger.info("=" * 70)
    
    return manifest_df.to_dict("records")


if __name__ == "__main__":
    main()