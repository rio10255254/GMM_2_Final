from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
R105B_ROOT = ROOT.parent / "R105B_EvidenceSetReconstructionFalsification"
R105B_SCRIPT = R105B_ROOT / "scripts" / "run_probe.py"
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
SOURCE = Path(CONFIG["source"])
RESULTS = ROOT / "results"
REPORTS = ROOT / "reports"
SCALE = 5


def load_r105b():
    spec = importlib.util.spec_from_file_location("r105b_real_exploratory", R105B_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(R105B_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_model(module, device):
    checkpoint = torch.load(
        R105B_ROOT / "weights" / "evidence_step0900.pth",
        map_location=device,
        weights_only=False,
    )
    model = module.EvidenceSetNet().to(device)
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval()
    return model


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return cv2.resize(image, (1024, 1024), interpolation=cv2.INTER_AREA).astype(np.float32)


def rough_center(image: np.ndarray) -> tuple[float, float]:
    background = cv2.GaussianBlur(image, (0, 0), 35.0, borderType=cv2.BORDER_REFLECT_101)
    positive = np.maximum(image - background - 2.0, 0.0)
    nonzero = positive[positive > 0]
    threshold = float(np.percentile(nonzero, 70)) if nonzero.size else 0.0
    weights = np.where(positive >= threshold, positive, 0.0)
    yy, xx = np.mgrid[: image.shape[0], : image.shape[1]].astype(np.float32)
    total = max(float(weights.sum()), 1e-9)
    return float((xx * weights).sum() / total), float((yy * weights).sum() / total)


def crop_for_model(image: np.ndarray, center: tuple[float, float]) -> np.ndarray:
    crop = cv2.getRectSubPix(image, (400, 400), center)
    return cv2.resize(crop, (96, 96), interpolation=cv2.INTER_AREA) / 255.0


def circle_fit(image: np.ndarray) -> dict[str, float]:
    value = image.astype(np.float32)
    smooth = cv2.GaussianBlur(value, (0, 0), 0.8, borderType=cv2.BORDER_REFLECT_101)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    gradient = np.sqrt(gx * gx + gy * gy)
    yy, xx = np.mgrid[: value.shape[0], : value.shape[1]].astype(np.float64)
    center_x = center_y = 48.0
    distance = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)
    annulus = (distance >= 17.0) & (distance <= 36.0)
    threshold = float(np.percentile(gradient[annulus], 65))
    selected = annulus & (gradient >= threshold)
    x, y = xx[selected], yy[selected]
    fitted_radius = 26.0
    for _ in range(4):
        design = np.stack([2.0 * x, 2.0 * y, np.ones_like(x)], axis=1)
        target = x * x + y * y
        fitted_x, fitted_y, constant = np.linalg.lstsq(design, target, rcond=None)[0]
        fitted_radius = float(np.sqrt(max(constant + fitted_x * fitted_x + fitted_y * fitted_y, 0.0)))
        residual = np.abs(np.sqrt((x - fitted_x) ** 2 + (y - fitted_y) ** 2) - fitted_radius)
        keep = residual < np.percentile(residual, 80)
        x, y = x[keep], y[keep]
    return {"center_x": float(fitted_x), "center_y": float(fitted_y), "radius": fitted_radius}


def edge_energy(image: np.ndarray) -> float:
    smooth = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 0.8, borderType=cv2.BORDER_REFLECT_101)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    return float(np.mean(np.sqrt(gx * gx + gy * gy)))


@torch.inference_mode()
def model_outputs(module, model, frames: np.ndarray, used: int, device) -> tuple[np.ndarray, np.ndarray]:
    tensor = torch.from_numpy(frames[None]).to(device=device, dtype=torch.float32)
    valid = module.make_valid(1, 4, used, device)
    details = model(tensor, valid)
    batch = {
        "raw": tensor,
        "illumination": torch.ones_like(tensor),
        "sigma_index": torch.full((1, 4), -1, device=device, dtype=torch.long),
        "dx": torch.zeros((1, 4), device=device),
        "dy": torch.zeros((1, 4), device=device),
        "exposure": torch.ones((1, 4), device=device),
    }
    evidence = module.physics_evidence(details["candidates"], batch, valid)
    return evidence["output"][0, 0].cpu().numpy(), evidence["uncertainty"][0, 0].cpu().numpy()


