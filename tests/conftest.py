"""
Pytest configuration and shared fixtures
"""

import pytest
import pandas as pd
from pathlib import Path


@pytest.fixture
def sample_tidy_df():
    """Create a sample tidy DataFrame for testing."""
    return pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=12, freq="ME"),
        "indicator": ["FBCF"] * 4 + ["GEIH"] * 4 + ["IIOC"] * 4,
        "value": [100 + i*10 for i in range(12)],
        "source": "TEST",
        "unit": "Index",
        "frequency": "Monthly"
    })


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directories."""
    raw = tmp_path / "raw"
    silver = tmp_path / "silver"
    gold = tmp_path / "gold"
    processed = tmp_path / "processed"
    reports = tmp_path / "reports"
    
    raw.mkdir()
    silver.mkdir()
    gold.mkdir()
    processed.mkdir()
    reports.mkdir()
    
    return {
        "raw": raw,
        "silver": silver,
        "gold": gold,
        "processed": processed,
        "reports": reports,
        "base": tmp_path
    }


@pytest.fixture
def sample_excel_dir(temp_data_dir):
    """
    Create mock Excel files for testing.
    Note: This is a simplified version; real tests would use actual Excel fixtures.
    """
    return temp_data_dir["raw"]
