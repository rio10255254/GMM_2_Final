"""R45B teacher residual and oracle-family diagnostics.

This is an analysis-only script.  It reads existing R44 motion reconstructions
and checks whether teacher models have stable, transferable boundary advantage
over the current motion anchor, R44B from R42.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = REPO_ROOT / "Experiments" / "R45_FamilyBoundaryAdapter"
R44_SCRIPT_DIR = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "scripts"
if str(R44_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(R44_SCRIPT_DIR))

import r44_motion_metrics  # noqa: E402
import r44g_boundary_shape_metrics as r44g  # noqa: E402


DEFAULT_PROFILE = "motion_val_unseen"
DEFAULT_DATA_ROOT = REPO_ROOT / "Training_Data" / "r44_universal_boundary_motion"
DEFAULT_RECON_ROOT = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "results" / "motion_recon"
DEFAULT_OUTPUT_DIR = EXPERIMENT_ROOT / "results" / "r45b_teacher_diagnostics"
DEFAULT_VISUAL_DIR = EXPERIMENT_ROOT / "results" / "visual_samples"
DEFAULT_REPORT = EXPERIMENT_ROOT / "reports" / "R45B_TEACHER_DIAGNOSTICS.md"
TARGET_FAMILIES = {"large_regions", "mixed_fields"}
BASE_MODEL = "R44B from R42"

DEFAULT_MODEL_MAP = {
    "R44B from R42": "r44_motion_from_r42_best_e24",
    "R44B from COMBO": "r44_motion_from_combo_e24",
    "R44B from R40": "r44_motion_from_r40_a045_e24",
    "R44C static heavy": "r44c_static_heavy_all_motion",
    "R41 direct": "r41_direct",
    "R42 best": "r42_best",
    "R44H StepB region KD": "r44h_stepb_region_kd_main",
}


def _finite_mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    return float(sum(vals) / len(vals)) if vals else float("nan")


def _safe_div(num: float, den: float, default: float = float("nan")) -> float:
    return float(num) / float(den) if float(den) != 0 else default


def _round4(value: float) -> float | None:
    return round(float(value), 4) if math.isfinite(float(value)) else None


def _json_safe(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


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


def write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def read_gray01(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"failed to read image: {path}")
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if img.dtype == np.uint16:
        return img.astype(np.float32) / 65535.0
    if img.dtype == np.uint8:
        return img.astype(np.float32) / 255.0
    arr = img.astype(np.float32)
    maxv = float(np.nanmax(arr)) if arr.size else 1.0
    return arr / maxv if maxv > 1.5 else arr


def _case_id(row: dict) -> str:
    return f"{row['stage']}|{int(row['sequence_id']):04d}|{int(row['frame_index']):02d}"


def compute_residual_advantage(base_abs_error, teacher_abs_error) -> dict:
    base = np.asarray(base_abs_error, dtype=np.float32).reshape(-1)
    teacher = np.asarray(teacher_abs_error, dtype=np.float32).reshape(-1)
    if base.shape != teacher.shape:
        raise ValueError(f"shape mismatch: base={base.shape} teacher={teacher.shape}")
    delta = base - teacher
    return {
        "mean_error_reduction": float(delta.mean()) if delta.size else float("nan"),
        "median_error_reduction": float(np.median(delta)) if delta.size else float("nan"),
        "teacher_better_fraction": float(np.mean(delta > 0.0)) if delta.size else float("nan"),
        "teacher_worse_fraction": float(np.mean(delta < 0.0)) if delta.size else float("nan"),
    }


def frame_oracle_rows(rows: list[dict], *, target_families: set[str] | None = None) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if target_families is not None and str(row["feature_family"]) not in target_families:
            continue
        grouped[str(row["case_id"])].append(row)
    out = []
    for case_id, group in sorted(grouped.items()):
        best = min(group, key=lambda r: float(r["shape_error_score"]))
        out.append(
            {
                "case_id": case_id,
                "feature_family": best["feature_family"],
                "oracle_model": best["model"],
                "oracle_shape_error_score": float(best["shape_error_score"]),
            }
        )
    return out


def family_oracle_rows(rows: list[dict], *, target_families: set[str] | None = None) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        family = str(row["feature_family"])
        if target_families is not None and family not in target_families:
            continue
        grouped[(family, str(row["model"]))].append(row)
    by_family: dict[str, list[dict]] = defaultdict(list)
    for (family, model), group in grouped.items():
        by_family[family].append(
            {
                "feature_family": family,
                "oracle_model": model,
                "avg_shape_error_score": _finite_mean(float(r["shape_error_score"]) for r in group),
                "case_count": len(group),
            }
        )
    out = []
    for family, candidates in sorted(by_family.items()):
        out.append(min(candidates, key=lambda r: float(r["avg_shape_error_score"])))
    return out


def summarize_teacher_transferability(
    *,
    teacher_name: str,
    target_shape_delta_pct: float,
    mean_error_reduction: float,
    teacher_better_fraction: float,
    motion_regression_pct: float,
    min_shape_gain_pct: float = 3.0,
    min_error_reduction: float = 0.002,
    min_better_fraction: float = 0.55,
    max_motion_regression_pct: float = 15.0,
) -> dict:
    reasons = []
    if float(target_shape_delta_pct) < float(min_shape_gain_pct):
        reasons.append("形狀優勢不足")
    if float(mean_error_reduction) < float(min_error_reduction) or float(teacher_better_fraction) < float(min_better_fraction):
        reasons.append("殘差方向不穩")
    if float(motion_regression_pct) > float(max_motion_regression_pct):
        reasons.append("位移退步過大")
    return {
        "teacher": teacher_name,
        "transferable": not reasons,
        "reason": "；".join(reasons) if reasons else "可作中間分支老師候選",
        "target_shape_delta_pct": float(target_shape_delta_pct),
        "mean_error_reduction": float(mean_error_reduction),
        "teacher_better_fraction": float(teacher_better_fraction),
        "motion_regression_pct": float(motion_regression_pct),
    }


def collect_shape_rows(*, profile: str, data_root: Path, recon_root: Path, model_map: dict[str, str]) -> list[dict]:
    rows = r44g.collect_shape_rows(profile=profile, data_root=data_root, recon_root=recon_root, model_map=model_map)
    for row in rows:
        row["case_id"] = f"{row['stage']}|{int(row['sequence_id']):04d}|{int(row['frame_index']):02d}"
    return rows


def target_rank_from_rows(rows: list[dict]) -> list[dict]:
    summary = r44g.summarize_rows(rows)
    return r44g.summarize_target_families(summary)


def motion_summary_by_model(*, profile: str, data_root: Path, recon_root: Path, model_map: dict[str, str]) -> dict[str, dict]:
    out = {}
    for model, folder in model_map.items():
        model_root = recon_root / folder
        if not model_root.exists():
            continue
        try:
            summary = r44_motion_metrics.summarize(profile, data_root, model_root)
        except FileNotFoundError:
            continue
        out[model] = {k: v for k, v in summary.items() if k != "rows"}
    return out


def residual_advantage_rows(
    *,
    profile: str,
    data_root: Path,
    recon_root: Path,
    model_map: dict[str, str],
    base_model: str = BASE_MODEL,
    target_families: set[str] = TARGET_FAMILIES,
) -> list[dict]:
    profile_dir = data_root / profile
    manifest = json.loads((profile_dir / "manifest.json").read_text(encoding="utf-8"))
    frames = [f for f in manifest["frames"] if str(f["feature_family"]) in target_families]
    base_folder = model_map[base_model]
    base_cache: dict[str, Path] = {}
    teacher_cache: dict[tuple[str, str], Path] = {}
    rows = []
    for frame in frames:
        stage = str(frame["stage"])
        case_id = _case_id(frame)
        lbl = read_gray01(profile_dir / frame["package_lbl"])
        boundary = r44_motion_metrics._read_gray(profile_dir / frame["package_boundary"])
        band = cv2.dilate((boundary > 0).astype(np.uint8), np.ones((7, 7), dtype=np.uint8), iterations=1).astype(bool)
        if int(band.sum()) == 0:
            continue
        base_out_dir = r44_motion_metrics._latest_stage_output(base_cache.setdefault("root", recon_root / base_folder), profile, stage)
        base_pred = read_gray01(base_out_dir / Path(frame["package_lbl"]).name)
        base_err = np.abs(base_pred - lbl)[band]
        for teacher, folder in model_map.items():
            if teacher == base_model:
                continue
            teacher_root = recon_root / folder
            if not teacher_root.exists():
                continue
            try:
                cache_key = (teacher, stage)
                if cache_key not in teacher_cache:
                    teacher_cache[cache_key] = r44_motion_metrics._latest_stage_output(teacher_root, profile, stage)
                teacher_pred = read_gray01(teacher_cache[cache_key] / Path(frame["package_lbl"]).name)
            except FileNotFoundError:
                continue
            teacher_err = np.abs(teacher_pred - lbl)[band]
            stats = compute_residual_advantage(base_err, teacher_err)
            rows.append(
                {
                    "teacher": teacher,
                    "case_id": case_id,
                    "stage": stage,
                    "feature_family": frame["feature_family"],
                    "sequence_id": int(frame["sequence_id"]),
                    "frame_index": int(frame["frame_index"]),
                    "band_pixels": int(band.sum()),
                    **stats,
                }
            )
    return rows


def summarize_residual_rows(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["teacher"]), str(row["feature_family"]))].append(row)
    out = []
    for (teacher, family), group in sorted(grouped.items()):
        out.append(
            {
                "teacher": teacher,
                "feature_family": family,
                "case_count": len(group),
                "avg_mean_error_reduction": _finite_mean(r["mean_error_reduction"] for r in group),
                "avg_median_error_reduction": _finite_mean(r["median_error_reduction"] for r in group),
                "avg_teacher_better_fraction": _finite_mean(r["teacher_better_fraction"] for r in group),
                "avg_teacher_worse_fraction": _finite_mean(r["teacher_worse_fraction"] for r in group),
            }
        )
    return out


def model_shape_summary(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["model"]), str(row["feature_family"]))].append(row)
    out = []
    for (model, family), group in sorted(grouped.items()):
        out.append(
            {
                "model": model,
                "feature_family": family,
                "case_count": len(group),
                "avg_shape_error_score": _finite_mean(r["shape_error_score"] for r in group),
                "avg_boundary_f_score": _finite_mean(r["boundary_f_score"] for r in group),
                "avg_fragmentation_ratio": _finite_mean(r["fragmentation_ratio"] for r in group),
                "avg_corner_retention": _finite_mean(r["corner_retention"] for r in group),
            }
        )
    return out


def build_teacher_verdicts(
    *,
    target_rank: list[dict],
    residual_summary: list[dict],
    motion_by_model: dict[str, dict],
    base_model: str = BASE_MODEL,
) -> list[dict]:
    base_target = next(row for row in target_rank if row["model"] == base_model)
    base_shape = float(base_target["target_shape_error_score"])
    base_motion = float(motion_by_model[base_model]["overall_motion_vector_error_px"])
    residual_by_teacher: dict[str, list[dict]] = defaultdict(list)
    for row in residual_summary:
        if row["feature_family"] in TARGET_FAMILIES:
            residual_by_teacher[row["teacher"]].append(row)
    verdicts = []
    for row in target_rank:
        model = str(row["model"])
        if model == base_model:
            continue
        if model not in motion_by_model:
            continue
        residual_group = residual_by_teacher.get(model, [])
        mean_reduction = _finite_mean(r["avg_mean_error_reduction"] for r in residual_group)
        better_fraction = _finite_mean(r["avg_teacher_better_fraction"] for r in residual_group)
        shape_delta = ((base_shape - float(row["target_shape_error_score"])) / base_shape) * 100.0
        motion_delta = ((float(motion_by_model[model]["overall_motion_vector_error_px"]) - base_motion) / base_motion) * 100.0
        verdicts.append(
            summarize_teacher_transferability(
                teacher_name=model,
                target_shape_delta_pct=shape_delta,
                mean_error_reduction=mean_reduction,
                teacher_better_fraction=better_fraction,
                motion_regression_pct=motion_delta,
            )
        )
    return sorted(verdicts, key=lambda r: (not r["transferable"], -float(r["target_shape_delta_pct"])))


def oracle_summary(shape_rows: list[dict], *, base_model: str = BASE_MODEL) -> dict:
    base_rows = [r for r in shape_rows if r["model"] == base_model and r["feature_family"] in TARGET_FAMILIES]
    base_target = _finite_mean(r["shape_error_score"] for r in base_rows)
    frame_rows = frame_oracle_rows(shape_rows, target_families=TARGET_FAMILIES)
    family_rows = family_oracle_rows(shape_rows, target_families=TARGET_FAMILIES)
    frame_avg = _finite_mean(r["oracle_shape_error_score"] for r in frame_rows)
    family_weighted_values = []
    for family_row in family_rows:
        family = family_row["feature_family"]
        model = family_row["oracle_model"]
        family_weighted_values.extend(
            float(r["shape_error_score"])
            for r in shape_rows
            if r["feature_family"] == family and r["model"] == model
        )
    family_avg = _finite_mean(family_weighted_values)
    return {
        "base_target_shape_error_score": base_target,
        "frame_oracle_shape_error_score": frame_avg,
        "frame_oracle_improvement_pct": ((base_target - frame_avg) / base_target) * 100.0,
        "family_oracle_shape_error_score": family_avg,
        "family_oracle_improvement_pct": ((base_target - family_avg) / base_target) * 100.0,
        "frame_oracle_model_counts": dict(Counter(r["oracle_model"] for r in frame_rows)),
        "family_oracle": family_rows,
        "frame_oracle_rows": frame_rows,
    }


def write_visual_sheet(
    *,
    profile: str,
    data_root: Path,
    recon_root: Path,
    model_map: dict[str, str],
    path: Path,
) -> None:
    profile_dir = data_root / profile
    examples = [
        ("stage_45_motion_regions", "0085_seq0085_f06.bmp", ["R44B from R42", "R44B from COMBO", "R41 direct"]),
        ("stage_47_motion_mixed", "0085_seq0085_f06.bmp", ["R44B from R42", "R44B from R40", "R44C static heavy"]),
    ]
    cols = ["GT + boundary", "Base", "Teacher 1", "Teacher 2"]
    cell_w, cell_h = 210, 242
    left = 150
    canvas = Image.new("RGB", (left + cell_w * len(cols) + 20, cell_h * len(examples) + 62), (250, 250, 250))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    draw.text((12, 14), "R45B teacher diagnostics: base vs possible teachers", fill=(20, 20, 20), font=font)
    for c, label in enumerate(cols):
        draw.text((left + c * cell_w + 8, 42), label, fill=(20, 20, 20), font=font)

    def crop_imgs(imgs, boundary, size=168):
        yy, xx = np.nonzero(boundary > 0)
        if len(xx) == 0:
            cy, cx = boundary.shape[0] // 2, boundary.shape[1] // 2
        else:
            cy = int((yy.min() + yy.max()) / 2)
            cx = int((xx.min() + xx.max()) / 2)
        h, w = boundary.shape
        y0 = max(0, min(h - size, cy - size // 2))
        x0 = max(0, min(w - size, cx - size // 2))
        return [img[y0 : y0 + size, x0 : x0 + size] for img in imgs]

    def to_u8(img01):
        if img01.dtype == np.uint8:
            return img01
        return np.clip(np.rint(img01 * 255.0), 0, 255).astype(np.uint8)

    def to_rgb(img, boundary=None):
        u8 = to_u8(img)
        rgb = np.stack([u8, u8, u8], axis=-1)
        if boundary is not None:
            rgb[boundary > 0] = [255, 40, 40]
        return Image.fromarray(rgb).resize((205, 205), Image.Resampling.NEAREST)

    for r, (stage, filename, models) in enumerate(examples):
        y = 62 + r * cell_h
        family = "large regions" if "regions" in stage else "mixed fields"
        draw.text((12, y + 92), family, fill=(20, 20, 20), font=font)
        boundary = cv2.imread(str(profile_dir / "geom" / "boundary" / stage / filename), cv2.IMREAD_GRAYSCALE)
        gt = read_gray01(profile_dir / "lbl" / stage / filename)
        imgs = [gt]
        for model in models:
            out_dir = r44_motion_metrics._latest_stage_output(recon_root / model_map[model], profile, stage)
            imgs.append(read_gray01(out_dir / filename))
        gt_crop, *pred_crops, boundary_crop = crop_imgs([gt, *imgs[1:], boundary], boundary)
        images = [to_rgb(gt_crop, boundary_crop)]
        for pred in pred_crops:
            images.append(to_rgb(pred, boundary_crop))
        for c, img in enumerate(images):
            canvas.paste(img, (left + c * cell_w, y + 22))
        draw.text((left + cell_w + 8, y + 228), models[0], fill=(20, 20, 20), font=font)
        draw.text((left + cell_w * 2 + 8, y + 228), models[1], fill=(20, 20, 20), font=font)
        draw.text((left + cell_w * 3 + 8, y + 228), models[2], fill=(20, 20, 20), font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def markdown_table(rows: list[dict], columns: list[tuple[str, str]], *, limit: int | None = None) -> str:
    use_rows = rows[:limit] if limit else rows
    lines = ["| " + " | ".join(label for label, _ in columns) + " |"]
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


def write_report(payload: dict, report: Path, visual_path: Path) -> None:
    oracle = payload["oracle"]
    verdicts = payload["teacher_verdicts"]
    target_rank = payload["target_rank"]
    lines = [
        "# R45B 老師殘差與理想分族診斷",
        "",
        "## 摘要",
        "",
        "- 本診斷不訓練模型，只讀取 R44 已有的 motion_val_unseen 重建結果。",
        "- 目的：確認局部較強的老師模型是否真的有穩定可轉移的邊界優勢，以及理想分族選擇的上限有多大。",
        "- 基準仍是 `R44B from R42`，因為它目前位移最穩。",
        "",
        "## 主要結論",
        "",
        f"- R44B from R42 的大區塊/混合合併形狀錯誤是 `{oracle['base_target_shape_error_score']:.4f}`。",
        f"- 完美逐張選擇器的理論形狀錯誤是 `{oracle['frame_oracle_shape_error_score']:.4f}`，改善 `{oracle['frame_oracle_improvement_pct']:.2f}%`。",
        f"- 只按結構類型選固定老師的理論形狀錯誤是 `{oracle['family_oracle_shape_error_score']:.4f}`，改善 `{oracle['family_oracle_improvement_pct']:.2f}%`。",
        "- 這代表能力分散確實存在，但不是很乾淨；逐張 oracle 有明顯空間，單純分族固定老師的空間較小。",
        "",
        "## 老師可轉移性判定",
        "",
        markdown_table(
            verdicts,
            [
                ("老師", "teacher"),
                ("可轉移", "transferable"),
                ("理由", "reason"),
                ("形狀改善%", "target_shape_delta_pct"),
                ("殘差改善", "mean_error_reduction"),
                ("老師較好比例", "teacher_better_fraction"),
                ("位移變化%", "motion_regression_pct"),
            ],
        ),
        "",
        "## 大區塊/混合總排名",
        "",
        markdown_table(
            target_rank,
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
        "## 理想分族選擇",
        "",
        markdown_table(
            oracle["family_oracle"],
            [
                ("結構類型", "feature_family"),
                ("最佳固定模型", "oracle_model"),
                ("平均形狀錯誤", "avg_shape_error_score"),
                ("樣本數", "case_count"),
            ],
        ),
        "",
        "## 逐張 oracle 選擇次數",
        "",
        markdown_table(
            [{"model": k, "count": v} for k, v in sorted(oracle["frame_oracle_model_counts"].items(), key=lambda kv: (-kv[1], kv[0]))],
            [("模型", "model"), ("次數", "count")],
        ),
        "",
        "## 代表圖",
        "",
        f"![R45B 老師比較]({visual_path.as_posix()})",
        "",
        "## 下一步",
        "",
        "- 若要繼續單一入口路線，下一步不應再做輸出端校正。",
        "- 較合理的是做中間特徵層的小分支，並且不要只用粗略 family label；至少需要能判斷單張圖內哪一塊邊界該由哪個老師引導。",
        "- 若只做固定分族老師，改善空間有限；若要追逐張 oracle 的上限，必須加入場景/區域選擇器。",
        "",
        "## 產物",
        "",
        "- `results/r45b_teacher_diagnostics/r45b_shape_rows.csv`：逐張形狀指標。",
        "- `results/r45b_teacher_diagnostics/r45b_target_rank.csv`：目標結構總排名。",
        "- `results/r45b_teacher_diagnostics/r45b_residual_summary.csv`：老師殘差方向統計。",
        "- `results/r45b_teacher_diagnostics/r45b_oracle_summary.json`：oracle 上限。",
        "- `results/visual_samples/r45b_teacher_diagnostics_sheet.png`：代表圖。",
    ]
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_diagnostics(
    *,
    profile: str = DEFAULT_PROFILE,
    data_root: Path = DEFAULT_DATA_ROOT,
    recon_root: Path = DEFAULT_RECON_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    visual_dir: Path = DEFAULT_VISUAL_DIR,
    report: Path = DEFAULT_REPORT,
    model_map: dict[str, str] | None = None,
) -> dict:
    model_map = model_map or DEFAULT_MODEL_MAP
    shape_rows = collect_shape_rows(profile=profile, data_root=data_root, recon_root=recon_root, model_map=model_map)
    shape_summary = model_shape_summary(shape_rows)
    target_rank = target_rank_from_rows(shape_rows)
    residual_rows = residual_advantage_rows(profile=profile, data_root=data_root, recon_root=recon_root, model_map=model_map)
    residual_summary = summarize_residual_rows(residual_rows)
    motion_by_model = motion_summary_by_model(profile=profile, data_root=data_root, recon_root=recon_root, model_map=model_map)
    oracle = oracle_summary(shape_rows)
    verdicts = build_teacher_verdicts(target_rank=target_rank, residual_summary=residual_summary, motion_by_model=motion_by_model)

    visual_path = visual_dir / "r45b_teacher_diagnostics_sheet.png"
    write_visual_sheet(profile=profile, data_root=data_root, recon_root=recon_root, model_map=model_map, path=visual_path)

    payload = {
        "profile": profile,
        "model_map": model_map,
        "target_rank": target_rank,
        "shape_summary": shape_summary,
        "motion_by_model": motion_by_model,
        "residual_summary": residual_summary,
        "teacher_verdicts": verdicts,
        "oracle": {k: v for k, v in oracle.items() if k != "frame_oracle_rows"},
        "visual_path": str(visual_path),
    }
    write_csv(shape_rows, output_dir / "r45b_shape_rows.csv")
    write_csv(shape_summary, output_dir / "r45b_shape_summary.csv")
    write_csv(target_rank, output_dir / "r45b_target_rank.csv")
    write_csv(residual_rows, output_dir / "r45b_residual_rows.csv")
    write_csv(residual_summary, output_dir / "r45b_residual_summary.csv")
    write_csv(oracle["frame_oracle_rows"], output_dir / "r45b_frame_oracle_rows.csv")
    write_csv(oracle["family_oracle"], output_dir / "r45b_family_oracle.csv")
    write_csv(verdicts, output_dir / "r45b_teacher_verdicts.csv")
    write_json(payload, output_dir / "r45b_oracle_summary.json")
    write_report(payload, report, visual_path)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run R45B teacher residual and oracle diagnostics.")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--recon-root", type=Path, default=DEFAULT_RECON_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--visual-dir", type=Path, default=DEFAULT_VISUAL_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    payload = run_diagnostics(
        profile=args.profile,
        data_root=args.data_root,
        recon_root=args.recon_root,
        output_dir=args.output_dir,
        visual_dir=args.visual_dir,
        report=args.report,
    )
    print(
        json.dumps(
            _json_safe(
                {
                    "target_rank_top3": payload["target_rank"][:3],
                    "oracle": payload["oracle"],
                    "teacher_verdicts": payload["teacher_verdicts"],
                    "report": str(args.report),
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
