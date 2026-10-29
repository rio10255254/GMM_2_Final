from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
_PROJECT_ROOT = Path(__file__).resolve().parents[4]


PROJECT_ROOT = Path(str(_PROJECT_ROOT))
EXPERIMENT_ROOT = PROJECT_ROOT / "Experiments" / "R26NewPSFCheck" / "pure_psf_control"
OLD_PSF_ARCHIVE = PROJECT_ROOT / "Experiments" / "R26NewPSFCheck" / "artifacts" / "package_cleanup_archive_20260326" / "psf_swap_20260326_093203" / "PSF_fitted_2D_FOVstack.package_old.mat"
ROOT_FORMAL_PSF = PROJECT_ROOT / "PSF_Fitting" / "Crop_circle_FreqFiltered" / "Fits" / "PSF_fitted_2D_FOVstack.mat"
PACKAGE_FORMAL_PSF = PROJECT_ROOT / "_deployment_package" / "GeoEdge_R26_正式交付版" / "GeoEdge_R26_使用包" / "內部檔案" / "PSF_Fitting" / "Crop_circle_FreqFiltered" / "Fits" / "PSF_fitted_2D_FOVstack.mat"
AUTO_TUNE_R26_REPORT = PROJECT_ROOT / "Traing_Progress" / "auto_tune_reports" / "auto_tune_report_20260316_185417.json"
ROOT_CAUSE_LIB = PROJECT_ROOT / "Experiments" / "R26NewPSFCheck" / "root_cause_centering" / "scripts" / "root_cause_centering_lib.py"
ANALYSIS_CORE_PATH = PROJECT_ROOT / "Experiments" / "R26NewPSFCheck" / "artifacts" / "package_cleanup_archive_20260326" / "analysis_single_image_recon" / "scripts" / "analysis_core.py"
ANALYSIS_CONFIG_PATH = PROJECT_ROOT / "Experiments" / "R26NewPSFCheck" / "artifacts" / "package_cleanup_archive_20260326" / "analysis_single_image_recon" / "scripts" / "analysis_config.json"
ROI_LOG_PATH = PROJECT_ROOT / "Experiments" / "R26NewPSFCheck" / "artifacts" / "package_cleanup_archive_20260326" / "analysis_single_image_recon" / "logs" / "roi_selection.json"
RAW_SAMPLE = PROJECT_ROOT / "Experiments" / "R26NewPSFCheck" / "ablation_single_sample" / "input" / "VisionTop_20251029182653732.bmp"
INFER_SCRIPT_PATH = PROJECT_ROOT / "Model" / "GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py"
AUTOTUNE_SCRIPT_PATH = PROJECT_ROOT / "Model" / "GeoEdgeAlignSR_v1_AutoTuneTrain.py"
OBS_EPOCHS = (10, 20, 40)
ROUND26_STAGE_DIRS = (
    "stage_08_annulus_focus",
    "stage_09_annulus_non_overlap",
    "stage_10_annulus_overlap",
    "stage_14_annulus_edge_defect_focus",
    "stage_15_annulus_sparse_clean",
    "stage_16_annulus_sparse_defect_clean",
    "stage_23_annulus_gmf_sequence_mid_clean",
    "stage_24_annulus_gmf_sequence_mid_defect",
    "stage_27_annulus_gmf_sequence_midwide_clean",
    "stage_28_annulus_gmf_sequence_midwide_defect",
)


