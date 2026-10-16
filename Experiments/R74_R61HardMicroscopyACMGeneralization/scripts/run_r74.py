from __future__ import annotations

import os
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.environ["GMM_ACM_EXPERIMENT_ROOT"] = str(ROOT)
RUNNER = Path(r"D:\GMM_2_Final\Experiments\R73_R61ExpandedSyntheticACMGeneralization\scripts\run_r73.py")
runpy.run_path(str(RUNNER), run_name="__main__")
