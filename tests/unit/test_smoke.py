"""Smoke test: the package imports and its sub-packages exist."""

import importlib

import radiografia


def test_version_is_defined():
    assert radiografia.__version__ == "0.1.0"


def test_subpackages_import():
    for name in ("domain", "data", "analytics", "reporting"):
        importlib.import_module(f"radiografia.{name}")
