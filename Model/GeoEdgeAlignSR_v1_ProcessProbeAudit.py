import argparse
import copy
import importlib.util
import json
import time
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = PROJECT_ROOT / "Model" / "GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py"
MID_STAGE_DIRS = (
    "stage_23_annulus_gmf_sequence_mid_clean",
    "stage_24_annulus_gmf_sequence_mid_defect",
    "stage_27_annulus_gmf_sequence_midwide_clean",
    "stage_28_annulus_gmf_sequence_midwide_defect",
)
TINY_STAGE_DIRS = (
    "stage_21_annulus_gmf_sequence_clean",
    "stage_22_annulus_gmf_sequence_defect",
)
MACRO_STAGE_DIRS = (
    "stage_25_annulus_gmf_sequence_macro_clean",
    "stage_26_annulus_gmf_sequence_macro_defect",
)


def _load_train_module():
    spec = importlib.util.spec_from_file_location("gesr_train_process_audit_mod", TRAIN_PATH)
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


def _stage_dirs_for_expect_dy(expect_dy: float):
    if abs(float(expect_dy) - 8.0) < 1.0e-6:
        return MACRO_STAGE_DIRS
    if abs(float(expect_dy) - 0.08) < 1.0e-6:
        return TINY_STAGE_DIRS
    return MID_STAGE_DIRS


def _apply_process_eval_cfg(
    train_mod,
    *,
    checkpoint_path: str,
    run_label: str,
    geom_method: str = "",
    expect_dy: float = 0.8,
):
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
    cfg.SEQ_VAL_INCLUDE_SUBDIRS = _stage_dirs_for_expect_dy(expect_dy)
    cfg.SEQ_VAL_BATCH_SIZE = 2
    cfg.SEQ_VAL_MAX_PAIRS = 224
    cfg.SEQ_VAL_ANNULUS_ENABLE = True
    cfg.SEQ_VAL_SIGN_Q = 0.85
    if geom_method:
        cfg.SEQ_GEOM_METHOD = str(geom_method)
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


def _process_score(summary: dict, expect_dy: float) -> float:
    ann_score = _safe_float(summary.get("best_ann_seq_score"), -1.0)
    ann_sign = _safe_float(summary.get("best_ann_seq_sign_acc"), 0.0)
    seq_score = _safe_float(summary.get("best_seq_val_score"), -1.0)
    seq_sign = _safe_float(summary.get("best_seq_val_sign_acc"), 0.0)
    center = _safe_float(summary.get("best_ann_seq_center_err_px"), 10.0)
    step = _safe_float(summary.get("best_ann_seq_step_err_rel"), 10.0)
    if abs(float(expect_dy) - 8.0) < 1.0e-6:
        score = (
            8.0 * ann_score
            + 10.0 * ann_sign
            + 4.0 * seq_score
            + 6.0 * seq_sign
            - 10.0 * center
            - 140.0 * step
        )
        if step > 0.04:
            score -= 45.0
        if ann_sign < 0.85:
            score -= 16.0
        if seq_sign < 0.68:
            score -= 12.0
    else:
        score = (
            10.0 * ann_score
            + 12.0 * ann_sign
            + 6.0 * seq_score
            + 8.0 * seq_sign
            - 100.0 * center
            - 70.0 * step
        )
        if center > 0.82:
            score -= 50.0
        if step > 0.40:
            score -= 35.0
        if ann_sign < 0.87:
            score -= 20.0
        if seq_sign < 0.68:
            score -= 18.0
    return float(score)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--candidate", required=True)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--geom-method", default="")
    p.add_argument("--expect-dy", type=float, default=0.8)
    p.add_argument("--output-json", required=True)
    p.add_argument("--output-md", required=True)
    p.add_argument("--seed", type=int, default=1261202)
    args = p.parse_args()

    train_mod = _load_train_module()
    snapshot = copy.deepcopy(vars(train_mod.TrainConfig()))
    _restore_cfg(train_mod, snapshot)
    _apply_process_eval_cfg(
        train_mod,
        checkpoint_path=str(args.checkpoint),
        run_label=f"process_probe_{args.candidate}_{str(float(args.expect_dy)).replace('.', 'p')}",
        geom_method=str(args.geom_method or ""),
        expect_dy=float(args.expect_dy),
    )
    summary = train_mod.run_one_seed(
        int(args.seed),
        args=SimpleNamespace(
            attrib_window=None,
            attrib_every=None,
            seed_deterministic=True,
            force_fast_eval=False,
        ),
    )
    payload = {
        "candidate": str(args.candidate),
        "checkpoint_path": str(args.checkpoint),
        "geom_method": str(args.geom_method or ""),
        "expect_dy": float(args.expect_dy),
        "summary": summary,
        "process_score": _process_score(summary, float(args.expect_dy)),
        "passes_target": (
            (
                _safe_float(summary.get("best_ann_seq_center_err_px"), 1e3) < 0.82
                and _safe_float(summary.get("best_ann_seq_step_err_rel"), 1e3) < 0.40
            )
            if abs(float(args.expect_dy) - 8.0) >= 1.0e-6
            else (
                _safe_float(summary.get("best_ann_seq_step_err_rel"), 1e3) <= 0.04
            )
        ),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }

    out_json = Path(args.output_json)
    out_md = Path(args.output_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    s = payload["summary"]
    lines = [
        "# Process Probe Audit",
        "",
        f"- candidate: {args.candidate}",
        f"- checkpoint_path: {args.checkpoint}",
        f"- geom_method: {str(args.geom_method or '')}",
        f"- expect_dy: {float(args.expect_dy):.2f}",
        f"- process_score: {payload['process_score']:.6f}",
        f"- passes_target: {payload['passes_target']}",
        "",
        "| metric | value |",
        "| --- | ---: |",
        f"| best_epoch | {s.get('best_epoch')} |",
        f"| best_epoch_is_baseline | {s.get('best_epoch_is_baseline')} |",
        f"| epoch0_tradeoff_score | {_safe_float(s.get('epoch0_tradeoff_score')):.6f} |",
        f"| epoch0_ann_seq_center_err_px | {_safe_float(s.get('epoch0_ann_seq_center_err_px')):.6f} |",
        f"| epoch0_ann_seq_step_err_rel | {_safe_float(s.get('epoch0_ann_seq_step_err_rel')):.6f} |",
        f"| best_ann_seq_center_err_px | {_safe_float(s.get('best_ann_seq_center_err_px')):.6f} |",
        f"| best_ann_seq_step_err_rel | {_safe_float(s.get('best_ann_seq_step_err_rel')):.6f} |",
        f"| best_minus_epoch0_center_err | {_safe_float(s.get('best_minus_epoch0_center_err')):.6f} |",
        f"| best_minus_epoch0_step_err | {_safe_float(s.get('best_minus_epoch0_step_err')):.6f} |",
        f"| best_ann_seq_sign_acc | {_safe_float(s.get('best_ann_seq_sign_acc')):.6f} |",
        f"| best_seq_val_sign_acc | {_safe_float(s.get('best_seq_val_sign_acc')):.6f} |",
    ]
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print("[PROCESS_AUDIT] COMPLETED")


if __name__ == "__main__":
    main()
