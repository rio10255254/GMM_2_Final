import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import torch
import torch.nn.functional as F


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "Experiments" / "Legacy" / "organized_20260314" / "branch_e" / "benchmark"
DEFAULT_SEED_MANIFEST = (
    PROJECT_ROOT
    / "Experiments"
    / "Legacy"
    / "organized_20260313"
    / "round18"
    / "selected"
    / "current_centerpush_seed.json"
)

if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

import GeoEdgeAlignSR_v1_DiagnosticMatrix as dm  # noqa: E402


ESTIMATOR_META = {
    "edge_centroid": {
        "trainable": True,
        "probe_candidate": "be_ctrl_edge",
        "label": "control edge-centroid",
    },
    "soft_centroid": {
        "trainable": True,
        "probe_candidate": "be_soft",
        "label": "soft-centroid",
    },
    "edge_band_refine": {
        "trainable": True,
        "probe_candidate": "be_edge_band",
        "label": "edge-band refine",
    },
    "soft_band_refine": {
        "trainable": True,
        "probe_candidate": "be_soft_band",
        "label": "soft-band refine",
    },
    "edge_algebraic_fit": {
        "trainable": True,
        "probe_candidate": "be_edge_algfit",
        "label": "edge-algebraic fit",
    },
    "algebraic_fit_raw": {
        "trainable": False,
        "probe_candidate": "",
        "label": "raw algebraic fit reference",
    },
}


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
    p.add_argument("--top-k-trainable", type=int, default=3)
    return p.parse_args()


