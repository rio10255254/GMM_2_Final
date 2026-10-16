from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
RUN_ALL_PATH = ROOT / "scripts" / "run_all.py"


def load_probe_module():
    spec = importlib.util.spec_from_file_location("r105a_run_all", RUN_ALL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {RUN_ALL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_model(module, mode: str, device: torch.device):
    steps = int(module.CONFIG["training"]["steps"])
    checkpoint = torch.load(
        ROOT / "weights" / f"{mode}_step{steps:04d}.pth",
        map_location=device,
        weights_only=False,
    )
    model = module.ProbeModel(mode).to(device)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval()
    return model


def image_panel(array: np.ndarray, size: int, *, heat: bool = False) -> Image.Image:
    value = np.clip(array, 0.0, 1.0)
    if heat:
        rgb = np.stack([value, value * 0.20, np.zeros_like(value)], axis=-1)
    else:
        rgb = np.repeat(value[..., None], 3, axis=-1)
    image = Image.fromarray(np.round(rgb * 255.0).astype(np.uint8), mode="RGB")
    return image.resize((size, size), Image.Resampling.BICUBIC)


def main() -> int:
    module = load_probe_module()
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    population = module.build_population(int(module.CONFIG["data"]["test_samples"]), "test")
    residual = load_model(module, "residual", device)
    renderer = load_model(module, "renderer", device)
    outputs = module.predict_population(renderer, residual, population, device)

    summary = json.loads((ROOT / "results" / "summary.json").read_text(encoding="utf-8"))
    r_rows = summary["decomposition"]["full_learned_renderer"]["per_image"]
    b_rows = summary["decomposition"]["matched_residual"]["per_image"]
    family_indices: dict[str, list[int]] = {}
    for index, family in enumerate(population.families):
        family_indices.setdefault(family, []).append(index)

    selected: list[tuple[int, str]] = []
    family_stats = {}
    for family, indices in family_indices.items():
        delta = np.array(
            [r_rows[index]["boundary_distance_px"] - b_rows[index]["boundary_distance_px"] for index in indices],
            dtype=np.float64,
        )
        ordered = np.argsort(delta)
        picks = [
            (indices[int(ordered[len(ordered) // 2])], "median"),
            (indices[int(ordered[-1])], "renderer worst"),
            (indices[int(ordered[0])], "renderer best"),
        ]
        selected.extend(picks)
        family_stats[family] = {
            "images": len(indices),
            "renderer_minus_residual_boundary_median_px": float(np.median(delta)),
            "renderer_minus_residual_boundary_p95_px": float(np.percentile(delta, 95)),
            "renderer_boundary_better_fraction": float(np.mean(delta < 0.0)),
            "selected_indices": [index for index, _ in picks],
        }

    panel = 176
    gap = 12
    label_h = 34
    row_h = panel + 42
    columns = ["Source", "Target", "Residual", "Renderer", "Residual error x8", "Renderer error x8"]
    width = gap + len(columns) * (panel + gap)
    height = label_h + len(selected) * row_h + gap
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for column, label in enumerate(columns):
        draw.text((gap + column * (panel + gap), 10), label, fill="black", font=font)

    source = population.source.numpy()[:, 0]
    target = population.target.numpy()[:, 0]
    for row, (index, kind) in enumerate(selected):
        top = label_h + row * row_h
        residual_image = outputs["matched_residual"][index]
        renderer_image = outputs["full_learned_renderer"][index]
        arrays = [
            (source[index], False),
            (target[index], False),
            (residual_image, False),
            (renderer_image, False),
            (np.abs(residual_image - target[index]) * 8.0, True),
            (np.abs(renderer_image - target[index]) * 8.0, True),
        ]
        for column, (array, heat) in enumerate(arrays):
            canvas.paste(image_panel(array, panel, heat=heat), (gap + column * (panel + gap), top))
        rb = b_rows[index]["boundary_distance_px"]
        rr = r_rows[index]["boundary_distance_px"]
        label = f"{population.families[index]} | {kind} | sample {index} | boundary residual {rb:.3f}px, renderer {rr:.3f}px"
        draw.text((gap, top + panel + 8), label, fill="black", font=font)

    reports = ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    canvas.save(reports / "R105A_VISUAL_QA.png", optimize=True)
    (ROOT / "results" / "visual_qa_selection.json").write_text(
        json.dumps({"device": str(device), "family_stats": family_stats}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"status": "complete", "image": str(reports / "R105A_VISUAL_QA.png"), "family_stats": family_stats}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
