import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "validate_inner_circle_psf_fit.py"
SUMMARY_PATH = ROOT / "results" / "20250605_inner_circle_roi_fine_prealign_validation" / "validation_summary.json"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_inner_circle_psf_fit", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validation_script_defines_acceptance_rules():
    module = load_module()

    assert module.ACCEPTANCE_RULES["image_count"] == 25
    assert module.ACCEPTANCE_RULES["min_edge_improvement_vs_sharp_pct"] > 0
    assert module.ACCEPTANCE_RULES["max_global_gaussian_edge_gap_pct"] > 0


def test_validation_cli_accepts_alternate_run_without_config_update():
    module = load_module()

    args = module.build_arg_parser().parse_args(
        [
            "--config",
            "configs/inner_circle_roi_fine_prealign_20250608.json",
            "--output-dir",
            "results/20250605_inner_circle_roi_fine_prealign_validation",
            "--no-update-config",
        ]
    )

    assert args.config == "configs/inner_circle_roi_fine_prealign_20250608.json"
    assert args.output_dir == "results/20250605_inner_circle_roi_fine_prealign_validation"
    assert args.no_update_config is True


def test_validation_summary_records_required_evidence_after_run():
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

    assert summary["run_id"] == "20250605_inner_circle_roi_fine_prealign_validation"
    assert summary["validated_fit_run_id"] == "20250605_inner_circle_roi_fine_prealign_fit"
    assert summary["image_count"] == 25
    assert summary["verdict"] in {"validated", "needs_review", "failed"}
    assert "bads_vs_sharp_edge_rmse_improvement_pct" in summary
    assert "bads_vs_gaussian_edge_rmse_gap_pct" in summary
    assert summary["artifacts"]["metrics_csv"].endswith("validation_metrics.csv")
    assert summary["artifacts"]["comparison_contact"].endswith("forward_model_comparison_contact.png")
    assert summary["artifacts"]["psf_consistency_map"].endswith("psf_consistency_map.png")


def test_fine_config_records_validation_status_after_run():
    config_path = ROOT / "configs" / "inner_circle_roi_fine_prealign_20250608.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["validation"]["summary"].endswith("validation_summary.json")
    assert config["validation"]["verdict"] in {"validated", "needs_review", "failed"}


def test_validation_advances_next_stage_with_gaussian_control():
    next_config_path = ROOT.parents[0] / "lab_data_generation" / "configs" / "lab_data_generation_20250605.json"
    next_config = json.loads(next_config_path.read_text(encoding="utf-8"))

    assert next_config["status"] == "ready_for_planning"
    assert next_config["psf_inputs"]["formal_bads_psf"].endswith("PSF_fitted_2D_FOVstack.mat")
    assert next_config["psf_inputs"]["gaussian_control_sigma_px"] == 3.5
    assert next_config["psf_validation_verdict"] == "validated"