def _coord_grid(x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    _, _, h, w = x.shape
    yy, xx = torch.meshgrid(
        torch.arange(h, device=x.device, dtype=x.dtype),
        torch.arange(w, device=x.device, dtype=x.dtype),
        indexing="ij",
    )
    return xx.view(1, 1, h, w), yy.view(1, 1, h, w)


def _edge_mag(x: torch.Tensor) -> torch.Tensor:
    dx = x[:, :, :, 1:] - x[:, :, :, :-1]
    dy = x[:, :, 1:, :] - x[:, :, :-1, :]
    dx = F.pad(dx, (0, 1, 0, 0))
    dy = F.pad(dy, (0, 0, 0, 1))
    return torch.sqrt(dx * dx + dy * dy + 1e-8)


def _sobel_edge(x: torch.Tensor) -> torch.Tensor:
    kx = torch.tensor(
        [[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]],
        dtype=x.dtype,
        device=x.device,
    ).view(1, 1, 3, 3)
    ky = torch.tensor(
        [[-1.0, -2.0, -1.0], [0.0, 0.0, 0.0], [1.0, 2.0, 1.0]],
        dtype=x.dtype,
        device=x.device,
    ).view(1, 1, 3, 3)
    gx = F.conv2d(x, kx, padding=1)
    gy = F.conv2d(x, ky, padding=1)
    return torch.sqrt(gx * gx + gy * gy + 1e-8)


def _moment_geom_tensor(wmap: torch.Tensor) -> Dict[str, torch.Tensor]:
    xx, yy = _coord_grid(wmap)
    wsum = wmap.sum(dim=(2, 3), keepdim=True).clamp_min(1e-6)
    cx = (wmap * xx).sum(dim=(2, 3), keepdim=True) / wsum
    cy = (wmap * yy).sum(dim=(2, 3), keepdim=True) / wsum
    rr = torch.sqrt((xx - cx) ** 2 + (yy - cy) ** 2 + 1e-6)
    mean_r = (wmap * rr).sum(dim=(2, 3), keepdim=True) / wsum
    var_r = (wmap * (rr - mean_r) ** 2).sum(dim=(2, 3), keepdim=True) / wsum
    thick = 2.0 * torch.sqrt(var_r + 1e-6)
    return {"cx": cx, "cy": cy, "mean_r": mean_r, "thick": thick}


def _tensor_geom_to_list(geom: Dict[str, torch.Tensor]) -> List[Dict[str, float]]:
    b = int(geom["cx"].shape[0])
    out: List[Dict[str, float]] = []
    for i in range(b):
        out.append(
            {
                "cx": float(geom["cx"][i].item()),
                "cy": float(geom["cy"][i].item()),
                "mean_r": float(geom["mean_r"][i].item()),
                "thick": float(geom["thick"][i].item()),
            }
        )
    return out


def _band_refine_tensor(base_wmap: torch.Tensor) -> Dict[str, torch.Tensor]:
    base = base_wmap.clamp_min(1e-6)
    rough = _moment_geom_tensor(base)
    xx, yy = _coord_grid(base)
    rr = torch.sqrt((xx - rough["cx"]) ** 2 + (yy - rough["cy"]) ** 2 + 1e-6)
    sigma = (0.5 * rough["thick"]).clamp_min(1.5)
    band = torch.exp(-0.5 * ((rr - rough["mean_r"]) / sigma) ** 2)
    refined = (base * band).clamp_min(1e-6)
    return _moment_geom_tensor(refined)


def _taubin_from_weight_batch(
    weight_map: torch.Tensor,
    fallback_geom: Dict[str, torch.Tensor],
) -> List[Dict[str, float]]:
    b, _, h, w = weight_map.shape
    yy, xx = torch.meshgrid(
        torch.arange(h, device=weight_map.device, dtype=weight_map.dtype),
        torch.arange(w, device=weight_map.device, dtype=weight_map.dtype),
        indexing="ij",
    )
    xx_flat = xx.reshape(-1)
    yy_flat = yy.reshape(-1)
    out: List[Dict[str, float]] = []
    for i in range(b):
        try:
            w_i = weight_map[i, 0].reshape(-1).clamp_min(0.0)
            w_sum = w_i.sum().clamp_min(1e-6)
            x = xx_flat
            y = yy_flat
            z = x * x + y * y
            wx = w_i * x
            wy = w_i * y
            a_xx = (wx * x).sum()
            a_xy = (wx * y).sum()
            a_x1 = wx.sum()
            a_yy = (wy * y).sum()
            a_y1 = wy.sum()
            a_11 = w_sum
            ata = torch.stack(
                [
                    torch.stack([a_xx, a_xy, a_x1]),
                    torch.stack([a_xy, a_yy, a_y1]),
                    torch.stack([a_x1, a_y1, a_11]),
                ]
            )
            atz = torch.stack([(wx * z).sum(), (wy * z).sum(), (w_i * z).sum()])
            coeffs = torch.linalg.solve(ata, atz)
            cx = 0.5 * coeffs[0]
            cy = 0.5 * coeffs[1]
            mean_r = torch.sqrt((cx ** 2 + cy ** 2 - coeffs[2]).clamp_min(1e-6))
            out.append(
                {
                    "cx": float(cx.item()),
                    "cy": float(cy.item()),
                    "mean_r": float(mean_r.item()),
                    "thick": float(fallback_geom["thick"][i].item()),
                }
            )
        except Exception:
            out.append(
                {
                    "cx": float(fallback_geom["cx"][i].item()),
                    "cy": float(fallback_geom["cy"][i].item()),
                    "mean_r": float(fallback_geom["mean_r"][i].item()),
                    "thick": float(fallback_geom["thick"][i].item()),
                }
            )
    return out


def build_geom_bank(batch: torch.Tensor) -> Dict[str, List[Dict[str, float]]]:
    edge_centroid = _moment_geom_tensor(_sobel_edge(batch).clamp_min(1e-6))
    soft_centroid = _moment_geom_tensor((_edge_mag(batch) + 0.10 * batch.abs()).clamp_min(1e-6))
    edge_band = _band_refine_tensor(_sobel_edge(batch).clamp_min(1e-6))
    soft_band = _band_refine_tensor((_edge_mag(batch) + 0.10 * batch.abs()).clamp_min(1e-6))
    raw_alg = _taubin_from_weight_batch(batch.clamp_min(1e-6), edge_centroid)
    edge_alg = _taubin_from_weight_batch(_sobel_edge(batch).clamp_min(1e-6), edge_centroid)
    return {
        "edge_centroid": _tensor_geom_to_list(edge_centroid),
        "soft_centroid": _tensor_geom_to_list(soft_centroid),
        "edge_band_refine": _tensor_geom_to_list(edge_band),
        "soft_band_refine": _tensor_geom_to_list(soft_band),
        "edge_algebraic_fit": edge_alg,
        "algebraic_fit_raw": raw_alg,
    }


def evaluate_rows(
    cfg,
    clean_stage_dir: Path,
    convolved_stage_dir: Path,
    model: torch.nn.Module | None,
    device: torch.device,
    base_seed: int,
    max_seqs: int,
) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    groups = dm.collect_sequence_groups(clean_stage_dir, max_seqs=max_seqs)
    domains = ["clean", "convolved"] + ([] if model is None else ["sr_round18"])
    estimators = tuple(ESTIMATOR_META.keys())
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
            spec, ss = dm.capture_sequence_spec(cfg, seq_start_idx=seq_start_idx, base_seed=base_seed)
            true_frames: List[Dict[str, float]] = []
            est_frames: Dict[str, List[Dict[str, float]]] = {name: [] for name in estimators}
            clean_batch = torch.cat([dm.load_image01(clean_path) for _, _, clean_path in items], dim=0)
            conv_batch = torch.cat([dm.load_image01(convolved_stage_dir / clean_path.name) for _, _, clean_path in items], dim=0)
            if domain == "clean":
                batch = clean_batch
            elif domain == "convolved":
                batch = conv_batch
            else:
                batch = dm.run_sr(model, device, conv_batch)
            geom_bank = build_geom_bank(batch)
            for local_i, (frame_idx, _, _) in enumerate(items):
                truth = dm.true_geom_for_frame(cfg, spec, ss=ss, frame_idx=frame_idx)
                true_frames.append(truth)
                for est_name in estimators:
                    geom = geom_bank[est_name][local_i]
                    est_frames[est_name].append(geom)
                    per_est[est_name]["abs_center"].append(math.hypot(geom["cx"] - truth["cx"], geom["cy"] - truth["cy"]))
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
                {
                    "stage_id": int(cfg.stage_id),
                    "stage_name": str(cfg.name),
                    "scale_px": float(cfg.sequence_step_px),
                    "scale_label": dm.SCALE_LABELS.get(float(cfg.sequence_step_px), str(cfg.sequence_step_px)),
                    "domain": domain,
                    "estimator": est_name,
                    "frame_count": int(metrics["frame_count"]),
                    "pair_count": int(metrics["pair_count"]),
                    "abs_center_err_px": dm.mean_or_nan(metrics["abs_center"]),
                    "delta_center_err_px": dm.mean_or_nan(metrics["delta_center"]),
                    "step_err_rel": dm.mean_or_nan(metrics["step_err"]),
                    "sign_acc": dm.mean_or_nan(metrics["sign"]),
                    "center_bias_x_px": dm.mean_or_nan(metrics["bias_x"]),
                    "center_bias_y_px": dm.mean_or_nan(metrics["bias_y"]),
                    "mean_r_err_px": dm.mean_or_nan(metrics["mean_r_err"]),
                    "thick_err_px": dm.mean_or_nan(metrics["thick_err"]),
                }
            )
    return rows


