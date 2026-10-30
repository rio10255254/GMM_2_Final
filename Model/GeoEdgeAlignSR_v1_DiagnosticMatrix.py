import argparse
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import torch
import torch.nn.functional as F


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
TRAINING_PROGRESS_ROOT = PROJECT_ROOT / "Experiments" / "Legacy"
DEFAULT_OUTPUT_ROOT = TRAINING_PROGRESS_ROOT / "organized_20260314" / "diagnostics"
DEFAULT_SEED_MANIFEST = (
    TRAINING_PROGRESS_ROOT
    / "organized_20260313"
    / "round18"
    / "selected"
    / "current_centerpush_seed.json"
)

if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))
if str(PROJECT_ROOT / "Training_Data") not in sys.path:
    sys.path.append(str(PROJECT_ROOT / "Training_Data"))

from GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest import (  # noqa: E402
    DEFAULT_PSF_PATH,
    extract_psf_path_from_ckpt,
    extract_state_dict,
    infer_arch_from_state,
    load_weights,
    normalize_to_01,
    read_image_keep_dtype,
)
from GeoEdgeAlignSR_v1_ModelA_v5_NoCoord import GeoEdgeAlignSR_v1_v5_NoCoord  # noqa: E402
import Data_Simulaion as DS  # noqa: E402


SEQ_RE = re.compile(r"(?P<idx>\d+)_seq(?P<seq>\d+)_f(?P<frame>\d+)", re.IGNORECASE)
DEFAULT_STAGE_IDS = [21, 22, 23, 24, 27, 28, 25, 26]
SCALE_LABELS = {
    0.08: "0.08px",
    0.8: "0.8px",
    8.0: "8px",
}


@dataclass
class StageRow:
    stage_id: int
    stage_name: str
    scale_px: float
    domain: str
    estimator: str
    truth_source: str
    frame_count: int
    pair_count: int
    abs_center_err_px: float
    delta_center_err_px: float
    step_err_rel: float
    sign_acc: float
    center_bias_x_px: float
    center_bias_y_px: float
    mean_r_err_px: float
    thick_err_px: float


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--weights-manifest", type=Path, default=DEFAULT_SEED_MANIFEST)
    p.add_argument("--weights-path", type=Path, default=None)
    p.add_argument("--device", default="auto")
    p.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    p.add_argument("--stage-ids", default="21,22,23,24,27,28,25,26")
    p.add_argument("--base-seed", type=int, default=42)
    p.add_argument("--max-seqs-per-stage", type=int, default=0)
    p.add_argument("--skip-sr", action="store_true")
    return p.parse_args()


def resolve_device(device_str: str) -> torch.device:
    if device_str == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device_str)


def resolve_weights_path(args: argparse.Namespace) -> Path:
    if args.weights_path is not None:
        return args.weights_path.expanduser().resolve()
    data = json.loads(args.weights_manifest.read_text(encoding="utf-8"))
    return Path(str(data["weights_path"])).expanduser().resolve()


def build_model(weights_path: Path, device: torch.device) -> torch.nn.Module:
    ckpt_obj = torch.load(weights_path, map_location="cpu")
    state_dict = extract_state_dict(ckpt_obj)
    arch = infer_arch_from_state(state_dict)
    psf_path = extract_psf_path_from_ckpt(ckpt_obj)
    if psf_path is None or (not psf_path.exists()):
        psf_path = DEFAULT_PSF_PATH.resolve()
    model = GeoEdgeAlignSR_v1_v5_NoCoord(
        in_ch=arch["in_ch"],
        base=arch["base"],
        use_physics_layer=arch["use_physics_layer"],
        use_sigmoid_output=True,
        use_upsample_conv=True,
        use_band_limit=arch["use_band_limit"],
        psf_fitted_path=str(psf_path),
        psf_deconv_reg=float(arch["psf_deconv_reg"] if arch["psf_deconv_reg"] is not None else 10.0),
        psf_phys_alpha_init=float(arch["psf_phys_alpha_init"] if arch["psf_phys_alpha_init"] is not None else 0.10),
        weak_psf_enable=bool(arch["weak_psf_enable"]),
        weak_psf_k=int(arch["weak_psf_k"]),
        weak_psf_reg=float(arch["weak_psf_reg"] if arch["weak_psf_reg"] is not None else 30.0),
        weak_psf_beta_init=float(arch["weak_psf_beta_init"] if arch["weak_psf_beta_init"] is not None else 0.02),
        weak_psf_gating_temp=float(arch["weak_psf_gating_temp"] if arch["weak_psf_gating_temp"] is not None else 2.5),
        weak_psf_psf_temp=float(arch["weak_psf_psf_temp"] if arch["weak_psf_psf_temp"] is not None else 2.5),
        weak_psf_entropy_mix=float(arch["weak_psf_entropy_mix"] if arch["weak_psf_entropy_mix"] is not None else 0.0),
        weak_psf_lowfreq_ratio=float(arch["weak_psf_lowfreq_ratio"] if arch["weak_psf_lowfreq_ratio"] is not None else 0.25),
        weak_psf_beta_scale_max=float(arch["weak_psf_beta_scale_max"] if arch["weak_psf_beta_scale_max"] is not None else 0.35),
    ).to(device)
    model.eval()
    load_weights(model, state_dict, strict=False)
    return model


