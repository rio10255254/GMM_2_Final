"""R75-v2 手動資料建立入口；修改設定後直接按執行。"""
from __future__ import annotations

import importlib.util
from pathlib import Path


PROFILE = "formal"           # "smoke" / "pilot" / "formal"
FORCE_REBUILD = False         # 改成 True 會重建所選資料包


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
CORE_PATH = EXPERIMENT_DIR / "scripts" / "r75v2_dataset.py"


def main() -> int:
    spec = importlib.util.spec_from_file_location("r75v2_dataset_core", CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"無法載入資料建立器：{CORE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    package_dir, manifest, audit = module.build_package(
        PROFILE,
        module.DATA_ROOT,
        force=FORCE_REBUILD,
    )
    print(f"資料位置：{package_dir}")
    print(f"總張數：{manifest['total_pairs']}")
    print(f"訓練／驗證／測試：{audit['split_counts']}")
    print(f"放大繪製抗鋸齒檢查：{audit['label_supersample_factor']}x，通過={audit['passed']}")
    print(f"六類資料分配：{audit['training_role_counts']}")
    print(f"完全不修改／近乎不修改：{audit['identity_mode_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
