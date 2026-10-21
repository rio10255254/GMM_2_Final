from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

import cv2
import numpy as np


EXPERIMENT = Path(__file__).resolve().parent
INPUT_DIR = EXPERIMENT / "inputs" / "shifted"
RESULTS_DIR = EXPERIMENT / "results"
QA_DIR = EXPERIMENT / "qa"
MOSR_CHECKPOINT = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Model_Packages"
    r"\V42_SoftLabelSNR_FullStandalone_20260709\results\training_results"
    r"\training_progress_V42_SoftLabelSNR_full_training_20260709_202710_20260709_202713"
    r"\epoch_120.pth.tar"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def find_mosr_output(root: Path) -> Path:
    candidates = sorted(
        path
        for path in root.rglob("outputs")
        if path.is_dir() and len(list(path.glob("*.png"))) == 126
    )
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one MOSR output leaf with 126 images, got {candidates}")
    return candidates[0]


def read_u16(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"Could not read {path}")
    if image.dtype != np.uint16 or image.shape != (512, 512):
        raise RuntimeError(f"Unexpected image at {path}: {image.dtype} {image.shape}")
    return image


def main() -> None:
    with (EXPERIMENT / "inputs" / "input_manifest.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    filenames = [row["filename"] for row in rows]
    expected = set(filenames)
    reference_names = [row["filename"] for row in rows if row["axis"] == "reference"]

    method_dirs = {
        "raw": INPUT_DIR,
        "base_unet": RESULTS_DIR / "base_unet",
        "edsr": RESULTS_DIR / "edsr",
        "nafnet": RESULTS_DIR / "nafnet",
        "mosr": find_mosr_output(RESULTS_DIR / "mosr_cli"),
    }

    report: dict[str, object] = {
        "expected_count": len(expected),
        "methods": {},
        "passed": True,
    }
    preview_root = QA_DIR / "output_previews_8bit"
    preview_root.mkdir(parents=True, exist_ok=True)

    raw_cache: dict[str, np.ndarray] = {
        name: read_u16(INPUT_DIR / name) for name in filenames
    }
    for method, directory in method_dirs.items():
        actual = {path.name for path in directory.glob("*.png")}
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        records = []
        nonconstant_count = 0
        for name in filenames:
            image = read_u16(directory / name)
            if int(image.max()) > int(image.min()):
                nonconstant_count += 1
            difference = image.astype(np.float64) - raw_cache[name].astype(np.float64)
            records.append(
                {
                    "minimum": int(image.min()),
                    "maximum": int(image.max()),
                    "mean": float(image.mean()),
                    "std": float(image.std()),
                    "clip_low": float(np.mean(image == 0)),
                    "clip_high": float(np.mean(image == 65535)),
                    "raw_mae_levels": float(np.mean(np.abs(difference))),
                }
            )

        method_passed = (
            not missing
            and not extra
            and nonconstant_count == len(filenames)
            and all(np.isfinite(row["mean"]) for row in records)
        )
        report["methods"][method] = {
            "directory": str(directory),
            "count": len(actual),
            "missing": missing,
            "extra": extra,
            "nonconstant_count": nonconstant_count,
            "global_minimum": min(row["minimum"] for row in records),
            "global_maximum": max(row["maximum"] for row in records),
            "mean_intensity_range": [
                min(row["mean"] for row in records),
                max(row["mean"] for row in records),
            ],
            "maximum_clipped_low_fraction": max(row["clip_low"] for row in records),
            "maximum_clipped_high_fraction": max(row["clip_high"] for row in records),
            "median_raw_mae_uint16_levels": float(
                np.median([row["raw_mae_levels"] for row in records])
            ),
            "passed": method_passed,
        }
        report["passed"] = bool(report["passed"] and method_passed)

        method_preview_dir = preview_root / method
        method_preview_dir.mkdir(parents=True, exist_ok=True)
        for name in reference_names:
            image = read_u16(directory / name)
            preview = np.clip(np.rint(image.astype(np.float32) / 257.0), 0, 255).astype(
                np.uint8
            )
            output = method_preview_dir / name.replace(".png", "_preview.png")
            if not cv2.imwrite(str(output), preview):
                raise RuntimeError(f"Could not write preview {output}")

    mapping = {method: str(directory) for method, directory in method_dirs.items()}
    (RESULTS_DIR / "method_outputs.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    mosr_manifest = {
        "method": "mosr",
        "checkpoint": str(MOSR_CHECKPOINT),
        "checkpoint_sha256": sha256_file(MOSR_CHECKPOINT),
        "checkpoint_epoch": 120,
        "output_directory": str(method_dirs["mosr"]),
        "input_count": len(filenames),
        "output_count": len(list(method_dirs["mosr"].glob("*.png"))),
        "input_dtype": "uint16",
        "input_normalization": "uint16 / 65535",
        "output_dtype": "uint16",
        "inference_support": "whole 512x512 crop; no tiling; align factor 64",
        "psf_source": "checkpoint buffers",
        "external_anchor_output_mode": "none",
        "strict_weight_loading": True,
    }
    (RESULTS_DIR / "mosr_inference_manifest.json").write_text(
        json.dumps(mosr_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (QA_DIR / "inference_output_qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Copy two fixed images into a small repeat-run folder. This is only for
    # deterministic MOSR QA; the experiment itself continues to use all inputs.
    repeat_dir = QA_DIR / "mosr_repeat_inputs"
    repeat_dir.mkdir(parents=True, exist_ok=True)
    repeat_names = ["50x_pillar__ref.png", "50x_pillar__x_m1p00.png"]
    for name in repeat_names:
        shutil.copy2(INPUT_DIR / name, repeat_dir / name)

    repeat_candidates = sorted(
        path
        for path in (QA_DIR / "mosr_repeat_cli").rglob("outputs")
        if path.is_dir() and len(list(path.glob("*.png"))) == len(repeat_names)
    )
    if repeat_candidates:
        if len(repeat_candidates) != 1:
            raise RuntimeError(f"Ambiguous MOSR repeat outputs: {repeat_candidates}")
        repeat_output = repeat_candidates[0]
        repeat_differences = {}
        for name in repeat_names:
            first = read_u16(method_dirs["mosr"] / name)
            second = read_u16(repeat_output / name)
            repeat_differences[name] = int(
                np.max(np.abs(first.astype(np.int32) - second.astype(np.int32)))
            )
        repeat_passed = max(repeat_differences.values()) <= 1
        report["mosr_deterministic_repeat_qa"] = {
            "repeat_directory": str(repeat_output),
            "maximum_uint16_level_difference_by_file": repeat_differences,
            "passed": repeat_passed,
        }
        report["passed"] = bool(report["passed"] and repeat_passed)

    (QA_DIR / "inference_output_qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
