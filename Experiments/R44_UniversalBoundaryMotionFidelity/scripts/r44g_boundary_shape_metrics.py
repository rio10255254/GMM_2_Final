"""R44G boundary-shape scorecard.

This diagnostic reads existing R44 motion reconstruction images and scores
whether reconstructed boundaries keep the expected shape: density, component
fragmentation, straight-edge coverage, and corner retention.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity"
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import r44_motion_metrics  # noqa: E402


DEFAULT_PROFILE = "motion_val_unseen"
DEFAULT_DATA_ROOT = REPO_ROOT / "Training_Data" / "r44_universal_boundary_motion"
DEFAULT_RECON_ROOT = EXPERIMENT_ROOT / "results" / "motion_recon"
DEFAULT_OUTPUT_DIR = EXPERIMENT_ROOT / "results" / "diagnostics"
DEFAULT_VISUAL_DIR = EXPERIMENT_ROOT / "results" / "visual_samples"
DEFAULT_REPORT = EXPERIMENT_ROOT / "reports" / "R44G_BOUNDARY_SHAPE_METRICS.md"
TARGET_FAMILIES = {"large_regions", "mixed_fields"}

DEFAULT_MODELS: dict[str, str] = {
    "COMBO": "combo",
    "R39 a030": "r39_a030",
    "R40 a045": "r40_a045",
    "R41 direct": "r41_direct",
    "R42 best": "r42_best",
    "R44B from R42": "r44_motion_from_r42_best_e24",
    "R44B from COMBO": "r44_motion_from_combo_e24",
    "R44B from R40": "r44_motion_from_r40_a045_e24",
    "R44C static heavy": "r44c_static_heavy_all_motion",
    "R44E repair from R44B/R42": "r44e_region_mix_repair_from_r44b_r42",
    "R44E region prior from R41": "r44e_region_prior_from_r41",
    "R44E mixed prior from R44B/R40": "r44e_mixed_prior_from_r44b_r40",
    "R44H StepB region KD": "r44h_stepb_region_kd_main",
}

SHORT_MODEL_LABELS = {
    "COMBO": "COMBO",
    "R39 a030": "R39",
    "R40 a045": "R40",
    "R41 direct": "R41",
    "R42 best": "R42",
    "R44B from R42": "R44B42",
    "R44B from COMBO": "R44BC",
    "R44B from R40": "R44B40",
    "R44C static heavy": "R44C",
    "R44E repair from R44B/R42": "R44Efix",
    "R44E region prior from R41": "R44Er41",
    "R44E mixed prior from R44B/R40": "R44Er40",
    "R44H StepB region KD": "R44H-B",
}


def _as_bool(mask_or_img: np.ndarray) -> np.ndarray:
    arr = np.asarray(mask_or_img)
    if arr.dtype == bool:
        return arr
    return arr > 0


def _round4(value: float) -> float | None:
    return round(float(value), 4) if math.isfinite(float(value)) else None


def _mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return float(sum(vals) / len(vals)) if vals else float("nan")


def _safe_div(num: float, den: float, default: float = float("nan")) -> float:
    return float(num) / float(den) if float(den) > 0 else default


def _component_count(mask: np.ndarray, *, min_pixels: int = 2) -> int:
    binary = _as_bool(mask).astype(np.uint8)
    if int(binary.sum()) == 0:
        return 0
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA] if count > 1 else np.asarray([], dtype=np.int32)
    return int(np.count_nonzero(areas >= int(min_pixels)))


def _component_bboxes(mask: np.ndarray, *, min_pixels: int = 8, min_span: int = 8) -> list[tuple[int, int, int, int]]:
    binary = _as_bool(mask).astype(np.uint8)
    if int(binary.sum()) == 0:
        return []
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
    boxes: list[tuple[int, int, int, int]] = []
    for idx in range(1, count):
        area = int(stats[idx, cv2.CC_STAT_AREA])
        x = int(stats[idx, cv2.CC_STAT_LEFT])
        y = int(stats[idx, cv2.CC_STAT_TOP])
        w = int(stats[idx, cv2.CC_STAT_WIDTH])
        h = int(stats[idx, cv2.CC_STAT_HEIGHT])
        if area >= min_pixels and w >= min_span and h >= min_span:
            boxes.append((x, y, w, h))
    return boxes


def _edge_pixels_for_box(gt: np.ndarray, box: tuple[int, int, int, int], *, tolerance: int) -> np.ndarray:
    x, y, w, h = box
    yy, xx = np.nonzero(gt)
    if yy.size == 0:
        return np.zeros_like(gt, dtype=bool)
    x2 = x + w - 1
    y2 = y + h - 1
    in_box = (xx >= x) & (xx <= x2) & (yy >= y) & (yy <= y2)
    near_side = (
        (np.abs(xx - x) <= tolerance)
        | (np.abs(xx - x2) <= tolerance)
        | (np.abs(yy - y) <= tolerance)
        | (np.abs(yy - y2) <= tolerance)
    )
    out = np.zeros_like(gt, dtype=bool)
    out[yy[in_box & near_side], xx[in_box & near_side]] = True
    return out


def straight_edge_coverage(gt_boundary: np.ndarray, pred_boundary: np.ndarray, *, tolerance: int = 2) -> float:
    gt = _as_bool(gt_boundary)
    pred = _as_bool(pred_boundary)
    boxes = _component_bboxes(gt, min_pixels=16, min_span=10)
    if not boxes:
        return float("nan")
    kernel = np.ones((tolerance * 2 + 1, tolerance * 2 + 1), dtype=np.uint8)
    pred_near = cv2.dilate(pred.astype(np.uint8), kernel, iterations=1).astype(bool)
    expected = np.zeros_like(gt, dtype=bool)
    for box in boxes:
        expected |= _edge_pixels_for_box(gt, box, tolerance=tolerance)
    total = int(expected.sum())
    return _safe_div(int((expected & pred_near).sum()), total)


def corner_retention(gt_boundary: np.ndarray, pred_boundary: np.ndarray, *, radius: int = 3) -> float:
    gt = _as_bool(gt_boundary)
    pred = _as_bool(pred_boundary)
    boxes = _component_bboxes(gt, min_pixels=16, min_span=10)
    if not boxes:
        return float("nan")
    h, w = gt.shape[:2]
    expected = 0
    retained = 0
    for x, y, bw, bh in boxes:
        corners = ((x, y), (x + bw - 1, y), (x, y + bh - 1), (x + bw - 1, y + bh - 1))
        for cx, cy in corners:
            x0 = max(0, cx - radius)
            x1 = min(w, cx + radius + 1)
            y0 = max(0, cy - radius)
            y1 = min(h, cy + radius + 1)
            if not bool(gt[y0:y1, x0:x1].any()):
                continue
            expected += 1
            if bool(pred[y0:y1, x0:x1].any()):
                retained += 1
    return _safe_div(retained, expected)


def boundary_f_score(gt_boundary: np.ndarray, pred_boundary: np.ndarray, *, tolerance: int = 2) -> float:
    gt = _as_bool(gt_boundary)
    pred = _as_bool(pred_boundary)
    gt_px = int(gt.sum())
    pred_px = int(pred.sum())
    if gt_px == 0 and pred_px == 0:
        return 1.0
    if gt_px == 0 or pred_px == 0:
        return 0.0
    kernel = np.ones((tolerance * 2 + 1, tolerance * 2 + 1), dtype=np.uint8)
    gt_near = cv2.dilate(gt.astype(np.uint8), kernel, iterations=1).astype(bool)
    pred_near = cv2.dilate(pred.astype(np.uint8), kernel, iterations=1).astype(bool)
    precision = _safe_div(int((pred & gt_near).sum()), pred_px, default=0.0)
    recall = _safe_div(int((gt & pred_near).sum()), gt_px, default=0.0)
    if precision + recall <= 0:
        return 0.0
    return float(2.0 * precision * recall / (precision + recall))


def boundary_shape_metrics(
    gt_boundary: np.ndarray,
    pred_boundary: np.ndarray,
    *,
    tolerance: int = 2,
    corner_radius: int = 3,
) -> dict:
    gt = _as_bool(gt_boundary)
    pred = _as_bool(pred_boundary)
    gt_px = int(gt.sum())
    pred_px = int(pred.sum())
    gt_components = _component_count(gt)
    pred_components = _component_count(pred)
    density_ratio = _safe_div(pred_px, gt_px)
    fragmentation_ratio = _safe_div(pred_components, gt_components)
    f_score = boundary_f_score(gt, pred, tolerance=tolerance)
    edge_cov = straight_edge_coverage(gt, pred, tolerance=tolerance)
    corner = corner_retention(gt, pred, radius=corner_radius)

    if not math.isfinite(density_ratio) or density_ratio <= 0:
        density_penalty = 4.0
    else:
        density_penalty = min(4.0, abs(math.log(density_ratio)))
    if not math.isfinite(fragmentation_ratio) or fragmentation_ratio <= 0:
        fragmentation_penalty = 4.0
    else:
        fragmentation_penalty = min(4.0, abs(math.log(fragmentation_ratio)))
    edge_penalty = 0.0 if not math.isfinite(edge_cov) else 1.0 - edge_cov
    corner_penalty = 0.0 if not math.isfinite(corner) else 1.0 - corner
    f_penalty = 1.0 - f_score
    shape_error = (
        0.30 * density_penalty
        + 0.20 * fragmentation_penalty
        + 0.20 * edge_penalty
        + 0.15 * corner_penalty
        + 0.15 * f_penalty
    )
    return {
        "boundary_gt_px": gt_px,
        "boundary_pred_px": pred_px,
        "boundary_density_ratio": float(density_ratio),
        "gt_component_count": int(gt_components),
        "pred_component_count": int(pred_components),
        "fragmentation_ratio": float(fragmentation_ratio),
        "boundary_f_score": float(f_score),
        "straight_edge_coverage": float(edge_cov),
        "corner_retention": float(corner),
        "shape_error_score": float(shape_error),
    }


def _load_manifest(profile_dir: Path) -> dict:
    manifest_path = profile_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _latest_stage_output_cached(cache: dict[tuple[Path, str, str], Path], recon_root: Path, profile: str, stage: str) -> Path:
    key = (recon_root, profile, stage)
    if key not in cache:
        cache[key] = r44_motion_metrics._latest_stage_output(recon_root, profile, stage)
    return cache[key]


def _prediction_boundary(pred_img: np.ndarray, gt_boundary: np.ndarray) -> np.ndarray:
    gt_count = int(_as_bool(gt_boundary).sum())
    return r44_motion_metrics.matched_gradient_boundary(pred_img, target_count=gt_count)


def collect_shape_rows(
    *,
    profile: str = DEFAULT_PROFILE,
    data_root: Path = DEFAULT_DATA_ROOT,
    recon_root: Path = DEFAULT_RECON_ROOT,
    model_map: dict[str, str] | None = None,
    frame_limit: int | None = None,
) -> list[dict]:
    model_map = model_map or DEFAULT_MODELS
    profile_dir = data_root / profile
    manifest = _load_manifest(profile_dir)
    frames = list(manifest["frames"])
    if frame_limit is not None:
        frames = frames[: int(frame_limit)]
    rows: list[dict] = []
    stage_cache: dict[tuple[Path, str, str], Path] = {}
    for model, folder in model_map.items():
        model_root = recon_root / folder
        if not model_root.exists():
            continue
        for frame in frames:
            stage = str(frame["stage"])
            out_dir = _latest_stage_output_cached(stage_cache, model_root, profile, stage)
            pred_path = out_dir / Path(frame["package_lbl"]).name
            if not pred_path.exists():
                continue
            gt_boundary = r44_motion_metrics._read_gray(profile_dir / frame["package_boundary"])
            pred_img = r44_motion_metrics._read_gray(pred_path)
            pred_boundary = _prediction_boundary(pred_img, gt_boundary)
            metrics = boundary_shape_metrics(gt_boundary, pred_boundary)
            rows.append(
                {
                    "model": model,
                    "recon_folder": folder,
                    "stage": stage,
                    "feature_family": str(frame["feature_family"]),
                    "sequence_id": int(frame["sequence_id"]),
                    "frame_index": int(frame["frame_index"]),
                    **metrics,
                }
            )
    if not rows:
        raise FileNotFoundError(f"no reconstruction images found under {recon_root}")
    return rows


def summarize_rows(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["model"]), str(row["feature_family"]))].append(row)
    summary: list[dict] = []
    for (model, family), group in sorted(grouped.items()):
        summary.append(
            {
                "model": model,
                "feature_family": family,
                "case_count": len(group),
                "avg_shape_error_score": _mean(r["shape_error_score"] for r in group),
                "avg_boundary_f_score": _mean(r["boundary_f_score"] for r in group),
                "avg_density_ratio": _mean(r["boundary_density_ratio"] for r in group),
                "avg_fragmentation_ratio": _mean(r["fragmentation_ratio"] for r in group),
                "avg_straight_edge_coverage": _mean(r["straight_edge_coverage"] for r in group),
                "avg_corner_retention": _mean(r["corner_retention"] for r in group),
            }
        )
    return summary


def summarize_target_families(summary_rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in summary_rows:
        if row["feature_family"] in TARGET_FAMILIES:
            grouped[str(row["model"])].append(row)
    rows: list[dict] = []
    for model, group in sorted(grouped.items()):
        rows.append(
            {
                "model": model,
                "target_family_count": len(group),
                "target_shape_error_score": _mean(r["avg_shape_error_score"] for r in group),
                "target_boundary_f_score": _mean(r["avg_boundary_f_score"] for r in group),
                "target_density_ratio": _mean(r["avg_density_ratio"] for r in group),
                "target_fragmentation_ratio": _mean(r["avg_fragmentation_ratio"] for r in group),
                "target_straight_edge_coverage": _mean(r["avg_straight_edge_coverage"] for r in group),
                "target_corner_retention": _mean(r["avg_corner_retention"] for r in group),
            }
        )
    return sorted(rows, key=lambda r: float(r["target_shape_error_score"]))


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _json_safe(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _value_color(value: float, min_v: float, max_v: float) -> tuple[int, int, int]:
    if not math.isfinite(value):
        return (225, 225, 225)
    if max_v <= min_v:
        t = 0.0
    else:
        t = max(0.0, min(1.0, (value - min_v) / (max_v - min_v)))
    # Low error is green; high error is red.
    r = int(90 + 150 * t)
    g = int(190 - 120 * t)
    b = int(95 - 25 * t)
    return (r, g, b)


def write_heatmap(summary_rows: list[dict], path: Path) -> None:
    families = sorted({str(row["feature_family"]) for row in summary_rows})
    models = [model for model in DEFAULT_MODELS if any(row["model"] == model for row in summary_rows)]
    table = {(row["feature_family"], row["model"]): float(row["avg_shape_error_score"]) for row in summary_rows}
    values = [v for v in table.values() if math.isfinite(v)]
    min_v = min(values) if values else 0.0
    max_v = max(values) if values else 1.0
    cell_w = 84
    cell_h = 34
    left = 150
    top = 74
    width = left + cell_w * len(models) + 24
    height = top + cell_h * len(families) + 44
    img = Image.new("RGB", (width, height), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((16, 14), "R44G boundary shape error (lower is better)", fill=(20, 20, 20), font=font)
    for col, model in enumerate(models):
        label = SHORT_MODEL_LABELS.get(model, model[:8])
        draw.text((left + col * cell_w + 4, 48), label, fill=(20, 20, 20), font=font)
    for row_idx, family in enumerate(families):
        y = top + row_idx * cell_h
        draw.text((16, y + 10), family, fill=(20, 20, 20), font=font)
        for col, model in enumerate(models):
            x = left + col * cell_w
            value = table.get((family, model), float("nan"))
            draw.rectangle([x, y, x + cell_w - 2, y + cell_h - 2], fill=_value_color(value, min_v, max_v), outline=(245, 245, 245))
            label = "NA" if not math.isfinite(value) else f"{value:.3f}"
            draw.text((x + 8, y + 10), label, fill=(10, 10, 10), font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def _markdown_table(rows: list[dict], columns: list[tuple[str, str]], *, limit: int | None = None) -> str:
    use_rows = rows[:limit] if limit else rows
    lines = ["| " + " | ".join(label for label, _key in columns) + " |"]
    lines.append("|" + "|".join("---" for _ in columns) + "|")
    for row in use_rows:
        cells = []
        for _label, key in columns:
            value = row.get(key, "")
            if isinstance(value, float):
                cells.append("" if not math.isfinite(value) else f"{value:.4f}")
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_report(summary_rows: list[dict], target_rows: list[dict], report_path: Path, heatmap_path: Path) -> None:
    by_large = sorted(
        [row for row in summary_rows if row["feature_family"] == "large_regions"],
        key=lambda r: float(r["avg_shape_error_score"]),
    )
    by_mixed = sorted(
        [row for row in summary_rows if row["feature_family"] == "mixed_fields"],
        key=lambda r: float(r["avg_shape_error_score"]),
    )
    best_target = target_rows[0] if target_rows else {}
    lines = [
        "# R44G 邊界形狀體檢",
        "",
        "## 摘要",
        "",
        "- 本報告是 R44 內部診斷，不新增訓練、不新增候選權重。",
        "- 目的：把 R44F 肉眼看到的邊界問題拆成可比較欄位：邊界厚度、破碎度、直邊保留、角點保留。",
        "- 分數 `shape_error_score` 越低越好；它不是新的升級門檻，而是用來判斷下一步該修什麼。",
        "",
        "## 主要結論",
        "",
    ]
    if best_target:
        lines.append(
            f"- 大區塊與混合場景合併後，目前最低形狀錯誤是 `{best_target['model']}`，"
            f"分數 `{float(best_target['target_shape_error_score']):.4f}`。"
        )
    if by_large:
        lines.append(
            f"- 大區塊最低形狀錯誤：`{by_large[0]['model']}`，"
            f"`{float(by_large[0]['avg_shape_error_score']):.4f}`。"
        )
    if by_mixed:
        lines.append(
            f"- 混合場景最低形狀錯誤：`{by_mixed[0]['model']}`，"
            f"`{float(by_mixed[0]['avg_shape_error_score']):.4f}`。"
        )
    r44b_r42 = next((row for row in target_rows if row["model"] == "R44B from R42"), None)
    if r44b_r42:
        lines.append(
            f"- `R44B from R42` 仍是已知位移主候選，但在大區塊/混合場景合併形狀分數是 "
            f"`{float(r44b_r42['target_shape_error_score']):.4f}`，不是本表最強。"
        )
    lines.extend(
        [
            "- 這表示現成候選不是完全沒能力，而是能力分散：最佳位移、最佳大區塊形狀與最佳混合場景形狀不在同一個模型上。",
            "- 若模型在位移向量上已經接近正確，但這裡分數仍差，代表問題主要是重建出的邊界形狀不忠實，而不是整張圖沒有跟著位移。",
            "",
            "## 大區塊與混合場景總排名",
            "",
            _markdown_table(
                target_rows,
                [
                    ("模型", "model"),
                    ("形狀錯誤↓", "target_shape_error_score"),
                    ("邊界 F↑", "target_boundary_f_score"),
                    ("厚度比≈1", "target_density_ratio"),
                    ("破碎比≈1", "target_fragmentation_ratio"),
                    ("直邊保留↑", "target_straight_edge_coverage"),
                    ("角點保留↑", "target_corner_retention"),
                ],
            ),
            "",
            "## 大區塊排名",
            "",
            _markdown_table(
                by_large,
                [
                    ("模型", "model"),
                    ("形狀錯誤↓", "avg_shape_error_score"),
                    ("邊界 F↑", "avg_boundary_f_score"),
                    ("厚度比≈1", "avg_density_ratio"),
                    ("破碎比≈1", "avg_fragmentation_ratio"),
                    ("直邊保留↑", "avg_straight_edge_coverage"),
                    ("角點保留↑", "avg_corner_retention"),
                ],
            ),
            "",
            "## 混合場景排名",
            "",
            _markdown_table(
                by_mixed,
                [
                    ("模型", "model"),
                    ("形狀錯誤↓", "avg_shape_error_score"),
                    ("邊界 F↑", "avg_boundary_f_score"),
                    ("厚度比≈1", "avg_density_ratio"),
                    ("破碎比≈1", "avg_fragmentation_ratio"),
                    ("直邊保留↑", "avg_straight_edge_coverage"),
                    ("角點保留↑", "avg_corner_retention"),
                ],
            ),
            "",
            "## 代表圖",
            "",
            f"![R44G 邊界形狀錯誤熱圖]({heatmap_path.as_posix()})",
            "",
            "## 產物",
            "",
            "- `results/diagnostics/r44g_boundary_shape_rows.csv`：逐張影像形狀指標。",
            "- `results/diagnostics/r44g_boundary_shape_scorecard.csv`：各模型、各結構類型彙整。",
            "- `results/diagnostics/r44g_boundary_shape_target_rank.csv`：大區塊與混合場景合併排名。",
            "- `results/diagnostics/r44g_boundary_shape_scorecard.json`：同一份結果的機器可讀版本。",
            "- `results/visual_samples/r44g_boundary_shape_heatmap.png`：分族熱圖。",
            "",
            "## 下一步判斷",
            "",
            "- 如果最低分模型仍主要輸在厚度比和破碎比，下一步訓練應把邊界厚度與連通性當主目標。",
            "- 如果直邊保留和角點保留是主要破口，下一步應針對大區塊、平台狀區塊與混合場景加入直邊/角點忠實約束。",
            "- 這份體檢不替代外部 GMF；它回答的是顯微結構邊界本身是否重建得像。",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the R44G boundary-shape scorecard.")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--recon-root", type=Path, default=DEFAULT_RECON_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--visual-dir", type=Path, default=DEFAULT_VISUAL_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--frame-limit", type=int, default=None)
    args = parser.parse_args(argv)

    rows = collect_shape_rows(
        profile=args.profile,
        data_root=args.data_root,
        recon_root=args.recon_root,
        frame_limit=args.frame_limit,
    )
    summary_rows = summarize_rows(rows)
    target_rows = summarize_target_families(summary_rows)

    rows_csv = args.output_dir / "r44g_boundary_shape_rows.csv"
    score_csv = args.output_dir / "r44g_boundary_shape_scorecard.csv"
    target_csv = args.output_dir / "r44g_boundary_shape_target_rank.csv"
    score_json = args.output_dir / "r44g_boundary_shape_scorecard.json"
    heatmap = args.visual_dir / "r44g_boundary_shape_heatmap.png"

    write_csv(rows, rows_csv)
    write_csv(summary_rows, score_csv)
    write_csv(target_rows, target_csv)
    write_json(
        {
            "profile": args.profile,
            "row_count": len(rows),
            "scorecard": summary_rows,
            "target_rank": target_rows,
        },
        score_json,
    )
    write_heatmap(summary_rows, heatmap)
    write_report(summary_rows, target_rows, args.report, heatmap)

    print(
        json.dumps(
            _json_safe(
                {
                    "row_count": len(rows),
                    "target_rank_top3": target_rows[:3],
                    "scorecard_csv": str(score_csv),
                    "report": str(args.report),
                    "heatmap": str(heatmap),
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
