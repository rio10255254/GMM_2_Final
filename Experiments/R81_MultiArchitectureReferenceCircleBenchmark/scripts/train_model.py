from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]


R81_ROOT = Path(__file__).resolve().parents[1]
MODERN_ROOT = (
    Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments'))
    / "Modern_Restoration_Benchmarks_20260719"
)
if str(MODERN_ROOT) not in sys.path:
    sys.path.insert(0, str(MODERN_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import train_modern_baseline as trainer  # noqa: E402
from model_zoo import (  # noqa: E402
    MODEL_SPECS,
    TRAINABLE_KEYS,
    build_model,
    serializable_spec,
    trainable_parameter_count,
)


DEFAULT_PACKAGE = (
    Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages'))
    / "V42_SoftLabelSNR_FullStandalone_20260709"
)

MICRO_BATCH = {
    "srcnn": 64,
    "vdsr": 64,
    "dncnn": 64,
    "unet": 64,
    "edsr": 64,
    "rdn": 64,
    "rcan": 64,
    "swinir": 32,
    "nafnet": 64,
    "restormer": 64,
    "pft": 32,
    "ucan": 16,
}


def install_registry() -> None:
    trainer.MODEL_SPECS = MODEL_SPECS
    trainer.build_model = build_model
    trainer.serializable_spec = serializable_spec
    trainer.trainable_parameter_count = trainable_parameter_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=TRAINABLE_KEYS, required=True)
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--micro-batch-size", type=int)
    parser.add_argument("--effective-batch-size", type=int, default=64)
    parser.add_argument("--validate-every", type=int, default=3)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--smoke-steps", type=int, default=0)
    return parser.parse_args()


def correct_manifest_text(output: Path) -> None:
    for filename in ("run_manifest.json", "training_summary.json"):
        path = output / filename
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["purpose"] = "Common-protocol external architecture baseline for R81"
        payload["common_training_rule"] = (
            "Same paired dataset and grouped split; 128-pixel random crops; fixed optical "
            "input adapter; L1+0.20*(1-SSIM); AdamW; "
            "effective batch 64; seed 1261200; "
            "15-epoch maximum; common validation schedule and best-validation checkpoint rule."
        )
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    arguments = parse_args()
    install_registry()
    output = arguments.output or (R81_ROOT / "results" / "training" / arguments.model)
    model_crop = 128
    amp_enabled = arguments.model != "pft"
    configuration = trainer.TrainConfig(
        model_key=arguments.model,
        epochs=arguments.epochs,
        crop_size=model_crop,
        micro_batch_size=arguments.micro_batch_size or MICRO_BATCH[arguments.model],
        effective_batch_size=arguments.effective_batch_size,
        validate_every=arguments.validate_every,
        amp=amp_enabled,
    )
    trainer.train(
        arguments.package.resolve(),
        output.resolve(),
        configuration,
        resume=arguments.resume,
        smoke_steps=arguments.smoke_steps,
    )
    correct_manifest_text(output.resolve())


if __name__ == "__main__":
    main()
