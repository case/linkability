"""Pytest fixtures for linkability tests."""

from pathlib import Path

import pytest


@pytest.fixture
def test_data_dir() -> Path:
    return Path(__file__).parent / "data"


@pytest.fixture
def test_zones_full_path(test_data_dir: Path) -> str:
    return str(test_data_dir / "test-zones-full.txt")


@pytest.fixture
def test_zones_brand_path(test_data_dir: Path) -> str:
    return str(test_data_dir / "test-zones-brand.txt")
