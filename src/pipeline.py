"""
PIPELINE ORCHESTRATOR

Main CLI entry point for running the complete ETL pipeline.
Coordinates BRONZE → SILVER → GOLD transformations end-to-end.

Usage:
    python -m src.pipeline run --stage all     # Run all stages
    python -m src.pipeline run --stage silver  # Run just silver
    python -m src.pipeline run --stage gold    # Run just gold
    python -m src.pipeline validate            # Run quality checks
    python -m src.pipeline build-report        # Generate reports
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Optional

from src.etl import ingest, clean, quality, gold


def setup_root_logging(log_dir: Path) -> None:
    """Setup root logger for all stages."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "pipeline.log"
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    root_logger.addHandler(handler)


def run_bronze(
    raw_dir: Path = Path("data/raw"),
    reports_dir: Path = Path("reports"),
    log_dir: Path = Path("logs"),
) -> bool:
    """Run BRONZE ingestion stage."""
    logger = logging.getLogger("pipeline.bronze")
    try:
        ingest.main(raw_dir=raw_dir, reports_dir=reports_dir, log_file=log_dir / "pipeline.log")
        logger.info("✅ BRONZE stage completed")
        return True
    except Exception as e:
        logger.error(f"❌ BRONZE stage failed: {e}", exc_info=True)
        return False


def run_silver(
    raw_dir: Path = Path("data/raw"),
    silver_dir: Path = Path("data/silver"),
    processed_dir: Path = Path("data/processed"),
    reports_dir: Path = Path("reports"),
    log_dir: Path = Path("logs"),
) -> bool:
    """Run SILVER cleaning stage."""
    logger = logging.getLogger("pipeline.silver")
    try:
        clean.main()
        logger.info("✅ SILVER stage completed")
        return True
    except Exception as e:
        logger.error(f"❌ SILVER stage failed: {e}", exc_info=True)
        return False


def run_gold(
    silver_dir: Path = Path("data/silver"),
    gold_dir: Path = Path("data/gold"),
    reports_dir: Path = Path("reports"),
    log_dir: Path = Path("logs"),
) -> bool:
    """
    Run GOLD analytics stage.
    Produce star-schema tables and feature engineering.
    """
    logger = logging.getLogger("pipeline.gold")
    try:
        gold.main()
        logger.info("✅ GOLD stage completed")
        return True
    except Exception as e:
        logger.error(f"❌ GOLD stage failed: {e}", exc_info=True)
        return False


def run_all_stages(
    raw_dir: Path = Path("data/raw"),
    silver_dir: Path = Path("data/silver"),
    gold_dir: Path = Path("data/gold"),
    processed_dir: Path = Path("data/processed"),
    reports_dir: Path = Path("reports"),
    log_dir: Path = Path("logs"),
) -> bool:
    """Run complete pipeline: BRONZE → SILVER → GOLD → QUALITY → MANIFEST."""
    logger = logging.getLogger("pipeline")
    
    logger.info("\n" + "=" * 70)
    logger.info("STARTING COMPLETE PIPELINE")
    logger.info("=" * 70 + "\n")
    
    # Bronze
    if not run_bronze(raw_dir, reports_dir, log_dir):
        return False
    
    # Silver
    if not run_silver(raw_dir, silver_dir, processed_dir, reports_dir, log_dir):
        return False
    
    # Gold
    if not run_gold(silver_dir, gold_dir, reports_dir, log_dir):
        return False
    
    # Reports
    if not run_reports(reports_dir, log_dir):
        logger.warning("Reports generation failed, but continuing...")
    
    # Quality
    if not run_quality(reports_dir, log_dir):
        logger.warning("Quality checks failed, but continuing...")
    
    # Manifest
    create_pipeline_manifest(raw_dir, silver_dir, gold_dir, reports_dir, log_dir)
    
    logger.info("\n" + "=" * 70)
    logger.info("✅ PIPELINE COMPLETED SUCCESSFULLY")
    logger.info("=" * 70 + "\n")
    
    return True


def run_quality(
    reports_dir: Path = Path("reports"),
    log_dir: Path = Path("logs"),
) -> bool:
    """Run quality checks."""
    logger = logging.getLogger("pipeline.quality")
    try:
        quality.main()
        logger.info("✅ QUALITY stage completed")
        return True
    except Exception as e:
        logger.error(f"❌ QUALITY stage failed: {e}", exc_info=True)
        return False


def run_reports(
    reports_dir: Path = Path("reports"),
    log_dir: Path = Path("logs"),
) -> bool:
    """Generate analytics reports and charts."""
    logger = logging.getLogger("pipeline.reports")
    try:
        import subprocess
        import sys
        result = subprocess.run([sys.executable, "scripts/generate_reports.py"], cwd=BASE_DIR)
        if result.returncode == 0:
            logger.info("✅ Reports generated")
            return True
        else:
            logger.error("❌ Reports generation failed")
            return False
    except Exception as e:
        logger.error(f"❌ Reports failed: {e}", exc_info=True)
        return False


def validate_data(
    reports_dir: Path = Path("reports"),
    log_dir: Path = Path("logs"),
) -> bool:
    """Run quality checks."""
    return run_quality(reports_dir, log_dir)


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PROYECTO_SEMINARIO ETL Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.pipeline run --stage all     (Run full pipeline)
  python -m src.pipeline run --stage silver  (Run silver and gold)
  python -m src.pipeline validate            (Run quality checks)
  python -m src.pipeline build-report        (Generate reports)
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # run command
    run_parser = subparsers.add_parser("run", help="Run ETL stages")
    run_parser.add_argument(
        "--stage",
        choices=["bronze", "silver", "gold", "all"],
        default="all",
        help="Stage to run (default: all)"
    )
    
    # validate command
    subparsers.add_parser("validate", help="Run data quality checks")
    
    # build-report command
    subparsers.add_parser("build-report", help="Generate all reports")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_root_logging(Path("logs"))
    logger = logging.getLogger("pipeline")
    
    # Execute commands
    if args.command == "run":
        success = False
        if args.stage == "bronze":
            success = run_bronze()
        elif args.stage == "silver":
            success = run_silver()
        elif args.stage == "gold":
            success = run_gold()
        elif args.stage == "all":
            success = run_all_stages()
        return 0 if success else 1
    
    elif args.command == "validate":
        success = validate_data()
        return 0 if success else 1
    
    elif args.command == "build-report":
        logger.info("Building reports...")
        run_all_stages()
        validate_data()
        logger.info("✅ Reports generated in reports/")
        return 0
    
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
