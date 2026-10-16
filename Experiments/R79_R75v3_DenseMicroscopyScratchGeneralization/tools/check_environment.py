"""R75-v3 執行環境與必要檔案檢查；直接按執行即可。"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MODULES = ("numpy", "cv2", "scipy", "torch", "torchmetrics", "matplotlib", "tqdm")
REQUIRED_FILES = (
    ROOT / "model" / "GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py",
    ROOT / "model" / "GeoEdgeAlignSR_v1_Utils.py",
    ROOT / "model" / "analytic_psf_bank.mat",
    ROOT / "training" / "runtime" / "GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py",
    ROOT / "scripts" / "r75v3_dataset.py",
    ROOT / "scripts" / "launch_r75v3.py",
    ROOT / "config" / "experiment.json",
    ROOT / "config" / "architecture_contract.json",
    ROOT / "data" / "live_validation" / "5x_dense_raw.bmp",
    ROOT / "data" / "live_validation" / "20x_mixed_raw.bmp",
    ROOT / "data" / "live_validation" / "50x_array_raw.bmp",
    ROOT / "data" / "live_validation" / "metadata.json",
)


def main() -> int:
    versions: dict[str, str] = {}
    missing_modules: list[str] = []
    for name in REQUIRED_MODULES:
        try:
            module = importlib.import_module(name)
            versions[name] = str(getattr(module, "__version__", "available"))
        except Exception as error:
            missing_modules.append(f"{name}: {error}")
    missing_files = [str(path) for path in REQUIRED_FILES if not path.is_file()]
    torch_module = sys.modules.get("torch")
    result = {
        "passed": not missing_modules and not missing_files,
        "python": sys.version.split()[0],
        "packages": versions,
        "cuda_available": bool(torch_module and torch_module.cuda.is_available()),
        "gpu": (
            torch_module.cuda.get_device_name(0)
            if torch_module and torch_module.cuda.is_available()
            else None
        ),
        "missing_modules": missing_modules,
        "missing_files": missing_files,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result["passed"]:
        raise SystemExit("R75-v3 執行環境不完整，請依上方缺少項目處理。")
    print("R75-v3 執行環境與必要檔案均完整。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
