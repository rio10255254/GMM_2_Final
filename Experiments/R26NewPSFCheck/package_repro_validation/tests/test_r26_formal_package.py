from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


PACKAGE_ROOT = Path(
    r"D:\GMM_2_Final\_deployment_package\GeoEdge_R26_正式交付版\GeoEdge_R26_使用包"
)
INTERNAL_ROOT = PACKAGE_ROOT / "內部檔案"
NEW_STANDARD_PSF_HASH = "BAFF1039744ED17CFFBA3D9F36A2535A7171BAC74E4B67669EDE412FB4B44F08"
NEW_STANDARD_CKPT_HASH = "0D68897E2F649111ACAE7B59D46F77F1F48EF4A2E0FB32F14C8C5FFDF014FE50"
LEGACY_PSF_HASH = "3AAB9CC1ED9EE0EB9C85227D026A3A8D86D0C035B8D06A46EB688551EFAE79CD"
LEGACY_CKPT_HASH = "1057F98B9B074621F1D8E7AEAD3D51545D839C79008E35011433868CA7E78CB0"


def test_formal_recipe_manifest_exists():
    recipe_path = INTERNAL_ROOT / "formal_r26_recipe.json"
    assert recipe_path.exists(), "formal_r26_recipe.json should exist in package internal root"

    data = json.loads(recipe_path.read_text(encoding="utf-8"))
    assert data["winner_name"] == "r26_sm035"
    assert data["source_winner_kind"] == "sweep"
    assert data["kind"] == "full_train_baseline"
    assert data["formal_run_kind"] == "full_train_baseline"
    assert data["formal_num_epoch"] == 60
    assert data["seed"] == 1261620
    assert data["deterministic"] is True
    assert data["hashes"]["official_psf_sha256"] == NEW_STANDARD_PSF_HASH
    assert data["hashes"]["official_deploy_checkpoint_sha256"] == NEW_STANDARD_CKPT_HASH
    assert data["hashes"]["legacy_psf_sha256"] == LEGACY_PSF_HASH
    assert data["hashes"]["legacy_deploy_checkpoint_sha256"] == LEGACY_CKPT_HASH
    assert "policy_status" not in data
    assert "TRAIN_INCLUDE_SUBDIRS" in data["overrides"]
    assert "SEQ_INCLUDE_SUBDIRS" in data["overrides"]
    assert "BEST_EPOCH_MIN" not in data["overrides"]
    assert "BEST_EPOCH_MAX" not in data["overrides"]
    assert "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH" not in data["overrides"]
    assert "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH" not in data["overrides"]
    assert "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH" not in data["overrides"]


def test_formal_wrapper_scripts_exist():
    assert (INTERNAL_ROOT / "GeoEdge_R26_FormalTrain.ps1").exists()
    assert (INTERNAL_ROOT / "GeoEdge_R26_FormalInfer.ps1").exists()


def test_formal_seed_checkpoint_exists():
    seed_ckpt = INTERNAL_ROOT / "weights" / "r25_sw010_seed_best_tradeoff.pth.tar"
    assert seed_ckpt.exists(), "package should carry the formal r25_sw010 seed checkpoint"


def test_formal_stage_subset_exists():
    src_root = INTERNAL_ROOT / "Training_Data" / "generated_convolved"
    lbl_root = INTERNAL_ROOT / "Training_Data" / "generated"
    required = {
        "stage_08_annulus_focus",
        "stage_09_annulus_non_overlap",
        "stage_10_annulus_overlap",
        "stage_14_annulus_edge_defect_focus",
        "stage_15_annulus_sparse_clean",
        "stage_16_annulus_sparse_defect_clean",
        "stage_23_annulus_gmf_sequence_mid_clean",
        "stage_24_annulus_gmf_sequence_mid_defect",
        "stage_27_annulus_gmf_sequence_midwide_clean",
        "stage_28_annulus_gmf_sequence_midwide_defect",
    }
    assert src_root.exists(), "generated_convolved subset root should exist"
    assert lbl_root.exists(), "generated subset root should exist"
    missing_src = sorted(name for name in required if not (src_root / name).exists())
    missing_lbl = sorted(name for name in required if not (lbl_root / name).exists())
    assert not missing_src, f"missing formal source stages: {missing_src}"
    assert not missing_lbl, f"missing formal label stages: {missing_lbl}"


