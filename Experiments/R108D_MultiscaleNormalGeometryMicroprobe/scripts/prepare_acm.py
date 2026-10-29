"""Prepare locked R73 and R74 ACM roots for frozen R108D outputs."""
from __future__ import annotations

import json
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = Path(str(PROJECT_ROOT / 'Experiments'))
OUTPUT = ROOT / "results" / "locked_inference"
SUITES = {
    "R73": EXPERIMENTS / "R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R73_novel_shapes/config/experiment.json",
    "R74": EXPERIMENTS / "R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R74_hard_microscopy/config/experiment.json",
}


def main() -> int:
    for suite, template in SUITES.items():
        config = json.loads(template.read_text(encoding="utf-8"))
        config["experiment_id"] = f"R108D_multiscale_normal_{suite}"
        run = ROOT / "results" / "acm" / suite
        (run / "config").mkdir(parents=True, exist_ok=True)
        (run / "results").mkdir(parents=True, exist_ok=True)
        (run / "config" / "experiment.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
        output_dirs = {
            family["name"]: str(OUTPUT / suite / family["stage"])
            for family in config["dataset"]["families"]
        }
        (run / "results" / "inference_manifest.json").write_text(
            json.dumps(
                {
                    "experiment_id": config["experiment_id"],
                    "methods": ["R108D_multiscale_normal"],
                    "output_dirs": output_dirs,
                    "status": "complete",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
