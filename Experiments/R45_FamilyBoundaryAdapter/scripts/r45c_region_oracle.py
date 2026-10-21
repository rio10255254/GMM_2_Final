"""R45C region-level oracle and residual diagnostics.

Analysis-only.  Re-uses R44 motion reconstructions, but evaluates shape-error
and residual-direction stats at patch granularity instead of whole-image.

Goal:  decide whether teacher specialisation is distributed at sub-image
scale (a region selector has space to work) or only at image scale (it does
not, and we should switch to multi-model routing).

R45B already established that *image-level* oracle improves the R44B from R42
combined large-region/mixed-field shape error from 0.3384 to 0.2253 (33.42%).
This script asks the next question:  if we split each image into patches,
how much further can a *patch-level* oracle go, and does the oracle teacher
also have a clean residual direction (positive in the boundary band)?
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = REPO_ROOT / "Experiments" / "R45_FamilyBoundaryAdapter"
R44_SCRIPT_DIR = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "scripts"
R45_SCRIPT_DIR = EXPERIMENT_ROOT / "scripts"
for _p in (R44_SCRIPT_DIR, R45_SCRIPT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import r44_motion_metrics  # noqa: E402
import r44g_boundary_shape_metrics as r44g  # noqa: E402
import r45b_teacher_diagnostics as r45b  # noqa: E402


DEFAULT_PROFILE = "motion_val_unseen"
DEFAULT_DATA_ROOT = REPO_ROOT / "Training_Data" / "r44_universal_boundary_motion"
DEFAULT_RECON_ROOT = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "results" / "motion_recon"
DEFAULT_OUTPUT_DIR = EXPERIMENT_ROOT / "results" / "r45c_region_oracle"
DEFAULT_REPORT = EXPERIMENT_ROOT / "reports" / "R45C_REGION_ORACLE.md"

TARGET_FAMILIES = {"large_regions", "mixed_fields"}
BASE_MODEL = "R44B from R42"
PATCH_SIZES_DEFAULT = (64, 128)
MIN_BOUNDARY_PX_PER_PATCH = 8
BAND_KERNEL_SIZE = 7  # match R45B residual band

DEFAULT_MODEL_MAP = r45b.DEFAULT_MODEL_MAP


def _patch_starts(length: int, patch: int) -> list[int]:
    """Non-overlapping patch starts; the last patch is anchored so it stays in
    bounds even if `length` is not a multiple of `patch`."""
    if length <= patch:
        return [0]
    stops = list(range(0, length - patch + 1, patch))
    last = length - patch
    if stops[-1] != last:
        stops.append(last)
    return stops


def _read_lbl01(path: Path) -> np.ndarray:
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


def _patch_shape_metrics(gt_boundary_patch: np.ndarray, pred_boundary_patch: np.ndarray) -> dict | None:
    if int(np.asarray(gt_boundary_patch).astype(bool).sum()) < MIN_BOUNDARY_PX_PER_PATCH:
        return None
    metrics = r44g.boundary_shape_metrics(gt_boundary_patch, pred_boundary_patch)
    score = float(metrics.get("shape_error_score", float("nan")))
    if not math.isfinite(score):
        return None
    return metrics


def _gather_predictions(
    *,
    profile: str,
    profile_dir: Path,
    recon_root: Path,
    model_map: dict[str, str],
    frame: dict,
    stage_cache: dict[tuple[Path, str], Path | None],
    gt_boundary_count: int,
) -> dict[str, dict]:
    """For one frame, read each candidate's prediction image and produce its
    image-level boundary mask (matched against GT boundary count)."""
    stage = str(frame["stage"])
    out: dict[str, dict] = {}
    for model, folder in model_map.items():
        model_root = recon_root / folder
        if not model_root.exists():
            continue
        cache_key = (model_root, stage)
        if cache_key not in stage_cache:
            try:
                stage_cache[cache_key] = r44_motion_metrics._latest_stage_output(model_root, profile, stage)
            except FileNotFoundError:
                stage_cache[cache_key] = None
        out_dir = stage_cache[cache_key]
        if out_dir is None:
            continue
        pred_path = out_dir / Path(frame["package_lbl"]).name
        if not pred_path.exists():
            continue
        pred_raw = r44_motion_metrics._read_gray(pred_path)
        pred_boundary = r44_motion_metrics.matched_gradient_boundary(pred_raw, target_count=gt_boundary_count)
        pred01 = pred_raw.astype(np.float32) / 255.0 if pred_raw.dtype == np.uint8 else pred_raw.astype(np.float32) / 65535.0
        out[model] = {"pred01": pred01, "boundary": pred_boundary}
    return out


def collect(
    *,
    profile: str,
    data_root: Path,
    recon_root: Path,
    model_map: dict[str, str],
    patch_size: int,
    target_families: set[str] = TARGET_FAMILIES,
    frame_limit: int | None = None,
    progress_every: int = 20,
) -> tuple[list[dict], list[dict]]:
    profile_dir = data_root / profile
    manifest = json.loads((profile_dir / "manifest.json").read_text(encoding="utf-8"))
    frames = [f for f in manifest["frames"] if str(f["feature_family"]) in target_families]
    if frame_limit is not None:
        frames = frames[: int(frame_limit)]
    stage_cache: dict[tuple[Path, str], Path | None] = {}
    band_kernel = np.ones((BAND_KERNEL_SIZE, BAND_KERNEL_SIZE), dtype=np.uint8)
    patch_rows: list[dict] = []
    residual_rows: list[dict] = []
    for idx, frame in enumerate(frames):
        if progress_every and (idx % progress_every == 0):
            print(f"  patch_size={patch_size}  frame {idx}/{len(frames)}  ({frame.get('stage')})", flush=True)
        stage = str(frame["stage"])
        case_id = r45b._case_id(frame)
        gt01 = _read_lbl01(profile_dir / frame["package_lbl"])
        gt_boundary = r44_motion_metrics._read_gray(profile_dir / frame["package_boundary"])
        gt_count = int(np.asarray(gt_boundary).astype(bool).sum())
        if gt_count == 0:
            continue
        band_full = cv2.dilate((gt_boundary > 0).astype(np.uint8), band_kernel, iterations=1).astype(bool)
        preds = _gather_predictions(
            profile=profile,
            profile_dir=profile_dir,
            recon_root=recon_root,
            model_map=model_map,
            frame=frame,
            stage_cache=stage_cache,
            gt_boundary_count=gt_count,
        )
        if BASE_MODEL not in preds:
            continue
        h, w = gt01.shape[:2]
        for y in _patch_starts(h, patch_size):
            for x in _patch_starts(w, patch_size):
                ys, xs = slice(y, y + patch_size), slice(x, x + patch_size)
                gt_b_patch = gt_boundary[ys, xs]
                if int(np.asarray(gt_b_patch).astype(bool).sum()) < MIN_BOUNDARY_PX_PER_PATCH:
                    continue
                gt01_patch = gt01[ys, xs]
                band_patch = band_full[ys, xs]
                patch_id = f"y{y:04d}x{x:04d}"
                base_pred01 = preds[BASE_MODEL]["pred01"][ys, xs]
                base_b_patch = preds[BASE_MODEL]["boundary"][ys, xs]
                base_metrics = _patch_shape_metrics(gt_b_patch, base_b_patch)
                if base_metrics is None:
                    continue
                patch_rows.append({
                    "case_id": case_id,
                    "stage": stage,
                    "feature_family": str(frame["feature_family"]),
                    "sequence_id": int(frame["sequence_id"]),
                    "frame_index": int(frame["frame_index"]),
                    "patch_id": patch_id,
                    "patch_size": patch_size,
                    "patch_y": int(y),
                    "patch_x": int(x),
                    "model": BASE_MODEL,
                    "shape_error_score": float(base_metrics["shape_error_score"]),
                    "boundary_f_score": float(base_metrics["boundary_f_score"]),
                    "density_ratio": float(base_metrics["boundary_density_ratio"]),
                    "fragmentation_ratio": float(base_metrics["fragmentation_ratio"]),
                })
                base_err = np.abs(base_pred01 - gt01_patch)
                for teacher in model_map:
                    if teacher == BASE_MODEL or teacher not in preds:
                        continue
                    teacher_pred01 = preds[teacher]["pred01"][ys, xs]
                    teacher_b_patch = preds[teacher]["boundary"][ys, xs]
                    t_metrics = _patch_shape_metrics(gt_b_patch, teacher_b_patch)
                    if t_metrics is None:
                        continue
                    patch_rows.append({
                        "case_id": case_id,
                        "stage": stage,
                        "feature_family": str(frame["feature_family"]),
                        "sequence_id": int(frame["sequence_id"]),
                        "frame_index": int(frame["frame_index"]),
                        "patch_id": patch_id,
                        "patch_size": patch_size,
                        "patch_y": int(y),
                        "patch_x": int(x),
                        "model": teacher,
                        "shape_error_score": float(t_metrics["shape_error_score"]),
                        "boundary_f_score": float(t_metrics["boundary_f_score"]),
                        "density_ratio": float(t_metrics["boundary_density_ratio"]),
                        "fragmentation_ratio": float(t_metrics["fragmentation_ratio"]),
                    })
                    if int(band_patch.sum()) >= MIN_BOUNDARY_PX_PER_PATCH:
                        teacher_err = np.abs(teacher_pred01 - gt01_patch)
                        delta = base_err[band_patch] - teacher_err[band_patch]
                        residual_rows.append({
                            "case_id": case_id,
                            "stage": stage,
                            "feature_family": str(frame["feature_family"]),
                            "patch_id": patch_id,
                            "patch_size": patch_size,
                            "teacher": teacher,
                            "band_pixels": int(band_patch.sum()),
                            "mean_error_reduction": float(delta.mean()),
                            "median_error_reduction": float(np.median(delta)),
                            "teacher_better_fraction": float(np.mean(delta > 0.0)),
                        })
    return patch_rows, residual_rows


def patch_oracle_summary(rows: list[dict]) -> dict:
    by_patch: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        by_patch[(row["case_id"], row["patch_id"])].append(row)
    base_vals: list[float] = []
    oracle_vals: list[float] = []
    family_base: dict[str, list[float]] = defaultdict(list)
    family_oracle: dict[str, list[float]] = defaultdict(list)
    selection_counts: Counter = Counter()
    family_selection: dict[str, Counter] = defaultdict(Counter)
    for (case, pid), group in by_patch.items():
        base_row = next((r for r in group if r["model"] == BASE_MODEL), None)
        if base_row is None:
            continue
        best_row = min(group, key=lambda r: float(r["shape_error_score"]))
        base_score = float(base_row["shape_error_score"])
        oracle_score = float(best_row["shape_error_score"])
        base_vals.append(base_score)
        oracle_vals.append(oracle_score)
        family = str(base_row["feature_family"])
        family_base[family].append(base_score)
        family_oracle[family].append(oracle_score)
        selection_counts[best_row["model"]] += 1
        family_selection[family][best_row["model"]] += 1

    def _avg(xs: list[float]) -> float:
        return float(sum(xs) / len(xs)) if xs else float("nan")

    base_mean = _avg(base_vals)
    oracle_mean = _avg(oracle_vals)
    return {
        "patch_count": len(base_vals),
        "base_avg_shape_error": base_mean,
        "oracle_avg_shape_error": oracle_mean,
        "improvement_pct": (
            ((base_mean - oracle_mean) / base_mean) * 100.0 if base_mean and math.isfinite(base_mean) else float("nan")
        ),
        "patch_oracle_model_counts": dict(selection_counts.most_common()),
        "by_family": {
            family: {
                "patch_count": len(family_base[family]),
                "base_avg_shape_error": _avg(family_base[family]),
                "oracle_avg_shape_error": _avg(family_oracle[family]),
                "improvement_pct": (
                    ((_avg(family_base[family]) - _avg(family_oracle[family])) / _avg(family_base[family])) * 100.0
                    if _avg(family_base[family]) and math.isfinite(_avg(family_base[family])) else float("nan")
                ),
                "patch_oracle_model_counts": dict(family_selection[family].most_common()),
            }
            for family in sorted(family_base)
        },
    }


def cleaning_rate_on_oracle(rows: list[dict], residuals: list[dict]) -> dict:
    by_patch: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        by_patch[(row["case_id"], row["patch_id"])].append(row)
    oracle_teacher: dict[tuple[str, str], str] = {}
    for key, group in by_patch.items():
        best = min(group, key=lambda r: float(r["shape_error_score"]))
        if best["model"] != BASE_MODEL:
            oracle_teacher[key] = best["model"]
    res_index: dict[tuple[str, str, str], dict] = {
        (r["case_id"], r["patch_id"], r["teacher"]): r for r in residuals
    }
    total = 0
    clean_mean = 0
    clean_fraction = 0
    clean_both = 0
    avg_mean_reduction = 0.0
    avg_better_fraction = 0.0
    for key, teacher in oracle_teacher.items():
        rec = res_index.get((key[0], key[1], teacher))
        if rec is None:
            continue
        total += 1
        avg_mean_reduction += float(rec["mean_error_reduction"])
        avg_better_fraction += float(rec["teacher_better_fraction"])
        if rec["mean_error_reduction"] > 0:
            clean_mean += 1
        if rec["teacher_better_fraction"] > 0.5:
            clean_fraction += 1
        if rec["mean_error_reduction"] > 0 and rec["teacher_better_fraction"] > 0.5:
            clean_both += 1
    if total == 0:
        return {
            "patches_with_teacher_oracle": 0,
            "clean_mean_reduction_pct": float("nan"),
            "clean_better_fraction_pct": float("nan"),
            "clean_both_pct": float("nan"),
            "avg_mean_error_reduction": float("nan"),
            "avg_teacher_better_fraction": float("nan"),
        }
    return {
        "patches_with_teacher_oracle": total,
        "clean_mean_reduction_pct": clean_mean / total * 100.0,
        "clean_better_fraction_pct": clean_fraction / total * 100.0,
        "clean_both_pct": clean_both / total * 100.0,
        "avg_mean_error_reduction": avg_mean_reduction / total,
        "avg_teacher_better_fraction": avg_better_fraction / total,
    }


def _write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields = sorted({k for r in rows for k in r})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _json_safe(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def write_report(summary: dict, report_path: Path) -> None:
    image_oracle_pct = 33.42  # R45B headline
    image_family_oracle_pct = 12.30  # R45B headline
    base_target_score = 0.3384  # R45B headline (R44B from R42)
    lines = [
        "# R45C 分區理想上限與殘差診斷",
        "",
        "## 摘要",
        "",
        "- 本診斷不訓練模型，沿用 R44 既有的 motion_val_unseen 重建結果。",
        "- 每張影像切成 patch，對每個 patch 計算 7 個候選模型的 R44G 形狀錯誤分數，找分區理想上限。",
        f"- 對比 R45B 整張理想上限改善 `{image_oracle_pct:.2f}%`、固定分族理想上限改善 `{image_family_oracle_pct:.2f}%`。",
        "- 同時看：在分區理想上限選到的老師上，邊界帶殘差方向是否乾淨。",
        "",
        "## 主要結果",
        "",
        "| Patch 大小 | 有效 patch 數 | R44B from R42 patch 平均 | 分區理想上限 | 改善% |",
        "|---:|---:|---:|---:|---:|",
    ]
    for key in sorted(summary):
        d = summary[key]
        lines.append(
            f"| {d['patch_size']} | {d['patch_count']} | "
            f"{d['base_avg_shape_error']:.4f} | "
            f"{d['oracle_avg_shape_error']:.4f} | "
            f"{d['improvement_pct']:.2f}% |"
        )
    lines.extend([
        "",
        f"R45B 整張層級基準（參考）：R44B from R42 整張平均 `{base_target_score:.4f}`，整張理想上限 `0.2253`，改善 `{image_oracle_pct:.2f}%`；",
        f"固定分族理想上限改善 `{image_family_oracle_pct:.2f}%`。",
        "",
        "## 殘差方向乾淨比例",
        "",
        "若分區理想老師在邊界帶 `mean_error_reduction > 0` 比例越高，代表分區層級老師優勢比 R45B image-level 更乾淨。",
        "",
        "| Patch 大小 | 含老師理想 patch 數 | mean_reduction>0 比例 | better_fraction>0.5 比例 | 兩條件都滿足比例 | 平均 mean_reduction | 平均 better_fraction |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for key in sorted(summary):
        d = summary[key]
        lines.append(
            f"| {d['patch_size']} | {d['cleaning_patches_with_teacher_oracle']} | "
            f"{d['cleaning_clean_mean_reduction_pct']:.2f}% | "
            f"{d['cleaning_clean_better_fraction_pct']:.2f}% | "
            f"{d['cleaning_clean_both_pct']:.2f}% | "
            f"{d['cleaning_avg_mean_error_reduction']:.4f} | "
            f"{d['cleaning_avg_teacher_better_fraction']:.4f} |"
        )
    lines.extend(["", "## 分族分析", ""])
    for key in sorted(summary):
        d = summary[key]
        lines.append(f"### Patch {d['patch_size']}")
        lines.append("")
        lines.append("| 結構類型 | Patch 數 | R44B from R42 patch 平均 | 分區理想上限 | 改善% |")
        lines.append("|---|---:|---:|---:|---:|")
        for fam in sorted(d["by_family"]):
            f = d["by_family"][fam]
            lines.append(
                f"| {fam} | {f['patch_count']} | {f['base_avg_shape_error']:.4f} | "
                f"{f['oracle_avg_shape_error']:.4f} | {f['improvement_pct']:.2f}% |"
            )
        lines.append("")
    lines.extend(["## 分區理想選擇老師統計", ""])
    for key in sorted(summary):
        d = summary[key]
        lines.append(f"### Patch {d['patch_size']}")
        lines.append("")
        lines.append("| 模型 | 被選次數 | 占比 |")
        lines.append("|---|---:|---:|")
        total = sum(d["patch_oracle_model_counts"].values()) or 1
        for model, cnt in sorted(d["patch_oracle_model_counts"].items(), key=lambda kv: -kv[1]):
            pct = cnt / total * 100.0
            lines.append(f"| {model} | {cnt} | {pct:.2f}% |")
        lines.append("")
    # decision
    finite_imps = [d["improvement_pct"] for d in summary.values() if math.isfinite(d.get("improvement_pct", float("nan")))]
    best_imp = max(finite_imps) if finite_imps else float("nan")
    finite_clean = [d["cleaning_clean_mean_reduction_pct"] for d in summary.values() if math.isfinite(d.get("cleaning_clean_mean_reduction_pct", float("nan")))]
    best_clean = max(finite_clean) if finite_clean else float("nan")
    lines.extend(["## 判定", ""])
    if not math.isfinite(best_imp):
        lines.append("無法計算分區改善百分比，請檢查資料量。")
    elif best_imp >= 25.0 and best_clean >= 50.0:
        lines.append(
            f"分區理想上限改善 `{best_imp:.2f}%` ≥ 25%，且殘差方向乾淨比例 `{best_clean:.2f}%` ≥ 50%。"
            "**選擇器路線通過**，能力分散是分區層級的且老師在分區上比較乾淨；"
            "下一步可進入容量探針與 selector 架構設計。"
        )
    elif best_imp >= 25.0 and best_clean < 50.0:
        lines.append(
            f"分區理想上限改善 `{best_imp:.2f}%` ≥ 25%，**但殘差方向乾淨比例只有 `{best_clean:.2f}%` < 50%**。"
            "形狀分數有空間，但老師依然不乾淨；selector 學形狀標籤恐學到風格與過衝。"
            "**建議轉路線 B（多模型路由）**，或先研究新的 supervision 訊號讓 selector 不依賴老師形狀標籤。"
        )
    elif best_imp <= 15.0:
        lines.append(
            f"分區理想上限改善 `{best_imp:.2f}%` ≤ 15%，能力分散主要是整張層級的，分區沒有額外空間。"
            "**轉路線 B（多模型路由）**：保留各模型，推論時直接路由，不再追求單模型整合。"
        )
    else:
        lines.append(
            f"分區理想上限改善 `{best_imp:.2f}%` 落在 15-25% 邊界區。"
            f"殘差方向乾淨比例最佳 `{best_clean:.2f}%`。"
            "若 ≥ 50% 仍可走選擇器路線，否則建議轉多模型路由。"
        )
    lines.append("")
    lines.extend([
        "## 產物",
        "",
        "- `results/r45c_region_oracle/r45c_patch_rows_<size>.csv`：每 patch、每模型的形狀錯誤分數。",
        "- `results/r45c_region_oracle/r45c_patch_residuals_<size>.csv`：每 patch、每老師的邊界帶殘差統計。",
        "- `results/r45c_region_oracle/r45c_region_oracle_summary.json`：理想上限與殘差乾淨比例彙整。",
        "",
        "## 方法",
        "",
        f"- Patch 切法：non-overlapping，最後一塊向內錨定避免出界；最小邊界 GT 像素數 `{MIN_BOUNDARY_PX_PER_PATCH}`。",
        f"- 邊界帶：GT boundary 經 `{BAND_KERNEL_SIZE}x{BAND_KERNEL_SIZE}` dilation（與 R45B 一致）。",
        "- 預測 boundary：整張影像用 `matched_gradient_boundary` 取與 GT 等量像素，再切 patch。",
        "- 形狀錯誤：直接套 R44G 的 `boundary_shape_metrics`。Patch 內若 component bbox 被 reject（min_pixels=16, min_span=10），對應 component metric 走 default penalty，但 ranking 仍成立。",
        "- 對比基準：R44B from R42（與 R45B 一致）；目標分族 `large_regions` + `mixed_fields`。",
        "",
    ])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    *,
    profile: str = DEFAULT_PROFILE,
    data_root: Path = DEFAULT_DATA_ROOT,
    recon_root: Path = DEFAULT_RECON_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report: Path = DEFAULT_REPORT,
    model_map: dict[str, str] | None = None,
    patch_sizes: tuple[int, ...] = PATCH_SIZES_DEFAULT,
    frame_limit: int | None = None,
) -> dict:
    model_map = model_map or DEFAULT_MODEL_MAP
    output_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict] = {}
    for ps in patch_sizes:
        print(f"[r45c] running patch_size={ps} ...", flush=True)
        rows, residuals = collect(
            profile=profile,
            data_root=data_root,
            recon_root=recon_root,
            model_map=model_map,
            patch_size=ps,
            frame_limit=frame_limit,
        )
        print(f"[r45c] patch_size={ps}  rows={len(rows)} residuals={len(residuals)}", flush=True)
        oracle = patch_oracle_summary(rows)
        cleaning = cleaning_rate_on_oracle(rows, residuals)
        summary[f"patch_{ps:03d}"] = {
            "patch_size": ps,
            "row_count": len(rows),
            "residual_row_count": len(residuals),
            **oracle,
            **{f"cleaning_{k}": v for k, v in cleaning.items()},
        }
        _write_csv(rows, output_dir / f"r45c_patch_rows_{ps}.csv")
        _write_csv(residuals, output_dir / f"r45c_patch_residuals_{ps}.csv")
    _write_json(summary, output_dir / "r45c_region_oracle_summary.json")
    write_report(summary, report)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run R45C region-level oracle and residual diagnostics.")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--recon-root", type=Path, default=DEFAULT_RECON_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--patch-sizes", type=int, nargs="+", default=list(PATCH_SIZES_DEFAULT))
    parser.add_argument("--frame-limit", type=int, default=None)
    args = parser.parse_args(argv)
    summary = run(
        profile=args.profile,
        data_root=args.data_root,
        recon_root=args.recon_root,
        output_dir=args.output_dir,
        report=args.report,
        patch_sizes=tuple(args.patch_sizes),
        frame_limit=args.frame_limit,
    )
    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
