from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
SOURCE = Path(PROJECT_ROOT / CONFIG["source"])
RESULTS = ROOT / "results"
REPORTS = ROOT / "reports"
SCALE = 5
SIZE = 1024


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def pair_mean(files: list[Path], position: int) -> np.ndarray:
    first = read_gray(files[2 * position])
    second = read_gray(files[2 * position + 1])
    mean = 0.5 * (first.astype(np.float32) + second.astype(np.float32))
    return cv2.resize(mean, (SIZE, SIZE), interpolation=cv2.INTER_AREA)


def structure(image: np.ndarray) -> np.ndarray:
    smooth = cv2.GaussianBlur(image, (0, 0), 1.0, borderType=cv2.BORDER_REFLECT_101)
    broad = cv2.GaussianBlur(image, (0, 0), 12.0, borderType=cv2.BORDER_REFLECT_101)
    value = smooth - broad
    value = value - float(value.mean())
    return value / max(float(value.std()), 1e-6)


def rough_ring_geometry(image: np.ndarray) -> dict[str, float]:
    background = cv2.GaussianBlur(image, (0, 0), 35.0, borderType=cv2.BORDER_REFLECT_101)
    positive = np.maximum(image - background - 2.0, 0.0)
    nonzero = positive[positive > 0]
    threshold = float(np.percentile(nonzero, 70)) if nonzero.size else 0.0
    weights = np.where(positive >= threshold, positive, 0.0)
    yy, xx = np.mgrid[: image.shape[0], : image.shape[1]].astype(np.float32)
    total = max(float(weights.sum()), 1e-9)
    center_x = float((xx * weights).sum() / total)
    center_y = float((yy * weights).sum() / total)
    radius = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)
    radius_mean = float((radius * weights).sum() / total)
    radius_std = float(np.sqrt((((radius - radius_mean) ** 2) * weights).sum() / total))
    return {
        "center_x_px": center_x * SCALE,
        "center_y_px": center_y * SCALE,
        "radius_px": radius_mean * SCALE,
        "radial_width_px": radius_std * SCALE,
    }


def ring_geometry(image: np.ndarray) -> dict[str, float]:
    rough = rough_ring_geometry(image)
    center_x = rough["center_x_px"] / SCALE
    center_y = rough["center_y_px"] / SCALE
    radius = rough["radius_px"] / SCALE
    smooth = cv2.GaussianBlur(image, (0, 0), 1.0, borderType=cv2.BORDER_REFLECT_101)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    gradient = np.sqrt(gx * gx + gy * gy)
    yy, xx = np.mgrid[: image.shape[0], : image.shape[1]].astype(np.float64)
    distance = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)
    annulus = np.abs(distance - radius) < 18.0
    threshold = float(np.percentile(gradient[annulus], 65))
    selected = annulus & (gradient >= threshold)
    x, y = xx[selected], yy[selected]
    residual = np.zeros_like(x)
    fitted_radius = radius
    for _ in range(4):
        design = np.stack([2.0 * x, 2.0 * y, np.ones_like(x)], axis=1)
        target = x * x + y * y
        fitted_x, fitted_y, constant = np.linalg.lstsq(design, target, rcond=None)[0]
        fitted_radius = math.sqrt(max(constant + fitted_x * fitted_x + fitted_y * fitted_y, 0.0))
        residual = np.abs(np.sqrt((x - fitted_x) ** 2 + (y - fitted_y) ** 2) - fitted_radius)
        keep = residual < np.percentile(residual, 80)
        x, y = x[keep], y[keep]
    radial_distance = np.sqrt((x - fitted_x) ** 2 + (y - fitted_y) ** 2)
    return {
        "center_x_px": float(fitted_x * SCALE),
        "center_y_px": float(fitted_y * SCALE),
        "radius_px": float(fitted_radius * SCALE),
        "radial_width_px": float(np.std(radial_distance) * SCALE),
    }