def load_image01(path: Path) -> torch.Tensor:
    raw, dtype = read_image_keep_dtype(path)
    x01 = normalize_to_01(raw, dtype)
    return torch.from_numpy(x01).unsqueeze(0).unsqueeze(0).float()


@torch.inference_mode()
def run_sr(model: torch.nn.Module, device: torch.device, img01: torch.Tensor) -> torch.Tensor:
    return model(img01.to(device)).clamp(0.0, 1.0).detach().cpu()


def edge_centroid_geom(img: torch.Tensor) -> Dict[str, float]:
    b, _, h, w = img.shape
    assert b == 1
    kx = torch.tensor(
        [[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]],
        dtype=img.dtype,
        device=img.device,
    ).view(1, 1, 3, 3)
    ky = torch.tensor(
        [[-1.0, -2.0, -1.0], [0.0, 0.0, 0.0], [1.0, 2.0, 1.0]],
        dtype=img.dtype,
        device=img.device,
    ).view(1, 1, 3, 3)
    gx = F.conv2d(img, kx, padding=1)
    gy = F.conv2d(img, ky, padding=1)
    edge = torch.sqrt(gx * gx + gy * gy + 1e-8)
    wmap = edge.clamp_min(1e-6)
    wsum = wmap.sum(dim=(2, 3), keepdim=True).clamp_min(1e-6)
    yy, xx = torch.meshgrid(
        torch.arange(h, device=img.device, dtype=img.dtype),
        torch.arange(w, device=img.device, dtype=img.dtype),
        indexing="ij",
    )
    xx = xx.view(1, 1, h, w)
    yy = yy.view(1, 1, h, w)
    cx = (wmap * xx).sum(dim=(2, 3), keepdim=True) / wsum
    cy = (wmap * yy).sum(dim=(2, 3), keepdim=True) / wsum
    rr = torch.sqrt((xx - cx) ** 2 + (yy - cy) ** 2 + 1e-6)
    mean_r = (wmap * rr).sum(dim=(2, 3), keepdim=True) / wsum
    var_r = (wmap * (rr - mean_r) ** 2).sum(dim=(2, 3), keepdim=True) / wsum
    thick = 2.0 * torch.sqrt(var_r + 1e-6)
    return {
        "cx": float(cx.item()),
        "cy": float(cy.item()),
        "mean_r": float(mean_r.item()),
        "thick": float(thick.item()),
    }


