from __future__ import annotations

import json
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[4]


PATCH_ROOT = Path(
    str(PROJECT_ROOT / 'Deliverables/Company_Packages/GeoEdge_R26_正式交付版/GeoEdge_R26_GPU補丁')
)
PAYLOAD_RUNTIME = PATCH_ROOT / "payload" / "內部檔案" / "portable_runtime"


def test_gpu_patch_payload_keeps_only_runtime_files():
    manifest_path = PATCH_ROOT / "patch_manifest.json"
    assert manifest_path.exists(), "GPU patch should carry patch_manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    assert data["patch_id"] == "geoedge-r26-gpu-runtime-offline"
    assert PAYLOAD_RUNTIME.exists(), "GPU patch should carry portable_runtime payload"


def test_gpu_patch_payload_does_not_ship_runtime_state_file():
    state_path = PAYLOAD_RUNTIME / ".geoedge_portable_runtime.json"
    assert not state_path.exists(), (
        "GPU patch payload should not ship machine-specific runtime state; "
        "the target package must generate this after install."
    )


def test_gpu_patch_installer_writes_fresh_target_runtime_state():
    install_text = (PATCH_ROOT / "INSTALL_GPU_PATCH.ps1").read_text(encoding="utf-8")
    assert ".geoedge_portable_runtime.json" in install_text
    assert "portable_root" in install_text
    assert "fixed_at" in install_text