def aggregate_rows(rows: List[Dict[str, float]]) -> List[dict]:
    groups: Dict[Tuple[float, str, str], List[Dict[str, float]]] = {}
    for row in rows:
        groups.setdefault((float(row["scale_px"]), str(row["domain"]), str(row["estimator"])), []).append(row)
    out: List[dict] = []
    for (scale_px, domain, estimator), items in sorted(groups.items()):
        def _wmean(key: str) -> float:
            vals = []
            for row in items:
                weight = row["pair_count"] if key in {"delta_center_err_px", "step_err_rel", "sign_acc"} else row["frame_count"]
                if weight <= 0:
                    continue
                vals.append((float(row[key]), int(weight)))
            if not vals:
                return float("nan")
            return float(sum(v * w for v, w in vals) / sum(w for _, w in vals))

        out.append(
            {
                "scale_px": float(scale_px),
                "scale_label": dm.SCALE_LABELS.get(float(scale_px), str(scale_px)),
                "domain": domain,
                "estimator": estimator,
                "trainable": bool(ESTIMATOR_META[estimator]["trainable"]),
                "probe_candidate": str(ESTIMATOR_META[estimator]["probe_candidate"]),
                "frame_count": int(sum(int(row["frame_count"]) for row in items)),
                "pair_count": int(sum(int(row["pair_count"]) for row in items)),
                "abs_center_err_px": _wmean("abs_center_err_px"),
                "delta_center_err_px": _wmean("delta_center_err_px"),
                "step_err_rel": _wmean("step_err_rel"),
                "sign_acc": _wmean("sign_acc"),
                "center_bias_x_px": _wmean("center_bias_x_px"),
                "center_bias_y_px": _wmean("center_bias_y_px"),
                "mean_r_err_px": _wmean("mean_r_err_px"),
                "thick_err_px": _wmean("thick_err_px"),
            }
        )
    return out