def edge_centroid_geom_batch(img: torch.Tensor) -> List[Dict[str, float]]:
    b, _, h, w = img.shape
    kx = torch.tensor(
        [[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]],
        dtype=img.dtype,
        device=img.device,
    ).view(1, 1, 3, 3)
    ky = torch.tensor(
        [[-1.0, -2.0, -1.0], [0.0, 0.0, 0.0], [1.0, 2.0, 1.0]],
        dtype=img.dtype,
        device=img.device,
    ).view(1, 1, 3, 3)
    gx = F.conv2d(img, kx, padding=1)
    gy = F.conv2d(img, ky, padding=1)
    edge = torch.sqrt(gx * gx + gy * gy + 1e-8)
    wmap = edge.clamp_min(1e-6)
    wsum = wmap.sum(dim=(2, 3), keepdim=True).clamp_min(1e-6)
    yy, xx = torch.meshgrid(
        torch.arange(h, device=img.device, dtype=img.dtype),
        torch.arange(w, device=img.device, dtype=img.dtype),
        indexing="ij",
    )
    xx = xx.view(1, 1, h, w)
    yy = yy.view(1, 1, h, w)
    cx = (wmap * xx).sum(dim=(2, 3), keepdim=True) / wsum
    cy = (wmap * yy).sum(dim=(2, 3), keepdim=True) / wsum
    rr = torch.sqrt((xx - cx) ** 2 + (yy - cy) ** 2 + 1e-6)
    mean_r = (wmap * rr).sum(dim=(2, 3), keepdim=True) / wsum
    var_r = (wmap * (rr - mean_r) ** 2).sum(dim=(2, 3), keepdim=True) / wsum
    thick = 2.0 * torch.sqrt(var_r + 1e-6)
    out = []
    for i in range(b):
        out.append(
            {
                "cx": float(cx[i].item()),
                "cy": float(cy[i].item()),
                "mean_r": float(mean_r[i].item()),
                "thick": float(thick[i].item()),
            }
        )
    return out


def algebraic_fit_geom(img: torch.Tensor) -> Dict[str, float]:
    b, _, h, w = img.shape
    assert b == 1
    yy, xx = torch.meshgrid(
        torch.arange(h, device=img.device, dtype=img.dtype),
        torch.arange(w, device=img.device, dtype=img.dtype),
        indexing="ij",
    )
    xx_flat = xx.reshape(-1)
    yy_flat = yy.reshape(-1)
    ec = edge_centroid_geom(img)
    try:
        w_i = img[0, 0].reshape(-1).clamp_min(0.0)
        w_sum = w_i.sum().clamp_min(1e-6)
        x = xx_flat
        y = yy_flat
        z = x * x + y * y
        wx = w_i * x
        wy = w_i * y
        Axx = (wx * x).sum()
        Axy = (wx * y).sum()
        Ax1 = wx.sum()
        Ayy = (wy * y).sum()
        Ay1 = wy.sum()
        A11 = w_sum
        ATA = torch.stack(
            [
                torch.stack([Axx, Axy, Ax1]),
                torch.stack([Axy, Ayy, Ay1]),
                torch.stack([Ax1, Ay1, A11]),
            ]
        )
        ATz = torch.stack([(wx * z).sum(), (wy * z).sum(), (w_i * z).sum()])
        coeffs = torch.linalg.solve(ATA, ATz)
        cx = 0.5 * coeffs[0]
        cy = 0.5 * coeffs[1]
        mean_r = torch.sqrt((cx ** 2 + cy ** 2 - coeffs[2]).clamp_min(1e-6))
        return {
            "cx": float(cx.item()),
            "cy": float(cy.item()),
            "mean_r": float(mean_r.item()),
            "thick": float(ec["thick"]),
        }
    except Exception:
        return ec


def get_stage_cfg(stage_id: int) -> DS.StageConfig:
    for cfg in DS.STAGES:
        if int(cfg.stage_id) == int(stage_id):
            return cfg
    raise KeyError(f"Unknown stage_id={stage_id}")


def capture_sequence_spec(cfg: DS.StageConfig, seq_start_idx: int, base_seed: int) -> Tuple[Dict[str, float], int]:
    saved: Dict[str, float] = {}
    original_ann = DS._sample_annulus_params
    original_def = DS._sample_annulus_edge_defect_spec

    def wrapped_ann(size_range, img_size):
        cx, cy, r_out, thickness = original_ann(size_range, img_size)
        saved.clear()
        saved.update(
            {
                "cx": float(cx),
                "cy": float(cy),
                "r_out": float(r_out),
                "r_in": float(r_out - thickness),
                "thickness": float(thickness),
                "kind": "annulus",
            }
        )
        return cx, cy, r_out, thickness

    def wrapped_def(size_range, img_size):
        spec = dict(original_def(size_range, img_size))
        spec["kind"] = "annulus_edge_defect"
        saved.clear()
        saved.update({k: float(v) if isinstance(v, (int, float)) else v for k, v in spec.items()})
        return spec

    DS._sample_annulus_params = wrapped_ann
    DS._sample_annulus_edge_defect_spec = wrapped_def
    try:
        _, _, ss = DS._render_stage_canvas(cfg, base_seed + int(seq_start_idx))
    finally:
        DS._sample_annulus_params = original_ann
        DS._sample_annulus_edge_defect_spec = original_def
    if not saved:
        raise RuntimeError(f"Failed to capture sequence spec for stage={cfg.name} seq_start_idx={seq_start_idx}")
    return saved, int(ss)


