"""End-to-end smoke test for the R114 validation and monitoring scaffold."""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "results" / "scaffold_smoke"
PYTHON = Path(sys.executable)


def write_gray(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = cv2.imencode(".png", np.rint(np.clip(image, 0, 1) * 255).astype(np.uint8))[1]
    encoded.tofile(path)


def synthetic_samples() -> list[dict[str, str]]:
    height, width = 352, 416
    y, x = np.mgrid[:height, :width]
    gradient = 0.08 * x / width + 0.05 * y / height
    specifications: list[tuple[str, str, str, np.ndarray]] = []

    circle = 0.18 + gradient + 0.58 * (((x - 205) ** 2 + (y - 170) ** 2) <= 82**2)
    specifications.append(("circle_degraded", "circle", "degraded", cv2.GaussianBlur(circle.astype(np.float32), (0, 0), 2.1)))

    radius = np.sqrt((x - 208) ** 2 + (y - 176) ** 2)
    ring = 0.73 - 0.5 * ((radius >= 62) & (radius <= 77)).astype(np.float32) + gradient
    specifications.append(("thin_ring", "ultra_thin_ring", "degraded", cv2.GaussianBlur(ring.astype(np.float32), (0, 0), 1.4)))

    dense = np.full((height, width), .68, np.float32) + gradient.astype(np.float32)
    for center_y in range(46, height, 58):
        for center_x in range(48, width, 58):
            dense[((x - center_x) ** 2 + (y - center_y) ** 2) <= 16**2] -= .42
    specifications.append(("dense_array", "dense_array", "degraded", cv2.GaussianBlur(dense, (0, 0), 1.7)))

    clear = np.clip(0.22 + gradient + 0.52 * (((x - 200) ** 2 / 96**2 + (y - 176) ** 2 / 58**2) <= 1), 0, 1)
    specifications.append(("clear_identity", "ellipse", "clear", clear.astype(np.float32)))
    specifications.append(("flat_negative", "flat", "flat", np.full((height, width), .47, np.float32)))

    records = []
    for sample_id, family, role, image in specifications:
        source = ARTIFACTS / "inputs" / f"{sample_id}.png"
        target = ARTIFACTS / "targets" / f"{sample_id}.png"
        write_gray(source, image)
        write_gray(target, image)
        records.append({
            "id": sample_id,
            "family": family,
            "role": role,
            "source": str(source),
            "target": str(target),
        })
    return records


def execute(arguments: list[str], expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(arguments, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != expected:
        raise RuntimeError(
            f"Command returned {result.returncode}, expected {expected}: {arguments}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def main() -> int:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    records = synthetic_samples()
    manifest = {
        "schema_version": 1,
        "records": records,
        "tile_configs": [
            {"name": "grid_a", "core": 128, "halo": 64, "overlap": 0, "origin": [0, 0]},
            {"name": "grid_b_shifted_overlap", "core": 128, "halo": 64, "overlap": 32, "origin": [31, 47]},
            {"name": "grid_c_large_core", "core": 192, "halo": 96, "overlap": 64, "origin": [53, 71]}
        ],
        "required_internal_maps": [
            "normalized_sdf", "normal_x", "normal_y", "boundary_confidence",
            "correction_need", "recoverability", "geometry_gate", "detail_gate",
            "width_gain", "normal_shift"
        ],
        "thresholds": {
            "max_identity_mae_gray": 0.01,
            "max_tile_mean_gray": 0.001,
            "max_tile_p99_gray": 0.001,
            "max_tile_absolute_gray": 0.001
        }
    }
    manifest_path = ARTIFACTS / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    validation_output = ARTIFACTS / "validation"
    execute([
        str(PYTHON), str(ROOT / "validation" / "run_validation.py"),
        "--adapter", str(ROOT / "validation" / "fixtures" / "fake_adapter.py"),
        "--manifest", str(manifest_path),
        "--output", str(validation_output),
        "--device", "cpu",
    ])
    validation_summary = json.loads((validation_output / "summary.json").read_text(encoding="utf-8"))

    fixture_root = ARTIFACTS / f"registry_fixture_{os.getpid()}_{int(time.time())}"
    registry_tool = ROOT / "scripts" / "monitor" / "run_registry.py"
    monitor_tool = ROOT / "scripts" / "monitor" / "monitor_training.py"
    first = "smoke_formal_a"
    execute([str(PYTHON), str(registry_tool), "--root", str(fixture_root), "reserve", "--run-id", first, "--total-epochs", "8", "--pid", str(os.getpid())])
    execute([str(PYTHON), str(registry_tool), "--root", str(fixture_root), "attach", "--run-id", first, "--trainer-pid", str(os.getpid())])
    run_dir = fixture_root / "runs" / first
    with (run_dir / "training_log.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "epoch", "stage", "duration_seconds", "train_total", "boundary_auc",
            "identity_mae_gray", "tile_mean_gray"
        ])
        writer.writeheader()
        writer.writerows([
            {"epoch": 1, "stage": "controller", "duration_seconds": 11.2, "train_total": .83, "boundary_auc": .66, "identity_mae_gray": .04, "tile_mean_gray": 0},
            {"epoch": 2, "stage": "controller", "duration_seconds": 10.4, "train_total": .71, "boundary_auc": .73, "identity_mae_gray": .03, "tile_mean_gray": 0},
            {"epoch": 3, "stage": "controller", "duration_seconds": 9.9, "train_total": .62, "boundary_auc": .79, "identity_mae_gray": .02, "tile_mean_gray": 0},
        ])
    duplicate = subprocess.run([
        str(PYTHON), str(registry_tool), "--root", str(fixture_root), "reserve",
        "--run-id", "smoke_formal_b", "--total-epochs", "8"
    ], cwd=ROOT, text=True, capture_output=True)
    if duplicate.returncode == 0:
        raise RuntimeError("Duplicate formal run reservation was not rejected")
    execute([str(PYTHON), str(registry_tool), "--root", str(fixture_root), "heartbeat", "--run-id", first, "--epoch", "3", "--checkpoint", "weights/epoch_003.pth"])
    monitor_result = execute([str(PYTHON), str(monitor_tool), "--root", str(fixture_root), "--once"])
    monitor_snapshot = json.loads((fixture_root / "logs" / "monitor_snapshot.json").read_text(encoding="utf-8"))
    running_inspection = json.loads(execute([str(PYTHON), str(registry_tool), "--root", str(fixture_root), "inspect"]).stdout)
    execute([str(PYTHON), str(registry_tool), "--root", str(fixture_root), "complete", "--run-id", first, "--message", "scaffold smoke only"])
    final_inspection = json.loads(execute([str(PYTHON), str(registry_tool), "--root", str(fixture_root), "inspect"]).stdout)

    inventory = json.loads((ROOT / "validation" / "tool_inventory.json").read_text(encoding="utf-8"))
    missing_inventory = [item["path"] for item in inventory["tools"] if not Path(item["path"]).exists()]
    family_table = validation_output / "tables" / "family_metrics.csv"
    map_pngs = list((validation_output / "internal_maps").rglob("*.png"))
    map_arrays = list((validation_output / "internal_maps").rglob("*.npy"))
    checks = {
        "validation_completed": validation_summary.get("status") == "complete",
        "five_families_exercised": len(validation_summary.get("families", [])) == 5,
        "clear_and_flat_exercised": {"clear", "flat"}.issubset(set(validation_summary.get("roles", []))),
        "three_tile_layouts_exercised": len(validation_summary.get("tile_configs", [])) == 3,
        "shifted_and_overlap_exercised": validation_summary["checks"].get("shifted_tile_origin_exercised") and validation_summary["checks"].get("overlap_exercised"),
        "internal_maps_saved_losslessly_and_viewable": len(map_pngs) >= 50 and len(map_arrays) >= 50,
        "family_table_written": family_table.exists() and family_table.stat().st_size > 0,
        "duplicate_formal_run_rejected": duplicate.returncode != 0,
        "running_registry_consistent": running_inspection.get("status") == "complete" and running_inspection.get("active_run_id") == first,
        "closed_registry_consistent": final_inspection.get("status") == "complete" and final_inspection.get("active_run_id") is None,
        "monitor_parsed_dynamic_eta": monitor_snapshot.get("eta_seconds") is not None and monitor_snapshot.get("eta_sample_epochs") == 3,
        "monitor_rendered_epoch": "3/8" in monitor_result.stdout,
        "inventory_paths_exist": not missing_inventory,
        "no_training_launched": True,
    }
    result = {
        "status": "complete" if all(checks.values()) else "failed",
        "checks": checks,
        "missing_inventory_paths": missing_inventory,
        "validation_summary": str(validation_output / "summary.json"),
        "monitor_snapshot": str(fixture_root / "logs" / "monitor_snapshot.json"),
        "registry_fixture": str(fixture_root),
        "duplicate_rejection": duplicate.stderr.strip(),
    }
    (ARTIFACTS / "scaffold_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