def _import_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    added = False
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
        added = True
    prev_module = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if prev_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = prev_module
        if added:
            try:
                sys.path.remove(module_dir)
            except ValueError:
                pass
    return module


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_round26_recipe(report_path: Path, candidate_name: str = "r26_sm035") -> dict[str, Any]:
    payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
    wanted = None
    for item in payload.get("candidates", []):
        if str(item.get("candidate")) == candidate_name:
            wanted = item
            break
    if wanted is None:
        raise KeyError(f"Candidate {candidate_name} not found in {report_path}")

    return {
        "seed": int(payload["seed"]),
        "deterministic": bool(payload.get("deterministic", False)),
        "sweep_epochs": int(payload["sweep_epochs"]),
        "final_epochs": int(payload["final_epochs"]),
        "candidate_name": str(wanted["candidate"]),
        "candidate_tag": str(candidate_name.replace("_", "")),
        "model_name_base": str(wanted["model_name_base"]),
        "common_overrides": dict(payload["common_overrides"]),
        "candidate_overrides": dict(wanted["overrides"]),
        "source_report": str(report_path),
    }


def build_control_spec(
    *,
    recipe: dict[str, Any],
    label: str,
    psf_path: Path,
    progress_root: Path,
    sweep_epochs: int = 40,
    checkpoint_every: int = 10,
) -> dict[str, Any]:
    model_name_base = f"{recipe['model_name_base']}_PURE_{label}"
    common_overrides = dict(recipe["common_overrides"])
    candidate_overrides = dict(recipe["candidate_overrides"])
    common_overrides["PSF_FITTED_PATH"] = str(psf_path)
    common_overrides["AUTO_SWEEP_SAVE_CKPT_EVERY_N_EPOCH"] = int(checkpoint_every)
    common_overrides["AUTO_SWEEP_SAVE_CKPT_EVERY_EPOCH"] = True
    common_overrides["AUTO_SWEEP_FAST_MONITOR_EVERY_EPOCH"] = int(checkpoint_every)

    return {
        "label": label,
        "psf_path": str(psf_path),
        "output_root": str(progress_root),
        "run_name": model_name_base,
        "seed": int(recipe["seed"]),
        "deterministic": bool(recipe["deterministic"]),
        "amp": False,
        "candidate_name": recipe["candidate_name"],
        "candidate_tag": label,
        "model_name_base": model_name_base,
        "sweep_epochs": int(sweep_epochs),
        "checkpoint_every": int(checkpoint_every),
        "common_overrides": common_overrides,
        "candidate_overrides": candidate_overrides,
    }


def resolve_round26_training_roots() -> dict[str, Any]:
    src_root = PROJECT_ROOT / "Training_Data" / "generated_convolved"
    lbl_root = PROJECT_ROOT / "Training_Data" / "generated"
    selected = []
    count = 0
    for name in ROUND26_STAGE_DIRS:
        src_dir = src_root / name
        lbl_dir = lbl_root / name
        if not src_dir.exists() or not lbl_dir.exists():
            raise FileNotFoundError(f"Missing stage directory for round26 recipe: {name}")
        n_src = len(list(src_dir.glob("*")))
        n_lbl = len(list(lbl_dir.glob("*")))
        if n_src != n_lbl:
            raise RuntimeError(f"Stage count mismatch for {name}: src={n_src} lbl={n_lbl}")
        selected.append({"stage": name, "n_src": n_src, "n_lbl": n_lbl})
        count += n_src
    return {
        "src_root": str(src_root),
        "lbl_root": str(lbl_root),
        "selected_stages": selected,
        "n_selected_src": int(count),
    }


def build_parity_rows(left: dict[str, Any], right: dict[str, Any], allowed_fields: tuple[str, ...] = ("psf_path", "output_root", "run_name")) -> list[dict[str, Any]]:
    fields = sorted(set(left.keys()) | set(right.keys()))
    rows = []
    for field in fields:
        lv = left.get(field)
        rv = right.get(field)
        if lv == rv:
            status = "same"
        elif field in allowed_fields:
            status = "allowed_difference"
        else:
            status = "unexpected_difference"
        rows.append({"field": field, "left": lv, "right": rv, "status": status})
    return rows


