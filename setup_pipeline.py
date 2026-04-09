"""
SETUP & MIGRATION HELPER

This script helps complete the v2.0.0 setup and validates the new pipeline.
Run this after git cloning or after installation. 

Usage:
    python setup_pipeline.py --check       (Validate installation)
    python setup_pipeline.py --install    (Install dependencies)
    python setup_pipeline.py --migrate    (Migrate from v1 to v2)  
    python setup_pipeline.py --test       (Run tests)
"""

import sys
from pathlib import Path
import importlib


def check_python_version():
    """Verify Python >= 3.8"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 3.8+ required, found {version.major}.{version.minor}")
        return False
    print(f"✅ Python {version.major}.{version.minor}")
    return True


def check_imports():
    """Check if all required packages are installed"""
    required = {
        "pandas": "Core data processing",
        "numpy": "Numerical computing",
        "openpyxl": "Excel file handling",
        "pyarrow": "Parquet file format",
        "yaml": "Configuration files (pyyaml)",
    }
    
    all_ok = True
    for package, description in required.items():
        try:
            importlib.import_module(package)
            print(f"✅ {package:15} - {description}")
        except ImportError:
            print(f"❌ {package:15} - NOT INSTALLED")
            all_ok = False
    
    return all_ok


def check_directories():
    """Verify all required directories exist"""
    dirs = [
        "config", "data/raw", "data/silver", "data/gold", "data/processed",
        "logs", "reports", "src", "src/etl", "tests", "notebooks"
    ]
    
    all_ok = True
    for dir_name in dirs:
        path = Path(dir_name)
        if path.exists():
            print(f"✅ {dir_name}/")
        else:
            print(f"❌ {dir_name}/ - NOT FOUND")
            all_ok = False
    
    return all_ok


def check_config_files():
    """Verify configuration files exist"""
    configs = ["config/sources.yaml", "config/schema.yaml"]
    
    all_ok = True
    for config in configs:
        path = Path(config)
        if path.exists():
            size = path.stat().st_size
            print(f"✅ {config} ({size} bytes)")
        else:
            print(f"❌ {config} - NOT FOUND")
            all_ok = False
    
    return all_ok


def check_etl_modules():
    """Verify ETL modules can be imported"""
    modules = [
        "src.etl.utils",
        "src.etl.ingest",
        "src.etl.clean",
        "src.etl.quality",
    ]
    
    all_ok = True
    for module in modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except Exception as e:
            print(f"❌ {module} - {e}")
            all_ok = False
    
    return all_ok


def print_health_check():
    """Run full health check"""
    print("\n" + "=" * 70)
    print("PIPELINE HEALTH CHECK")
    print("=" * 70 + "\n")
    
    checks = [
        ("Python Version", check_python_version),
        ("\nRequired Packages", check_imports),
        ("\nDirectory Structure", check_directories),
        ("\nConfiguration Files", check_config_files),
        ("\nETL Modules", check_etl_modules),
    ]
    
    results = []
    for name, check_fn in checks:
        print(f"\n{name}")
        print("-" * 50)
        results.append(check_fn())
    
    all_passed = all(results)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL CHECKS PASSED - Pipeline is ready!")
    else:
        print("❌ SOME CHECKS FAILED - Review errors above")
    print("=" * 70 + "\n")
    
    return all_passed


def print_migration_guide():
    """Print v1 → v2 migration guide"""
    guide = """
╔══════════════════════════════════════════════════════════════════════╗
║  MIGRATION GUIDE: v1.0 → v2.0 (Medallion Architecture)             ║
╚══════════════════════════════════════════════════════════════════════╝

## What's New

✨ BRONZE LAYER (data/raw)
  - Immutable source data with SHA256 integrity checks
  - Manifest tracking: raw_manifest.csv

✨ SILVER LAYER (data/silver)
  - Clean, standardized data in long format (tidy)
  - Schema validation, uniqueness checks, missingness tracking
  - Output: indicators_tidy.parquet

✨ GOLD LAYER (data/gold)
  - Analytics-ready tables
  - national_panel.parquet: yearly aggregates
  - metrics_summary.parquet: growth rates, moving averages, lags

