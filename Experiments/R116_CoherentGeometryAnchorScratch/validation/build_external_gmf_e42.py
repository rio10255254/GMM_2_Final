"""Build and verify the 101-frame external-GMF package for R116 E42."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import pandas as pd
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
INPUT = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/External_GMF_Packages/Pitch1um_Y_100_Raw_Even_R109E48/pitch1um_y100_raw/bmp'))
CHECKPOINT = ROOT / "runs" / "r116_formal_scratch_20260903_202052" / "failure_snapshot.pth"
OUTPUT = ROOT / "results" / "detailed_validation" / "06_external_gmf" / "E042"

from inference.tiled import forward_tiled
from model.r116_model import build_model


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    value = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(f"Could not read {path}")
    return value


def write_gray(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(".bmp", value.astype(np.uint8))
    if not success:
        raise RuntimeError(f"Could not encode {path}")
    encoded.tofile(str(path))


def main() -> int:
    inputs = sorted(INPUT.glob("frame_*.bmp"))
    if len(inputs) != 101 or [path.name for path in inputs] != [f"frame_{index:04d}.bmp" for index in range(101)]:
        raise RuntimeError("External-GMF input population must be exactly frame_0000 through frame_0100")
    saved = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    if saved.get("scratch") is not True or saved.get("checkpoint_loaded") is not False:
        raise RuntimeError("E42 checkpoint provenance mismatch")
    device = torch.device("cuda:0")
    model = build_model().to(device)
    model.load_state_dict(saved["model"], strict=True)
    model.requires_grad_(False).eval()
    output_dir = OUTPUT / "bmp"
    rows = []
    for index, source in enumerate(inputs, start=1):
        raw = read_gray(source)
        destination = output_dir / source.name
        if destination.is_file():
            output = read_gray(destination)
        else:
            tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
            with torch.inference_mode():
                prediction = forward_tiled(model, tensor, core_size=1024, halo=224)
            output = np.rint(prediction[0, 0].clamp(0, 1).cpu().numpy() * 255.0).astype(np.uint8)
            write_gray(destination, output)
        if output.shape != raw.shape:
            raise RuntimeError(f"Shape mismatch: {source.name}")
        difference = np.abs(output.astype(np.int16) - raw.astype(np.int16))
        rows.append({
            "frame": source.name,
            "source": str(source),
            "source_sha256": sha256(source),
            "output": str(destination),
            "output_sha256": sha256(destination),
            "height": raw.shape[0],
            "width": raw.shape[1],
            "mean_abs_change_gray": float(difference.mean()),
            "p99_abs_change_gray": float(np.quantile(difference, 0.99)),
            "max_abs_change_gray": int(difference.max()),
            "changed_pixel_fraction": float(np.mean(difference > 0)),
            "changed_over_2_gray_fraction": float(np.mean(difference > 2)),
            "exactly_identical": bool(np.array_equal(raw, output)),
        })
        if index % 5 == 0 or index == len(inputs):
            print(json.dumps({"done": index, "total": len(inputs), "frame": source.name}), flush=True)
    frame = pd.DataFrame(rows)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT / "reconstruction_manifest.csv", index=False, encoding="utf-8-sig")
    paths = OUTPUT / "paths_for_gmf_tool.tsv"
    with paths.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["case", "image_folder", "score_destination"])
        writer.writerow(["R116_E042", str(output_dir), str(OUTPUT / "_gmf_scores" / "GMF_score.txt")])
    payload = {
        "status": "complete",
        "candidate": "R116 E42",
        "checkpoint": str(CHECKPOINT),
        "checkpoint_sha256": sha256(CHECKPOINT),
        "input_dir": str(INPUT),
        "output_dir": str(output_dir),
        "frames": len(frame),
        "all_shapes": sorted({(int(row.height), int(row.width)) for row in frame.itertuples()}),
        "mean_abs_change_gray_median": float(frame["mean_abs_change_gray"].median()),
        "mean_abs_change_gray_max": float(frame["mean_abs_change_gray"].max()),
        "changed_pixel_fraction_median": float(frame["changed_pixel_fraction"].median()),
        "changed_over_2_gray_fraction_max": float(frame["changed_over_2_gray_fraction"].max()),
        "exactly_identical_frames": int(frame["exactly_identical"].sum()),
        "external_score_present": (OUTPUT / "_gmf_scores" / "GMF_score.txt").is_file(),
        "external_gmf_required": True,
    }
    (OUTPUT / "summary.json").write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