def test_run_full_train_no_longer_calls_generic_training_directly():
    bat_text = (PACKAGE_ROOT / "RUN_FULL_TRAIN.bat").read_text(encoding="utf-8")
    assert "GeoEdge_AutoLauncher.ps1" in bat_text

    native_text = (INTERNAL_ROOT / "GeoEdge_NativeLauncher.ps1").read_text(encoding="utf-8")
    docker_text = (INTERNAL_ROOT / "GeoEdge_Launcher.ps1").read_text(encoding="utf-8")
    assert "GeoEdge_R26_FormalTrain.ps1" in native_text
    assert "GeoEdge_R26_FormalTrain.ps1" in docker_text
    assert "train-quick" not in native_text
    assert "train-quick" not in docker_text


def test_cleanup_removed_nonformal_package_artifacts():
    removed_paths = [
        PACKAGE_ROOT / "RUN_QUICK_TRAIN.bat",
        PACKAGE_ROOT / "檔案結構說明.md",
        PACKAGE_ROOT / "容器進階",
        PACKAGE_ROOT / "輸出結果" / "驗證分析",
        INTERNAL_ROOT / "analysis_scripts",
        INTERNAL_ROOT / "Reconstruct_Progress",
        INTERNAL_ROOT / "Traing_Progress",
        INTERNAL_ROOT / "GeoEdge_PackageSmokeTest.ps1",
        INTERNAL_ROOT / "weights" / "legacy_baseline",
        INTERNAL_ROOT
        / "PSF_Fitting"
        / "Crop_circle_FreqFiltered"
        / "Fits"
        / "legacy_baseline",
        PACKAGE_ROOT / "參考文件" / "R26_PACKAGE_NOTES.md",
    ]
    still_present = [str(path) for path in removed_paths if path.exists()]
    assert not still_present, f"package should not retain cleanup targets: {still_present}"


def test_policy_transition_docs_present():
    docs_root = PACKAGE_ROOT / "參考文件"
    manifest = docs_root / "R26_LEGACY_BASELINE_MANIFEST.md"
    assert docs_root.exists(), "package should retain the policy-transition reference docs root"
    assert manifest.exists(), "package should retain the legacy baseline manifest after the PSF policy transition"


def test_formal_train_adapter_uses_pretrained_seed_not_resume():
    adapter_text = (
        INTERNAL_ROOT / "Model" / "GeoEdge_R26_FormalTrainAdapter.py"
    ).read_text(encoding="utf-8")
    assert "--resume-checkpoint" not in adapter_text
    assert "--reset-epoch" not in adapter_text


def test_formal_wrapper_scripts_avoid_powershell7_only_ternary():
    train_text = (INTERNAL_ROOT / "GeoEdge_R26_FormalTrain.ps1").read_text(encoding="utf-8")
    infer_text = (INTERNAL_ROOT / "GeoEdge_R26_FormalInfer.ps1").read_text(encoding="utf-8")
    assert "($ProgressRoot ? $ProgressRoot :" not in train_text
    assert "($InputDir ? $InputDir :" not in infer_text
    assert "($ReconRoot ? $ReconRoot :" not in infer_text


