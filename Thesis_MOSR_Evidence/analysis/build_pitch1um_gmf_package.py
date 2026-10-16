"""Build a filename-aligned external-GMF package for R103 E48 and R104 E48.

The generated package contains Raw, R103 E48, and R104 E48 arms with identical
frame_####.bmp names, plus a mapping and hash manifest.  It deliberately does
not parse or invent GMF coordinates; the external tool writes those later.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import shutil
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch


IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_checkpoint_model(
    *,
    experiment_root: Path,
    checkpoint: Path,
    module_name: str,
    config: dict,
    device: torch.device,
):
    sys.path.insert(0, str(experiment_root / "model"))
    sys.path.insert(0, str(experiment_root / "inference"))
    module = importlib.import_module(module_name)
    bounds = config["model"]["branch_bounds"]
    if module_name == "r103_model":
        model = module.build_model(
            base=int(config["model"]["base_channels"]),
            low_bound=float(bounds["radiometry"]),
            contour_bound=float(bounds["contour"]),
            texture_bound=float(bounds["texture"]),
            combined_bound=float(bounds["combined"]),
        )
    else:
        model = module.build_model(
            base=int(config["model"]["base_channels"]),
            low_bound=float(bounds["radiometry"]),
            illumination_bound=float(bounds["illumination"]),
            contour_bound=float(bounds["contour_proposal"]),
            texture_bound=float(bounds["texture_proposal"]),
            combined_bound=float(bounds["combined"]),
            gate_initial_probability=float(config["model"].get("gate_initial_probability", 0.12)),
        )
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    state = payload.get("ema_state_dict") or payload.get("model_state_dict") or payload.get("state_dict")
    if state is None:
        raise KeyError(f"No model state found in {checkpoint}")
    model.load_state_dict(state, strict=True)
    model = model.to(device).eval()
    return model, payload


def write_tsv(path: Path, rows: list[dict]) -> None:
    fields = ["case", "role", "image_folder", "score_folder", "image_count", "note"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--r103-root", type=Path, required=True)
    parser.add_argument("--r103-checkpoint", type=Path, required=True)
    parser.add_argument("--r104-root", type=Path, required=True)
    parser.add_argument("--r104-checkpoint", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--core-size", type=int, default=512)
    parser.add_argument("--r103-halo", type=int, default=128)
    parser.add_argument("--r104-halo", type=int, default=160)
    parser.add_argument("--tile-batch", type=int, default=4)
    parser.add_argument(
        "--even-one-based",
        action="store_true",
        help="Keep the 2nd, 4th, 6th, ... files after filename sorting.",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_dir():
        raise FileNotFoundError(source)
    for checkpoint in (args.r103_checkpoint, args.r104_checkpoint):
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)

    all_images = sorted(
        (path for path in source.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda path: path.name,
    )
    if not all_images:
        raise RuntimeError(f"No supported images in {source}")
    images = all_images[1::2] if args.even_one_based else all_images

    output.mkdir(parents=True, exist_ok=True)
    case_names = {
        "raw": "pitch1um_y100_raw",
        "r103": "pitch1um_y100_r103_e48",
        "r104": "pitch1um_y100_r104_e48",
    }
    case_dirs = {key: output / value / "bmp" for key, value in case_names.items()}
    score_dirs = {key: output / "_gmf_scores" / value for key, value in case_names.items()}
    for folder in list(case_dirs.values()) + list(score_dirs.values()):
        folder.mkdir(parents=True, exist_ok=True)

    config103 = load_config(args.r103_root / "config" / "experiment.json")
    config104 = load_config(args.r104_root / "config" / "experiment.json")
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(f"CUDA requested but unavailable: {device}")
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True
    model103, payload103 = load_checkpoint_model(
        experiment_root=args.r103_root.resolve(), checkpoint=args.r103_checkpoint.resolve(),
        module_name="r103_model", config=config103, device=device,
    )
    model104, payload104 = load_checkpoint_model(
        experiment_root=args.r104_root.resolve(), checkpoint=args.r104_checkpoint.resolve(),
        module_name="r104_model", config=config104, device=device,
    )
    # load_checkpoint_model adds the canonical inference directory to sys.path.
    from reconstruct import reconstruct_tensor

    mapping_rows: list[dict] = []
    arm_stats = {key: {"count": 0, "finite": True, "shape_set": set(), "mean_abs_change_gray": []} for key in case_names}
    started = time.perf_counter()

    for index, source_path in enumerate(images):
        if index % 10 == 0:
            print(f"[GMF package] {index}/{len(images)} {source_path.name}", flush=True)
        frame_name = f"frame_{index:04d}.bmp"
        raw_bytes = source_path.read_bytes()
        raw_output = case_dirs["raw"] / frame_name
        raw_output.write_bytes(raw_bytes)
        raw = cv2.imread(str(source_path), cv2.IMREAD_GRAYSCALE)
        if raw is None:
            raise RuntimeError(f"Unable to read {source_path}")
        if raw.ndim != 2:
            raise RuntimeError(f"Expected grayscale input: {source_path}")
        input_tensor = torch.from_numpy(raw.astype(np.float32) / 255.0).view(1, 1, *raw.shape)
        if device.type == "cuda":
            input_tensor = input_tensor.to(device, non_blocking=True)

        output_paths = {"raw": raw_output}
        for key, model, halo in (("r103", model103, args.r103_halo), ("r104", model104, args.r104_halo)):
            prediction = reconstruct_tensor(
                model, input_tensor, core_size=args.core_size, halo=halo, tile_batch=args.tile_batch
            )
            array_float = prediction.float().cpu().squeeze().numpy()
            if array_float.shape != raw.shape:
                raise RuntimeError(f"Shape mismatch for {key} {source_path}: {array_float.shape} vs {raw.shape}")
            if not np.isfinite(array_float).all():
                raise RuntimeError(f"Non-finite output for {key} {source_path}")
            array = np.clip(array_float * 255.0 + 0.5, 0, 255).astype(np.uint8)
            target = case_dirs[key] / frame_name
            if not cv2.imwrite(str(target), array):
                raise RuntimeError(f"Unable to write {target}")
            output_paths[key] = target
            arm_stats[key]["mean_abs_change_gray"].append(float(np.mean(np.abs(array.astype(np.float32) - raw.astype(np.float32)))))
            arm_stats[key]["shape_set"].add(tuple(array.shape))
            arm_stats[key]["finite"] = arm_stats[key]["finite"] and bool(np.isfinite(array).all())
            arm_stats[key]["count"] += 1

        arm_stats["raw"]["shape_set"].add(tuple(raw.shape))
        arm_stats["raw"]["finite"] = arm_stats["raw"]["finite"] and bool(np.isfinite(raw).all())
        arm_stats["raw"]["count"] += 1
        mapping_rows.append({
            "sequence_index": index,
            "frame_name": frame_name,
            "original_filename": source_path.name,
            "original_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "raw_sha256": sha256_file(raw_output),
            "r103_sha256": sha256_file(output_paths["r103"]),
            "r104_sha256": sha256_file(output_paths["r104"]),
        })
        del input_tensor
        if device.type == "cuda":
            torch.cuda.synchronize()
        if index % 10 == 0 or index == len(images) - 1:
            elapsed = time.perf_counter() - started
            print(f"[GMF package] completed {index + 1}/{len(images)} elapsed={elapsed:.1f}s", flush=True)

    mapping_path = output / "source_mapping.csv"
    with mapping_path.open("w", encoding="utf-8", newline="") as handle:
        fields = list(mapping_rows[0].keys())
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(mapping_rows)

    tsv_rows = []
    notes = {
        "raw": "Raw control; byte-preserved source frames, identical normalized order.",
        "r103": "R103 epoch 48; canonical tiled inference; no external coordinates included yet.",
        "r104": "R104 epoch 48; canonical tiled inference; no external coordinates included yet.",
    }
    for key in ("raw", "r103", "r104"):
        tsv_rows.append({
            "case": case_names[key],
            "role": "raw_input" if key == "raw" else key + "_e48",
            "image_folder": str(case_dirs[key]),
            "score_folder": str(score_dirs[key]),
            "image_count": len(images),
            "note": notes[key],
        })
    write_tsv(output / "paths_for_gmf_tool.tsv", tsv_rows)

    def clean_stats(value: dict) -> dict:
        return {
            "count": value["count"],
            "finite": value["finite"],
            "shapes": sorted([list(shape) for shape in value["shape_set"]]),
            "mean_abs_change_gray_median": float(np.median(value["mean_abs_change_gray"])) if value["mean_abs_change_gray"] else 0.0,
            "mean_abs_change_gray_p95": float(np.percentile(value["mean_abs_change_gray"], 95)) if value["mean_abs_change_gray"] else 0.0,
        }

    manifest = {
        "status": "ready_for_external_gmf",
        "package": "Pitch1um_Y_100_Cropped_Output_R103E48_R104E48",
        "source": str(source),
        "source_total_count": len(all_images),
        "source_count": len(images),
        "selection": "sorted by original filename, then keep 1-based even positions (2,4,6,...)" if args.even_one_based else "all files sorted by original filename",
        "source_order": "selected files normalized to frame_####.bmp; all arms share the same order",
        "image_shape": [int(raw.shape[0]), int(raw.shape[1])],
        "inference": {
            "r103": {"checkpoint": str(args.r103_checkpoint.resolve()), "checkpoint_sha256": sha256_file(args.r103_checkpoint.resolve()), "epoch": payload103.get("epoch"), "core_size": args.core_size, "halo": args.r103_halo, "tile_batch": args.tile_batch, "precision": "float32"},
            "r104": {"checkpoint": str(args.r104_checkpoint.resolve()), "checkpoint_sha256": sha256_file(args.r104_checkpoint.resolve()), "epoch": payload104.get("epoch"), "core_size": args.core_size, "halo": args.r104_halo, "tile_batch": args.tile_batch, "precision": "float32"},
        },
        "arms": {key: clean_stats(value) for key, value in arm_stats.items()},
        "coordinate_files": "not present; place the external GMF output in each row's score_folder as GMF_score.txt",
        "elapsed_seconds": time.perf_counter() - started,
        "artifacts": {"paths_tsv": "paths_for_gmf_tool.tsv", "mapping": "source_mapping.csv", "scores_root": "_gmf_scores"},
    }
    (output / "package_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    selection_note = "Only the 2nd, 4th, 6th, ... files after filename sorting are included (one frame per two-image position)." if args.even_one_based else "All source files are included."
    readme = f"""# External GMF package: Pitch1um_Y_100 / R103 E48 / R104 E48

This package contains {len(images)} selected frames from:

`{source}`

{selection_note}

The three arms use the same normalized names and order:

- `pitch1um_y100_raw\\bmp`: byte-preserved Raw control
- `pitch1um_y100_r103_e48\\bmp`: R103 epoch 48 reconstruction
- `pitch1um_y100_r104_e48\\bmp`: R104 epoch 48 reconstruction

Run the external GMF program on every `image_folder` listed in
`paths_for_gmf_tool.tsv`. Put each returned `GMF_score.txt` into the matching
folder under `_gmf_scores`. Do not rename or reorder frames. The original
filename mapping and SHA-256 hashes are in `source_mapping.csv`.

The score folders are intentionally empty until the external program returns.
"""
    (output / "README_EXTERNAL_GMF.md").write_text(readme, encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
