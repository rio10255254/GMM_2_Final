"""R75 手動訓練入口。

使用方式：修改下方「可手動調整的設定」，然後在編輯器按執行即可。
命令列參數不是必要條件。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


# =====================================================================
# 可手動調整的設定
# =====================================================================
ACTION = "train"             # "train" / "check_only" / "build_data_only"
PROFILE = "formal"           # "smoke" / "pilot" / "formal"
DEVICE = "cuda:0"            # 沒有 GPU 時可改成 "cpu"
SEED = 750031                 # 允許：750031 / 750032 / 750033
EPOCHS = 100
LEARNING_RATE = 2e-5
BATCH_SIZE = 8
VALIDATION_BATCH_SIZE = 2
NUM_WORKERS = 4
# 此模型的邊界損失在目前環境使用半精度會溢位並跳過全部更新；正式訓練固定關閉。
USE_AMP = False
BUILD_DATA_IF_NEEDED = True
FORCE_REBUILD_DATA = False
MAX_TRAIN_BATCHES_PER_EPOCH = None  # 正式訓練維持 None；試跑可填 1
RUN_SUFFIX = "manual"
LIVE_VALIDATION_IMAGE = "data/live_validation/pillar_center9_50x_raw.bmp"
LIVE_VALIDATION_EVERY_N_EPOCHS = 5
ENABLE_LIVE_VALIDATION = True


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
LAUNCHER_PATH = EXPERIMENT_DIR / "scripts" / "launch_r75.py"
DATA_BUILDER_PATH = EXPERIMENT_DIR / "scripts" / "r75_dataset.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"無法載入：{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_arguments() -> list[str]:
    arguments = [
        "--profile", PROFILE,
        "--device", DEVICE,
        "--seed", str(SEED),
        "--num-epoch", str(EPOCHS),
        "--lr", str(LEARNING_RATE),
        "--batch-size", str(BATCH_SIZE),
        "--val-batch-size", str(VALIDATION_BATCH_SIZE),
        "--num-workers", str(NUM_WORKERS),
        "--run-suffix", RUN_SUFFIX,
        "--live-validation-image", str(EXPERIMENT_DIR / LIVE_VALIDATION_IMAGE),
        "--live-validation-every", str(LIVE_VALIDATION_EVERY_N_EPOCHS),
    ]
    if BUILD_DATA_IF_NEEDED:
        arguments.append("--build-data")
    if FORCE_REBUILD_DATA:
        arguments.append("--force-data")
    if not USE_AMP:
        arguments.append("--no-amp")
    else:
        arguments.append("--amp")
    if MAX_TRAIN_BATCHES_PER_EPOCH is not None:
        arguments.extend(["--max-train-batches", str(MAX_TRAIN_BATCHES_PER_EPOCH)])
    if not ENABLE_LIVE_VALIDATION:
        arguments.append("--disable-live-validation")
    if ACTION == "check_only":
        arguments.append("--dry-run")
    return arguments


def main() -> int:
    if ACTION == "build_data_only":
        builder = _load_module("r75_manual_dataset_builder", DATA_BUILDER_PATH)
        package_dir, manifest, audit = builder.build_package(
            PROFILE,
            builder.DATA_ROOT,
            force=FORCE_REBUILD_DATA,
        )
        print(f"資料已準備：{package_dir}")
        print(f"影像數：{manifest['total_pairs']}，來源檢查：{audit['passed']}")
        return 0
    if ACTION not in {"train", "check_only"}:
        raise ValueError(f"ACTION 必須是 train、check_only 或 build_data_only，目前為：{ACTION}")
    launcher = _load_module("r75_manual_training_launcher", LAUNCHER_PATH)
    return int(launcher.main(build_arguments()))


if __name__ == "__main__":
    raise SystemExit(main())