def test_formal_adapter_applies_historical_r26_run_semantics():
    adapter_path = INTERNAL_ROOT / "Model" / "GeoEdge_R26_FormalTrainAdapter.py"
    recipe_path = INTERNAL_ROOT / "formal_r26_recipe.json"

    if str(INTERNAL_ROOT / "Model") not in sys.path:
        sys.path.insert(0, str(INTERNAL_ROOT / "Model"))

    adapter_spec = importlib.util.spec_from_file_location("geoedge_formal_adapter_test", adapter_path)
    assert adapter_spec and adapter_spec.loader
    adapter_mod = importlib.util.module_from_spec(adapter_spec)
    adapter_spec.loader.exec_module(adapter_mod)

    train_path = INTERNAL_ROOT / "Model" / "GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py"
    train_mod = adapter_mod._load_module(train_path, "geoedge_formal_train_mod_test")
    recipe = adapter_mod._resolved_recipe(recipe_path)
    adapter_mod._apply_recipe(train_mod, recipe)

    assert recipe["model_name"] == "GESR_v1_v5_ST0p8_SWP_r26sm035"
    assert recipe["source_winner_kind"] == "sweep"
    assert recipe["formal_run_kind"] == "full_train_baseline"
    assert recipe["formal_simpletest_mode"] is False
    assert recipe["formal_num_epoch"] == 60
    assert train_mod.CFG.MODEL_NAME == "GESR_v1_v5_ST0p8_SWP_r26sm035"
    assert train_mod.MODEL_NAME_BASE == "GESR_v1_v5_ST0p8_SWP_r26sm035"
    assert train_mod.RUN_TAG_BASE == "GESR_v1_v5_ST0p8_SWP_r26sm035"
    assert train_mod.CFG.SIMPLETEST_MODE is False
    assert train_mod.CFG.NUM_EPOCH == 60
    assert train_mod.CFG.SIMPLETEST_MAX_EPOCH == 60
    assert train_mod.CFG.LOAD_RESET_EPOCH is True
    assert train_mod.CFG.LOAD_RESET_OPTIMIZER is False
    assert train_mod.CFG.RESUME_CHECKPOINT is None
    assert train_mod.CFG.BEST_EPOCH_MIN == 20
    assert train_mod.CFG.BEST_EPOCH_MAX == 60
    assert train_mod.CFG.EARLY_MAX_TRAIN_BATCHES_PER_EPOCH == 0
    assert train_mod.CFG.EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH == 0
    assert train_mod.CFG.EARLY_FAST_VAL_UNTIL_EPOCH == 0


def test_native_launcher_show_config_returns_json():
    launcher = INTERNAL_ROOT / "GeoEdge_NativeLauncher.ps1"
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(launcher),
            "-Action",
            "show-config",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    stdout = result.stdout.strip()
    assert stdout, "show-config should emit JSON instead of exiting silently"
    data = json.loads(stdout)
    assert data["demo_weights"] == "weights\\r26_sm035_best_tradeoff.pth.tar"
    assert "train_quick_simpletest_max_epoch" not in data


def test_formal_dry_run_exposes_reset_epoch_launch_default():
    adapter = INTERNAL_ROOT / "Model" / "GeoEdge_R26_FormalTrainAdapter.py"
    recipe = INTERNAL_ROOT / "formal_r26_recipe.json"
    progress_root = PACKAGE_ROOT / "輸出結果" / "訓練結果"
    result = subprocess.run(
        [
            sys.executable,
            str(adapter),
            "--recipe",
            str(recipe),
            "--progress-root",
            str(progress_root),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["model_name"] == "GESR_v1_v5_ST0p8_SWP_r26sm035"
    assert payload["formal_run_kind"] == "full_train_baseline"
    assert payload["formal_num_epoch"] == 60
    assert payload["train_reset_epoch"] is True
    assert payload["train_reset_optimizer"] is False


def test_infer_script_uses_unicode_safe_image_io():
    infer_text = (
        INTERNAL_ROOT / "Model" / "GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py"
    ).read_text(encoding="utf-8")
    assert "cv2.imread(str(path), cv2.IMREAD_UNCHANGED)" not in infer_text
    assert "cv2.imwrite(str(out_path), out_u8)" not in infer_text
    assert "cv2.imwrite(str(out_path), out)" not in infer_text
    assert "imread_unicode" in infer_text
    assert "imwrite_unicode" in infer_text
