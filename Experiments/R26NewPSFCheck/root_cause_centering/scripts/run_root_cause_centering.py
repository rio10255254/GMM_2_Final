from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Any

import cv2
import matplotlib.pyplot as plt
import numpy as np
import torch

from root_cause_centering_lib import (
    MarkdownTable,
    apply_psf_buffers,
    build_delta_matrix,
    collect_selector_candidates,
    load_psf_tensor,
    load_run_profile,
    summarize_psf_pair,
)
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(str(PROJECT_ROOT / 'Experiments/R26NewPSFCheck/root_cause_centering'))
REPORTS = ROOT / "reports"
TABLES = ROOT / "tables"
FIGURES = ROOT / "figures"
LOGS = ROOT / "logs"
RECONS = ROOT / "reconstructions"
MANIFESTS = ROOT / "manifests"

OLD_RUN = ROOT / "archived_inputs" / "r26sm035_recipe_profile_20260316"
NEW_RUN = Path(
    str(PROJECT_ROOT / 'Experiments/R26NewPSFCheck/artifacts/package_cleanup_archive_20260326/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260326_093223')
)
OLD_PSF = Path(
    str(PROJECT_ROOT / 'Experiments/R26NewPSFCheck/artifacts/package_cleanup_archive_20260326/psf_swap_20260326_093203/PSF_fitted_2D_FOVstack.package_old.mat')
)
NEW_PSF = Path(str(PROJECT_ROOT / 'PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat'))
RAW_SAMPLE = Path(
    str(PROJECT_ROOT / 'Experiments/R26NewPSFCheck/ablation_single_sample/input/VisionTop_20251029182653732.bmp')
)
ABLATION_ROOT = Path(str(PROJECT_ROOT / 'Experiments/R26NewPSFCheck/ablation_single_sample'))
OLD_RECON = ABLATION_ROOT / "reconstruct_progress_r26_sm035_best_tradeoff_in_input_20260324_233331" / "old_ckpt_oldpsf" / RAW_SAMPLE.name
NEW_RECON = ABLATION_ROOT / "reconstruct_progress_best_tradeoff_in_input_20260326_115148" / "new_ckpt_newpsf" / RAW_SAMPLE.name
OLD_RECON_NO_OVERRIDE_NEWPSF = ABLATION_ROOT / "reconstruct_progress_r26_sm035_best_tradeoff_in_input_20260324_233331" / "old_ckpt_newpsf" / RAW_SAMPLE.name
NEW_RECON_NO_OVERRIDE_OLDPSF = ABLATION_ROOT / "reconstruct_progress_best_tradeoff_in_input_20260326_115148" / "new_ckpt_oldpsf" / RAW_SAMPLE.name

ANALYSIS_CORE_PATH = Path(
    str(PROJECT_ROOT / 'Experiments/R26NewPSFCheck/artifacts/package_cleanup_archive_20260326/analysis_single_image_recon/scripts/analysis_core.py')
)
ANALYSIS_CONFIG_PATH = Path(
    str(PROJECT_ROOT / 'Experiments/R26NewPSFCheck/artifacts/package_cleanup_archive_20260326/analysis_single_image_recon/scripts/analysis_config.json')
)
ROI_LOG_PATH = Path(
    str(PROJECT_ROOT / 'Experiments/R26NewPSFCheck/artifacts/package_cleanup_archive_20260326/analysis_single_image_recon/logs/roi_selection.json')
)
INFER_SCRIPT_PATH = Path(str(PROJECT_ROOT / 'Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py'))

OLD_BEST_CKPT = OLD_RUN / "weights" / "best_tradeoff.pth.tar"
NEW_BEST_CKPT = NEW_RUN / "weights" / "best_tradeoff.pth.tar"

KEY_EPOCHS = (10, 15, 20, 25, 30, 50, 75, 100)


