"""R46 完整評估 pipeline:訓練完成後一鍵跑完所有評估。

階段:
1. 找 R46 best_tradeoff.pth.tar checkpoint
2. 跑 R39 + R40 重建(run_r46_recon.py)
3. 跑 capability eval + 合併 csv(r46_capability_eval.py)
4. 跑 Rayleigh 診斷 + 配對 t 檢定 + plots(r46_rayleigh_diagnostic.py)
5. 跑視覺驗證 zoom case(r46_visual_verification.py)

每階段獨立可重跑;若已產出可跳過。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
R46_ROOT = REPO_ROOT / "Experiments" / "R46_CornerAwareFineTune"
SCRIPT_DIR = R46_ROOT / "scripts"
TRAINING_PROGRESS_DIR = REPO_ROOT / "Traing_Progress"


def find_latest_r46_checkpoint() -> Path | None:
    """找 Traing_Progress/training_progress_GESR_v1_v5_ST0p8_SWP_r46_*_*/weights/best_tradeoff.pth.tar
    取 timestamp 最晚那個。"""
    candidates = sorted(TRAINING_PROGRESS_DIR.glob(
        "training_progress_GESR_v1_v5_ST0p8_SWP_r46_a025_corner_finetune_*"
    ))
    if not candidates:
        return None
    candidates.sort(reverse=True)  # newest first
    for c in candidates:
        weights = c / "weights" / "best_tradeoff.pth.tar"
        if weights.exists():
            return weights
    return None


def run_step(name: str, cmd: list[str], skip: bool = False) -> int:
    if skip:
        print(f"\n[SKIP] {name}")
        return 0
    print(f"\n[STEP] {name}")
    print(f"  cmd: {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        print(f"  [FAIL] {name} returned {result.returncode}")
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R46 full evaluation pipeline")
    parser.add_argument("--weights", type=Path, default=None,
                        help="R46 best_tradeoff.pth.tar(預設自動找最新)")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--skip-recon", action="store_true")
    parser.add_argument("--skip-eval", action="store_true")
    parser.add_argument("--skip-diagnostic", action="store_true")
    parser.add_argument("--skip-visual", action="store_true")
    args = parser.parse_args(argv)

    weights = args.weights
    if weights is None:
        weights = find_latest_r46_checkpoint()
        if weights is None:
            print("[FAIL] R46 best_tradeoff.pth.tar not found in Traing_Progress/")
            print("       Either training is not done, or pass --weights explicitly.")
            return 1
    weights = Path(weights).resolve()
    if not weights.exists():
        print(f"[FAIL] weights path missing: {weights}")
        return 1
    print(f"[R46 pipeline] using weights: {weights}")

    # Step 1: 重建
    rc = run_step(
        "1. R39 + R40 recon",
        [sys.executable, str(SCRIPT_DIR / "run_r46_recon.py"),
         "--weights", str(weights), "--device", args.device],
        skip=args.skip_recon,
    )
    if rc != 0 and not args.skip_recon:
        return rc

    # Step 2: capability eval + 合併 csv
    rc = run_step(
        "2. R46 capability eval + merge with a025 csv",
        [sys.executable, str(SCRIPT_DIR / "r46_capability_eval.py")],
        skip=args.skip_eval,
    )
    if rc != 0 and not args.skip_eval:
        return rc

    # Step 3: Rayleigh 診斷 + paired t-test + plots
    rc = run_step(
        "3. R46 Rayleigh diagnostic (5-model)",
        [sys.executable, str(SCRIPT_DIR / "r46_rayleigh_diagnostic.py")],
        skip=args.skip_diagnostic,
    )
    if rc != 0 and not args.skip_diagnostic:
        return rc

    # Step 4: 視覺驗證 zoom case
    rc = run_step(
        "4. R46 visual verification",
        [sys.executable, str(SCRIPT_DIR / "r46_visual_verification.py")],
        skip=args.skip_visual,
    )
    if rc != 0 and not args.skip_visual:
        return rc

    print("\n[R46 pipeline] done.")
    print(f"  results -> {R46_ROOT / 'results'}")
    print(f"  next: 寫 reports/R46_RESULTS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
