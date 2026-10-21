"""Materialize the fixed 48-scene development sequence bank.

Only synthetic development records are used. The target/mask references remain
in the immutable R118 package; each observation stores one compressed uint8
source and an auditable generation record.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data/package"
SELECTION = ROOT / "config/selected_scene_ids.json"
OUT = ROOT / "data/development_sequences"
BANK_SEED = 1198001


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stable_seed(scene_id: int, protocol: int, condition: int, frame: int, repeat: int) -> int:
    return int((BANK_SEED + scene_id * 1009 + protocol * 100003 + condition * 1009 + frame * 9176 + repeat * 17) % (2**32 - 1))


def kernel(name: str) -> np.ndarray:
    size = 17
    axis = np.arange(-(size // 2), size // 2 + 1, dtype=np.float32)
    yy, xx = np.meshgrid(axis, axis, indexing="ij")
    if name == "baseline":
        value = np.zeros((size, size), np.float32); value[size // 2, size // 2] = 1
    elif name == "rotated_anisotropic":
        theta = np.deg2rad(31.0); xr = xx * np.cos(theta) + yy * np.sin(theta); yr = -xx * np.sin(theta) + yy * np.cos(theta)
        value = np.exp(-.5 * ((xr / 2.0) ** 2 + (yr / .75) ** 2))
    elif name == "centered_asymmetric_tail":
        value = np.exp(-.5 * ((xx / 1.45) ** 2 + (yy / 1.0) ** 2))
        value += .23 * np.exp(-.5 * (((xx - 3.0) / 2.8) ** 2 + ((yy + .4) / 1.3) ** 2))
    else:
        raise ValueError(name)
    value = np.maximum(value, 0).astype(np.float32); value /= max(float(value.sum()), 1e-12)
    # Every primary kernel is centered; record the centroid to expose the
    # pure-kernel-translation ambiguity rather than hiding it as stage motion.
    cy, cx = np.indices(value.shape, dtype=np.float32)
    cx = float((value * (cx - size // 2)).sum()); cy = float((value * (cy - size // 2)).sum())
    if abs(cx) > 1e-6 or abs(cy) > 1e-6:
        # Recenter by shifting the sampled kernel with a subpixel warp.
        value = cv2.warpAffine(value, np.float32([[1, 0, -cx], [0, 1, -cy]]), (size, size), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        value = np.maximum(value, 0); value /= max(float(value.sum()), 1e-12)
    return value


def apply_kernel(image: np.ndarray, kernel_value: np.ndarray) -> np.ndarray:
    center = (kernel_value.shape[0] // 2, kernel_value.shape[1] // 2)
    if np.count_nonzero(np.abs(kernel_value) > 1e-8) == 1 and abs(float(kernel_value[center]) - 1.0) < 1e-6:
        return image
    return cv2.filter2D(image, -1, kernel_value, borderType=cv2.BORDER_REFLECT)


def shifted(image: np.ndarray, dx: float, dy: float) -> np.ndarray:
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(image, matrix, (image.shape[1], image.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def observation(base: np.ndarray, dx: float, dy: float, gain: float, kernel_value: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    value = apply_kernel(shifted(base, dx, dy), kernel_value)
    value = np.clip(value * gain, 0, 1)
    sigma = float(rng.uniform(.3, 3.0)) / 255.0
    value += rng.normal(0, sigma, value.shape).astype(np.float32)
    value += rng.normal(0, sigma * .15, (value.shape[0], 1)).astype(np.float32)
    value += rng.normal(0, sigma * .1, (1, value.shape[1])).astype(np.float32)
    return np.clip(value, 0, 1), sigma


def build(force: bool = False) -> dict:
    if OUT.exists() and any(OUT.iterdir()) and not force:
        raise FileExistsError(f"{OUT} is non-empty; use --force only for this generated bank")
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8-sig"))
    records = {int(r["scene_index"]): r for r in manifest["records"] if r["split"] == "validation"}
    selection = json.loads(SELECTION.read_text(encoding="utf-8-sig"))
    scene_ids = sorted(int(x) for x in selection["development_bank_scene_ids"])
    if len(scene_ids) != 48 or any(x not in records for x in scene_ids):
        raise ValueError("development bank scene IDs are not the frozen 48 validation records")
    base_manifest_sha = sha(PACKAGE / "manifest.json")
    out_records = []
    kernels = {name: kernel(name) for name in ("baseline", "rotated_anisotropic", "centered_asymmetric_tail")}
    protocols = [("static_repeat", 0), ("motion_x", 1), ("motion_y", 2), ("motion_diag", 3), ("exposure_static", 4), ("blur_static", 5)]
    for scene_id in scene_ids:
        source_path = PACKAGE / records[scene_id]["source_a"]
        target_path = PACKAGE / records[scene_id]["target_a"]
        mask_path = PACKAGE / records[scene_id]["mask_a"]
        base = np.load(source_path).astype(np.float32)
        if base.max() > 1.5: base /= 255.0
        target = np.load(target_path).astype(np.uint8)
        mask = np.load(mask_path).astype(np.uint8)
        complete = bool(mask[20:-20, 20:-20].sum() > 0 and mask[:20].sum() == 0 and mask[-20:].sum() == 0 and mask[:, :20].sum() == 0 and mask[:, -20:].sum() == 0)
        obs_specs = []
        for protocol, pindex in protocols:
            if protocol == "static_repeat":
                obs_specs.extend((protocol, "condition00", 0, 0, "baseline", 1.0, rep) for rep in range(8))
            elif protocol == "motion_x":
                obs_specs.extend((protocol, "condition00", -1 + .125 * frame, 0, "baseline", 1.0, 0) for frame in range(17))
            elif protocol == "motion_y":
                obs_specs.extend((protocol, "condition00", 0, -1 + .125 * frame, "baseline", 1.0, 0) for frame in range(17))
            elif protocol == "motion_diag":
                obs_specs.extend((protocol, "condition00", -1 + .125 * frame, -1 + .125 * frame, "baseline", 1.0, 0) for frame in range(17))
            elif protocol == "exposure_static":
                for condition, gain in enumerate((.7, .85, 1.0, 1.15, 1.3)):
                    obs_specs.extend((protocol, f"exposure{condition:02d}", 0, 0, "baseline", gain, rep) for rep in range(4))
            elif protocol == "blur_static":
                for condition, name in enumerate(("baseline", "rotated_anisotropic", "centered_asymmetric_tail")):
                    obs_specs.extend((protocol, f"blur{condition:02d}", 0, 0, name, 1.0, rep) for rep in range(4))
        for index, (protocol, condition, dx, dy, kernel_id, gain, repeat) in enumerate(obs_specs):
            pindex = next(value for name, value in protocols if name == protocol)
            frame = index if protocol.startswith("motion") else repeat
            condition_code = sum(ord(c) for c in condition) % 997
            rng = np.random.default_rng(stable_seed(scene_id, pindex, condition_code, frame, repeat))
            source, sigma = observation(base, dx, dy, gain, kernels[kernel_id], rng)
            filename = f"obs_{len(out_records):05d}.npz"
            out_path = OUT / filename
            np.savez_compressed(out_path, source=np.rint(source * 255).astype(np.uint8))
            ref_rel = str((Path("data/package") / records[scene_id]["target_a"]).as_posix())
            mask_rel = str((Path("data/package") / records[scene_id]["mask_a"]).as_posix())
            out_records.append({"schema_version": 1, "scene_id": f"dev_{scene_id}", "sequence_id": f"dev_{scene_id}_{protocol}_{condition}", "condition_id": condition, "protocol": protocol, "frame_index": frame if protocol.startswith("motion") else repeat, "family": records[scene_id]["family"], "polarity": records[scene_id]["polarity"], "split": "development", "true_x_px": float(dx), "true_y_px": float(dy), "noise_seed": stable_seed(scene_id, pindex, hash(condition) % 997, frame, repeat), "kernel_id": kernel_id, "exposure_gain": gain, "noise_sigma_gray": sigma * 255, "source": str((Path("data/development_sequences") / filename).as_posix()), "reference": ref_rel, "mask": mask_rel, "source_sha256": sha(out_path), "reference_sha256": sha(PACKAGE / records[scene_id]["target_a"]), "complete_object_in_roi": complete, "rendered_before_sensor_sampling": True})
    # Python's hash is salted; rewrite the recorded seeds from the stable fields
    # before writing. This guards reproducibility if the process hash seed changes.
    for row in out_records:
        row["noise_seed"] = stable_seed(int(row["scene_id"].split("_")[1]), {"static_repeat": 0, "motion_x": 1, "motion_y": 2, "motion_diag": 3, "exposure_static": 4, "blur_static": 5}[row["protocol"]], sum(ord(c) for c in row["condition_id"]) % 997, int(row["frame_index"]), int(row["frame_index"]) if row["protocol"] in {"static_repeat", "exposure_static", "blur_static"} else 0)
    output = {"schema_version": 1, "status": "complete", "created_at_utc": datetime.now(timezone.utc).isoformat(), "bank_seed": BANK_SEED, "base_manifest_sha256": base_manifest_sha, "selection_sha256": sha(SELECTION), "count": len(out_records), "expected_count": 48 * 91, "kernel_definitions": {name: {"sum": float(value.sum()), "centroid_x_px": float((value * (np.indices(value.shape, dtype=np.float32)[1] - value.shape[1] // 2)).sum()), "centroid_y_px": float((value * (np.indices(value.shape, dtype=np.float32)[0] - value.shape[0] // 2)).sum())} for name, value in kernels.items()}, "records": out_records}
    (OUT / "manifest.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--force", action="store_true")
    args = parser.parse_args(); result = build(args.force); print(json.dumps({k: result[k] for k in ("status", "count", "expected_count", "base_manifest_sha256", "selection_sha256")}, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
