"""
Structure and sanity tests for the R26 performance benchmark.
"""
from __future__ import annotations

from pathlib import Path

import pytest

PERF_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Directory structure tests
# ---------------------------------------------------------------------------

class TestDirectoryStructure:
    """Verify the expected directory layout exists."""

    def test_performance_root_exists(self):
        assert PERF_ROOT.is_dir()

    def test_scripts_dir(self):
        scripts = PERF_ROOT / "scripts"
        assert scripts.is_dir()

    def test_configs_dir(self):
        configs = PERF_ROOT / "configs"
        assert configs.is_dir()

    def test_results_dir(self):
        results = PERF_ROOT / "results"
        assert results.is_dir()

    def test_reports_dir(self):
        reports = PERF_ROOT / "reports"
        assert reports.is_dir()

    def test_readme_exists(self):
        assert (PERF_ROOT / "README.md").is_file()


# ---------------------------------------------------------------------------
# Script existence tests
# ---------------------------------------------------------------------------

class TestScriptsExist:
    """Verify all benchmark scripts exist."""

    def test_inference_benchmark_script(self):
        assert (PERF_ROOT / "scripts" / "run_inference_benchmark.py").is_file()

    def test_training_benchmark_script(self):
        assert (PERF_ROOT / "scripts" / "run_training_benchmark.py").is_file()

    def test_cross_device_compare_script(self):
        assert (PERF_ROOT / "scripts" / "run_cross_device_compare.py").is_file()


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestConfig:
    """Verify device_config.py is importable and has required fields."""

    def test_config_importable(self):
        import sys
        sys.path.insert(0, str(PERF_ROOT / "configs"))
        import device_config  # noqa: F401

    def test_config_has_required_fields(self):
        import sys
        sys.path.insert(0, str(PERF_ROOT / "configs"))
        import device_config as cfg
        required = [
            "DEVICE_NAME", "CHECKPOINT", "PSF_PATH", "TEST_INPUT_DIR",
            "CUDA_DEVICE", "INCLUDE_CPU", "TRAINING_MODE",
            "TRAINING_QUICK_EPOCHS", "WARMUP_RUNS", "BENCHMARK_RUNS",
            "TRAINING_SRC_DIR", "TRAINING_LBL_DIR",
        ]
        for field in required:
            assert hasattr(cfg, field), f"device_config missing required field: {field}"

    def test_device_name_is_string(self):
        import sys
        sys.path.insert(0, str(PERF_ROOT / "configs"))
        import device_config as cfg
        assert isinstance(cfg.DEVICE_NAME, str)
        assert len(cfg.DEVICE_NAME) > 0

    def test_training_mode_valid(self):
        import sys
        sys.path.insert(0, str(PERF_ROOT / "configs"))
        import device_config as cfg
        assert cfg.TRAINING_MODE in ("quick", "full")
