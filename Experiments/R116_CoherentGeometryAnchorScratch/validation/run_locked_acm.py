"""Reuse the unchanged locked R73/R74 ACM pipeline with the R116 adapter."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
R114 = Path(r"D:\GMM_2_Final\Experiments\R114_ConfidenceGatedRecoverableScratch")
for path in (R114, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from validation import adapter


def load_locked_runner():
    import inference as inference_package
    import model as model_package
    import validation as validation_package
    r114_validation = str(R114 / "validation")
    if r114_validation not in validation_package.__path__:
        validation_package.__path__.append(r114_validation)
    r114_inference = str(R114 / "inference")
    if r114_inference not in inference_package.__path__:
        inference_package.__path__.append(r114_inference)
    r114_model = str(R114 / "model")
    if r114_model not in model_package.__path__:
        model_package.__path__.append(r114_model)
    path = R114 / "validation" / "run_split_profile_locked_acm.py"
    spec = importlib.util.spec_from_file_location("r116_locked_acm_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import locked ACM runner: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    locked = load_locked_runner()
    locked.load_model = adapter.load_model
    locked.canonical_tile_config = adapter.canonical_tile_config
    locked.predict_canonical_tiled = adapter.predict_canonical_tiled
    return locked.main()


if __name__ == "__main__":
    raise SystemExit(main())