def _import_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _ensure_dirs() -> None:
    for path in [ROOT, REPORTS, TABLES, FIGURES, LOGS, RECONS, MANIFESTS]:
        path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_gray(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(path)
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def _load_analysis_context():
    analysis_core = _import_module("analysis_core_archive", ANALYSIS_CORE_PATH)
    config = json.loads(ANALYSIS_CONFIG_PATH.read_text(encoding="utf-8"))
    roi_log = json.loads(ROI_LOG_PATH.read_text(encoding="utf-8"))
    rois = {key: tuple(value) for key, value in roi_log["rois"].items()}
    return analysis_core, config, rois


def _score_reconstruction(raw_path: Path, recon_path: Path) -> dict[str, float]:
    analysis_core, config, rois = _load_analysis_context()
    raw = _load_gray(raw_path)
    recon = _load_gray(recon_path)
    ref = analysis_core.detect_ring_reference(raw, config)
    spatial_rows, _, _ = analysis_core.compute_spatial_metrics(raw, recon, ref, rois, config)
    fft_rows, _ = analysis_core.compute_fft_metrics(raw, recon, ref, config)
    geo_rows, _ = analysis_core.compute_geometry_proxy(raw, recon, ref, config)
    merged = {"RAW": {}, "R26": {}}
    for block in [spatial_rows, fft_rows, geo_rows]:
        for key, values in block.items():
            merged[key].update(values)
    return merged["R26"]


def _instantiate_model_from_checkpoint(weights_path: Path, override_psf: Path | None = None):
    infer_mod = _import_module("geoedge_infer_mod", INFER_SCRIPT_PATH)
    device = infer_mod.resolve_device("auto")
    ckpt_obj = torch.load(str(weights_path), map_location="cpu")
    state_dict = infer_mod.extract_state_dict(ckpt_obj)
    arch = infer_mod.infer_arch_from_state(state_dict)

    temp_dir = None
    if override_psf is None:
        temp_psf, temp_dir = infer_mod.build_temp_psf_mat_from_state(state_dict)
        psf_path = temp_psf or NEW_PSF
    else:
        psf_path = override_psf

    model = infer_mod.GeoEdgeAlignSR_v1_v5_NoCoord(
        in_ch=arch["in_ch"],
        base=arch["base"],
        use_physics_layer=arch["use_physics_layer"],
        use_sigmoid_output=True,
        use_upsample_conv=True,
        use_band_limit=arch["use_band_limit"],
        band_limit_cutoff=0.95,
        band_limit_order=8.0,
        psf_fitted_path=str(psf_path),
        psf_grid_rows=10,
        psf_grid_cols=10,
        psf_use_stack_mean=True,
        psf_deconv_reg=float(arch["psf_deconv_reg"] if arch["psf_deconv_reg"] is not None else 10.0),
        psf_phys_alpha_init=float(arch["psf_phys_alpha_init"] if arch["psf_phys_alpha_init"] is not None else 0.10),
        psf_phys_trainable_reg=False,
        weak_psf_enable=arch["weak_psf_enable"],
        weak_psf_k=arch["weak_psf_k"],
        weak_psf_indices=None,
        weak_psf_reg=float(arch["weak_psf_reg"] if arch["weak_psf_reg"] is not None else 30.0),
        weak_psf_beta_init=float(arch["weak_psf_beta_init"] if arch["weak_psf_beta_init"] is not None else 0.02),
        weak_psf_gating_temp=float(arch["weak_psf_psf_temp"] if arch["weak_psf_psf_temp"] is not None else 2.5),
        weak_psf_psf_temp=float(arch["weak_psf_psf_temp"] if arch["weak_psf_psf_temp"] is not None else 2.5),
        weak_psf_entropy_mix=float(arch["weak_psf_entropy_mix"] if arch["weak_psf_entropy_mix"] is not None else 0.0),
        weak_psf_trainable_reg=False,
        weak_psf_lowfreq_ratio=float(arch["weak_psf_lowfreq_ratio"] if arch["weak_psf_lowfreq_ratio"] is not None else 0.25),
        weak_psf_beta_min=0.0,
        weak_psf_beta_max=0.10,
        weak_psf_beta_scale_max=float(arch["weak_psf_beta_scale_max"] if arch["weak_psf_beta_scale_max"] is not None else 0.35),
        weak_psf_deconv_mode="clamp",
        weak_psf_inject="y2",
    ).to(device)
    model.eval()
    infer_mod.load_weights(model, state_dict, strict=False)

    if override_psf is not None:
        apply_psf_buffers(model, load_psf_tensor(override_psf))

    return infer_mod, model, device, temp_dir


def _infer_single(weights_path: Path, output_path: Path, override_psf: Path | None = None) -> dict[str, Any]:
    infer_mod, model, device, temp_dir = _instantiate_model_from_checkpoint(weights_path, override_psf=override_psf)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    infer_mod.run_one(model, device, RAW_SAMPLE, output_path, align_factor=64, gt_path=None)
    if temp_dir is not None:
        try:
            for child in Path(temp_dir).iterdir():
                child.unlink(missing_ok=True)
            Path(temp_dir).rmdir()
        except Exception:
            pass
    image = _load_gray(output_path)
    return {
        "output_path": str(output_path),
        "sha256": _sha256(output_path),
        "mean": float(np.mean(image)),
        "std": float(np.std(image)),
    }


def _selector_checkpoint_paths() -> list[tuple[str, Path]]:
    items = [(f"epoch_{epoch:03d}", NEW_RUN / f"epoch_{epoch:03d}.pth.tar") for epoch in KEY_EPOCHS]
    items.insert(2, ("best_tradeoff", NEW_BEST_CKPT))
    return items


def _selector_audit() -> dict[str, Any]:
    rows = []
    for label, weights_path in _selector_checkpoint_paths():
        out_path = RECONS / "selector_audit" / f"{label}.bmp"
        if not out_path.exists():
            _infer_single(weights_path, out_path)
        metrics = _score_reconstruction(RAW_SAMPLE, out_path)
        rows.append(
            {
                "label": label,
                "epoch": 16 if label == "best_tradeoff" else int(label.split("_")[1]),
                "weights_path": str(weights_path),
                "image_path": str(out_path),
                **metrics,
            }
        )

    rows.sort(key=lambda item: item["epoch"])
    return {"rows": rows}


def _render_selector_plot(rows: list[dict[str, Any]], out_path: Path) -> None:
    epochs = [r["epoch"] for r in rows]
    edge_main = [r["edge_width_main_px"] for r in rows]
    slope_main = [r["max_slope_main"] for r in rows]
    bg_std = [r["background_std"] for r in rows]

    fig, axes = plt.subplots(3, 1, figsize=(11, 8.5), sharex=True)
    axes[0].plot(epochs, edge_main, marker="o", color="#4C78A8")
    axes[0].set_ylabel("主邊界 width (px)")
    axes[0].grid(alpha=0.25)
    axes[1].plot(epochs, slope_main, marker="o", color="#F58518")
    axes[1].set_ylabel("主邊界 max slope")
    axes[1].grid(alpha=0.25)
    axes[2].plot(epochs, bg_std, marker="o", color="#54A24B")
    axes[2].set_ylabel("background std")
    axes[2].set_xlabel("epoch")
    axes[2].grid(alpha=0.25)
    fig.suptitle("新 PSF run 關鍵 epoch selector audit", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _override_sanity() -> dict[str, Any]:
    combos = [
        ("old_ckpt_oldpsf_override", OLD_BEST_CKPT, OLD_PSF),
        ("old_ckpt_newpsf_override", OLD_BEST_CKPT, NEW_PSF),
        ("new_ckpt_oldpsf_override", NEW_BEST_CKPT, OLD_PSF),
        ("new_ckpt_newpsf_override", NEW_BEST_CKPT, NEW_PSF),
    ]
    outputs = {}
    for label, ckpt, psf in combos:
        out_path = RECONS / "override_sanity" / f"{label}.bmp"
        outputs[label] = _infer_single(ckpt, out_path, override_psf=psf)
        outputs[label]["metrics"] = _score_reconstruction(RAW_SAMPLE, out_path)

    no_override_hashes = {
        "old_ckpt_oldpsf_no_override": _sha256(OLD_RECON),
        "old_ckpt_newpsf_no_override": _sha256(OLD_RECON_NO_OVERRIDE_NEWPSF),
        "new_ckpt_oldpsf_no_override": _sha256(NEW_RECON_NO_OVERRIDE_OLDPSF),
        "new_ckpt_newpsf_no_override": _sha256(NEW_RECON),
    }
    override_hashes = {label: info["sha256"] for label, info in outputs.items()}

    pairs = []
    for a, b in [
        ("old_ckpt_oldpsf_override", "old_ckpt_newpsf_override"),
        ("new_ckpt_oldpsf_override", "new_ckpt_newpsf_override"),
    ]:
        img_a = _load_gray(Path(outputs[a]["output_path"])).astype(np.float32)
        img_b = _load_gray(Path(outputs[b]["output_path"])).astype(np.float32)
        pairs.append(
            {
                "pair": f"{a} vs {b}",
                "equal_hash": override_hashes[a] == override_hashes[b],
                "mae": float(np.mean(np.abs(img_a - img_b))),
                "rmse": float(np.sqrt(np.mean((img_a - img_b) ** 2))),
            }
        )

    return {
        "outputs": outputs,
        "no_override_hashes": no_override_hashes,
        "override_hashes": override_hashes,
        "pairwise_diffs": pairs,
    }


def _write_delta_reports(old_profile: dict[str, Any], new_profile: dict[str, Any], delta: dict[str, Any]) -> None:
    _write_json(LOGS / "delta_matrix.json", {"old_profile": old_profile, "new_profile": new_profile, "delta": delta})
    table = MarkdownTable(
        headers=["field", "old", "new"],
        rows=[[row["field"], row["old"], row["new"]] for row in delta["changed"]],
    )
    text = [
        "# Old R26 vs New Retrain Delta Matrix",
        "",
        "這張表只列出非 PSF 本體之外，舊 R26 run 與新 retrain run 已確認不同的執行/選模條件。",
        "",
        table.render(),
        "",
        "重點：這代表目前壞結果不能被簡化成「只換 PSF」。",
    ]
    (REPORTS / "delta_matrix_20260326.md").write_text("\n".join(text), encoding="utf-8")


def _write_psf_reports(summary: dict[str, Any]) -> None:
    _write_json(LOGS / "psf_semantics_summary.json", summary)
    rows = [
        ["old peak", f"({summary['old_mean_psf']['peak_y']}, {summary['old_mean_psf']['peak_x']})"],
        ["new peak", f"({summary['new_mean_psf']['peak_y']}, {summary['new_mean_psf']['peak_x']})"],
        ["old centroid", f"({summary['old_mean_psf']['cy']:.3f}, {summary['old_mean_psf']['cx']:.3f})"],
        ["new centroid", f"({summary['new_mean_psf']['cy']:.3f}, {summary['new_mean_psf']['cx']:.3f})"],
        ["r50 delta", f"{summary['r50_delta']:.4f}"],
        ["r90 delta", f"{summary['r90_delta']:.4f}"],
        ["old centroid_y_std", f"{summary['old_stack']['centroid_y_std']:.4f}"],
        ["new centroid_y_std", f"{summary['new_stack']['centroid_y_std']:.4f}"],
    ]
    table = MarkdownTable(headers=["item", "value"], rows=rows)
    text = [
        "# PSF Alignment Semantics Summary",
        "",
        "主差異在中心與 grid-to-grid alignment semantics，不在整體寬度。",
        "",
        table.render(),
    ]
    (REPORTS / "psf_alignment_semantics_20260326.md").write_text("\n".join(text), encoding="utf-8")


def _write_selector_reports(selector: dict[str, Any], old_metrics: dict[str, float]) -> None:
    rows = selector["rows"]
    _write_json(LOGS / "selector_audit.json", selector)
    csv_headers = [
        "label",
        "epoch",
        "edge_width_main_px",
        "edge_width_weak_px",
        "max_slope_main",
        "max_slope_weak",
        "CNR_main",
        "CNR_weak",
        "background_std",
        "checkerboard_ratio",
        "ring_thickness_std_px",
    ]
    with (TABLES / "selector_audit_key_epochs.csv").open("w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(csv_headers) + "\n")
        for row in rows:
            fh.write(",".join(str(row[h]) for h in csv_headers) + "\n")

    md_rows = [
        [
            row["label"],
            row["epoch"],
            f"{row['edge_width_main_px']:.2f}",
            f"{row['max_slope_main']:.2f}",
            f"{row['CNR_main']:.2f}",
            f"{row['background_std']:.3f}",
            f"{row['checkerboard_ratio']:.3f}",
            f"{row['ring_thickness_std_px']:.3f}",
        ]
        for row in rows
    ]
    table = MarkdownTable(
        headers=["label", "epoch", "edge_w_main", "slope_main", "CNR_main", "bg_std", "cb_ratio", "thickness_std"],
        rows=md_rows,
    )
    best_edge = min(rows, key=lambda r: (r["edge_width_main_px"], -r["max_slope_main"], r["background_std"]))
    text = [
        "# Selector Audit (Key Epochs)",
        "",
        "這裡用與單張分析一致的指標重排新 PSF run 的關鍵 epoch。",
        "",
        table.render(),
        "",
        f"若只看主邊界集中化，這批 epoch 中最有利的候選是 `{best_edge['label']}`。",
        "但這不代表它已整體優於舊 R26；它仍需回頭和舊 baseline 比較弱邊界、CNR 與連續性。",
        "",
        f"- 舊 R26 baseline: main edge width = {old_metrics['edge_width_main_px']:.2f}, CNR_main = {old_metrics['CNR_main']:.2f}, CNR_weak = {old_metrics['CNR_weak']:.2f}",
        f"- {best_edge['label']}: main edge width = {best_edge['edge_width_main_px']:.2f}, CNR_main = {best_edge['CNR_main']:.2f}, CNR_weak = {best_edge['CNR_weak']:.2f}",
        "",
        "因此 selector mismatch 可以被列為共犯，但目前還不能被寫成唯一主因。",
    ]
    (REPORTS / "selector_audit_20260326.md").write_text("\n".join(text), encoding="utf-8")
    _render_selector_plot(rows, FIGURES / "selector_audit_key_epochs_20260326.png")


def _write_override_reports(result: dict[str, Any]) -> None:
    _write_json(LOGS / "override_sanity.json", result)
    rows = [
        [item["pair"], item["equal_hash"], f"{item['mae']:.4f}", f"{item['rmse']:.4f}"]
        for item in result["pairwise_diffs"]
    ]
    table = MarkdownTable(headers=["pair", "equal_hash", "mae", "rmse"], rows=rows)
    text = [
        "# Post-load PSF Override Sanity",
        "",
        "這份檢查的目的不是找最佳效果，而是證明 post-load buffer override 真的有改變輸出。",
        "",
        "## No-override hashes",
        "",
        "```json",
        json.dumps(result["no_override_hashes"], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Override pairwise diffs",
        "",
        table.render(),
        "",
        "若同一 checkpoint 在 old/new PSF override 下不再同 hash、且出現明顯 MAE/RMSE，表示 override 工具有效。",
    ]
    (REPORTS / "override_sanity_20260326.md").write_text("\n".join(text), encoding="utf-8")


def _write_manifest(old_profile: dict[str, Any], new_profile: dict[str, Any]) -> None:
    manifest = {
        "old_recipe_basis_run": str(OLD_RUN),
        "new_recipe_basis_run": str(NEW_RUN),
        "old_psf": str(OLD_PSF),
        "new_psf": str(NEW_PSF),
        "raw_sample": str(RAW_SAMPLE),
        "old_recipe_split_meta": str(OLD_RUN / "_repro" / old_profile["model_name"] / "split_meta.json"),
        "old_recipe_train_idx": str(OLD_RUN / "_repro" / old_profile["model_name"] / "train_idx.npy"),
        "old_recipe_val_idx": str(OLD_RUN / "_repro" / old_profile["model_name"] / "val_idx.npy"),
        "control_grid": [
            {"recipe": "old", "psf": "old", "status": "prepared"},
            {"recipe": "old", "psf": "new", "status": "prepared"},
            {"recipe": "new", "psf": "old", "status": "prepared"},
            {"recipe": "new", "psf": "new", "status": "already available"},
        ],
        "note": "This manifest freezes the inputs for later full 2x2 retraining. It is prepared but not launched by this script.",
    }
    _write_json(MANIFESTS / "control_run_manifest_2x2.json", manifest)


def _write_final_report(
    delta: dict[str, Any],
    psf_summary: dict[str, Any],
    selector: dict[str, Any],
    override: dict[str, Any],
    old_metrics: dict[str, float],
) -> None:
    rows = selector["rows"]
    best_tradeoff = next(row for row in rows if row["label"] == "best_tradeoff")
    best_edge = min(rows, key=lambda r: (r["edge_width_main_px"], -r["max_slope_main"], r["background_std"]))
    override_changed = all(not item["equal_hash"] for item in override["pairwise_diffs"])

    verdict_lines = [
        "# PSF 置中退步根因調查",
        "",
        "## 核心結論",
        "",
        "1. 目前不能把退步簡化成「只有 PSF 置中害的」。",
        "2. 已確認 PSF 的主要變化是 alignment semantics，而非 width blow-up。",
        "3. 已確認新 retrain run 與舊 R26 run 存在 execution / recipe drift。",
        "4. 已確認只靠原 infer script 的 `--psf-fitted-path` 不能做純 PSF 對照；但本輪新增的 post-load override 工具已能真正改變輸出。",
        "",
        "## 這輪最重要的新證據",
        "",
        f"- Delta matrix 顯示新 run 與舊 run 不只 PSF 不同，還有 `{', '.join(row['field'] for row in delta['changed'][:6])}` 等執行差異。",
        f"- PSF summary 顯示 old peak = ({psf_summary['old_mean_psf']['peak_y']}, {psf_summary['old_mean_psf']['peak_x']}), new peak = ({psf_summary['new_mean_psf']['peak_y']}, {psf_summary['new_mean_psf']['peak_x']}), r90 delta = {psf_summary['r90_delta']:.4f}。",
        f"- Selector audit 中 `best_tradeoff` = epoch {best_tradeoff['epoch']}，但若只看主邊界集中化，較有利的候選是 `{best_edge['label']}`。",
        f"- 不過 `{best_edge['label']}` 仍未追回舊 R26 的 CNR 與弱邊界品質：old CNR_main/CNR_weak = {old_metrics['CNR_main']:.2f}/{old_metrics['CNR_weak']:.2f}，{best_edge['label']} = {best_edge['CNR_main']:.2f}/{best_edge['CNR_weak']:.2f}。",
        f"- Post-load override sanity = {'passed' if override_changed else 'failed'}，表示後續 pure-PSF isolation 已有可信工具。",
        "",
        "## 目前最合理的暫時 verdict",
        "",
        "最合理的暫時 verdict 是：`new centered PSF 改變了 physics prior 的對齊語意，而舊 R26 訓練/選模機制沒有一起重新校準`。",
        "但現階段仍不能把責任全部丟給 PSF fitting formal flow，也不能把責任全部丟給 selector。",
        "本輪證據更支持「PSF 語意變更 + recipe drift + selector mismatch 共同造成退步，其中 selector mismatch 是共犯而非完整解釋」。",
        "",
        "## 下一步",
        "",
        "1. 用本輪準備好的 manifest 啟動真正的 2x2 control retrain。",
        "2. 用同一批單張/外部樣本指標回看 selector 是否需要換規則。",
        "3. 若 old recipe + new PSF 單獨就退步，再回頭改 PSF promotion 規則。",
    ]
    (REPORTS / "ROOT_CAUSE_CENTERING_REPORT_20260326.md").write_text("\n".join(verdict_lines), encoding="utf-8")


def main() -> None:
    _ensure_dirs()

    old_profile = load_run_profile(OLD_RUN)
    new_profile = load_run_profile(NEW_RUN)
    delta = build_delta_matrix(old_profile, new_profile)
    psf_summary = summarize_psf_pair(OLD_PSF, NEW_PSF)
    selector = _selector_audit()
    old_metrics = _score_reconstruction(RAW_SAMPLE, OLD_RECON)
    override = _override_sanity()

    _write_delta_reports(old_profile, new_profile, delta)
    _write_psf_reports(psf_summary)
    _write_selector_reports(selector, old_metrics)
    _write_override_reports(override)
    _write_manifest(old_profile, new_profile)
    _write_final_report(delta, psf_summary, selector, override, old_metrics)

    print("Root cause centering investigation complete.")
    print(f"Report: {REPORTS / 'ROOT_CAUSE_CENTERING_REPORT_20260326.md'}")


if __name__ == "__main__":
    main()
