from __future__ import annotations

import importlib.util
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[4]


LIB_PATH = Path(
    str(PROJECT_ROOT / 'Experiments/R26NewPSFCheck/pure_psf_control/scripts/pure_psf_control_lib.py')
)
REPORT_PATH = Path(
    str(PROJECT_ROOT / 'Experiments/Legacy/auto_tune_reports/auto_tune_report_20260316_185417.json')
)


def _load_lib():
    spec = importlib.util.spec_from_file_location("pure_psf_control_lib", LIB_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_load_round26_recipe_extracts_r26sm035():
    lib = _load_lib()
    recipe = lib.load_round26_recipe(REPORT_PATH, candidate_name="r26_sm035")
    assert recipe["seed"] == 1261620
    assert recipe["sweep_epochs"] == 12
    assert recipe["candidate_name"] == "r26_sm035"
    assert recipe["model_name_base"] == "GESR_v1_v5_ST0p8_SWP_r26sm035"
    assert recipe["common_overrides"]["VAL_RATIO"] == 0.05
    assert recipe["candidate_overrides"]["SEQ_STEP_MAG_WEIGHT"] == 0.35
    assert "PRETRAINED_PATH" in recipe["candidate_overrides"]


def test_build_parity_rows_only_flags_non_allowed_diffs():
    lib = _load_lib()
    left = {
        "psf_path": "old.mat",
        "output_root": "runs\\old",
        "run_name": "old_psf",
        "seed": 1261620,
        "deterministic": True,
        "amp": False,
    }
    right = {
        "psf_path": "new.mat",
        "output_root": "runs\\new",
        "run_name": "new_psf",
        "seed": 1261620,
        "deterministic": True,
        "amp": False,
    }
    rows = lib.build_parity_rows(left, right)
    changed = {row["field"]: row for row in rows if row["status"] == "allowed_difference"}
    assert set(changed) == {"psf_path", "output_root", "run_name"}
    assert not [row for row in rows if row["status"] == "unexpected_difference"]


def test_should_abort_after_epoch40_when_new_psf_is_consistently_worse():
    lib = _load_lib()
    baseline_rows = [
        {"epoch": 20, "edge_width_main_px": 35.0, "max_slope_main": 5.5, "CNR_main": 10.0, "background_std": 0.8},
        {"epoch": 40, "edge_width_main_px": 33.0, "max_slope_main": 6.0, "CNR_main": 12.0, "background_std": 0.7},
    ]
    candidate_rows = [
        {"epoch": 20, "edge_width_main_px": 42.0, "max_slope_main": 3.0, "CNR_main": 6.0, "background_std": 1.0},
        {"epoch": 40, "edge_width_main_px": 44.0, "max_slope_main": 2.8, "CNR_main": 5.5, "background_std": 1.1},
    ]
    verdict = lib.should_abort_after_epoch40(baseline_rows, candidate_rows)
    assert verdict["abort"] is True
    assert verdict["evaluated_epochs"] == [20, 40]


def test_should_not_abort_if_epoch40_recovers():
    lib = _load_lib()
    baseline_rows = [
        {"epoch": 20, "edge_width_main_px": 35.0, "max_slope_main": 5.5, "CNR_main": 10.0, "background_std": 0.8},
        {"epoch": 40, "edge_width_main_px": 33.0, "max_slope_main": 6.0, "CNR_main": 12.0, "background_std": 0.7},
    ]
    candidate_rows = [
        {"epoch": 20, "edge_width_main_px": 42.0, "max_slope_main": 3.0, "CNR_main": 6.0, "background_std": 1.0},
        {"epoch": 40, "edge_width_main_px": 32.5, "max_slope_main": 6.1, "CNR_main": 12.5, "background_std": 0.68},
    ]
    verdict = lib.should_abort_after_epoch40(baseline_rows, candidate_rows)
    assert verdict["abort"] is False


def test_resolve_round26_training_roots_points_to_stage_layout():
    lib = _load_lib()
    roots = lib.resolve_round26_training_roots()
    assert roots["src_root"].endswith("Training_Data\\generated_convolved")
    assert roots["lbl_root"].endswith("Training_Data\\generated")
    assert roots["n_selected_src"] == 918


def test_build_control_spec_enables_epoch_checkpoints():
    lib = _load_lib()
    recipe = lib.load_round26_recipe(REPORT_PATH, candidate_name="r26_sm035")
    spec = lib.build_control_spec(
        recipe=recipe,
        label="old_psf",
        psf_path=Path(r"D:\dummy\old.mat"),
        progress_root=Path(r"D:\dummy\runs"),
        sweep_epochs=40,
        checkpoint_every=10,
    )
    assert spec["common_overrides"]["AUTO_SWEEP_SAVE_CKPT_EVERY_EPOCH"] is True
    assert spec["common_overrides"]["AUTO_SWEEP_SAVE_CKPT_EVERY_N_EPOCH"] == 10