def true_geom_for_frame(cfg: DS.StageConfig, spec: Dict[str, float], ss: int, frame_idx: int) -> Dict[str, float]:
    seq_center = 0.5 * (int(cfg.sequence_length) - 1)
    offset = (float(frame_idx) - seq_center) * float(cfg.sequence_step_px)
    cx = float(spec["cx"]) / float(ss)
    cy = float(spec["cy"]) / float(ss)
    if str(cfg.sequence_axis).lower() == "x":
        cx += offset
    else:
        cy += offset
    mean_r = 0.5 * (float(spec["r_out"]) + float(spec["r_in"])) / float(ss)
    thick = (float(spec["r_out"]) - float(spec["r_in"])) / float(ss)
    return {"cx": cx, "cy": cy, "mean_r": mean_r, "thick": thick}


def collect_sequence_groups(stage_dir: Path, max_seqs: int = 0) -> List[List[Tuple[int, int, Path]]]:
    grouped: Dict[int, List[Tuple[int, int, Path]]] = {}
    for path in sorted(stage_dir.glob("*.tif")):
        m = SEQ_RE.search(path.name)
        if m is None:
            continue
        seq_id = int(m.group("seq"))
        frame_idx = int(m.group("frame"))
        img_idx = int(m.group("idx"))
        grouped.setdefault(seq_id, []).append((frame_idx, img_idx, path))
    out = []
    for seq_id in sorted(grouped):
        items = sorted(grouped[seq_id], key=lambda x: x[0])
        out.append(items)
        if max_seqs > 0 and len(out) >= max_seqs:
            break
    return out


