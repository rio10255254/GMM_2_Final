"""Prepare the locked epoch-0/5/.../30 developmental ACM checkpoint screen."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
R82 = Path(r"D:\GMM_2_Final\Experiments\R82_R39R40CrossSceneGeneralizationBenchmark")
OUTPUT = ROOT / "results" / "formal_checkpoint_screen"
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
EPOCHS = [5, 10, 15, 20, 25, 30]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def formal_run() -> Path:
    matches = [
        path for path in (ROOT / "runs").glob("*adapter_tail_formal*")
        if path.is_dir() and (path / "epoch_030.pth.tar").is_file() and not (path / "INVALIDATED.json").is_file()
    ]
    if not matches:
        raise FileNotFoundError("Completed 30-epoch R83 formal run was not found.")
    return max(matches, key=lambda path: path.stat().st_mtime_ns)


def checkpoint_map(run: Path) -> dict[str, Path]:
    mapping = {f"R83E{epoch:02d}": run / f"epoch_{epoch:03d}.pth.tar" for epoch in EPOCHS}
    for method, checkpoint in mapping.items():
        if not checkpoint.is_file():
            raise FileNotFoundError(f"Missing locked candidate {method}: {checkpoint}")
        payload = torch.load(checkpoint, map_location="cpu")
        if int(payload.get("epoch", -1)) != int(method[-2:]):
            raise RuntimeError(f"Checkpoint epoch mismatch for {method}")
        if not isinstance(payload.get("ema_state_dict"), dict):
            raise RuntimeError(f"EMA state is missing for {method}")
    return mapping


def load_inference_module():
    path = ROOT / "inference" / "infer_r83.py"
    spec = importlib.util.spec_from_file_location("r83_inference_for_formal_screen", path)
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


def prepare_external_configs(methods: list[str]) -> tuple[dict, dict]:
    configs, manifests = {}, {}
    for suite in ("R73_novel_shapes", "R74_hard_microscopy"):
        source_root = R82 / "results" / "acm_external" / suite
        config = json.loads((source_root / "config" / "experiment.json").read_text(encoding="utf-8"))
        prior = json.loads((source_root / "results" / "inference_manifest.json").read_text(encoding="utf-8"))
        suite_root = OUTPUT / suite
        (suite_root / "config").mkdir(parents=True, exist_ok=True)
        (suite_root / "results").mkdir(parents=True, exist_ok=True)
        config["experiment_id"] = f"R83_formal_checkpoint_screen_{suite}"
        (suite_root / "config" / "experiment.json").write_text(
            json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        configs[suite] = config
        manifests[suite] = {
            "suite": suite,
            "methods": ["Raw", "R79", *methods],
            "output_dirs": {"Raw": prior["output_dirs"]["Raw"], "R79": prior["output_dirs"]["R79"]},
        }
    return configs, manifests


def main() -> int:
    selection = CONFIG["formal_checkpoint_selection"]
    if selection["eligible_epochs"] != [0, *EPOCHS]:
        raise RuntimeError("Formal checkpoint epoch lock changed.")
    run = formal_run()
    checkpoints = checkpoint_map(run)
    methods = list(checkpoints)
    module = load_inference_module()
    suite_configs, inference_manifests = prepare_external_configs(methods)
    r82_config = json.loads((R82 / "config" / "experiment.json").read_text(encoding="utf-8"))
    sem_cfg = r82_config["sem_acm"]
    raw_sem = Path(sem_cfg["raw_input_dir"])
    checkpoint_records = []

    for method, checkpoint in checkpoints.items():
        model, state_key = module.build_model(checkpoint, "cuda:0", True)
        if state_key != "ema_state_dict":
            raise RuntimeError(f"Formal screen must use EMA weights, got {state_key} for {method}")
        checkpoint_records.append({
            "method": method,
            "epoch": int(method[-2:]),
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
            inference_manifests[suite]["output_dirs"][method] = reconstruct_tree(
                module, model, raw_dirs, target_root
            )
        sem_target = OUTPUT / "SEM" / "results" / "reconstructions" / "sem_acm" / method
        for exposure in sem_cfg["optical_exposures"]:
            source = raw_sem / f"{exposure}.bmp"
            reconstruction = module.infer_tiled(model, module.read_gray(source), "cuda:0", 4096, 0)
            module.write_bmp(sem_target / source.name, reconstruction)
        del model
        torch.cuda.empty_cache()

    for suite, manifest in inference_manifests.items():
        (OUTPUT / suite / "results" / "inference_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    sem_root = OUTPUT / "SEM"
    (sem_root / "config").mkdir(parents=True, exist_ok=True)
    selected_sem_cfg = dict(sem_cfg)
    selected_sem_cfg["selected_pillar_ids"] = CONFIG["locked_confirmation"]["sem_acm"]["development_pillar_ids"]
    sem_config = {
        "experiment_id": "R83_formal_checkpoint_screen_SEM_development_only",
        "models": {name: {} for name in ["R79", *methods]},
        "sem_acm": selected_sem_cfg,
    }
    (sem_root / "config" / "experiment.json").write_text(
        json.dumps(sem_config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    prior_r79 = R82 / "results" / "reconstructions" / "sem_acm" / "R79"
    r79_target = sem_root / "results" / "reconstructions" / "sem_acm" / "R79"
    r79_target.mkdir(parents=True, exist_ok=True)
    for source in prior_r79.glob("*.bmp"):
        shutil.copy2(source, r79_target / source.name)

    manifest = {
        "experiment_id": CONFIG["experiment_id"],
        "role": "locked_formal_checkpoint_developmental_screen",
        "formal_run": str(run),
        "checkpoint_records": checkpoint_records,
        "epoch_zero_baseline": CONFIG["parent_model"],
        "selection_policy": selection,
        "sem_processed_pillar_ids": selected_sem_cfg["selected_pillar_ids"],
        "reserved_confirmation_processed": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "inference_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"prepared": True, **manifest}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
