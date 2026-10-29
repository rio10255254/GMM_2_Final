"""Run one frozen R116 intervention through the unchanged locked ACM suite."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
R114 = Path(str(PROJECT_ROOT / 'Experiments/R114_ConfidenceGatedRecoverableScratch'))
for path in (R114, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from validation import intervention_adapter
from validation.interventions import MODES


def _pop_intervention_argument() -> str:
    if "--intervention" not in sys.argv:
        raise ValueError(f"--intervention is required; choose one of {MODES}")
    index = sys.argv.index("--intervention")
    if index + 1 >= len(sys.argv):
        raise ValueError("--intervention has no value")
    mode = sys.argv[index + 1]
    del sys.argv[index:index + 2]
    if mode not in MODES:
        raise ValueError(f"unknown intervention {mode}; choose one of {MODES}")
    return mode


def _load_locked_runner():
    import inference as inference_package
    import model as model_package
    import validation as validation_package
    for package, path in (
        (validation_package, R114 / "validation"),
        (inference_package, R114 / "inference"),
        (model_package, R114 / "model"),
    ):
        if str(path) not in package.__path__:
            package.__path__.append(str(path))
    path = R114 / "validation" / "run_split_profile_locked_acm.py"
    spec = importlib.util.spec_from_file_location("r116_intervention_locked_acm", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import locked ACM runner: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    mode = _pop_intervention_argument()
    os.environ["R116_INTERVENTION_MODE"] = mode
    locked = _load_locked_runner()
    locked.load_model = intervention_adapter.load_model
    locked.canonical_tile_config = intervention_adapter.canonical_tile_config
    locked.predict_canonical_tiled = intervention_adapter.predict_canonical_tiled
    return locked.main()


if __name__ == "__main__":
    raise SystemExit(main())
