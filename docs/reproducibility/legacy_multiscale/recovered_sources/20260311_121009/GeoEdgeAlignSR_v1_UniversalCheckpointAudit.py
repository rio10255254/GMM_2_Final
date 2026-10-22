import argparse
import copy
import importlib.util
import json
import math
import sys
import time
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = PROJECT_ROOT / "Model" / "GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py"

SEQ_STAGE_DIRS = (
    "stage_19_annulus_microstep_sequence_clean",
    "stage_20_annulus_microstep_sequence_defect",
    "stage_21_annulus_gmf_sequence_clean",
    "stage_22_annulus_gmf_sequence_defect",
    "stage_23_annulus_gmf_sequence_mid_clean",
    "stage_24_annulus_gmf_sequence_mid_defect",
    "stage_25_annulus_gmf_sequence_macro_clean",
    "stage_26_annulus_gmf_sequence_macro_defect",
)

SCALES = (0.08, 0.8, 8.0)


def _load_train_module():
    spec = importlib.util.spec_from_file_location("gesr_train_audit_mod", TRAIN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load training module from {TRAIN_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _safe_float(v, default=float("nan")):
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _restore_cfg(train_mod, snapshot: dict):
    for k, v in snapshot.items():
        setattr(train_mod.CFG, k, copy.deepcopy(v))


def _apply_common_eval_cfg(train_mod, *, checkpoint_path: str, expect_dy: float, run_label: str):
    cfg = train_mod.CFG
    cfg.LOAD_MODEL = True
    cfg.PRETRAINED_PATH = str(checkpoint_path)
    cfg.LOAD_RESET_OPTIMIZER = True
    cfg.LOAD_RESET_EPOCH = True
    cfg.SEED_DETERMINISTIC = True
    cfg.REPRO_MODE = True
    cfg.REPRO_DETERMINISTIC = True
    cfg.REPRO_NUM_WORKERS = 0
    cfg.NUM_WORKERS = 0
    cfg.GMF_VALIDATE_ENABLE = False
    cfg.GMF_VALIDATE_SOURCE = "seq_val"
    cfg.GMF_EXPECT_DX_PX = 0.0
    cfg.GMF_EXPECT_DY_PX = float(expect_dy)
    cfg.SEQ_ENABLE = False
    cfg.SEQ_VAL_ENABLE = True
    cfg.SEQ_VAL_INCLUDE_SUBDIRS = SEQ_STAGE_DIRS
    cfg.SEQ_VAL_BATCH_SIZE = 2
    cfg.SEQ_VAL_MAX_PAIRS = 160
    cfg.SEQ_VAL_ANNULUS_ENABLE = True
    cfg.SEQ_VAL_SIGN_Q = 0.85
    cfg.SIMPLETEST_MODE = True
    cfg.SIMPLETEST_MAX_EPOCH = 0
    cfg.NUM_EPOCH = 0
    cfg.SEED_SWEEP_ENABLE = False
    cfg.SAVE_MONITOR_EVERY_EPOCH = False
    cfg.SAVE_LAST_GOOD_TO_DISK = False
    cfg.TERMINAL_MINIMAL = True
    cfg.MODEL_NAME = str(run_label)
    train_mod.MODEL_NAME_BASE = str(run_label)
    train_mod.RUN_TAG_BASE = str(run_label)
    train_mod.RUN_TAG = str(run_label)


def _per_scale_deploy_score(summary: dict, scale: float) -> float:
    ann_score = _safe_float(summary.get("best_ann_seq_score"), -1.0)
    ann_sign = _safe_float(summary.get("best_ann_seq_sign_acc"), 0.0)
    ann_step = _safe_float(summary.get("best_ann_seq_step_err_rel"), 10.0)
    ann_center = _safe_float(summary.get("best_ann_seq_center_err_px"), 10.0)
    ann_thick = _safe_float(summary.get("best_ann_seq_thickness_err_rel"), 10.0)
    seq_score = _safe_float(summary.get("best_seq_val_score"), -1.0)
    seq_sign = _safe_float(summary.get("best_seq_val_sign_acc"), 0.0)

    score = (
        42.0 * ann_score
        + 14.0 * ann_sign
        - 18.0 * ann_step
        - 5.0 * ann_center
        - 14.0 * ann_thick
        + 8.0 * seq_score
        + 6.0 * seq_sign
    )

    if scale >= 7.5:
        if ann_sign < 0.78:
            score -= 40.0
        if seq_sign < 0.58:
            score -= 28.0
        if ann_center > 0.42:
            score -= 35.0
        if ann_step > 0.52:
            score -= 35.0
    elif scale >= 0.5:
        if ann_sign < 0.78:
            score -= 45.0
        if seq_sign < 0.58:
            score -= 32.0
        if ann_center > 0.42:
            score -= 40.0
        if ann_step > 0.52:
            score -= 40.0
    else:
        if ann_sign < 0.72:
            score -= 15.0
        if ann_center > 0.45:
            score -= 12.0

    return float(score)


def _deployment_score(scale_rows: dict) -> float:
    s008 = scale_rows[0.08]["deploy_scale_score"]
    s08 = scale_rows[0.8]["deploy_scale_score"]
    s8 = scale_rows[8.0]["deploy_scale_score"]

    ann_sign_08 = _safe_float(scale_rows[0.8]["summary"].get("best_ann_seq_sign_acc"), 0.0)
    ann_sign_8 = _safe_float(scale_rows[8.0]["summary"].get("best_ann_seq_sign_acc"), 0.0)
    seq_sign_08 = _safe_float(scale_rows[0.8]["summary"].get("best_seq_val_sign_acc"), 0.0)
    seq_sign_8 = _safe_float(scale_rows[8.0]["summary"].get("best_seq_val_sign_acc"), 0.0)
    center_08 = _safe_float(scale_rows[0.8]["summary"].get("best_ann_seq_center_err_px"), 10.0)
    center_8 = _safe_float(scale_rows[8.0]["summary"].get("best_ann_seq_center_err_px"), 10.0)
    step_08 = _safe_float(scale_rows[0.8]["summary"].get("best_ann_seq_step_err_rel"), 10.0)
    step_8 = _safe_float(scale_rows[8.0]["summary"].get("best_ann_seq_step_err_rel"), 10.0)
    thick_08 = _safe_float(scale_rows[0.8]["summary"].get("best_ann_seq_thickness_err_rel"), 10.0)
    thick_8 = _safe_float(scale_rows[8.0]["summary"].get("best_ann_seq_thickness_err_rel"), 10.0)
    span = max(s008, s08, s8) - min(s008, s08, s8)

    score = (
        3.2 * s08
        + 3.0 * s8
        + 0.8 * s008
        + 10.0 * min(ann_sign_08, ann_sign_8)
        + 8.0 * min(seq_sign_08, seq_sign_8)
        - 18.0 * max(center_08, center_8)
        - 28.0 * max(step_08, step_8)
        - 14.0 * max(thick_08, thick_8)
        - 3.0 * span
    )
    return float(score)


def _evaluate_checkpoint(train_mod, snapshot: dict, *, checkpoint_path: str, expect_dy: float, seed: int, label: str) -> dict:
    _restore_cfg(train_mod, snapshot)
    _apply_common_eval_cfg(train_mod, checkpoint_path=checkpoint_path, expect_dy=expect_dy, run_label=label)
    args = SimpleNamespace(
        attrib_window=None,
        attrib_every=None,
        seed_deterministic=True,
        force_fast_eval=False,
    )
    summary = train_mod.run_one_seed(int(seed), args=args)
    return {
        "expect_dy": float(expect_dy),
        "checkpoint_path": str(checkpoint_path),
        "summary": summary,
        "deploy_scale_score": _per_scale_deploy_score(summary, float(expect_dy)),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--candidate", required=True)
    p.add_argument("--checkpoint-0p08", required=True)
    p.add_argument("--checkpoint-0p8", required=True)
    p.add_argument("--checkpoint-8px", required=True)
    p.add_argument("--output-json", required=True)
    p.add_argument("--output-md", required=True)
    p.add_argument("--seed", type=int, default=3407)
    args = p.parse_args()

    train_mod = _load_train_module()
    snapshot = copy.deepcopy(vars(train_mod.TrainConfig()))

    ckpt_map = {
        "checkpoint_0p08": str(args.checkpoint_0p08),
        "checkpoint_0p8": str(args.checkpoint_0p8),
        "checkpoint_8px": str(args.checkpoint_8px),
    }
    results = []
    for ckpt_label, ckpt_path in ckpt_map.items():
        per_scale = {}
        for scale in SCALES:
            run_label = f"universal_audit_{args.candidate}_{ckpt_label}_{str(scale).replace('.', 'p')}"
            print(f"[AUDIT] candidate={args.candidate} checkpoint={ckpt_label} scale={scale}")
            per_scale[scale] = _evaluate_checkpoint(
                train_mod,
                snapshot,
                checkpoint_path=ckpt_path,
                expect_dy=scale,
                seed=int(args.seed),
                label=run_label,
            )
        deploy_score = _deployment_score(per_scale)
        results.append(
            {
                "candidate": str(args.candidate),
                "checkpoint_label": ckpt_label,
                "checkpoint_path": ckpt_path,
                "per_scale": per_scale,
                "deployment_score": deploy_score,
            }
        )

    results.sort(key=lambda x: x["deployment_score"], reverse=True)
    best = results[0]
    payload = {
        "candidate": str(args.candidate),
        "results": results,
        "best_checkpoint_label": best["checkpoint_label"],
        "best_checkpoint_path": best["checkpoint_path"],
        "best_deployment_score": best["deployment_score"],
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }

    out_json = Path(args.output_json)
    out_md = Path(args.output_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# Universal Checkpoint Audit",
        "",
        f"- candidate: {args.candidate}",
        f"- best_checkpoint_label: {best['checkpoint_label']}",
        f"- best_checkpoint_path: {best['checkpoint_path']}",
        f"- best_deployment_score: {best['deployment_score']:.6f}",
        "",
        "| checkpoint | s0.08 | s0.8 | s8 | deploy |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in results:
        lines.append(
            f"| {row['checkpoint_label']} | "
            f"{row['per_scale'][0.08]['deploy_scale_score']:.3f} | "
            f"{row['per_scale'][0.8]['deploy_scale_score']:.3f} | "
            f"{row['per_scale'][8.0]['deploy_scale_score']:.3f} | "
            f"{row['deployment_score']:.3f} |"
        )
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print("[AUDIT] COMPLETED")


if __name__ == "__main__":
    main()
