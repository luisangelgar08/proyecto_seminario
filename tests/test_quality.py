"""
Unit tests for quality.py module
"""

import pytest
import pandas as pd
from src.etl import quality_new


class TestSchemaValidation:
    """Tests for schema validation"""
    
    def test_schema_validation_pass(self, sample_tidy_df):
        """Test that valid schema passes"""
        passed, errors = quality_new.validate_schema(
            sample_tidy_df,
            required_columns=["date", "indicator", "value", "source", "unit", "frequency"]
        )
        assert passed, "Valid schema should pass"
        assert len(errors) == 0
    
    def test_schema_validation_missing_column(self):
        """Test that missing required column fails"""
        df = pd.DataFrame({
            "date": pd.date_range("2020", periods=3, freq="ME"),
            "indicator": ["A", "B", "C"]
        })
        passed, errors = quality_new.validate_schema(
            df,
            required_columns=["date", "indicator", "value"]
        )
        assert not passed, "Missing 'value' should fail"
        assert any("value" in e for e in errors)


class TestMissingness:
    """Tests for missingness checks"""
    
    def test_no_missingness(self, sample_tidy_df):
        """Test clean data with no nulls"""
        passed, stats = quality_new.check_missingness(
            sample_tidy_df,
            null_threshold_pct=10.0
        )
        assert passed, "Clean data should pass"
        for col_stats in stats.values():
            assert col_stats["null_pct"] == 0.0
    
    def test_high_missingness(self):
        """Test data with high missingness"""
        df = pd.DataFrame({
            "value": [1, 2, None, None, None, None, None, None, None, None],
            "indicator": ["A"] * 10
        })
        passed, stats = quality_new.check_missingness(
            df,
            null_threshold_pct=50.0
        )
        assert not passed, "High missingness should fail"
        assert stats["value"]["null_pct"] > 50.0


class TestUniqueness:
    """Tests for uniqueness checks"""
    
    def test_unique_keys(self, sample_tidy_df):
        """Test data with unique keys"""
        passed, stats = quality_new.check_uniqueness(
            sample_tidy_df[["date", "indicator", "value"]],
            key_columns=["date", "indicator"]
        )
        assert passed, "Unique keys should pass"
        assert stats["n_duplicates"] == 0
    
    def test_duplicate_keys(self):
        """Test data with duplicate keys"""
        df = pd.DataFrame({
            "date": ["2020-01-01", "2020-01-01", "2020-01-02"],
            "indicator": ["A", "A", "B"],
            "value": [100, 100.5, 200]
        })
        passed, stats = quality_new.check_uniqueness(
            df,
            key_columns=["date", "indicator"]
        )
        assert not passed, "Duplicate keys should fail"
        assert stats["n_duplicates"] > 0


class TestValueRanges:
    """Tests for value range checks"""
    
    def test_valid_ranges(self, sample_tidy_df):
        """Test data within valid ranges"""
        passed, stats = quality_new.check_value_ranges(
            sample_tidy_df,
            column="value",
            min_val=0,
            max_val=1000,
            allow_negative=False
        )
        assert passed, "Values within range should pass"
        assert len(stats["violations"]) == 0
    
    def test_negative_violation(self):
        """Test negative values when not allowed"""
        df = pd.DataFrame({
            "value": [100, -50, 200]
        })
        passed, stats = quality_new.check_value_ranges(
            df,
            column="value",
            allow_negative=False
        )
        assert not passed, "Negative values should fail"
        assert any("Negative" in v for v in stats["violations"])


class TestOutlierDetection:
    """Tests for outlier detection"""
    
    def test_outlier_detection(self):
        """Test IQR outlier detection"""
        # Create data with clear outliers
        normal_values = [100] * 20
        outliers = [1000]
        df = pd.DataFrame({
            "value": normal_values + outliers
        })
        
        passed, stats = quality_new.check_outliers(
            df,
            column="value",
            threshold=1.5
        )
        assert passed, "Outlier detection doesn't fail (only reports)"
        assert stats["n_outliers"] > 0, "Should detect outliers"


class TestTimeConsistency:
    """Tests for temporal consistency"""
    
    def test_monotonic_time(self, sample_tidy_df):
        """Test monotonic increasing time"""
        passed, stats = quality_new.check_time_consistency(
            sample_tidy_df,
            date_col="date"
        )
        assert passed, "Monotonic time should pass"
        assert stats["null_dates"] == 0
    
    def test_non_monotonic_time(self):
        """Test non-monotonic time"""
        df = pd.DataFrame({
            "date": ["2020-01-15", "2020-01-10", "2020-01-20"]
        })
        passed, stats = quality_new.check_time_consistency(
            df,
            date_col="date"
        )
        assert not passed, "Non-monotonic time should fail"
        assert stats["negative_gaps"] > 0
