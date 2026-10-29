"""Reconstruct only the Raw-locked current-top30 frames for R109 interventions."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
R109 = Path(str(PROJECT_ROOT / 'Experiments/R109_StagedMidpointWidthScratch'))
CHECKPOINT = R109 / "weights" / "selected" / "R109.pth"
SEQUENCE_CONFIG = Path(str(PROJECT_ROOT / 'Experiments/R111_R109V42ThesisReplacementQualification/config/r109_thesis_sequence_config.json'))
TOP30 = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/tables/top30_raw_motion_selection.csv'))
OUTPUT = ROOT / "results" / "physical_validation" / "lsc_interventions" / "reconstructions"
HALO = 192
CORE = 512


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Cannot read {path}")
    return image


def write_gray(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", image)
    if not ok:
        raise RuntimeError(f"Cannot encode {path}")
    encoded.tofile(str(path))


@torch.inference_mode()
def reconstruct(model, intervention_module, image: np.ndarray, variants: tuple[str, ...], device: torch.device) -> tuple[dict[str, np.ndarray], int]:
    source = torch.from_numpy(image.astype(np.float32)[None, None] / 255.0)
    height, width = image.shape
    padded = F.pad(source, (HALO, HALO, HALO, HALO), mode="reflect")
    output = {variant: np.zeros((height, width), np.float32) for variant in variants}
    full_max = 0.0
    for top in range(0, height, CORE):
        for left in range(0, width, CORE):
            core_h, core_w = min(CORE, height - top), min(CORE, width - left)
            tile = padded[..., top : top + core_h + 2 * HALO, left : left + core_w + 2 * HALO].to(device)
            requested = tuple(dict.fromkeys(("full", *variants)))
            values, _, qa = intervention_module.render_variants(model, tile, requested)
            full_max = max(full_max, float(qa["full_reproduction_max_abs"]))
            for variant in variants:
                value = values[variant][0, 0, HALO : HALO + core_h, HALO : HALO + core_w].cpu().numpy()
                output[variant][top : top + core_h, left : left + core_w] = value
    return {variant: np.round(np.clip(value, 0, 1) * 255).astype(np.uint8) for variant, value in output.items()}, int(round(full_max * 255))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", default="no_shift,smoothed_controls")
    parser.add_argument("--all-frames", action="store_true")
    args = parser.parse_args()
    variants = tuple(value.strip() for value in args.variants.split(",") if value.strip())
    sys.path.insert(0, str(R109 / "model"))
    sys.path.insert(0, str(ROOT / "scripts" / "structure"))
    from r109_model import build_model
    import r109_interventions

    invalid = sorted(set(variants) - set(r109_interventions.SUPPORTED_VARIANTS))
    if invalid:
        raise RuntimeError(f"Unsupported variants: {invalid}")
    config = json.loads(SEQUENCE_CONFIG.read_text(encoding="utf-8"))
    top = pd.read_csv(TOP30)
    selected = top.loc[top["top30_raw_motion_selected"].astype(str).str.lower().isin({"true", "1", "yes"})].copy()
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = build_model().to(device).eval()
    model.load_state_dict(torch.load(CHECKPOINT, map_location="cpu", weights_only=False)["model"])
    records: list[dict[str, object]] = []
    full_reproduction_max = 0
    for sequence, specification in config["sequences"].items():
        pairs = selected.loc[selected["sequence"].eq(sequence)]
        if len(pairs) != 30:
            raise RuntimeError(f"{sequence}: expected 30 selected pairs")
        indices = (
            list(range(int(specification["frame_count"])))
            if args.all_frames
            else sorted(set(pairs["end_frame_index"].astype(int)) | set(pairs["end_frame_index"].astype(int) - 1))
        )
        raw_dir = Path(PROJECT_ROOT / specification["raw_dir"])
        for done, frame_index in enumerate(indices, 1):
            filename = f"frame_{frame_index:04d}.bmp"
            image = read_gray(raw_dir / filename)
            outputs, reproduction = reconstruct(model, r109_interventions, image, variants, device)
            full_reproduction_max = max(full_reproduction_max, reproduction)
            for variant, value in outputs.items():
                destination = OUTPUT / variant / sequence / filename
                write_gray(destination, value)
                records.append({"sequence": sequence, "frame_index": frame_index, "variant": variant, "output": str(destination), "sha256": sha256(destination)})
            if done % 10 == 0 or done == len(indices):
                print(json.dumps({"sequence": sequence, "done": done, "total": len(indices)}), flush=True)
    manifest = OUTPUT.parent / "reconstruction_manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "variants": list(variants),
        "records": len(records),
        "unique_frames": int(len(records) / len(variants)),
        "checkpoint_sha256": sha256(CHECKPOINT),
        "full_renderer_reproduction_max_gray": full_reproduction_max,
    }
    (OUTPUT.parent / "reconstruction_state.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if full_reproduction_max != 0:
        raise RuntimeError(f"Full renderer reproduction failed: {result}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
