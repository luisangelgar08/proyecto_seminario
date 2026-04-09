"""
Unit tests for ingest.py module
"""

import pytest
from pathlib import Path
from src.etl import ingest


class TestDiscoverRawFiles:
    """Tests for file discovery"""
    
    def test_discover_xlsx_files(self, temp_data_dir):
        """Test discovering .xlsx files"""
        raw = temp_data_dir["raw"]
        
        # Create mock files
        (raw / "file1.xlsx").touch()
        (raw / "file2.xlsx").touch()
        (raw / "file3.csv").touch()  # Should not be included
        
        files = ingest.discover_raw_files(raw, patterns=["*.xlsx", "*.xls"])
        
        assert len(files) >= 2, "Should find at least 2 Excel files"
        assert all(f.suffix in [".xlsx", ".xls"] for f in files)
    
    def test_discover_no_files(self, temp_data_dir):
        """Test when no files found"""
        raw = temp_data_dir["raw"]
        
        files = ingest.discover_raw_files(raw)
        
        assert len(files) == 0, "No files should be found"
    
    def test_files_sorted(self, temp_data_dir):
        """Test that discovered files are sorted"""
        raw = temp_data_dir["raw"]
        
        names = ["z_file.xlsx", "a_file.xlsx", "m_file.xlsx"]
        for name in names:
            (raw / name).touch()
        
        files = ingest.discover_raw_files(raw)
        filenames = [f.name for f in files]
        
        assert filenames == sorted(filenames), "Files should be sorted"


class TestCreateFileManifest:
    """Tests for manifest creation"""
    
    def test_manifest_creation(self, temp_data_dir):
        """Test creating manifest from files"""
        import logging
        logger = logging.getLogger("test")
        raw = temp_data_dir["raw"]
        
        # Create a test file
        test_file = raw / "test.xlsx"
        test_file.write_text("test content")
        
        files = [test_file]
        manifest = ingest.create_file_manifest(files, logger)
        
        assert len(manifest) == 1
        assert manifest.iloc[0]["file"] == "test.xlsx"
        assert "sha256" in manifest.columns
        assert "size_bytes" in manifest.columns
        assert "ingested_at" in manifest.columns
    
    def test_manifest_columns(self, temp_data_dir):
        """Test manifest has required columns"""
        import logging
        logger = logging.getLogger("test")
        raw = temp_data_dir["raw"]
        
        test_file = raw / "test.xlsx"
        test_file.write_text("test")
        
        manifest = ingest.create_file_manifest([test_file], logger)
        
        required_cols = ["file", "path", "sha256", "size_bytes", "ingested_at"]
        for col in required_cols:
            assert col in manifest.columns, f"Missing column: {col}"

    def test_discover_from_config(self, temp_data_dir):
        """Patterns loaded from config/sources.yaml should be used"""
        # write config file with custom pattern
        cfg_path = Path("config/sources.yaml")
        cfg_path.parent.mkdir(exist_ok=True)
        cfg_path.write_text("""
sources:
  - name: TEST
    file_pattern: '*.abc'
""")
        raw = temp_data_dir["raw"]
        (raw / "file1.abc").touch()
        (raw / "file2.xlsx").touch()
        files = ingest.discover_raw_files(raw)
        assert all(f.suffix == ".abc" for f in files), "Should only match .abc pattern from config"

    def test_quarantine_on_hash_fail(self, temp_data_dir, monkeypatch):
        """If hashing fails, file is moved to quarantine and not included"""
        import logging
        logger = logging.getLogger("test")
        raw = temp_data_dir["raw"]
        corrupt = raw / "bad.xlsx"
        corrupt.write_text("bad")
        # monkeypatch hash_file to raise for this path
        def fake_hash(p):
            raise IOError("cannot read")
        monkeypatch.setattr(ingest, "hash_file", fake_hash)
        manifest = ingest.create_file_manifest([corrupt], logger)
        assert manifest.empty
        quarantined = raw.parent / "quarantine" / "bad.xlsx"
        assert quarantined.exists(), "File should have been moved to quarantine"