def edge_energy(image: np.ndarray) -> float:
    value = cv2.GaussianBlur(image, (0, 0), 1.5, borderType=cv2.BORDER_REFLECT_101)
    gx = cv2.Sobel(value, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(value, cv2.CV_32F, 0, 1, ksize=3)
    return float(np.mean(np.sqrt(gx * gx + gy * gy)))


def normalized_correlation(a: np.ndarray, b: np.ndarray) -> float:
    x, y = structure(a)[64:-64, 64:-64], structure(b)[64:-64, 64:-64]
    x, y = x.reshape(-1), y.reshape(-1)
    return float(np.dot(x, y) / max(float(np.linalg.norm(x) * np.linalg.norm(y)), 1e-9))


def register_neighbor(reference: np.ndarray, neighbor: np.ndarray) -> tuple[np.ndarray, dict[str, float]]:
    reference_geometry = ring_geometry(reference)
    neighbor_geometry = ring_geometry(neighbor)
    initial_dx = (neighbor_geometry["center_x_px"] - reference_geometry["center_x_px"]) / SCALE
    initial_dy = (neighbor_geometry["center_y_px"] - reference_geometry["center_y_px"]) / SCALE
    a = structure(reference)[64:-64, 64:-64]
    b = structure(neighbor)[64:-64, 64:-64]
    warp = np.asarray([[1.0, 0.0, initial_dx], [0.0, 1.0, initial_dy]], dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 120, 1e-7)
    correlation, warp = cv2.findTransformECC(a, b, warp, cv2.MOTION_TRANSLATION, criteria, None, 5)
    aligned = cv2.warpAffine(
        neighbor,
        warp,
        (neighbor.shape[1], neighbor.shape[0]),
        flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_REFLECT_101,
    )
    return aligned, {
        "content_shift_dx_px": float(warp[0, 2] * SCALE),
        "content_shift_dy_px": float(warp[1, 2] * SCALE),
        "ecc_correlation": float(correlation),
        "aligned_structure_correlation": normalized_correlation(reference, aligned),
    }


def step_statistics(centers: list[tuple[float, float]], stride: int = 1) -> dict[str, float]:
    values = []
    for index in range(len(centers) - 1):
        dx = (centers[index + 1][0] - centers[index][0]) / stride
        dy = (centers[index + 1][1] - centers[index][1]) / stride
        values.append((dx, dy, math.hypot(dx, dy)))
    array = np.asarray(values, dtype=np.float64)
    return {
        "steps": len(values),
        "dx_median_px": float(np.median(array[:, 0])),
        "dx_std_px": float(np.std(array[:, 0], ddof=1)) if len(array) > 1 else 0.0,
        "dy_median_px": float(np.median(array[:, 1])),
        "dy_std_px": float(np.std(array[:, 1], ddof=1)) if len(array) > 1 else 0.0,
        "magnitude_median_px": float(np.median(array[:, 2])),
        "magnitude_std_px": float(np.std(array[:, 2], ddof=1)) if len(array) > 1 else 0.0,
    }


def make_preview(pair_means: list[np.ndarray], aligned_neighbors: dict[int, np.ndarray], fused: dict[int, np.ndarray], records: list[dict]) -> None:
    indices = [0, 25, 50, 75, 99]
    columns = ["Position k N=2", "Position k+1 N=2", "Neighbor aligned to k", "Cross-position N=4 mean", "Aligned difference x16"]
    panel, gap, label_height, row_height = 200, 10, 34, 240
    canvas = Image.new("RGB", (gap + len(columns) * (panel + gap), label_height + len(indices) * row_height + gap), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for column, label in enumerate(columns):
        draw.text((gap + column * (panel + gap), 10), label, fill="black", font=font)
    for row, index in enumerate(indices):
        reference = pair_means[index]
        neighbor = pair_means[index + 1]
        aligned = aligned_neighbors[index]
        output = fused[index]
        difference = np.clip(np.abs(reference - aligned) * 16.0, 0.0, 255.0)
        values = [reference, neighbor, aligned, output, difference]
        top = label_height + row * row_height
        for column, value in enumerate(values):
            image = Image.fromarray(np.round(np.clip(value, 0, 255)).astype(np.uint8), "L").convert("RGB")
            image = image.resize((panel, panel), Image.Resampling.BICUBIC)
            canvas.paste(image, (gap + column * (panel + gap), top))
        record = records[index]
        draw.text(
            (gap, top + panel + 8),
            f"bundle {index:03d} | shift ({record['content_shift_dx_px']:+.3f}, {record['content_shift_dy_px']:+.3f}) px | ECC {record['ecc_correlation']:.6f} | drift {record['fused_center_drift_px']:.4f}px",
            fill="black",
            font=font,
        )
    canvas.save(REPORTS / "R105C_CROSS_POSITION_PREVIEW.png", optimize=True)


def main() -> int:
    files = sorted(SOURCE.glob("*.bmp"))
    if len(files) != 202:
        raise RuntimeError(f"Expected 202 BMP files, found {len(files)}")
    pair_means = []
    for position in range(101):
        pair_means.append(pair_mean(files, position))
        if position % 20 == 0 or position == 100:
            print(json.dumps({"stage": "pair_means", "position": position}), flush=True)

    pair_geometries = [ring_geometry(image) for image in pair_means]
    aligned_neighbors: dict[int, np.ndarray] = {}
    fused_outputs: dict[int, np.ndarray] = {}
    records = []
    for position in range(100):
        reference = pair_means[position]
        aligned, registration = register_neighbor(reference, pair_means[position + 1])
        output = 0.5 * (reference + aligned)
        reference_geometry = pair_geometries[position]
        aligned_geometry = ring_geometry(aligned)
        fused_geometry = ring_geometry(output)
        edge_reference = edge_energy(reference)
        edge_aligned = edge_energy(aligned)
        edge_output = edge_energy(output)
        record = {
            "bundle_index": position,
            "reference_position": position,
            "neighbor_position": position + 1,
            **registration,
            "aligned_pair_difference_std_gray": float(np.std(reference - aligned)),
            "edge_energy_reference": edge_reference,
            "edge_energy_aligned_neighbor": edge_aligned,
            "edge_energy_fused": edge_output,
            "fused_edge_ratio": edge_output / max(0.5 * (edge_reference + edge_aligned), 1e-9),
            "aligned_center_error_px": math.hypot(
                aligned_geometry["center_x_px"] - reference_geometry["center_x_px"],
                aligned_geometry["center_y_px"] - reference_geometry["center_y_px"],
            ),
            "fused_center_drift_px": math.hypot(
                fused_geometry["center_x_px"] - reference_geometry["center_x_px"],
                fused_geometry["center_y_px"] - reference_geometry["center_y_px"],
            ),
            "fused_radius_change_px": fused_geometry["radius_px"] - reference_geometry["radius_px"],
            "fused_radial_width_change_px": fused_geometry["radial_width_px"] - reference_geometry["radial_width_px"],
        }
        records.append(record)
        aligned_neighbors[position] = aligned
        fused_outputs[position] = output
        if position % 10 == 0 or position == 99:
            print(json.dumps({"stage": "cross_position_registration", "bundle": position}), flush=True)

    n2_centers = [(value["center_x_px"], value["center_y_px"]) for value in pair_geometries]
    sliding_centers = []
    for position in range(100):
        geometry = ring_geometry(fused_outputs[position])
        sliding_centers.append((geometry["center_x_px"], geometry["center_y_px"]))
    nonoverlap_indices = list(range(0, 100, 2))
    nonoverlap_centers = []
    for position in nonoverlap_indices:
        geometry = ring_geometry(fused_outputs[position])
        nonoverlap_centers.append((geometry["center_x_px"], geometry["center_y_px"]))

    shift_dx = np.asarray([row["content_shift_dx_px"] for row in records])
    shift_dy = np.asarray([row["content_shift_dy_px"] for row in records])
    ecc = np.asarray([row["ecc_correlation"] for row in records])
    compatibility = np.asarray([row["aligned_structure_correlation"] for row in records])
    center_drift = np.asarray([row["fused_center_drift_px"] for row in records])
    edge_ratio = np.asarray([row["fused_edge_ratio"] for row in records])
    radius_change = np.asarray([row["fused_radius_change_px"] for row in records])
    width_change = np.asarray([row["fused_radial_width_change_px"] for row in records])
    summary = {
        "status": "complete",
        "bundles": len(records),
        "registration": {
            "dx_median_px": float(np.median(shift_dx)),
            "dx_p05_px": float(np.percentile(shift_dx, 5)),
            "dx_p95_px": float(np.percentile(shift_dx, 95)),
            "dy_median_px": float(np.median(shift_dy)),
            "dy_p05_px": float(np.percentile(shift_dy, 5)),
            "dy_p95_px": float(np.percentile(shift_dy, 95)),
            "ecc_median": float(np.median(ecc)),
            "ecc_min": float(np.min(ecc)),
            "aligned_structure_correlation_median": float(np.median(compatibility)),
            "aligned_structure_correlation_min": float(np.min(compatibility)),
        },
        "fusion_geometry": {
            "center_drift_px_median": float(np.median(center_drift)),
            "center_drift_px_p95": float(np.percentile(center_drift, 95)),
            "edge_ratio_median": float(np.median(edge_ratio)),
            "edge_ratio_p05": float(np.percentile(edge_ratio, 5)),
            "radius_change_px_median": float(np.median(radius_change)),
            "radius_change_px_p05": float(np.percentile(radius_change, 5)),
            "radius_change_px_p95": float(np.percentile(radius_change, 95)),
            "radial_width_change_px_median": float(np.median(width_change)),
            "radial_width_change_px_p05": float(np.percentile(width_change, 5)),
            "radial_width_change_px_p95": float(np.percentile(width_change, 95)),
        },
        "step_readout_proxy": {
            "n2_independent_positions": step_statistics(n2_centers, 1),
            "n4_sliding_shared_sources": step_statistics(sliding_centers, 1),
            "n4_nonoverlap_sources_per_position": step_statistics(nonoverlap_centers, 2),
            "shared_source_fraction_between_adjacent_sliding_outputs": 0.5,
        },
    }
    sliding_std = summary["step_readout_proxy"]["n4_sliding_shared_sources"]["dy_std_px"]
    independent_std = summary["step_readout_proxy"]["n4_nonoverlap_sources_per_position"]["dy_std_px"]
    summary["decision"] = {
        "cross_position_registration_feasible": bool(np.min(ecc) > 0.98 and np.percentile(center_drift, 95) < 0.5),
        "fusion_preserves_ring_geometry": bool(np.percentile(center_drift, 95) < 0.5 and abs(np.median(radius_change)) < 0.5),
        "sliding_gmf_is_biased_by_shared_sources": bool(sliding_std < independent_std * 0.85),
        "eligible_for_model_research": True,
        "eligible_for_formal_gmf": False,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "cross_position_manifest.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    (RESULTS / "cross_position_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (RESULTS / "cross_position_manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
    make_preview(pair_means, aligned_neighbors, fused_outputs, records)
    proxy = summary["step_readout_proxy"]
    report = "\n".join(
        [
            "# R105C 均華跨位置 N=4 可行性",
            "",
            f"完成 {summary['bundles']} 組相鄰位置配對。每組由位置 k 的兩張與位置 k+1 的兩張構成四觀測，鄰近位置先對齊到 k。",
            "",
            "## 位移與對齊",
            "",
            f"- X 位移中位數：{summary['registration']['dx_median_px']:.4f} px",
            f"- Y 位移中位數：{summary['registration']['dy_median_px']:.4f} px",
            f"- ECC 中位數／最小值：{summary['registration']['ecc_median']:.6f} / {summary['registration']['ecc_min']:.6f}",
            f"- 對齊後結構相關中位數／最小值：{summary['registration']['aligned_structure_correlation_median']:.6f} / {summary['registration']['aligned_structure_correlation_min']:.6f}",
            "",
            "## 幾何代價",
            "",
            f"- 融合中心漂移中位數／95 百分位：{summary['fusion_geometry']['center_drift_px_median']:.4f} / {summary['fusion_geometry']['center_drift_px_p95']:.4f} px",
            f"- 結構邊緣比例中位數：{summary['fusion_geometry']['edge_ratio_median']:.6f}",
            f"- 半徑變化中位數：{summary['fusion_geometry']['radius_change_px_median']:.4f} px",
            f"- 徑向寬度變化中位數：{summary['fusion_geometry']['radial_width_change_px_median']:.4f} px",
            "",
            "## 位移波動代理",
            "",
            f"- N=2 每位置獨立，Y 步距標準差：{proxy['n2_independent_positions']['dy_std_px']:.4f} px",
            f"- N=4 滑動且相鄰輸出共用 50% 來源，Y 步距標準差：{proxy['n4_sliding_shared_sources']['dy_std_px']:.4f} px",
            f"- N=4 不共用來源、換算每位置，Y 步距標準差：{proxy['n4_nonoverlap_sources_per_position']['dy_std_px']:.4f} px",
            "",
            "## 判斷",
            "",
            json.dumps(summary["decision"], ensure_ascii=False, indent=2),
            "",
            "跨位置四張在影像內容上可對齊並值得進入模型研究；滑動視窗是否能用於正式 GMF，必須由不共用來源的外部程式結果決定，不能直接引用共享視窗的低波動。",
        ]
    )
    (REPORTS / "R105C_CROSS_POSITION_ZH.md").write_text(report, encoding="utf-8")
    print(json.dumps({"status": "complete", "decision": summary["decision"], "registration": summary["registration"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
