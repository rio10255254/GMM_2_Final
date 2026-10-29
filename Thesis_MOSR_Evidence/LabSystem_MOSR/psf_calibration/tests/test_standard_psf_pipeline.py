import json
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(__file__).resolve().parents[1]


def test_standard_pipeline_copies_project_wholefov_fitter():
    standard_dir = ROOT / "scripts" / "standard_wholefov"
    expected = [
        "HDR_fitting_2D_WholeFOV_impl.m",
        "HDR_fitting_2D_WholeFOV_reasonable_v1.m",
        "HDR_fitting_2D_WholeFOV_candidate_prealign.m",
        "vlab_translate_image.m",
    ]

    for name in expected:
        path = standard_dir / name
        assert path.exists(), f"missing standard copied fitter file: {name}"
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "Copied for LabSystem_MOSR" in text


def test_standard_pipeline_manifest_records_original_sources():
    manifest_path = ROOT / "scripts" / "standard_wholefov" / "SOURCE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["source_project_root"].endswith(str(PROJECT_ROOT / 'PSF_Fitting'))
    assert len(manifest["copied_files"]) >= 4
    for item in manifest["copied_files"]:
        assert item["source_sha256"]
        assert item["copied_sha256"]
        assert item["source_relpath"].endswith(item["copied_relpath"].split("/")[-1])


def test_superseded_fullframe_and_edge_artifacts_are_archived():
    archive = ROOT / "archive" / "20250608_psf_cleanup"

    assert not (ROOT / "configs" / "standard_wholefov_20250605.json").exists()
    assert not (ROOT / "results" / "20250605_edge_psf").exists()
    assert not (ROOT / "inputs" / "20250605_standard_wholefov").exists()
    assert (archive / "configs" / "standard_wholefov_20250605.fullframe_blocked.json").exists()
    assert (archive / "configs" / "psf_calibration_20250605.edge_exploratory.json").exists()
    assert (archive / "inputs" / "20250605_standard_wholefov_fullframe_blocked").exists()
    assert (archive / "results" / "20250605_edge_psf_exploratory").exists()
    assert (archive / "scripts" / "run_lab_wholefov_standard_fit.m").exists()


def test_superseded_first_bads_fit_is_archived():
    archive = ROOT / "archive" / "20250608_psf_cleanup"

    assert not (ROOT / "configs" / "inner_circle_roi_standard_wholefov_20250605.json").exists()
    assert not (ROOT / "scripts" / "run_lab_inner_circle_roi_standard_fit.m").exists()
    assert not (ROOT / "results" / "20250605_inner_circle_roi_standard_fit").exists()
    assert not (ROOT / "results" / "20250605_inner_circle_roi_validation").exists()

    assert (
        archive
        / "configs"
        / "inner_circle_roi_standard_wholefov_20250605.superseded_by_fine.json"
    ).exists()
    assert (archive / "scripts" / "run_lab_inner_circle_roi_standard_fit.m").exists()
    assert (
        archive
        / "results"
        / "20250605_inner_circle_roi_standard_fit_superseded_by_fine"
        / "PSF_fitted_2D_FOVstack.mat"
    ).exists()
    assert (
        archive
        / "results"
        / "20250605_inner_circle_roi_validation_superseded_by_fine"
        / "validation_summary.json"
    ).exists()


def test_inner_circle_roi_fine_config_is_ready_for_copied_fitter():
    config_path = ROOT / "configs" / "inner_circle_roi_fine_prealign_20250608.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["method"] == "project_standard_wholefov_zernike_bads"
    assert config["status"] == "validated_ready_for_lab_data_generation"
    assert config["effective_pixel_size_um"] == 0.1725
    assert 579 < config["target_diameter_px"] < 581
    assert config["measurement_image_count"] == 25

    gt_path = ROOT / "inputs" / "20250605_inner_circle_roi" / "GT" / "LAB_INNER_CIRCLE_GT_901.bmp"
    measured_dir = ROOT / "inputs" / "20250605_inner_circle_roi" / "measured"
    runner_path = ROOT / "scripts" / "run_lab_inner_circle_roi_fine_prealign_fit.m"
    output_dir = ROOT / "results" / "20250605_inner_circle_roi_fine_prealign_fit"

    assert gt_path.exists()
    assert len(list(measured_dir.glob("VisionTop_*.bmp"))) == 25
    assert runner_path.exists()
    assert "HDR_fitting_2D_WholeFOV_impl" in runner_path.read_text(encoding="utf-8")
    assert (output_dir / "batch_results.csv").exists()
    assert (output_dir / "PSF_fitted_2D_FOVstack.mat").exists()
    assert (output_dir / "fit_summary.json").exists()


def test_fine_prealign_run_records_more_detailed_search():
    config_path = ROOT / "configs" / "inner_circle_roi_fine_prealign_20250608.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["method"] == "project_standard_wholefov_zernike_bads"
    assert config["comparison_to"] == "20250605_inner_circle_roi_standard_fit"
    assert config["prealign_search_step"] == 0.10
    assert config["prealign_crop_size"] == 385
    assert config["measurement_image_count"] == 25
    assert config["output_dir"].endswith("20250605_inner_circle_roi_fine_prealign_fit")

    runner_path = ROOT / "scripts" / "run_lab_inner_circle_roi_fine_prealign_fit.m"
    assert runner_path.exists()
    runner_text = runner_path.read_text(encoding="utf-8")
    assert "'prealign_search_step', 0.10" in runner_text
    assert "'prealign_crop_size', 385" in runner_text