def make_preview(rows: list[dict], images: dict[int, dict[str, np.ndarray]]) -> None:
    indices = [0, 25, 50, 75, 99]
    columns = ["Reference raw", "Same-position N=2", "Cross-position N=4", "N=4 minus N=2 x8", "N=4 uncertainty x8"]
    panel, gap, label_height, row_height = 190, 10, 34, 230
    canvas = Image.new("RGB", (gap + len(columns) * (panel + gap), label_height + len(indices) * row_height + gap), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for column, label in enumerate(columns):
        draw.text((gap + column * (panel + gap), 10), label, fill="black", font=font)
    for row_number, index in enumerate(indices):
        item = images[index]
        values = [
            (item["reference"], False),
            (item["n2"], False),
            (item["n4"], False),
            (np.abs(item["n4"] - item["n2"]) * 8.0, True),
            (item["uncertainty"] * 8.0, True),
        ]
        top = label_height + row_number * row_height
        for column, (value, heat) in enumerate(values):
            clipped = np.clip(value, 0.0, 1.0)
            rgb = np.stack([clipped, clipped * 0.18, np.zeros_like(clipped)], axis=-1) if heat else np.repeat(clipped[..., None], 3, axis=-1)
            image = Image.fromarray(np.round(rgb * 255).astype(np.uint8), "RGB").resize((panel, panel), Image.Resampling.BICUBIC)
            canvas.paste(image, (gap + column * (panel + gap), top))
        record = rows[index]
        draw.text(
            (gap, top + panel + 8),
            f"bundle {index:03d} | N2 center {record['n2_center_shift_px']:.3f}px | N4 center {record['n4_center_shift_px']:.3f}px | N4-N2 {record['n4_minus_n2_mae_gray']:.3f} gray",
            fill="black",
            font=font,
        )
    canvas.save(REPORTS / "R105C_R105B_REAL_EXPLORATORY.png", optimize=True)


def main() -> int:
    module = load_r105b()
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model = load_model(module, device)
    files = sorted(SOURCE.glob("*.bmp"))
    registration = json.loads((RESULTS / "cross_position_manifest.json").read_text(encoding="utf-8"))
    rows = []
    preview_images: dict[int, dict[str, np.ndarray]] = {}
    for position in range(100):
        first = read_gray(files[2 * position])
        second = read_gray(files[2 * position + 1])
        next_first = read_gray(files[2 * (position + 1)])
        next_second = read_gray(files[2 * (position + 1) + 1])
        record = registration[position]
        warp = np.asarray(
            [
                [1.0, 0.0, record["content_shift_dx_px"] / SCALE],
                [0.0, 1.0, record["content_shift_dy_px"] / SCALE],
            ],
            dtype=np.float32,
        )
        next_first = cv2.warpAffine(next_first, warp, (1024, 1024), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT_101)
        next_second = cv2.warpAffine(next_second, warp, (1024, 1024), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT_101)
        reference_mean = 0.5 * (first + second)
        center = rough_center(reference_mean)
        frames = np.stack(
            [
                crop_for_model(first, center),
                crop_for_model(second, center),
                crop_for_model(next_first, center),
                crop_for_model(next_second, center),
            ]
        ).astype(np.float32)
        n1, _ = model_outputs(module, model, frames, 1, device)
        n2, _ = model_outputs(module, model, frames, 2, device)
        n4, uncertainty = model_outputs(module, model, frames, 4, device)
        reference = frames[0]
        geometry_reference = circle_fit(reference)
        geometry_n1 = circle_fit(n1)
        geometry_n2 = circle_fit(n2)
        geometry_n4 = circle_fit(n4)
        def center_shift(geometry):
            return float(np.hypot(geometry["center_x"] - geometry_reference["center_x"], geometry["center_y"] - geometry_reference["center_y"]))
        result = {
            "bundle_index": position,
            "n1_center_shift_px": center_shift(geometry_n1),
            "n2_center_shift_px": center_shift(geometry_n2),
            "n4_center_shift_px": center_shift(geometry_n4),
            "n1_radius_change_px": geometry_n1["radius"] - geometry_reference["radius"],
            "n2_radius_change_px": geometry_n2["radius"] - geometry_reference["radius"],
            "n4_radius_change_px": geometry_n4["radius"] - geometry_reference["radius"],
            "n1_edge_ratio": edge_energy(n1) / max(edge_energy(reference), 1e-9),
            "n2_edge_ratio": edge_energy(n2) / max(edge_energy(reference), 1e-9),
            "n4_edge_ratio": edge_energy(n4) / max(edge_energy(reference), 1e-9),
            "n2_minus_n1_mae_gray": float(np.mean(np.abs(n2 - n1)) * 255.0),
            "n4_minus_n2_mae_gray": float(np.mean(np.abs(n4 - n2)) * 255.0),
            "n4_uncertainty_gray": float(np.mean(uncertainty) * 255.0),
        }
        rows.append(result)
        if position in {0, 25, 50, 75, 99}:
            preview_images[position] = {
                "reference": reference,
                "n2": n2,
                "n4": n4,
                "uncertainty": uncertainty,
            }
        if position % 10 == 0 or position == 99:
            print(json.dumps({"stage": "real_exploratory", "bundle": position}), flush=True)

    metrics = [key for key in rows[0] if key != "bundle_index"]
    summary = {
        "status": "complete_exploratory",
        "bundles": len(rows),
        "warning": "R105B was trained only on procedural 96x96 data. Real blur, exposure and illumination parameters were not estimated; physics selection used identity nuisance settings. These outputs are not a model validation or delivery result.",
        "median": {key: float(np.median([row[key] for row in rows])) for key in metrics},
        "p95": {key: float(np.percentile([row[key] for row in rows], 95)) for key in metrics},
    }
    summary["decision"] = {
        "cross_position_changes_output": summary["median"]["n4_minus_n2_mae_gray"] > 0.02,
        "cross_position_center_not_worse_than_n2": summary["median"]["n4_center_shift_px"] <= summary["median"]["n2_center_shift_px"] + 0.05,
        "cross_position_edge_not_worse_than_n2": summary["median"]["n4_edge_ratio"] >= summary["median"]["n2_edge_ratio"] * 0.98,
        "eligible_for_real_model_adaptation": True,
        "eligible_for_external_gmf": False,
    }
    (RESULTS / "r105b_real_exploratory_manifest.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (RESULTS / "r105b_real_exploratory_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    make_preview(rows, preview_images)
    report = "\n".join(
        [
            "# R105C 使用 R105B 探針的真實跨位置探索",
            "",
            summary["warning"],
            "",
            f"- N=1 中心變化中位數：{summary['median']['n1_center_shift_px']:.4f} px",
            f"- N=2 中心變化中位數：{summary['median']['n2_center_shift_px']:.4f} px",
            f"- 跨位置 N=4 中心變化中位數：{summary['median']['n4_center_shift_px']:.4f} px",
            f"- N=2 邊緣比例中位數：{summary['median']['n2_edge_ratio']:.4f}",
            f"- 跨位置 N=4 邊緣比例中位數：{summary['median']['n4_edge_ratio']:.4f}",
            f"- N=4 相對 N=2 的平均變化：{summary['median']['n4_minus_n2_mae_gray']:.4f} 灰階",
            f"- N=4 不確定性中位數：{summary['median']['n4_uncertainty_gray']:.4f} 灰階",
            "",
            "## 判斷",
            "",
            json.dumps(summary["decision"], ensure_ascii=False, indent=2),
            "",
            "這只能確認跨位置四張能被現有概念探針讀取，以及輸出是否出現明顯幾何破壞；不能用來聲稱真實重建變準。",
        ]
    )
    (REPORTS / "R105C_R105B_REAL_EXPLORATORY_ZH.md").write_text(report, encoding="utf-8")
    print(json.dumps({"status": "complete", "decision": summary["decision"], "median": summary["median"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
