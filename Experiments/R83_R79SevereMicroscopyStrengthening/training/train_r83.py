"""R83 手動補強訓練入口。

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
PROFILE = "pilot"            # "smoke" / "pilot" / "formal"
CANDIDATE = "adapter_tail"   # "adapter_only" / "adapter_tail"
DEVICE = "cuda:0"            # 沒有 GPU 時可改成 "cpu"
SEED = 830917                 # 允許：830917 / 830918 / 830919
EPOCHS = 4                    # 正式補強改成 30
LEARNING_RATE = 5e-6
BATCH_SIZE = 8
VALIDATION_BATCH_SIZE = 2
NUM_WORKERS = 4
BUILD_DATA_IF_NEEDED = True
FORCE_REBUILD_DATA = False
MAX_TRAIN_BATCHES_PER_EPOCH = None  # 正式訓練維持 None；試跑可填 1
RUN_SUFFIX = "manual"
LIVE_VALIDATION_DIR = "data/live_validation"
LIVE_VALIDATION_EVERY_N_EPOCHS = 2
ENABLE_LIVE_VALIDATION = True


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
LAUNCHER_PATH = EXPERIMENT_DIR / "scripts" / "launch_r83.py"
DATA_BUILDER_PATH = EXPERIMENT_DIR / "scripts" / "r83_dataset.py"


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
        "--candidate", CANDIDATE,
        "--device", DEVICE,
        "--seed", str(SEED),
        "--num-epoch", str(EPOCHS),
        "--lr", str(LEARNING_RATE),
        "--batch-size", str(BATCH_SIZE),
        "--val-batch-size", str(VALIDATION_BATCH_SIZE),
        "--num-workers", str(NUM_WORKERS),
        "--run-suffix", RUN_SUFFIX,
        "--live-validation-dir", str(EXPERIMENT_DIR / LIVE_VALIDATION_DIR),
        "--live-validation-every", str(LIVE_VALIDATION_EVERY_N_EPOCHS),
    ]
    if BUILD_DATA_IF_NEEDED:
        arguments.append("--build-data")
    if FORCE_REBUILD_DATA:
        arguments.append("--force-data")
    if MAX_TRAIN_BATCHES_PER_EPOCH is not None:
        arguments.extend(["--max-train-batches", str(MAX_TRAIN_BATCHES_PER_EPOCH)])
    if not ENABLE_LIVE_VALIDATION:
        arguments.append("--disable-live-validation")
    if ACTION == "check_only":
        arguments.append("--dry-run")
    return arguments


def main() -> int:
    if ACTION == "build_data_only":
        builder = _load_module("r83_manual_dataset_builder", DATA_BUILDER_PATH)
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
    launcher = _load_module("r83_manual_training_launcher", LAUNCHER_PATH)
    return int(launcher.main(build_arguments()))


if __name__ == "__main__":
    raise SystemExit(main())
