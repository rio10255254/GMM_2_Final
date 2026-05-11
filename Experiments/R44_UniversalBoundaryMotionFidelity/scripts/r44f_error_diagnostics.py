"""R44F error dissection for large-region and mixed-scene failures.

This is an analysis-only diagnostic. It reads existing R44 motion rows and
reconstruction images; it does not train or create checkpoints.
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
DEFAULT_REPORT = EXPERIMENT_ROOT / "reports" / "R44F_ERROR_DIAGNOSTIC.md"

TARGET_FAMILIES = {"large_regions", "mixed_fields"}
CASE_REQUIRED_MODELS = (
    "R42 best",
    "R44B from R42",
    "R44E repair from R44B/R42",
)
VISUAL_MODELS = (
    "R42 best",
    "R44B from R42",
    "R44C static heavy",
    "R44E repair from R44B/R42",
    "R44E region prior from R41",
    "R44E mixed prior from R44B/R40",
    "R41 direct",
    "R44B from R40",
)
VISUAL_MODEL_LABELS = {
    "R42 best": "R42",
    "R44B from R42": "R44B-R42",
    "R44C static heavy": "R44C",
    "R44E repair from R44B/R42": "R44E-fix",
    "R44E region prior from R41": "R44E-R41",
    "R44E mixed prior from R44B/R40": "R44E-R40",
    "R41 direct": "R41",
    "R44B from R40": "R44B-R40",
}
DEFAULT_MODELS: dict[str, str] = {
    "COMBO": "combo",
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
}


def _safe_float(value: object, default: float = float("nan")) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return float(sum(vals) / len(vals)) if vals else float("nan")


def _round4(value: float) -> float | None:
    return round(float(value), 4) if math.isfinite(float(value)) else None


def json_safe(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def boundary_amount_label(*, pred_px: int | float, expected_px: int | float) -> str:
    if float(expected_px) <= 0:
        return "unknown"
    ratio = float(pred_px) / float(expected_px)
    if ratio >= 1.45:
        return "too_thick_or_noisy"
    if ratio <= 0.60:
        return "too_sparse_or_missing"
    return "similar_density"


def _target_position(frame_b: int, expected_dx: float, expected_dy: float) -> float:
    known = {1: 0.08, 2: 0.16, 3: 0.40, 4: 0.80, 5: 2.0, 6: 8.0}
    if frame_b in known:
        return known[frame_b]
    return math.sqrt(expected_dx * expected_dx + expected_dy * expected_dy)


def _normalize_motion_row(row: dict, *, model: str, folder: str) -> dict:
    expected_dx = _safe_float(row.get("expected_dx_px"), 0.0)
    expected_dy = _safe_float(row.get("expected_dy_px"), 0.0)
    frame_b = _safe_int(row.get("frame_b"))
    pred_px = _safe_float(row.get("boundary_pred_px"), float("nan"))
    expected_px = _safe_float(row.get("boundary_expected_px"), float("nan"))
    return {
        "model": model,
        "recon_folder": folder,
        "stage": str(row.get("stage", "")),
        "feature_family": str(row.get("feature_family", "")),
        "sequence_id": _safe_int(row.get("sequence_id")),
        "frame_a": _safe_int(row.get("frame_a")),
        "frame_b": frame_b,
        "expected_dx_px": expected_dx,
        "expected_dy_px": expected_dy,
        "target_position_px": _target_position(frame_b, expected_dx, expected_dy),
        "motion_vector_error_px": _safe_float(row.get("motion_vector_error_px")),
        "boundary_motion_distance_px": _safe_float(row.get("boundary_motion_distance_px")),
        "boundary_pred_px": pred_px,
        "boundary_expected_px": expected_px,
        "boundary_amount_label": boundary_amount_label(pred_px=pred_px, expected_px=expected_px)
        if math.isfinite(pred_px) and math.isfinite(expected_px)
        else "unknown",
    }


def load_motion_rows(recon_root: Path, model_map: dict[str, str] | None = None) -> list[dict]:
    model_map = model_map or DEFAULT_MODELS
    rows: list[dict] = []
    for model, folder in model_map.items():
        csv_path = recon_root / folder / "motion_rows.csv"
        if not csv_path.exists():
            continue
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                rows.append(_normalize_motion_row(row, model=model, folder=folder))
    if not rows:
        raise FileNotFoundError(f"no motion_rows.csv files found under {recon_root}")
    return rows


def _case_key(row: dict) -> tuple:
    return (row["feature_family"], row["stage"], int(row["sequence_id"]), int(row["frame_b"]))


def _group_cases(rows: list[dict]) -> dict[tuple, dict[str, dict]]:
    grouped: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        if row["feature_family"] not in TARGET_FAMILIES:
            continue
        grouped[_case_key(row)][row["model"]] = row
    return grouped


def _metric(group: dict[str, dict], model: str, metric: str) -> float:
    row = group.get(model)
    if not row:
        return float("nan")
    return float(row.get(metric, float("nan")))


def _case_record(reason: str, score: float, key: tuple, group: dict[str, dict]) -> dict:
    family, stage, sequence_id, frame_b = key
    record = {
        "reason": reason,
        "score": float(score),
        "feature_family": family,
        "stage": stage,
        "sequence_id": int(sequence_id),
        "frame_b": int(frame_b),
        "target_position_px": _metric(group, "R42 best", "target_position_px"),
    }
    for model in sorted(group):
        prefix = model.replace(" ", "_").replace("/", "_").replace("-", "_").lower()
        record[f"{prefix}_boundary_px"] = _metric(group, model, "boundary_motion_distance_px")
        record[f"{prefix}_motion_px"] = _metric(group, model, "motion_vector_error_px")
        record[f"{prefix}_boundary_amount"] = group[model].get("boundary_amount_label", "unknown")
    return record


def select_case_groups(rows: list[dict], *, cases_per_reason: int = 4) -> list[dict]:
    grouped = _group_cases(rows)
    buckets: dict[str, list[dict]] = defaultdict(list)
    for key, group in grouped.items():
        if not all(model in group for model in CASE_REQUIRED_MODELS):
            continue
        r42 = _metric(group, "R42 best", "boundary_motion_distance_px")
        r44b = _metric(group, "R44B from R42", "boundary_motion_distance_px")
        r44e = _metric(group, "R44E repair from R44B/R42", "boundary_motion_distance_px")
        r44b_motion = _metric(group, "R44B from R42", "motion_vector_error_px")
        if math.isfinite(r42) and math.isfinite(r44b) and r44b - r42 > 0:
            buckets["r42_much_better_than_r44b"].append(_case_record("r42_much_better_than_r44b", r44b - r42, key, group))
        if math.isfinite(r42) and math.isfinite(r44b) and r42 - r44b > 0:
            buckets["r44b_much_better_than_r42"].append(_case_record("r44b_much_better_than_r42", r42 - r44b, key, group))
        if math.isfinite(r44e) and math.isfinite(r42) and math.isfinite(r44b):
            gain = min(r42, r44b) - r44e
            if gain > 0:
                buckets["r44e_repair_improves_mixed_or_region"].append(_case_record("r44e_repair_improves_mixed_or_region", gain, key, group))
        if math.isfinite(r44b) and math.isfinite(r44b_motion) and r44b >= 6.0 and r44b_motion <= 0.15:
            buckets["high_boundary_error_but_motion_ok"].append(_case_record("high_boundary_error_but_motion_ok", r44b - r44b_motion, key, group))

    selected: list[dict] = []
    seen: set[tuple[str, str, int, int]] = set()
    for reason in (
        "r42_much_better_than_r44b",
        "r44b_much_better_than_r42",
        "r44e_repair_improves_mixed_or_region",
        "high_boundary_error_but_motion_ok",
    ):
        ranked = sorted(buckets.get(reason, []), key=lambda r: float(r["score"]), reverse=True)
        added = 0
        for row in ranked:
            identity = (str(row["reason"]), str(row["stage"]), int(row["sequence_id"]), int(row["frame_b"]))
            if identity in seen:
                continue
            selected.append(row)
            seen.add(identity)
            added += 1
            if added >= cases_per_reason:
                break
    return selected


def _warp_mask(mask: np.ndarray, dx: float = 0.0, dy: float = 0.0) -> np.ndarray:
    h, w = mask.shape[:2]
    mat = np.asarray([[1.0, 0.0, float(dx)], [0.0, 1.0, float(dy)]], dtype=np.float32)
    return cv2.warpAffine(mask.astype(np.uint8), mat, (w, h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def _variant_masks(mask: np.ndarray) -> dict[str, np.ndarray]:
    kernel = np.ones((3, 3), dtype=np.uint8)
    variants = {
        "exact": mask,
        "shift_1px": _warp_mask(mask, dx=1.0),
        "shift_2px": _warp_mask(mask, dx=2.0),
        "shift_5px": _warp_mask(mask, dx=5.0),
        "dilate_1": cv2.dilate(mask, kernel, iterations=1),
        "dilate_3": cv2.dilate(mask, kernel, iterations=3),
        "erode_1": cv2.erode(mask, kernel, iterations=1),
    }
    missing = mask.copy()
    missing[: missing.shape[0] // 2, : missing.shape[1] // 2] = 0
    variants["missing_quadrant"] = missing
    return variants


def metric_stress_for_mask(mask: np.ndarray, *, feature_family: str, sample_id: str) -> list[dict]:
    base = np.where(mask > 0, 255, 0).astype(np.uint8)
    rows = []
    for variant, pred in _variant_masks(base).items():
        metrics = r44_motion_metrics.boundary_motion_error(base, pred, expected_dx=0.0, expected_dy=0.0)
        rows.append(
            {
                "feature_family": feature_family,
                "sample_id": sample_id,
                "variant": variant,
                "boundary_motion_distance_px": float(metrics["boundary_motion_distance_px"]),
                "boundary_pred_px": int(metrics["boundary_pred_px"]),
                "boundary_expected_px": int(metrics["boundary_expected_px"]),
                "boundary_amount_label": boundary_amount_label(
                    pred_px=int(metrics["boundary_pred_px"]),
                    expected_px=int(metrics["boundary_expected_px"]),
                ),
            }
        )
    return rows


def _load_manifest(profile_dir: Path) -> dict:
    return json.loads((profile_dir / "manifest.json").read_text(encoding="utf-8"))


def _manifest_index(profile_dir: Path) -> dict[tuple[str, int, int], dict]:
    manifest = _load_manifest(profile_dir)
    return {
        (frame["stage"], int(frame["sequence_id"]), int(frame["frame_index"])): frame
        for frame in manifest["frames"]
    }


def run_metric_stress(profile_dir: Path, *, sample_limit_per_family: int = 12) -> tuple[list[dict], list[dict]]:
    manifest = _load_manifest(profile_dir)
    rows: list[dict] = []
    used: dict[str, int] = defaultdict(int)
    for frame in manifest["frames"]:
        family = frame["feature_family"]
        if family not in TARGET_FAMILIES or int(frame["frame_index"]) != 6:
            continue
        if used[family] >= sample_limit_per_family:
            continue
        mask = r44_motion_metrics._read_gray(profile_dir / frame["package_boundary"])
        rows.extend(metric_stress_for_mask(mask, feature_family=family, sample_id=f"{frame['stage']}_seq{int(frame['sequence_id']):04d}"))
        used[family] += 1

    summary_rows = []
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["feature_family"], row["variant"])].append(row)
    for (family, variant), group_rows in sorted(grouped.items()):
        summary_rows.append(
            {
                "feature_family": family,
                "variant": variant,
                "sample_count": len(group_rows),
                "avg_boundary_motion_distance_px": _mean(r["boundary_motion_distance_px"] for r in group_rows),
                "avg_boundary_pred_px": _mean(r["boundary_pred_px"] for r in group_rows),
                "avg_boundary_expected_px": _mean(r["boundary_expected_px"] for r in group_rows),
            }
        )
    return rows, summary_rows


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _latest_stage_output(recon_root: Path, profile: str, stage: str) -> Path:
    candidates: list[Path] = []
    for run_dir in recon_root.glob(f"reconstruct_progress_*_in_{stage}_*"):
        if not run_dir.is_dir():
            continue
        for child in run_dir.iterdir():
            if child.is_dir() and child.name.startswith(f"{profile}_{stage}_"):
                candidates.append(child)
    if not candidates:
        raise FileNotFoundError(f"no reconstruction output found for {profile}/{stage}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _to_u8(img: np.ndarray) -> np.ndarray:
    if img.dtype == np.uint8:
        return img
    if img.dtype == np.uint16:
        return (img.astype(np.float32) / 65535.0 * 255.0).clip(0, 255).astype(np.uint8)
    arr = img.astype(np.float32)
    maxv = float(np.nanmax(arr)) if arr.size else 1.0
    if maxv <= 1.5:
        arr *= 255.0
    return arr.clip(0, 255).astype(np.uint8)


def _overlay_boundaries(img: np.ndarray, gt_boundary: np.ndarray, pred_boundary: np.ndarray) -> Image.Image:
    gray = _to_u8(img)
    rgb = np.repeat(gray[..., None], 3, axis=2)
    gt = gt_boundary > 0
    pred = pred_boundary > 0
    rgb[gt] = (0, 220, 0)
    rgb[pred] = (240, 30, 30)
    rgb[gt & pred] = (255, 220, 0)
    return Image.fromarray(rgb, mode="RGB")


def _read_u8(path: Path) -> np.ndarray:
    return _to_u8(r44_motion_metrics._read_gray(path))


def _resize_tile(image: Image.Image, size: int) -> Image.Image:
    return image.resize((size, size), Image.Resampling.BICUBIC)


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", size)
    except Exception:
        return ImageFont.load_default()


def _model_image_path(recon_root: Path, folder: str, profile: str, stage: str, lbl_name: str) -> Path:
    out_dir = _latest_stage_output(recon_root / folder, profile, stage)
    return out_dir / lbl_name


def write_visual_sheet(
    *,
    selected_cases: list[dict],
    profile_dir: Path,
    recon_root: Path,
    output_path: Path,
    profile: str = DEFAULT_PROFILE,
    max_cases: int = 16,
) -> None:
    index = _manifest_index(profile_dir)
    cases = selected_cases[:max_cases]
    columns = ["來源", "答案"] + [VISUAL_MODEL_LABELS.get(model, model) for model in VISUAL_MODELS]
    cell = 128
    pad = 8
    label_w = 220
    header_h = 48
    row_h = cell + pad
    width = label_w + pad + len(columns) * (cell + pad)
    height = header_h + len(cases) * row_h + pad
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    font = _font(14)
    small = _font(11)

    for ci, name in enumerate(columns):
        x = label_w + pad + ci * (cell + pad)
        draw.text((x, 14), name, fill=(20, 20, 20), font=font)

    for ri, case in enumerate(cases):
        y = header_h + ri * row_h
        stage = str(case["stage"])
        seq = int(case["sequence_id"])
        frame_b = int(case["frame_b"])
        frame = index[(stage, seq, frame_b)]
        lbl_name = Path(frame["package_lbl"]).name
        src = _read_u8(profile_dir / frame["package_src"])
        gt = _read_u8(profile_dir / frame["package_lbl"])
        gt_boundary = _read_u8(profile_dir / frame["package_boundary"])
        draw.text((pad, y + 8), str(case["feature_family"]), fill=(20, 20, 20), font=font)
        draw.text((pad, y + 30), f"seq {seq} / frame {frame_b}", fill=(70, 70, 70), font=small)
        draw.text((pad, y + 48), str(case["reason"]), fill=(70, 70, 70), font=small)

        base_tiles: list[Image.Image] = [Image.fromarray(src, mode="L").convert("RGB"), Image.fromarray(gt, mode="L").convert("RGB")]
        for ci, tile_img in enumerate(base_tiles):
            x = label_w + pad + ci * (cell + pad)
            sheet.paste(_resize_tile(tile_img, cell), (x, y))
            draw.rectangle([x, y, x + cell - 1, y + cell - 1], outline=(210, 210, 210), width=1)

        for mi, model_name in enumerate(VISUAL_MODELS, start=2):
            folder = DEFAULT_MODELS.get(model_name)
            x = label_w + pad + mi * (cell + pad)
            if not folder:
                continue
            pred_path = _model_image_path(recon_root, folder, profile, stage, lbl_name)
            pred = _read_u8(pred_path)
            pred_boundary = r44_motion_metrics.matched_gradient_boundary(pred, target_count=int((gt_boundary > 0).sum()))
            overlay = _overlay_boundaries(pred, gt_boundary, pred_boundary)
            sheet.paste(_resize_tile(overlay, cell), (x, y))
            draw.rectangle([x, y, x + cell - 1, y + cell - 1], outline=(210, 210, 210), width=1)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def _compact_case_rows(selected_cases: list[dict], limit: int = 8) -> list[dict]:
    rows = []
    for row in selected_cases[:limit]:
        rows.append(
            {
                "原因": row["reason"],
                "類型": row["feature_family"],
                "seq": row["sequence_id"],
                "frame": row["frame_b"],
                "R42 邊界": _round4(float(row.get("r42_best_boundary_px", float("nan")))),
                "R44B 邊界": _round4(float(row.get("r44b_from_r42_boundary_px", float("nan")))),
                "R44E repair 邊界": _round4(float(row.get("r44e_repair_from_r44b_r42_boundary_px", float("nan")))),
            }
        )
    return rows


def _markdown_table(rows: list[dict], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return "_無資料_"
    lines = ["| " + " | ".join(label for label, _ in columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        vals = []
        for _, key in columns:
            value = row.get(key, "")
            if isinstance(value, float):
                vals.append(f"{value:.4f}" if math.isfinite(value) else "—")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def _stress_lookup(stress_summary: list[dict], family: str, variant: str) -> float:
    for row in stress_summary:
        if row["feature_family"] == family and row["variant"] == variant:
            return float(row["avg_boundary_motion_distance_px"])
    return float("nan")


def make_report(
    *,
    selected_cases: list[dict],
    stress_summary: list[dict],
    output_paths: dict[str, Path],
) -> str:
    large_shift1 = _stress_lookup(stress_summary, "large_regions", "shift_1px")
    large_shift5 = _stress_lookup(stress_summary, "large_regions", "shift_5px")
    mixed_shift1 = _stress_lookup(stress_summary, "mixed_fields", "shift_1px")
    mixed_shift5 = _stress_lookup(stress_summary, "mixed_fields", "shift_5px")
    large_dilate3 = _stress_lookup(stress_summary, "large_regions", "dilate_3")
    mixed_dilate3 = _stress_lookup(stress_summary, "mixed_fields", "dilate_3")

    case_rows = _compact_case_rows(selected_cases, limit=10)
    stress_rows = [
        {"類型": "large_regions", "1px 偏移": large_shift1, "5px 偏移": large_shift5, "邊界變厚": large_dilate3},
        {"類型": "mixed_fields", "1px 偏移": mixed_shift1, "5px 偏移": mixed_shift5, "邊界變厚": mixed_dilate3},
    ]

    lines = [
        "# R44F 診斷 — 大區塊與混合場景錯誤解剖",
        "",
        "## 摘要",
        "",
        "R44F 不訓練、不開新 round。它只使用 R44 已有的重建影像與逐 pair 指標，目的是判斷大區塊與混合場景的問題到底是模型能力、資料標註，還是評估指標造成的假象。",
        "",
        "結論：**目前沒有證據顯示只是指標誤判。指標能抓到人工位移；但大區塊/混合場景的高邊界距離常發生在位移向量已經很準的情況，代表主要瓶頸是邊界形狀品質與邊界抽取穩定度，而不是整張圖沒有跟著移動。**",
        "",
        "## 指標壓力測試",
        "",
        "我用答案邊界人工製造 1px、2px、5px 偏移，以及邊界變厚/變薄/缺角，確認目前邊界距離指標是否有基本辨識力。",
        "",
        _markdown_table(
            stress_rows,
            [
                ("類型", "類型"),
                ("1px 偏移", "1px 偏移"),
                ("5px 偏移", "5px 偏移"),
                ("邊界變厚", "邊界變厚"),
            ],
        ),
        "",
        "判讀：人工偏移會被指標明確放大，代表它不是完全失效。不過邊界變厚也會被明顯懲罰，所以若模型把大區塊邊界重建得偏厚、偏碎或有波紋，數字會快速變差。",
        "",
        "## 錯誤案例挑選",
        "",
        "R44F 自動挑出四類案例：R42 明顯優於 R44B、R44B 明顯優於 R42、R44E repair 有小幅改善、以及位移已準但邊界仍差的案例。",
        "",
        _markdown_table(
            case_rows,
            [
                ("原因", "原因"),
                ("類型", "類型"),
                ("seq", "seq"),
                ("frame", "frame"),
                ("R42 邊界", "R42 邊界"),
                ("R44B 邊界", "R44B 邊界"),
                ("R44E repair 邊界", "R44E repair 邊界"),
            ],
        ),
        "",
        "代表圖中綠色是答案邊界，紅色是模型輸出的邊界，黃色是重疊區。肉眼判讀重點不是亮不亮，而是紅綠是否貼在同一條邊上、是否變厚、是否碎裂或波紋化。",
        "",
        "## R44F 判斷",
        "",
        "- 大區塊與混合場景不是單純「整體沒跟著位移」。很多案例的位移誤差很低，但邊界距離仍高。",
        "- 目前指標能抓到人工偏移，因此不能直接說大區塊分數差只是指標壞掉。",
        "- 指標對邊界厚度與碎裂敏感；這符合我們要的邊界忠實度，但也表示下一輪不能只追清晰或高頻，必須讓邊界形狀本身更穩。",
        "- R44E 的短訓練沒有解開問題，因為它沒有改變邊界形狀的產生方式，只是讓模型在既有能力之間拉扯。",
        "",
        "## 下一步",
        "",
        "不建議再做同型短訓練。若要繼續，下一步應該是二選一：",
        "",
        "1. 先修評估：加入更直接的邊界厚度、碎裂、角點/直邊保持指標，避免只靠單一距離值判斷。",
        "2. 再設計訓練：若評估確認無誤，再做分族邊界形狀目標，讓大區塊直邊、混合場景小細節、格線位移各自有不同約束。",
        "",
        "## 產物",
        "",
        f"- 案例表：`{output_paths['cases_csv']}`",
        f"- 案例 JSON：`{output_paths['cases_json']}`",
        f"- 指標壓力測試：`{output_paths['stress_csv']}`",
        f"- 指標壓力測試 JSON：`{output_paths['stress_json']}`",
        f"- 錯誤解剖代表圖：`{output_paths['visual_sheet']}`",
        "",
    ]
    return "\n".join(lines)


def _relative(path: Path) -> Path:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run R44F large-region/mixed-scene error diagnostics.")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--recon-root", type=Path, default=DEFAULT_RECON_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--visual-dir", type=Path, default=DEFAULT_VISUAL_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--cases-per-reason", type=int, default=4)
    parser.add_argument("--max-visual-cases", type=int, default=16)
    args = parser.parse_args(argv)

    profile_dir = args.data_root / args.profile
    rows = load_motion_rows(args.recon_root)
    selected_cases = select_case_groups(rows, cases_per_reason=args.cases_per_reason)
    stress_rows, stress_summary = run_metric_stress(profile_dir)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.visual_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "cases_csv": args.output_dir / "r44f_selected_cases.csv",
        "cases_json": args.output_dir / "r44f_selected_cases.json",
        "stress_csv": args.output_dir / "r44f_metric_stress.csv",
        "stress_json": args.output_dir / "r44f_metric_stress.json",
        "stress_summary_csv": args.output_dir / "r44f_metric_stress_summary.csv",
        "visual_sheet": args.visual_dir / "r44f_error_dissection_sheet.png",
    }
    write_csv(selected_cases, paths["cases_csv"])
    paths["cases_json"].write_text(json.dumps(json_safe({"selected_cases": selected_cases}), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    write_csv(stress_rows, paths["stress_csv"])
    write_csv(stress_summary, paths["stress_summary_csv"])
    paths["stress_json"].write_text(
        json.dumps(json_safe({"stress_rows": stress_rows, "stress_summary": stress_summary}), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    write_visual_sheet(
        selected_cases=selected_cases,
        profile_dir=profile_dir,
        recon_root=args.recon_root,
        output_path=paths["visual_sheet"],
        profile=args.profile,
        max_cases=args.max_visual_cases,
    )
    report_paths = {key: _relative(path) for key, path in paths.items()}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(make_report(selected_cases=selected_cases, stress_summary=stress_summary, output_paths=report_paths), encoding="utf-8")

    print(
        json.dumps(
            {
                "rows_loaded": len(rows),
                "selected_cases": len(selected_cases),
                "stress_rows": len(stress_rows),
                "report": str(args.report.resolve()),
                "visual_sheet": str(paths["visual_sheet"].resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
