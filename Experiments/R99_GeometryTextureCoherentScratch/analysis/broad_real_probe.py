from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "R99_scratch_seed990053_20260814_105831"
WEIGHTS = ROOT / "weights" / "formal" / "seed_990053" / RUN_ID / "weights"
OUT = ROOT / "reports" / "deep_dive"
SETS = {
    "5x": Path(str(PROJECT_ROOT / 'Shared_Sources' / 'Real_Sample_Captures' / '20260704_5x')),
    "20x": Path(str(PROJECT_ROOT / 'Shared_Sources' / 'Real_Sample_Captures' / '20260704_20x')),
    "50x": Path(str(PROJECT_ROOT / 'Shared_Sources' / 'Real_Sample_Captures' / '20260702_100MG_位移_50x')),
}
EPOCHS = (24, 40)
CENTERS = ((448, 448), (448, 1600), (768, 1024), (1088, 448), (1088, 1600))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image.astype(np.float32) / 255.0


def summarize(rows: list[dict[str, float]]) -> dict[str, object]:
    result: dict[str, object] = {"count": len(rows)}
    for key in rows[0]:
        values = np.asarray([row[key] for row in rows], dtype=np.float64)
        result[key] = {
            "mean": float(values.mean()),
            "p10": float(np.percentile(values, 10)),
            "median": float(np.median(values)),
            "p90": float(np.percentile(values, 90)),
            "maximum": float(values.max()),
        }
    return result


def save_sheet(path: Path, raw: np.ndarray, e24: np.ndarray, e40: np.ndarray) -> None:
    panels = []
    for label, image in (("RAW", raw), ("E24", e24), ("E40", e40)):
        panel = np.rint(np.clip(image, 0, 1) * 255).astype(np.uint8)
        cv2.putText(panel, label, (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 255, 2, cv2.LINE_AA)
        panels.append(panel)
    if not cv2.imwrite(str(path), np.concatenate(panels, axis=1)):
        raise RuntimeError(path)


def main() -> int:
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model_module = load_module("r99_broad_model", ROOT / "model" / "r99_model.py")
    tools = load_module("r99_deep_tools", ROOT / "analysis" / "deep_dive_r99.py")
    selected: dict[str, list[tuple[str, np.ndarray]]] = {}
    for set_name, folder in SETS.items():
        files = sorted(path for path in folder.rglob("*") if path.suffix.lower() in {".bmp", ".png", ".tif", ".tiff", ".jpg", ".jpeg"})
        indices = np.linspace(0, len(files) - 1, 12, dtype=int)
        patches = []
        for file_index in indices:
            image = read_gray(files[int(file_index)])
            for center_y, center_x in CENTERS:
                patch = image[center_y - 448:center_y + 448, center_x - 448:center_x + 448]
                if patch.shape != (896, 896):
                    raise RuntimeError(f"Unexpected patch {patch.shape} from {files[int(file_index)]}")
                patch_id = f"{files[int(file_index)].parent.name}/{files[int(file_index)].name}@{center_y},{center_x}"
                patches.append((patch_id, patch))
        selected[set_name] = patches

    all_rows: dict[str, dict[str, list[dict[str, float]]]] = {str(epoch): {name: [] for name in SETS} for epoch in EPOCHS}
    cached_outputs: dict[str, dict[str, dict[str, np.ndarray]]] = {str(epoch): {name: {} for name in SETS} for epoch in EPOCHS}
    raw_cache: dict[str, dict[str, np.ndarray]] = {name: {} for name in SETS}

    for epoch in EPOCHS:
        checkpoint = torch.load(WEIGHTS / f"epoch_{epoch:03d}.pth.tar", map_location="cpu", weights_only=False)
        model = model_module.build_model().to(device).eval()
        model.load_state_dict(checkpoint["ema_state_dict"], strict=True)
        for set_name, patches in selected.items():
            for start in range(0, len(patches), 5):
                batch_rows = patches[start:start + 5]
                tensor = torch.from_numpy(np.stack([row[1] for row in batch_rows])).unsqueeze(1).to(device)
                with torch.inference_mode():
                    details = model(tensor, return_details=True)
                core = slice(192, 704)
                raw = tensor[..., core, core].float()
                output = details["output"][..., core, core].float()
                for local, (patch_id, _patch) in enumerate(batch_rows):
                    metrics = tools.stage_metrics(raw[local:local + 1], output[local:local + 1])
                    for component in ("low_delta", "transport_delta", "edge_delta", "detail_delta"):
                        metrics[f"{component}_mean_abs_gray"] = tools.component_metrics(details[component][local:local + 1, ..., core, core].float())["mean_abs_gray"]
                    all_rows[str(epoch)][set_name].append(metrics)
                    cached_outputs[str(epoch)][set_name][patch_id] = np.rint(output[local, 0].cpu().numpy() * 255).astype(np.uint8)
                    if epoch == EPOCHS[0]:
                        raw_cache[set_name][patch_id] = np.rint(raw[local, 0].cpu().numpy() * 255).astype(np.uint8)
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()

    report = {epoch: {name: summarize(rows) for name, rows in sets.items()} for epoch, sets in all_rows.items()}
    paired_change: dict[str, object] = {}
    for set_name in SETS:
        e24 = all_rows["24"][set_name]
        e40 = all_rows["40"][set_name]
        deltas = np.asarray([right["mean_abs_gray"] - left["mean_abs_gray"] for left, right in zip(e24, e40)])
        paired_change[set_name] = {
            "fraction_e40_more_intervention": float(np.mean(deltas > 0)),
            "median_added_change_gray": float(np.median(deltas)),
            "p90_added_change_gray": float(np.percentile(deltas, 90)),
        }
        worst = int(np.argmax([row["mean_abs_gray"] for row in e40]))
        patch_id = selected[set_name][worst][0]
        save_sheet(
            OUT / f"broad_probe_worst_{set_name}.png",
            raw_cache[set_name][patch_id].astype(np.float32) / 255.0,
            cached_outputs["24"][set_name][patch_id].astype(np.float32) / 255.0,
            cached_outputs["40"][set_name][patch_id].astype(np.float32) / 255.0,
        )
        paired_change[set_name]["worst_patch_id"] = patch_id
    payload = {"sampling": {"frames_per_set": 12, "patches_per_frame": 5, "patch_size": 896, "evaluated_core": 512}, "epochs": report, "paired_change": paired_change}
    (OUT / "broad_real_probe.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "report": str(OUT / "broad_real_probe.json"),
        "paired_change": paired_change,
        "mean_abs_gray": {epoch: {name: round(report[epoch][name]["mean_abs_gray"]["mean"], 3) for name in SETS} for epoch in report},
        "low_branch_gray": {epoch: {name: round(report[epoch][name]["low_delta_mean_abs_gray"]["mean"], 3) for name in SETS} for epoch in report},
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
