"""Reconstruct locked developmental suites with the two R83 pilot candidates."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
R82 = Path(r"D:\GMM_2_Final\Experiments\R82_R39R40CrossSceneGeneralizationBenchmark")
OUTPUT = ROOT / "results" / "pilot_acm_screen"
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))


def latest_file(root: Path, filename: str) -> Path:
    matches = [path for path in root.rglob(filename) if not (path.parent / "INVALIDATED.json").is_file()]
    if not matches:
        raise FileNotFoundError(f"No {filename} below {root}")
    return max(matches, key=lambda path: path.stat().st_mtime_ns)


CHECKPOINTS = {
    "AdapterOnlyE4": latest_file(ROOT / "weights" / "pilot" / "adapter_only", "best_tradeoff.pth.tar"),
    "AdapterTailE4": latest_file(ROOT / "weights" / "pilot" / "adapter_tail", "latest.pth.tar"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_inference_module():
    path = ROOT / "inference" / "infer_r83.py"
    spec = importlib.util.spec_from_file_location("r83_inference_for_pilot_screen", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reconstruct_tree(module, model, input_dirs: dict[str, Path], output_root: Path) -> dict[str, str]:
    outputs = {}
    for family, input_dir in input_dirs.items():
        target_dir = output_root / input_dir.name
        outputs[family] = str(target_dir)
        for source_path in sorted(input_dir.glob("*.bmp")):
            image = module.read_gray(source_path)
            reconstruction = module.infer_tiled(model, image, "cuda:0", 4096, 0)
            module.write_bmp(target_dir / source_path.name, reconstruction)
    return outputs


def prepare_external_configs() -> tuple[dict, dict]:
    configs, manifests = {}, {}
    for suite in ("R73_novel_shapes", "R74_hard_microscopy"):
        source_root = R82 / "results" / "acm_external" / suite
        config = json.loads((source_root / "config" / "experiment.json").read_text(encoding="utf-8"))
        prior = json.loads((source_root / "results" / "inference_manifest.json").read_text(encoding="utf-8"))
        suite_root = OUTPUT / suite
        (suite_root / "config").mkdir(parents=True, exist_ok=True)
        (suite_root / "results").mkdir(parents=True, exist_ok=True)
        config["experiment_id"] = f"R83_pilot_screen_{suite}"
        (suite_root / "config" / "experiment.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        configs[suite] = config
        manifests[suite] = {
            "suite": suite,
            "methods": ["Raw", "R79", *CHECKPOINTS],
            "output_dirs": {"Raw": prior["output_dirs"]["Raw"], "R79": prior["output_dirs"]["R79"]},
        }
    return configs, manifests


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    module = load_inference_module()
    suite_configs, inference_manifests = prepare_external_configs()
    checkpoint_records = []
    for method, checkpoint in CHECKPOINTS.items():
        model, state_key = module.build_model(checkpoint, "cuda:0", True)
        checkpoint_records.append({
            "method": method,
            "checkpoint": str(checkpoint),
            "checkpoint_sha256": sha256(checkpoint),
            "state_key": state_key,
        })
        for suite, config in suite_configs.items():
            raw_dirs = {
                row["name"]: Path(inference_manifests[suite]["output_dirs"]["Raw"][row["name"]])
                for row in config["dataset"]["families"]
            }
            target_root = OUTPUT / suite / "results" / "reconstructions" / method
            inference_manifests[suite]["output_dirs"][method] = reconstruct_tree(module, model, raw_dirs, target_root)

        sem_cfg = json.loads((R82 / "config" / "experiment.json").read_text(encoding="utf-8"))["sem_acm"]
        raw_sem = Path(sem_cfg["raw_input_dir"])
        sem_target = OUTPUT / "SEM" / "results" / "reconstructions" / "sem_acm" / method
        for exposure in sem_cfg["optical_exposures"]:
            source = raw_sem / f"{exposure}.bmp"
            image = module.read_gray(source)
            reconstruction = module.infer_tiled(model, image, "cuda:0", 4096, 0)
            module.write_bmp(sem_target / source.name, reconstruction)
        del model

    for suite, manifest in inference_manifests.items():
        path = OUTPUT / suite / "results" / "inference_manifest.json"
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    r82_config = json.loads((R82 / "config" / "experiment.json").read_text(encoding="utf-8"))
    sem_root = OUTPUT / "SEM"
    (sem_root / "config").mkdir(parents=True, exist_ok=True)
    sem_config = {
        "experiment_id": "R83_pilot_screen_SEM",
        "models": {name: {} for name in ["R79", *CHECKPOINTS]},
        "sem_acm": r82_config["sem_acm"],
    }
    (sem_root / "config" / "experiment.json").write_text(json.dumps(sem_config, indent=2, ensure_ascii=False), encoding="utf-8")
    prior_r79 = R82 / "results" / "reconstructions" / "sem_acm" / "R79"
    r79_target = sem_root / "results" / "reconstructions" / "sem_acm" / "R79"
    r79_target.mkdir(parents=True, exist_ok=True)
    for source in prior_r79.glob("*.bmp"):
        shutil.copy2(source, r79_target / source.name)

    manifest = {
        "experiment_id": CONFIG["experiment_id"],
        "role": "pilot_candidate_developmental_screen",
        "checkpoint_records": checkpoint_records,
        "sem_selection_scope": CONFIG["locked_confirmation"]["sem_acm"]["development_pillar_ids"],
        "reserved_sem_confirmation_scope": CONFIG["locked_confirmation"]["sem_acm"]["reserved_confirmation_pillar_ids"],
    }
    (OUTPUT / "inference_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"prepared": True, **manifest}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