def should_abort_after_epoch40(baseline_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_epoch_base = {int(r["epoch"]): r for r in baseline_rows}
    by_epoch_cand = {int(r["epoch"]): r for r in candidate_rows}
    evaluated = []
    failures = []
    for epoch in (20, 40):
        if epoch not in by_epoch_base or epoch not in by_epoch_cand:
            continue
        evaluated.append(epoch)
        base = by_epoch_base[epoch]
        cand = by_epoch_cand[epoch]
        failed = (
            float(cand["edge_width_main_px"]) > float(base["edge_width_main_px"])
            and float(cand["max_slope_main"]) < float(base["max_slope_main"])
            and float(cand["CNR_main"]) < float(base["CNR_main"])
            and float(cand["background_std"]) > float(base["background_std"])
        )
        failures.append({"epoch": epoch, "failed": bool(failed)})
    abort = bool(evaluated) and all(item["failed"] for item in failures) and len(evaluated) == len(failures)
    return {"abort": abort, "evaluated_epochs": evaluated, "failures": failures}


def snapshot_and_restore_official_psf(*, backup_root: Path) -> dict[str, Any]:
    ensure_dir(backup_root)
    root_backup = backup_root / "root_formal_before_restore.mat"
    pkg_backup = backup_root / "package_formal_before_restore.mat"
    shutil.copy2(ROOT_FORMAL_PSF, root_backup)
    shutil.copy2(PACKAGE_FORMAL_PSF, pkg_backup)
    shutil.copy2(OLD_PSF_ARCHIVE, ROOT_FORMAL_PSF)
    shutil.copy2(OLD_PSF_ARCHIVE, PACKAGE_FORMAL_PSF)
    result = {
        "old_psf_archive": str(OLD_PSF_ARCHIVE),
        "root_formal_before": {"path": str(root_backup), "sha256": sha256_file(root_backup)},
        "package_formal_before": {"path": str(pkg_backup), "sha256": sha256_file(pkg_backup)},
        "root_formal_after": {"path": str(ROOT_FORMAL_PSF), "sha256": sha256_file(ROOT_FORMAL_PSF)},
        "package_formal_after": {"path": str(PACKAGE_FORMAL_PSF), "sha256": sha256_file(PACKAGE_FORMAL_PSF)},
    }
    return result


def _load_gray(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(path)
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def _load_analysis_context():
    analysis_core = _import_module("analysis_core_archive_pure", ANALYSIS_CORE_PATH)
    config = json.loads(ANALYSIS_CONFIG_PATH.read_text(encoding="utf-8"))
    roi_log = json.loads(ROI_LOG_PATH.read_text(encoding="utf-8"))
    rois = {key: tuple(value) for key, value in roi_log["rois"].items()}
    return analysis_core, config, rois


def score_reconstruction(raw_path: Path, recon_path: Path) -> dict[str, float]:
    analysis_core, config, rois = _load_analysis_context()
    raw = _load_gray(raw_path)
    recon = _load_gray(recon_path)
    ref = analysis_core.detect_ring_reference(raw, config)
    spatial_rows, _, _ = analysis_core.compute_spatial_metrics(raw, recon, ref, rois, config)
    fft_rows, _ = analysis_core.compute_fft_metrics(raw, recon, ref, config)
    geo_rows, _ = analysis_core.compute_geometry_proxy(raw, recon, ref, config)
    merged = {"RAW": {}, "R26": {}}
    for block in (spatial_rows, fft_rows, geo_rows):
        for key, values in block.items():
            merged[key].update(values)
    return merged["R26"]


def instantiate_model_from_checkpoint(weights_path: Path):
    infer_mod = _import_module("geoedge_infer_mod_pure", INFER_SCRIPT_PATH)
    root_cause_lib = _import_module("root_cause_lib_pure", ROOT_CAUSE_LIB)
    device = infer_mod.resolve_device("auto")
    ckpt_obj = infer_mod.torch.load(str(weights_path), map_location="cpu")
    state_dict = infer_mod.extract_state_dict(ckpt_obj)
    arch = infer_mod.infer_arch_from_state(state_dict)
    temp_psf, temp_dir = infer_mod.build_temp_psf_mat_from_state(state_dict)
    psf_path = temp_psf or ROOT_FORMAL_PSF
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
    root_cause_lib.apply_psf_buffers(model, root_cause_lib.load_psf_tensor(Path(psf_path)))
    return infer_mod, model, device, temp_dir


def infer_single(weights_path: Path, output_path: Path) -> dict[str, Any]:
    infer_mod, model, device, temp_dir = instantiate_model_from_checkpoint(weights_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    infer_mod.run_one(model, device, RAW_SAMPLE, output_path, align_factor=64, gt_path=None)
    if temp_dir is not None:
        shutil.rmtree(temp_dir, ignore_errors=True)
    image = _load_gray(output_path)
    return {
        "output_path": str(output_path),
        "sha256": sha256_file(output_path),
        "mean": float(np.mean(image)),
        "std": float(np.std(image)),
    }


def run_old_recipe_sweep(spec: dict[str, Any]) -> dict[str, Any]:
    autotune = _import_module("autotune_pure", AUTOTUNE_SCRIPT_PATH)
    train_roots = resolve_round26_training_roots()
    autotune.train_mod._set_training_progress_root(str(Path(spec["output_root"])))
    autotune.train_mod.TRAIN_SRC_DIR = str(train_roots["src_root"])
    autotune.train_mod.TRAIN_LBL_DIR = str(train_roots["lbl_root"])
    base_cfg_snapshot = autotune.copy.deepcopy(vars(autotune.train_mod.TrainConfig()))
    result = autotune._run_one_candidate(
        candidate_name=str(spec["candidate_name"]),
        candidate_tag=str(spec["candidate_tag"]),
        model_name_base=str(spec["model_name_base"]),
        base_cfg_snapshot=base_cfg_snapshot,
        common_overrides=dict(spec["common_overrides"]),
        candidate_overrides=dict(spec["candidate_overrides"]),
        sweep_epochs=int(spec["sweep_epochs"]),
        seed=int(spec["seed"]),
        deterministic=bool(spec["deterministic"]),
    )
    return result


def collect_epoch_metrics(run_dir: Path, recon_root: Path, epochs: tuple[int, ...] = OBS_EPOCHS) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for epoch in epochs:
        ckpt = Path(run_dir) / f"epoch_{epoch:03d}.pth.tar"
        if not ckpt.exists():
            continue
        out_path = ensure_dir(recon_root) / f"epoch_{epoch:03d}.bmp"
        infer_meta = infer_single(ckpt, out_path)
        metrics = score_reconstruction(RAW_SAMPLE, out_path)
        rows.append({"epoch": int(epoch), "checkpoint_path": str(ckpt), **infer_meta, **metrics})
    return rows


def find_latest_usable_run(line_root: Path, epochs: tuple[int, ...] = OBS_EPOCHS) -> Path | None:
    root = Path(line_root)
    if not root.exists():
        return None
    candidates = sorted(
        [p for p in root.iterdir() if p.is_dir() and p.name.startswith("training_progress_")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        ok = True
        for epoch in epochs:
            if not (path / f"epoch_{epoch:03d}.pth.tar").exists():
                ok = False
                break
        if ok:
            return path
    return None


def write_markdown_table(path: Path, headers: list[str], rows: list[list[Any]]) -> None:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_epoch_metrics_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize_line(line_name: str, rows: list[dict[str, Any]]) -> list[list[Any]]:
    out: list[list[Any]] = []
    for row in rows:
        out.append([
            line_name,
            row["epoch"],
            f"{row['edge_width_main_px']:.2f}",
            f"{row['max_slope_main']:.2f}",
            f"{row['CNR_main']:.2f}",
            f"{row['background_std']:.3f}",
            f"{row['checkerboard_ratio']:.3f}",
            f"{row['ring_thickness_std_px']:.3f}",
        ])
    return out
