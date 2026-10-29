import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = PROJECT_ROOT / "Model"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

PENDING_ROOT = PROJECT_ROOT / "Traing_Progress" / "organized_20260310" / "pending"
STATUS_DIR = PENDING_ROOT / "status"
ROOT_STATUS_MD = PROJECT_ROOT / "000_ROUND7_SEQUENCE_STATUS.md"
ROOT_STATUS_JSON = PROJECT_ROOT / "000_ROUND7_SEQUENCE_STATUS.json"


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def _ensure_dirs() -> None:
    STATUS_DIR.mkdir(parents=True, exist_ok=True)


def _write_status(state: str, step: str, message: str) -> None:
    payload = {
        "updated_at": _now(),
        "state": state,
        "step": step,
        "message": message,
    }
    ROOT_STATUS_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    ROOT_STATUS_MD.write_text(
        "\n".join(
            [
                "# Round7 Sequence Pipeline 狀態",
                "",
                f"- updated_at: `{payload['updated_at']}`",
                f"- state: `{state}`",
                f"- step: `{step}`",
                f"- message: `{message}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _smoke_sequence_loader() -> None:
    from Model import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as train_mod

    train_mod.CFG.SEQ_ENABLE = True
    train_mod.CFG.SEQ_INCLUDE_SUBDIRS = (
        "stage_19_annulus_microstep_sequence_clean",
        "stage_20_annulus_microstep_sequence_defect",
    )
    loader = train_mod.make_sequence_loader()
    if loader is None:
        raise RuntimeError("sequence loader unexpectedly returned None")
    batch = next(iter(loader))
    shapes = [tuple(t.shape) for t in batch]
    print(f"[ROUND7] sequence loader ok | pairs={len(loader.dataset)} shapes={shapes}", flush=True)


def _run_autotune(expect_dy: float, sweep_epochs: int, final_epochs: int, skip_final: bool) -> None:
    cmd = [
        sys.executable,
        "-u",
        str(PROJECT_ROOT / "Model" / "GeoEdgeAlignSR_v1_AutoTuneTrain.py"),
        "--profile",
        "round7_sequence_microstep_probe",
        "--expect-dy",
        f"{expect_dy}",
        "--sweep-epochs",
        str(sweep_epochs),
        "--final-epochs",
        str(final_epochs),
        "--deterministic",
    ]
    if skip_final:
        cmd.append("--skip-final")
    print(f"[ROUND7] run autotune: {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True, cwd=str(PROJECT_ROOT))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sweep-epochs", type=int, default=4)
    p.add_argument("--final-epochs", type=int, default=6)
    p.add_argument("--with-final", action="store_true", help="Run final continuation after sweep.")
    args = p.parse_args()

    _ensure_dirs()
    os.chdir(PROJECT_ROOT)
    os.environ["PYTHONIOENCODING"] = "utf-8"

    try:
        _write_status("running", "generate_stage_19_20", "生成 19/20 sequence-aware 微位移資料中")
        from Training_Data import Data_Simulaion as ds

        stages = ds.select_stages(ds.STAGES, [19, 20])
        print(f"[ROUND7] generate stages={[s.name for s in stages]}", flush=True)
        ds.run_pipeline(stages, base_seed=ds.RUN_BASE_SEED)

        _write_status("running", "convolve_stage_19_20", "對 19/20 做 PSF 卷積中")
        from Training_Data import PSF_Convolution as pc

        psfs = pc.load_psfs(pc.PSF_MAT_PATH)
        pc.run(pc.INPUT_ROOT, pc.OUTPUT_ROOT, psfs, noise_seed=pc.RUN_NOISE_SEED, stage_ids=[19, 20])

        _write_status("running", "smoke_sequence_loader", "驗證 sequence loader 中")
        _smoke_sequence_loader()

        _write_status("running", "autotune_round7", "執行 round7_sequence_microstep_probe")
        _run_autotune(
            expect_dy=0.08,
            sweep_epochs=int(args.sweep_epochs),
            final_epochs=int(args.final_epochs),
            skip_final=not bool(args.with_final),
        )

        _write_status("stopped", "done", "round7 sequence pipeline 全部完成")
        print("[ROUND7] done", flush=True)
    except Exception as exc:
        _write_status("error", "failed", f"{type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    main()