📊 DATA GOVERNANCE
  - config/sources.yaml: source definitions
  - config/schema.yaml: expected schemas & validation rules
  - reports/run_manifest.json: execution traceability
  - reports/quality_report.md: rich quality reports

🔧 CLI ORCHESTRATOR
  - python -m src.pipeline run --stage all
  - python -m src.pipeline validate
  - python -m src.pipeline build-report

📝 LOGGING & TRACEABILITY
  - logs/pipeline.log: consolidated pipeline logs
  - File hashing & integrity checks
  - Run manifests with git commit tracking


## Migration Steps

1. ✅ NEW CODE DEPLOYED
   - utils.py with logging, hashing, IO helpers
   - Refactored ingest.py, clean.py with type hints
   - New quality_new.py with comprehensive checks
   - pipeline.py orchestrator with CLI
   - Tests in tests/

2. 📝 KEEP EXISTING CODE FOR NOW
   - Old src/etl/quality.py still works
   - Legacy outputs in data/processed/ maintained for backward compatibility

3. 🔄 TRANSITION STRATEGY
   a) Install dependencies: pip install -r requirements.txt
   b) Test new pipeline: python -m src.pipeline run --stage all
   c) Compare outputs with old version
   d) Once validated, replace old quality.py with quality_new.py

4. 🚀 GOING FORWARD
   - Use: python -m src.pipeline run --stage [bronze|silver|gold|all]
   - For validation: python -m src.pipeline validate
   - Monitor: logs/pipeline.log


## File Changes Checklist

□ Directory structure created (config/, logs/, data/silver/, data/gold/, tests/)
□ Config files created (config/sources.yaml, config/schema.yaml)
□ Utils module created (src/etl/utils.py)
□ Pipeline orchestrator created (src/pipeline.py)
□ Quality refactored (src/etl/quality_new.py)
□ Tests added (tests/test_quality.py, tests/test_ingest.py)
□ Requirements updated (requirements.txt)
□ README updated (comprehensive documentation)
□ ingest.py refactored (type hints, logging)
□ clean.py refactored (type hints, logging)


## Validation Checklist

□ python -m src.pipeline run --stage all
□ python -m src.pipeline validate
□ pytest tests/ -v
□ Review logs/pipeline.log
□ Verify outputs in data/silver/ and data/gold/
□ Check reports/quality_report.md
□ Compare legacy outputs (data/processed/) match new outputs


## FAQ

Q: Do I need to replace the old quality.py?
A: Not immediately. quality_new.py coexists. When ready, rename quality.py to _old.py
   and quality_new.py to quality.py

Q: How do I use the old scripts still?
A: They still work! python src/etl/clean.py, etc. But use CLI for new workflows.

Q: Where are logs?
A: logs/pipeline.log (consolidated) and in reports/run_manifest.json (structured)

Q: How do I run just one stage?
A: python -m src.pipeline run --stage silver

Q: How do I know if data quality is good?
A: Review reports/quality_report.md and reports/quality_checks.csv


## Next Steps

1. Install: pip install -r requirements.txt
2. Test: python setup_pipeline.py --check
3. Run: python -m src.pipeline run --stage all
4. Validate: python -m src.pipeline validate
5. Review: open reports/quality_report.md

Questions? Check the updated README.md for comprehensive documentation.

════════════════════════════════════════════════════════════════════════
    """
    print(guide)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pipeline setup helper")
    parser.add_argument("--check", action="store_true", help="Run health check")
    parser.add_argument("--migrate", action="store_true", help="Show migration guide")
    parser.add_argument("--test", action="store_true", help="Run pytest")
    
    args = parser.parse_args()
    
    if args.check:
        okay = print_health_check()
        sys.exit(0 if okay else 1)
    
    elif args.migrate:
        print_migration_guide()
    
    elif args.test:
        import subprocess
        result = subprocess.run(["pytest", "tests/", "-v"], cwd=".")
        sys.exit(result.returncode)
    
    else:
        print_health_check()
        print_migration_guide()
