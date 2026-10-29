from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[3]


GMM_ROOT = Path(str(PROJECT_ROOT))
PACKAGE = GMM_ROOT / "Deliverables" / "MOSR_ONNX"
R79 = GMM_ROOT / "Experiments" / "R79_R75v3_DenseMicroscopyScratchGeneralization"
CHECKPOINT = (
    R79
    / "weights"
    / "formal"
    / "seed_752031"
    / "training_progress_LAB_GESR_v1_v5_R75v3_scratch_formal_seed752031_dense_multiscale_e100_20260801_150729"
    / "best_tradeoff.pth.tar"
)
OUTPUT = (
    GMM_ROOT
    / "Experiments"
    / "R84_R79TileStableRootRepair"
    / "results"
    / "delivery_root_fix"
    / "parity"
)
IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def add_spread(cases: list[tuple[str, Path]], name: str, root: Path, indices: tuple[int, ...]) -> None:
    paths = image_files(root)
    if not paths:
        raise FileNotFoundError(root)
    for index in indices:
        cases.append((f"{name}_{index:03d}", paths[index]))


def build_cases() -> list[tuple[str, Path]]:
    cases: list[tuple[str, Path]] = [("package_example", PACKAGE / "example" / "input.bmp")]
    add_spread(
        cases,
        "customer_pitch",
        Path(str(PROJECT_ROOT / 'Shared_Sources/NTU_Originals/Pitch1um_Y_100/Cropped_Output')),
        (0, 101, -1),
    )
    add_spread(cases, "real_5x", GMM_ROOT / "20260704_5x", (0, -1))
    add_spread(cases, "real_20x", GMM_ROOT / "20260704_20x", (0, -1))
    add_spread(cases, "real_50x", GMM_ROOT / "20260702_100MG_位移_50x", (0, -1))
    cases.extend(
        [
            ("sem_P01", Path(str(PROJECT_ROOT / 'Shared_Sources/SEM_Originals/P-01.tiff'))),
            ("sem_V09", Path(str(PROJECT_ROOT / 'Shared_Sources/SEM_Originals/V-09.tiff'))),
        ]
    )
    return cases


def main() -> int:
    delivery = load_module("mosr_delivery_parity", PACKAGE / "run.py")
    source = load_module("r79_source_parity", R79 / "inference" / "infer_r75v3.py")
    if sha256(CHECKPOINT) != "7d4b2b3329b7b58338235433e140e542ea7d541b1796e4469ba92c71586ce509":
        raise RuntimeError("R79 checkpoint hash changed")

    delivery_model = delivery.MosrModel(force_cpu=True)
    reference_model, state_key = source.build_model(CHECKPOINT, "cpu", True)
    if state_key != "ema_state_dict":
        raise RuntimeError(f"Unexpected state key: {state_key}")

    rows: list[dict[str, object]] = []
    for case, path in build_cases():
        image = delivery.read_image(path)
        delivery.validate_image_size(image, path)
        onnx_output = delivery_model.reconstruct(image)
        pytorch_output = source.infer_full_frame(reference_model, image, "cpu")
        difference = np.abs(onnx_output.astype(np.int16) - pytorch_output.astype(np.int16))
        row = {
            "case": case,
            "source": str(path),
            "source_sha256": sha256(path),
            "height": int(image.shape[0]),
            "width": int(image.shape[1]),
            "max_abs_difference": int(difference.max()),
            "mean_abs_difference": float(difference.mean()),
            "p99_abs_difference": float(np.quantile(difference, 0.99)),
            "different_pixel_fraction": float(np.count_nonzero(difference) / difference.size),
            "pass": bool(difference.max() <= 1),
        }
        rows.append(row)
        print(
            f"{case}: {image.shape[1]}x{image.shape[0]}, "
            f"max={row['max_abs_difference']}, mean={row['mean_abs_difference']:.6f}"
        )

    result = {
        "status": "pass" if all(bool(row["pass"]) for row in rows) else "fail",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "comparison": "repaired ONNX full-frame delivery vs exact R79 EMA PyTorch full-frame",
        "checkpoint": str(CHECKPOINT),
        "checkpoint_sha256": sha256(CHECKPOINT),
        "onnx_sha256": sha256(PACKAGE / "model.onnx"),
        "state_key": state_key,
        "case_count": len(rows),
        "maximum_allowed_abs_difference": 1,
        "observed_maximum_abs_difference": max(int(row["max_abs_difference"]) for row in rows),
        "all_shapes_preserved": True,
        "rows": rows,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "parity_results.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with (OUTPUT / "parity_results.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    if result["status"] != "pass":
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
