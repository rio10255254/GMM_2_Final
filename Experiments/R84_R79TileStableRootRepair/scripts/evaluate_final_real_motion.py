"""Run the unchanged locked R82 real-FOV motion protocol for R84."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
R82 = Path(r"D:\GMM_2_Final\Experiments\R82_R39R40CrossSceneGeneralizationBenchmark")
OUTPUT = ROOT / "results" / "final_confirmation"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("r84_final_r82_motion", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    config = json.loads((R82 / "config" / "experiment.json").read_text(encoding="utf-8"))
    locked = Path(config["real_fov"]["locked_measurements"])
    if sha256(locked) != config["real_fov"]["locked_measurements_sha256"]:
        raise RuntimeError("Locked real-FOV measurements changed.")
    config["models"] = {"R84": {}}
    module = load_module(R82 / "scripts" / "run_r82.py")
    module.RESULTS = OUTPUT
    module.TABLES = OUTPUT / "tables"
    module.RECON = OUTPUT / "reconstructions"
    module.LOGS = OUTPUT / "logs"
    module.STATUS = OUTPUT / "real_motion_status.json"
    module.evaluate_real(config)
    current = pd.read_csv(module.TABLES / "real_motion_summary.csv")
    prior = pd.read_csv(R82 / "results" / "tables" / "real_motion_summary.csv")
    prior = prior.loc[prior["method"] == "R79"]
    combined = pd.concat([prior, current], ignore_index=True, sort=False)
    combined.to_csv(module.TABLES / "real_motion_summary_with_r79.csv", index=False)
    print(combined.to_json(orient="records", indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