def choose_probe_candidates(agg_rows: List[dict], top_k: int) -> dict:
    def _row(scale_px: float, domain: str, estimator: str) -> dict | None:
        for row in agg_rows:
            if float(row["scale_px"]) == float(scale_px) and row["domain"] == domain and row["estimator"] == estimator:
                return row
        return None

    scored = []
    for estimator, meta in ESTIMATOR_META.items():
        clean = _row(0.8, "clean", estimator)
        conv = _row(0.8, "convolved", estimator)
        sr = _row(0.8, "sr_round18", estimator)
        if clean is None or conv is None:
            raise KeyError((0.8, "clean/convolved", estimator))
        avg_abs = 0.5 * (float(clean["abs_center_err_px"]) + float(conv["abs_center_err_px"]))
        avg_delta = 0.5 * (float(clean["delta_center_err_px"]) + float(conv["delta_center_err_px"]))
        avg_step = 0.5 * (float(clean["step_err_rel"]) + float(conv["step_err_rel"]))
        avg_sign = 0.5 * (float(clean["sign_acc"]) + float(conv["sign_acc"]))
        sr_gap = (
            float(sr["abs_center_err_px"]) - float(conv["abs_center_err_px"])
            if sr is not None
            else float("nan")
        )
        scored.append(
            {
                "estimator": estimator,
                "trainable": bool(meta["trainable"]),
                "probe_candidate": str(meta["probe_candidate"]),
                "label": str(meta["label"]),
                "avg_clean_conv_abs_center_err_px": avg_abs,
                "avg_clean_conv_delta_center_err_px": avg_delta,
                "avg_clean_conv_step_err_rel": avg_step,
                "avg_clean_conv_sign_acc": avg_sign,
                "sr_minus_convolved_abs_center_err_px": sr_gap,
            }
        )

    control = next(row for row in scored if row["estimator"] == "edge_centroid")
    non_control = [
        row for row in scored
        if row["trainable"] and row["probe_candidate"] and row["estimator"] != "edge_centroid"
    ]
    non_control.sort(
        key=lambda row: (
            row["avg_clean_conv_abs_center_err_px"],
            row["avg_clean_conv_delta_center_err_px"],
            row["avg_clean_conv_step_err_rel"],
            -row["avg_clean_conv_sign_acc"],
        )
    )
    chosen = [control["probe_candidate"]]
    chosen.extend(row["probe_candidate"] for row in non_control[: max(1, int(top_k))])
    best_non_control = non_control[0] if non_control else control
    return {
        "control_estimator": control["estimator"],
        "control_probe_candidate": control["probe_candidate"],
        "best_non_control_estimator": best_non_control["estimator"],
        "best_non_control_probe_candidate": best_non_control["probe_candidate"],
        "chosen_probe_candidates": chosen,
        "estimator_ranking_0p8_clean_conv": scored,
        "non_control_improvement_vs_edge_abs_px": (
            control["avg_clean_conv_abs_center_err_px"] - best_non_control["avg_clean_conv_abs_center_err_px"]
        ),
        "selection_policy": "0.8px clean+convolved avg abs_center_err primary, delta_center secondary, step_err tertiary, sign_acc tie-breaker",
    }