def mean_or_nan(vals: List[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else float("nan")


def evaluate_rows(
    cfg: DS.StageConfig,
    clean_stage_dir: Path,
    convolved_stage_dir: Path,
    model: torch.nn.Module | None,
    device: torch.device,
    base_seed: int,
    max_seqs: int,
) -> List[StageRow]:
    rows: List[StageRow] = []
    groups = collect_sequence_groups(clean_stage_dir, max_seqs=max_seqs)
    domains = ["clean", "convolved"] + ([] if model is None else ["sr_round18"])
    estimators = ("edge_centroid", "algebraic_fit")
    for domain in domains:
        per_est = {
            name: {
                "abs_center": [],
                "delta_center": [],
                "step_err": [],
                "sign": [],
                "bias_x": [],
                "bias_y": [],
                "mean_r_err": [],
                "thick_err": [],
                "frame_count": 0,
                "pair_count": 0,
            }
            for name in estimators
        }
        for items in groups:
            seq_start_idx = int(items[0][1])
            spec, ss = capture_sequence_spec(cfg, seq_start_idx=seq_start_idx, base_seed=base_seed)
            est_frames: Dict[str, List[Dict[str, float]]] = {k: [] for k in estimators}
            true_frames: List[Dict[str, float]] = []
            clean_batch = torch.cat([load_image01(clean_path) for _, _, clean_path in items], dim=0)
            conv_batch = torch.cat([load_image01(convolved_stage_dir / clean_path.name) for _, _, clean_path in items], dim=0)
            if domain == "clean":
                batch = clean_batch
            elif domain == "convolved":
                batch = conv_batch
            else:
                batch = run_sr(model, device, conv_batch)

            edge_geoms = edge_centroid_geom_batch(batch)
            alg_geoms = [algebraic_fit_geom(batch[i : i + 1]) for i in range(batch.shape[0])]
            geom_bank = {
                "edge_centroid": edge_geoms,
                "algebraic_fit": alg_geoms,
            }

            for local_i, (frame_idx, _, _) in enumerate(items):
                truth = true_geom_for_frame(cfg, spec, ss=ss, frame_idx=frame_idx)
                true_frames.append(truth)
                for est_name in estimators:
                    geom = geom_bank[est_name][local_i]
                    est_frames[est_name].append(geom)
                    per_est[est_name]["abs_center"].append(
                        math.hypot(geom["cx"] - truth["cx"], geom["cy"] - truth["cy"])
                    )
                    per_est[est_name]["bias_x"].append(geom["cx"] - truth["cx"])
                    per_est[est_name]["bias_y"].append(geom["cy"] - truth["cy"])
                    per_est[est_name]["mean_r_err"].append(abs(geom["mean_r"] - truth["mean_r"]))
                    per_est[est_name]["thick_err"].append(abs(geom["thick"] - truth["thick"]))
                    per_est[est_name]["frame_count"] += 1

            for est_name in estimators:
                for i in range(len(items) - 1):
                    gt_a = true_frames[i]
                    gt_b = true_frames[i + 1]
                    pr_a = est_frames[est_name][i]
                    pr_b = est_frames[est_name][i + 1]
                    gt_dx = gt_b["cx"] - gt_a["cx"]
                    gt_dy = gt_b["cy"] - gt_a["cy"]
                    pr_dx = pr_b["cx"] - pr_a["cx"]
                    pr_dy = pr_b["cy"] - pr_a["cy"]
                    per_est[est_name]["delta_center"].append(math.hypot(pr_dx - gt_dx, pr_dy - gt_dy))
                    use_y = abs(gt_dy) >= abs(gt_dx)
                    gt_step = gt_dy if use_y else gt_dx
                    pr_step = pr_dy if use_y else pr_dx
                    per_est[est_name]["step_err"].append(abs(pr_step - gt_step) / max(abs(gt_step), 0.08))
                    if abs(gt_step) <= 0.02:
                        per_est[est_name]["sign"].append(0.5)
                    else:
                        per_est[est_name]["sign"].append(1.0 if (pr_step * gt_step) > 0.0 else 0.0)
                    per_est[est_name]["pair_count"] += 1

        for est_name, metrics in per_est.items():
            rows.append(
                StageRow(
                    stage_id=int(cfg.stage_id),
                    stage_name=str(cfg.name),
                    scale_px=float(cfg.sequence_step_px),
                    domain=domain,
                    estimator=est_name,
                    truth_source="generator_replay",
                    frame_count=int(metrics["frame_count"]),
                    pair_count=int(metrics["pair_count"]),
                    abs_center_err_px=mean_or_nan(metrics["abs_center"]),
                    delta_center_err_px=mean_or_nan(metrics["delta_center"]),
                    step_err_rel=mean_or_nan(metrics["step_err"]),
                    sign_acc=mean_or_nan(metrics["sign"]),
                    center_bias_x_px=mean_or_nan(metrics["bias_x"]),
                    center_bias_y_px=mean_or_nan(metrics["bias_y"]),
                    mean_r_err_px=mean_or_nan(metrics["mean_r_err"]),
                    thick_err_px=mean_or_nan(metrics["thick_err"]),
                )
            )
    return rows


def aggregate_rows(rows: List[StageRow]) -> List[dict]:
    groups: Dict[Tuple[float, str, str], List[StageRow]] = {}
    for row in rows:
        groups.setdefault((row.scale_px, row.domain, row.estimator), []).append(row)
    out = []
    for (scale_px, domain, estimator), items in sorted(groups.items()):
        def _wmean(key: str) -> float:
            vals = []
            for row in items:
                weight = row.pair_count if key in {"delta_center_err_px", "step_err_rel", "sign_acc"} else row.frame_count
                if weight <= 0:
                    continue
                vals.append((getattr(row, key), weight))
            if not vals:
                return float("nan")
            num = sum(v * w for v, w in vals)
            den = sum(w for _, w in vals)
            return float(num / den)

        out.append(
            {
                "scale_px": float(scale_px),
                "scale_label": SCALE_LABELS.get(float(scale_px), str(scale_px)),
                "domain": domain,
                "estimator": estimator,
                "stages": [row.stage_name for row in items],
                "frame_count": int(sum(row.frame_count for row in items)),
                "pair_count": int(sum(row.pair_count for row in items)),
                "abs_center_err_px": _wmean("abs_center_err_px"),
                "delta_center_err_px": _wmean("delta_center_err_px"),
                "step_err_rel": _wmean("step_err_rel"),
                "sign_acc": _wmean("sign_acc"),
                "center_bias_x_px": _wmean("center_bias_x_px"),
                "center_bias_y_px": _wmean("center_bias_y_px"),
                "mean_r_err_px": _wmean("mean_r_err_px"),
                "thick_err_px": _wmean("thick_err_px"),
                "truth_source": "generator_replay",
            }
        )
    return out


def choose_branch(agg: List[dict]) -> dict:
    def _row(scale_px: float, domain: str, estimator: str) -> dict:
        for row in agg:
            if float(row["scale_px"]) == float(scale_px) and row["domain"] == domain and row["estimator"] == estimator:
                return row
        raise KeyError((scale_px, domain, estimator))

    clean_ec = _row(0.8, "clean", "edge_centroid")
    clean_af = _row(0.8, "clean", "algebraic_fit")
    conv_ec = _row(0.8, "convolved", "edge_centroid")
    conv_af = _row(0.8, "convolved", "algebraic_fit")
    sr_ec = _row(0.8, "sr_round18", "edge_centroid")
    sr_af = _row(0.8, "sr_round18", "algebraic_fit")

    af_gain_clean = float(clean_ec["abs_center_err_px"] - clean_af["abs_center_err_px"])
    af_gain_conv = float(conv_ec["abs_center_err_px"] - conv_af["abs_center_err_px"])
    best_clean_center = float(min(clean_ec["abs_center_err_px"], clean_af["abs_center_err_px"]))
    best_conv_center = float(min(conv_ec["abs_center_err_px"], conv_af["abs_center_err_px"]))
    best_clean_delta = float(min(clean_ec["delta_center_err_px"], clean_af["delta_center_err_px"]))
    best_conv_delta = float(min(conv_ec["delta_center_err_px"], conv_af["delta_center_err_px"]))
    sr_penalty_best = float(min(sr_ec["abs_center_err_px"], sr_af["abs_center_err_px"]) - best_conv_center)

    # If the estimator is already badly misaligned on clean/convolved, fix it before
    # touching labels or adding more training rounds.
    estimator_floor_present = (
        (best_clean_center > 20.0)
        or (best_conv_center > 20.0)
        or (best_clean_delta > 0.5)
        or (best_conv_delta > 0.5)
    )
    af_material_gain = (af_gain_clean >= 0.03) or (af_gain_conv >= 0.03)
    estimator_bias = bool(estimator_floor_present or af_material_gain)
    sr_mismatch = sr_penalty_best >= 0.03

    if estimator_floor_present and sr_mismatch:
        branch = "Branch E then L"
        rationale = "Current estimators are already misaligned on clean/convolved, and SR adds extra error on top."
    elif estimator_floor_present:
        branch = "Branch E"
        rationale = "Current estimators already fail on clean/convolved against generator truth, so estimator alignment must be fixed first."
    elif estimator_bias:
        branch = "Branch E"
        rationale = "Algebraic-fit shows a material gain over edge-centroid on clean/convolved, so estimator-side work should lead."
    else:
        branch = "Branch L"
        rationale = "Estimator gap on clean/convolved is small; remaining error is more likely target/label alignment on SR."

    return {
        "primary_scale_px": 0.8,
        "af_gain_clean": af_gain_clean,
        "af_gain_convolved": af_gain_conv,
        "best_clean_center_err": best_clean_center,
        "best_convolved_center_err": best_conv_center,
        "best_clean_delta_center_err": best_clean_delta,
        "best_convolved_delta_center_err": best_conv_delta,
        "best_sr_minus_best_convolved": sr_penalty_best,
        "estimator_floor_present": bool(estimator_floor_present),
        "estimator_bias_present": bool(estimator_bias),
        "sr_mismatch_present": bool(sr_mismatch),
        "recommended_branch": branch,
        "rationale": rationale,
    }


def write_outputs(output_root: Path, weights_path: Path, raw_rows: List[StageRow], agg_rows: List[dict], decision: dict) -> Tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    raw_json = output_root / f"DIAGNOSTIC_MATRIX_RAW_{ts}.json"
    summary_json = output_root / f"DIAGNOSTIC_MATRIX_SUMMARY_{ts}.json"
    summary_md = output_root / f"DIAGNOSTIC_MATRIX_SUMMARY_{ts}.md"

    raw_payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "weights_path": str(weights_path),
        "rows": [row.__dict__ for row in raw_rows],
    }
    raw_json.write_text(json.dumps(raw_payload, indent=2), encoding="utf-8")

    summary_payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "weights_path": str(weights_path),
        "aggregated_rows": agg_rows,
        "decision": decision,
        "truth_source_note": "Absolute center truth is replayed from the deterministic synthetic generator, not inferred from the clean raster.",
    }
    summary_json.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    lines = [
        "# Diagnostic Matrix Summary",
        f"- generated_at: {summary_payload['generated_at']}",
        f"- weights_path: `{weights_path}`",
        "- truth_source: generator_replay",
        f"- recommended_branch: **{decision['recommended_branch']}**",
        f"- rationale: {decision['rationale']}",
        "",
        "| scale | domain | estimator | abs_center_err_px | delta_center_err_px | step_err_rel | sign_acc | bias_x | bias_y | frames | pairs |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in agg_rows:
        lines.append(
            f"| {row['scale_label']} | {row['domain']} | {row['estimator']} | "
            f"{row['abs_center_err_px']:.4f} | {row['delta_center_err_px']:.4f} | "
            f"{row['step_err_rel']:.4f} | {row['sign_acc']:.4f} | "
            f"{row['center_bias_x_px']:.4f} | {row['center_bias_y_px']:.4f} | "
            f"{row['frame_count']} | {row['pair_count']} |"
        )
    lines.extend(
        [
            "",
            "## Decision Signals",
            f"- af_gain_clean: {decision['af_gain_clean']:.4f}",
            f"- af_gain_convolved: {decision['af_gain_convolved']:.4f}",
            f"- best_sr_minus_best_convolved: {decision['best_sr_minus_best_convolved']:.4f}",
            f"- estimator_bias_present: {decision['estimator_bias_present']}",
            f"- sr_mismatch_present: {decision['sr_mismatch_present']}",
        ]
    )
    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_json, summary_md


def main() -> None:
    args = parse_args()
    stage_ids = [int(x.strip()) for x in str(args.stage_ids).split(",") if x.strip()]
    device = resolve_device(args.device)
    weights_path = resolve_weights_path(args)
    print(f"[DIAG] device={device}")
    print(f"[DIAG] weights={weights_path}")
    model = None if args.skip_sr else build_model(weights_path, device)
    raw_rows: List[StageRow] = []
    for stage_id in stage_ids:
        cfg = get_stage_cfg(stage_id)
        clean_dir = PROJECT_ROOT / "Training_Data" / "generated" / cfg.name
        conv_dir = PROJECT_ROOT / "Training_Data" / "generated_convolved" / cfg.name
        print(f"[DIAG] stage={cfg.stage_id} {cfg.name} scale={cfg.sequence_step_px}")
        raw_rows.extend(
            evaluate_rows(
                cfg=cfg,
                clean_stage_dir=clean_dir,
                convolved_stage_dir=conv_dir,
                model=model,
                device=device,
                base_seed=int(args.base_seed),
                max_seqs=int(args.max_seqs_per_stage),
            )
        )
    agg_rows = aggregate_rows(raw_rows)
    decision = choose_branch(agg_rows)
    summary_json, summary_md = write_outputs(args.output_root, weights_path, raw_rows, agg_rows, decision)
    print(f"[DIAG] summary_json={summary_json}")
    print(f"[DIAG] summary_md={summary_md}")
    print(f"[DIAG] recommended_branch={decision['recommended_branch']}")


if __name__ == "__main__":
    main()
