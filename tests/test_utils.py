"""
Tests for utils enhancements (safe_read_parquet, move_to_quarantine)
"""

import pytest
from pathlib import Path
from src.etl import utils


def test_safe_read_parquet_success(tmp_path, monkeypatch):
    # create a small parquet file
    df = utils.pd.DataFrame({"x": [1, 2, 3]})
    file = tmp_path / "test.parquet"
    df.to_parquet(file)
    # should read without error
    out = utils.safe_read_parquet(file)
    assert len(out) == 3


def test_safe_read_parquet_retry(tmp_path, monkeypatch):
    file = tmp_path / "fake.parquet"
    # monkeypatch pd.read_parquet to fail twice then succeed
    call_count = {"n": 0}
    def fake_read(p):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise IOError("temporary")
        return utils.pd.DataFrame({"y": [0]})
    monkeypatch.setattr(utils.pd, "read_parquet", fake_read)
    result = utils.safe_read_parquet(file, retries=3, delay=0.01)
    assert "y" in result.columns
    assert call_count["n"] == 3


def test_move_to_quarantine(tmp_path):
    src = tmp_path / "orig.txt"
    src.write_text("hello")
    quarantine = tmp_path / "quarantine"
    dest = utils.move_to_quarantine(src, quarantine)
    assert dest.exists()
    assert not src.exists()
