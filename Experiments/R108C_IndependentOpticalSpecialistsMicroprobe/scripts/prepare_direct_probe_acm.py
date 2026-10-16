"""Prepare locked ACM roots for the direct edge+texture causal probe."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = Path(r"D:\GMM_2_Final\Experiments")
PROBE = ROOT / "results" / "direct_edge_texture_probe"
SUITES = {
    "R73": EXPERIMENTS / "R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R73_novel_shapes/config/experiment.json",
    "R74": EXPERIMENTS / "R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R74_hard_microscopy/config/experiment.json",
}


def main() -> int:
    for suite, template in SUITES.items():
        config = json.loads(template.read_text(encoding="utf-8"))
        config["experiment_id"] = f"R108C_direct_edge_texture_{suite}"
        run = ROOT / "results" / "acm" / f"direct_edge_texture_{suite}"
        (run / "config").mkdir(parents=True, exist_ok=True)
        (run / "results").mkdir(parents=True, exist_ok=True)
        (run / "config" / "experiment.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
        output_dirs = {
            family["name"]: str(PROBE / suite / family["stage"])
            for family in config["dataset"]["families"]
        }
        manifest = {
            "experiment_id": config["experiment_id"],
            "methods": ["R108C_direct_edge_texture"],
            "output_dirs": output_dirs,
            "status": "complete",
        }
        (run / "results" / "inference_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