def write_outputs(output_root: Path, weights_path: Path, raw_rows: List[Dict[str, float]], agg_rows: List[dict], decision: dict) -> Tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    raw_json = output_root / f"BRANCH_E_ESTIMATOR_BENCHMARK_RAW_{ts}.json"
    summary_json = output_root / f"BRANCH_E_ESTIMATOR_BENCHMARK_SUMMARY_{ts}.json"
    summary_md = output_root / f"BRANCH_E_ESTIMATOR_BENCHMARK_SUMMARY_{ts}.md"
    raw_json.write_text(
        json.dumps(
            {
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "weights_path": str(weights_path),
                "rows": raw_rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    summary_payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "weights_path": str(weights_path),
        "aggregated_rows": agg_rows,
        "decision": decision,
    }
    summary_json.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    lines = [
        "# Branch E Estimator Benchmark Summary",
        "",
        f"- generated_at: {summary_payload['generated_at']}",
        f"- weights_path: `{weights_path}`",
        f"- chosen_probe_candidates: `{', '.join(decision['chosen_probe_candidates'])}`",
        f"- best_non_control_estimator: `{decision['best_non_control_estimator']}`",
        f"- improvement_vs_edge_abs_px: {decision['non_control_improvement_vs_edge_abs_px']:.4f}",
        f"- selection_policy: {decision['selection_policy']}",
        "",
        "| scale | domain | estimator | abs_center_err_px | delta_center_err_px | step_err_rel | sign_acc | bias_x | bias_y | trainable |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in agg_rows:
        lines.append(
            f"| {row['scale_label']} | {row['domain']} | {row['estimator']} | "
            f"{row['abs_center_err_px']:.4f} | {row['delta_center_err_px']:.4f} | "
            f"{row['step_err_rel']:.4f} | {row['sign_acc']:.4f} | "
            f"{row['center_bias_x_px']:.4f} | {row['center_bias_y_px']:.4f} | "
            f"{int(row['trainable'])} |"
        )
    lines.extend(
        [
            "",
            "## 0.8px Clean/Convolved Ranking",
            "",
            "| estimator | trainable | probe_candidate | avg_abs | avg_delta | avg_step | avg_sign | sr_gap |",
            "|---|---:|---|---:|---:|---:|---:|---:|",
        ]
    )
    ranking = sorted(
        decision["estimator_ranking_0p8_clean_conv"],
        key=lambda row: (
            row["avg_clean_conv_abs_center_err_px"],
            row["avg_clean_conv_delta_center_err_px"],
            row["avg_clean_conv_step_err_rel"],
            -row["avg_clean_conv_sign_acc"],
        ),
    )
    for row in ranking:
        lines.append(
            f"| {row['estimator']} | {int(row['trainable'])} | {row['probe_candidate'] or '-'} | "
            f"{row['avg_clean_conv_abs_center_err_px']:.4f} | {row['avg_clean_conv_delta_center_err_px']:.4f} | "
            f"{row['avg_clean_conv_step_err_rel']:.4f} | {row['avg_clean_conv_sign_acc']:.4f} | "
            f"{row['sr_minus_convolved_abs_center_err_px']:.4f} |"
        )
    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_json, summary_md


def main() -> None:
    args = parse_args()
    stage_ids = [int(x.strip()) for x in str(args.stage_ids).split(",") if x.strip()]
    device = dm.resolve_device(args.device)
    weights_path = dm.resolve_weights_path(args)
    print(f"[BRANCH_E][BENCH] device={device}")
    print(f"[BRANCH_E][BENCH] weights={weights_path}")
    model = None if args.skip_sr else dm.build_model(weights_path, device)
    raw_rows: List[Dict[str, float]] = []
    for stage_id in stage_ids:
        cfg = dm.get_stage_cfg(stage_id)
        clean_dir = PROJECT_ROOT / "Training_Data" / "generated" / cfg.name
        conv_dir = PROJECT_ROOT / "Training_Data" / "generated_convolved" / cfg.name
        print(f"[BRANCH_E][BENCH] stage={cfg.stage_id} {cfg.name} scale={cfg.sequence_step_px}")
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
    decision = choose_probe_candidates(agg_rows, top_k=int(args.top_k_trainable))
    summary_json, summary_md = write_outputs(args.output_root, weights_path, raw_rows, agg_rows, decision)
    print(f"[BRANCH_E][BENCH] summary_json={summary_json}")
    print(f"[BRANCH_E][BENCH] summary_md={summary_md}")
    print(f"[BRANCH_E][BENCH] chosen_probe_candidates={','.join(decision['chosen_probe_candidates'])}")


if __name__ == "__main__":
    main()
