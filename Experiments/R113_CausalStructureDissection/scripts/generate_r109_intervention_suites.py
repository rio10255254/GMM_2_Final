"""Generate matched R73/R74 causal intervention reconstructions with fixed tiling."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
R109 = Path(str(PROJECT_ROOT / 'Experiments/R109_StagedMidpointWidthScratch'))
CHECKPOINT = R109 / "weights" / "selected" / "R109.pth"
OUTPUT = ROOT / "results" / "physical_validation" / "intervention_reconstructions"
SOURCES = {
    "R73": Path(str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/data/r73_synthetic_acm_val/src')),
    "R74": Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val/src')),
}
CANONICAL = {
    "R73": R109 / "results" / "posttraining" / "E048" / "R73",
    "R74": R109 / "results" / "posttraining" / "E048" / "R74",
}
VARIANTS = ("full", "no_shift", "no_width", "learned_support_only", "smoothed_controls")
CORE = 512
HALO = 192


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
def tiled_variants(model, intervention_module, image: np.ndarray, device: torch.device, core: int) -> dict[str, np.ndarray]:
    source = torch.from_numpy(image.astype(np.float32)[None, None] / 255.0)
    height, width = image.shape
    padded = F.pad(source, (HALO, HALO, HALO, HALO), mode="reflect")
    result = {variant: np.zeros((height, width), np.float32) for variant in VARIANTS}
    for top in range(0, height, core):
        for left in range(0, width, core):
            core_h = min(core, height - top)
            core_w = min(core, width - left)
            tile = padded[..., top : top + core_h + 2 * HALO, left : left + core_w + 2 * HALO].to(device)
            values, _, qa = intervention_module.render_variants(model, tile, VARIANTS)
            if qa["full_reproduction_max_abs"] > 1e-7:
                raise RuntimeError(f"Full renderer reproduction mismatch: {qa}")
            for variant, value in values.items():
                result[variant][top : top + core_h, left : left + core_w] = value[0, 0, HALO : HALO + core_h, HALO : HALO + core_w].cpu().numpy()
    return {variant: np.round(np.clip(value, 0, 1) * 255.0).astype(np.uint8) for variant, value in result.items()}


def main() -> int:
    sys.path.insert(0, str(R109 / "model"))
    sys.path.insert(0, str(ROOT / "scripts" / "structure"))
    from r109_model import build_model
    import r109_interventions

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    payload = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = build_model().to(device).eval()
    model.load_state_dict(payload["model"])
    manifest: list[dict[str, object]] = []
    canonical_max_difference = 0
    parity: dict[str, object] = {}
    for suite, source_root in SOURCES.items():
        files = sorted(source_root.rglob("*.bmp"))
        if len(files) != 100:
            raise RuntimeError(f"{suite}: expected 100 files, found {len(files)}")
        for index, source_path in enumerate(files, 1):
            relative = source_path.relative_to(source_root)
            image = read_gray(source_path)
            outputs = tiled_variants(model, r109_interventions, image, device, CORE)
            if index == 1:
                alternate = tiled_variants(model, r109_interventions, image, device, 128)
                parity[suite] = {
                    variant: {
                        "max_gray_difference": int(np.max(np.abs(outputs[variant].astype(np.int16) - alternate[variant].astype(np.int16)))),
                        "mean_gray_difference": float(np.mean(np.abs(outputs[variant].astype(np.float32) - alternate[variant].astype(np.float32)))),
                    }
                    for variant in VARIANTS
                }
            canonical_path = CANONICAL[suite] / relative
            canonical = read_gray(canonical_path)
            canonical_difference = int(np.max(np.abs(outputs["full"].astype(np.int16) - canonical.astype(np.int16))))
            canonical_max_difference = max(canonical_max_difference, canonical_difference)
            for variant, output in outputs.items():
                destination = OUTPUT / suite / variant / relative
                write_gray(destination, output)
                manifest.append(
                    {
                        "suite": suite,
                        "family": relative.parent.name,
                        "filename": relative.name,
                        "variant": variant,
                        "source": str(source_path),
                        "output": str(destination),
                        "output_sha256": sha256(destination),
                        "full_vs_canonical_max_gray": canonical_difference if variant == "full" else None,
                    }
                )
            if index % 20 == 0 or index == len(files):
                print(json.dumps({"suite": suite, "done": index, "total": len(files)}), flush=True)

    table = OUTPUT / "output_manifest.csv"
    table.parent.mkdir(parents=True, exist_ok=True)
    with table.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest[0]))
        writer.writeheader()
        writer.writerows(manifest)
    state = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "checkpoint": str(CHECKPOINT),
        "checkpoint_sha256": sha256(CHECKPOINT),
        "device": str(device),
        "suites": {suite: 100 for suite in SOURCES},
        "variants": list(VARIANTS),
        "output_rows": len(manifest),
        "canonical_full_max_gray_difference": canonical_max_difference,
        "tile_grid_parity": parity,
    }
    (OUTPUT / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    if len(manifest) != 1000 or canonical_max_difference > 0 or any(
        item["max_gray_difference"] > 1 or item["mean_gray_difference"] > 0.001
        for suite in parity.values() for item in suite.values()
    ):
        raise RuntimeError(f"Intervention suite validation failed: {state}")
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
