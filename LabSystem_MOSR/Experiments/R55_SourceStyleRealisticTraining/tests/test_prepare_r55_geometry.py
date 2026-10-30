from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prepare_r55_geometry.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_r55_geometry", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_bmp(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", img)
    assert ok
    path.write_bytes(encoded.tobytes())


def test_prepare_package_writes_geometry_and_manifest(tmp_path: Path):
    module = load_module()
    package = tmp_path / "r53_realistic_calibrated_train_6000"
    src = np.full((64, 64), 80, np.uint8)
    lbl = np.full((64, 64), 80, np.uint8)
    lbl[:, 30:34] = 170
    _write_bmp(package / "src" / "stage" / "sample.bmp", src)
    _write_bmp(package / "lbl" / "stage" / "sample.bmp", lbl)
    manifest = {
        "total_pairs": 1,
        "pairs": [
            {
                "package_src": "src/stage/sample.bmp",
                "package_lbl": "lbl/stage/sample.bmp",
                "src": str(package / "src" / "stage" / "sample.bmp"),
                "lbl": str(package / "lbl" / "stage" / "sample.bmp"),
            }
        ],
    }
    (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    summary = module.prepare_package(package)

    assert summary["written"] == 1
    updated = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert updated["geometry_sidecars"] is True
    assert updated["geometry_count"] == 1
    assert (package / "geom" / "boundary" / "stage" / "sample.bmp").exists()
    assert (package / "geom" / "centerline" / "stage" / "sample.bmp").exists()
    assert (package / "geom" / "distance" / "stage" / "sample.npy").exists()
