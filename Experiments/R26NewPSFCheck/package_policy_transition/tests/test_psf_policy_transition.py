from __future__ import annotations

import json
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(str(PROJECT_ROOT))
PACKAGE_INTERNAL = ROOT / r"_deployment_package\GeoEdge_R26_正式交付版\GeoEdge_R26_使用包\內部檔案"
PACKAGE_DOCS = ROOT / r"_deployment_package\GeoEdge_R26_正式交付版\GeoEdge_R26_使用包\參考文件"
POLICY_ROOT = ROOT / "docs" / "policy"

NEW_STANDARD_PSF_HASH = "BAFF1039744ED17CFFBA3D9F36A2535A7171BAC74E4B67669EDE412FB4B44F08"
NEW_STANDARD_CKPT_HASH = "0D68897E2F649111ACAE7B59D46F77F1F48EF4A2E0FB32F14C8C5FFDF014FE50"
LEGACY_PSF_HASH = "3AAB9CC1ED9EE0EB9C85227D026A3A8D86D0C035B8D06A46EB688551EFAE79CD"
LEGACY_CKPT_HASH = "1057F98B9B074621F1D8E7AEAD3D51545D839C79008E35011433868CA7E78CB0"


def test_policy_files_exist():
    assert (POLICY_ROOT / "PSF_POLICY_TRANSITION_R26.md").exists()
    assert (POLICY_ROOT / "PSF_STANDARD_POLICY.json").exists()


def test_package_legacy_manifest_exists():
    assert (PACKAGE_DOCS / "R26_LEGACY_BASELINE_MANIFEST.md").exists()


def test_candidate_manifest_exists():
    candidate_manifest = ROOT / r"Experiments\R26NewPSFCheck\formal_newpsf_candidate\candidate_manifest.json"
    assert candidate_manifest.exists()


def test_current_standard_policy_points_to_new_psf():
    policy = json.loads((POLICY_ROOT / "PSF_STANDARD_POLICY.json").read_text(encoding="utf-8"))
    assert policy["current_standard"]["psf_sha256"] == NEW_STANDARD_PSF_HASH
    assert policy["legacy_baseline"]["psf_sha256"] == LEGACY_PSF_HASH


def test_package_recipe_promoted_to_new_standard():
    recipe = json.loads((PACKAGE_INTERNAL / "formal_r26_recipe.json").read_text(encoding="utf-8"))
    assert recipe["hashes"]["official_psf_sha256"] == NEW_STANDARD_PSF_HASH
    assert recipe["hashes"]["official_deploy_checkpoint_sha256"] == NEW_STANDARD_CKPT_HASH
    assert recipe["hashes"]["legacy_psf_sha256"] == LEGACY_PSF_HASH
    assert recipe["hashes"]["legacy_deploy_checkpoint_sha256"] == LEGACY_CKPT_HASH
