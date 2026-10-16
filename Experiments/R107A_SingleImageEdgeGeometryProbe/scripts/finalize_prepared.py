"""Finalize and hash the prepared R107 code and data package."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "experiment.json"
PACKAGE = ROOT / "data" / "package"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, payload) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config["status"] not in {"ready_to_train", "ready_to_train_repaired"}:
        raise RuntimeError("Config status must be ready_to_train or ready_to_train_repaired")
    manifest_path = PACKAGE / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["status"] != "complete" or manifest["counts"] != {"train": 5000, "validation": 512}:
        raise RuntimeError("Dataset package is incomplete")
    expected = len(manifest["records"])
    for folder in ("targets", "masks", "sdf"):
        if len(list((PACKAGE / folder).glob("*.npy"))) != expected:
            raise RuntimeError(f"Unexpected file count in {folder}")
    manifest["config_sha256"] = sha256(CONFIG_PATH)
    atomic_json(manifest_path, manifest)

    included_roots = ["config", "data/package", "model", "training", "inference", "validation", "scripts", "design"]
    files = [ROOT / "README.md", ROOT / "requirements.txt"]
    for relative in included_roots:
        files.extend(path for path in (ROOT / relative).rglob("*") if path.is_file() and not path.name.endswith(".tmp"))
    files = sorted(set(files), key=lambda path: path.as_posix().lower())
    rows = []
    for index, path in enumerate(files, start=1):
        rows.append({"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)})
        if index % 1000 == 0 or index == len(files):
            print(json.dumps({"stage": "hash", "completed": index, "total": len(files)}), flush=True)
    with (ROOT / "FILE_MANIFEST_SHA256.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "bytes", "sha256"]); writer.writeheader(); writer.writerows(rows)

    prepared = {
        "status": "ready_to_train_repaired",
        "experiment_id": config["experiment_id"],
        "formal_training_attempted": True,
        "active_formal_training": False,
        "scratch_only": True,
        "dataset": {
            "train": 5000,
            "validation": 512,
            "records": expected,
            "bytes": sum(row["bytes"] for row in rows if row["path"].startswith("data/package/")),
            "manifest_sha256": sha256(manifest_path),
            "group_overlap_count": manifest["group_overlap_count"],
            "training_uses_real_pixels": manifest["training_uses_real_pixels"],
        },
        "model": {"parameters": 382230, "free_image_residual": False, "global_sdf_renderer": False, "input_images": 1},
        "failed_formal_attempt": {
            "run": "runs/r107_formal_scratch_20260825",
            "status": "failed_nonfinite_epoch1",
            "last_completed_epoch": 1,
            "last_global_step": 625,
            "checkpoint_written": False,
            "weights_reusable": False,
            "failure_record": "runs/r107_formal_scratch_20260825/failure.json"
        },
        "repair": {
            "summary": "Keep analytic endpoint operations in FP32, bound shared head features, evaluate parameter heads in FP32, and stop immediately on non-finite forward, loss, gradient, or parameter values.",
            "weights_inherited": False,
            "authoritative_stability_run": "runs/r107_bounded_heads_probe_700",
            "steps": 700,
            "passed_original_failure_step": 625,
            "training_history": "runs/r107_bounded_heads_probe_700/training_history.json",
            "checkpoint": "runs/r107_bounded_heads_probe_700/weights/epoch_006.pth",
            "checkpoint_sha256": "6c1ba97aae4b540c29bfc881c0e18443d8c81be362af66ff3f2d08c1e44f2594",
            "preview": "runs/r107_bounded_heads_probe_700/previews/epoch_006.png",
            "validation": "validation/bounded_heads_700_validation.json"
        },
        "superseded_diagnostic_runs": [
            "r107_smoke", "r107_smoke_v2", "r107_ready_smoke", "r107_amp_smoke", "r107_amp_smoke_v2",
            "r107_aux_smoke", "r107_nonfinite_repair_probe", "r107_forward_nan_probe",
            "r107_fp32_heads_probe_100", "r107_bounded_heads_probe_100"
        ],
        "validation": {
            "prepared": "validation/prepared_validation.json",
            "repaired_checkpoint": "validation/bounded_heads_700_validation.json",
            "forward_finite": True,
            "fixed_midpoint_abs_error": 1.1920928955078125e-07,
            "identity_mae_gray": 0.0017281110631302,
            "full_tile_max_abs_gray": 0.0005775690078735352
        },
        "file_manifest": "FILE_MANIFEST_SHA256.csv",
        "config_sha256": sha256(CONFIG_PATH),
        "warnings": ["cuDNN may emit a non-fatal execution-plan fallback warning for separable depthwise blur on this Windows/PyTorch build."],
        "next_action": "Start a new formal scratch run with a new run ID. Do not resume or reuse weights from the failed formal attempt or diagnostic probes."
    }
    atomic_json(ROOT / "PREPARED_STATE.json", prepared)
    print(json.dumps(prepared, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
