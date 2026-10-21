"""Verify identical checkpoint structure and fixed optical tensors across R63 runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import torch


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = EXPERIMENT_ROOT / "results" / "training_manifest.json"
OPTICAL_KEYS = (
    "physics_layer.PSFs",
    "physics_layer.PSF_mean",
    "physics_layer.PSF_center",
    "physics_layer.alpha",
    "physics_layer.reg",
)
DECLARED_REMOVED_PREFIXES = {
    "no_boundary_residual_adapter": ("boundary_adapter.",),
    "no_quality_gate": ("quality_gate.",),
}


def tensor_digest(tensor: torch.Tensor) -> str:
    value = tensor.detach().cpu().contiguous().numpy()
    return hashlib.sha256(value.tobytes()).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not manifest.get("complete"):
        raise RuntimeError("Training manifest is incomplete")
    reference_record = next(
        record
        for record in manifest["records"]
        if record["variant"] == "full_control" and int(record["seed"]) == 1261200
    )
    reference_payload = torch.load(Path(reference_record["checkpoint"]), map_location="cpu")
    reference_state = reference_payload["state_dict"]
    reference_model_config = reference_payload.get("model_config", {})
    reference_output_config = {
        "boundary_residual_adapter": bool(
            reference_model_config.get("boundary_residual_adapter", {}).get("enable")
        ),
        "raw_anchor_output": str(
            reference_model_config.get("raw_anchor_output", {}).get("mode")
        ),
        "quality_gate": bool(reference_model_config.get("quality_gate", {}).get("enable")),
    }
    if reference_output_config != {
        "boundary_residual_adapter": True,
        "raw_anchor_output": "detail",
        "quality_gate": True,
    }:
        raise RuntimeError(f"Unexpected full-control output config: {reference_output_config}")
    reference_signature = {
        key: (tuple(value.shape), str(value.dtype))
        for key, value in reference_state.items()
    }
    records = []
    structure_digests: dict[str, set[str]] = {}
    optical_digests: dict[str, set[str]] = {key: set() for key in OPTICAL_KEYS}
    for record in manifest["records"]:
        checkpoint = Path(record["checkpoint"])
        payload = torch.load(checkpoint, map_location="cpu")
        state = payload["state_dict"]
        model_config = payload.get("model_config", {})
        actual_output_config = {
            "boundary_residual_adapter": bool(
                model_config.get("boundary_residual_adapter", {}).get("enable")
            ),
            "raw_anchor_output": str(model_config.get("raw_anchor_output", {}).get("mode")),
            "quality_gate": bool(model_config.get("quality_gate", {}).get("enable")),
        }
        expected_output_config = dict(reference_output_config)
        if record["variant"] == "no_boundary_residual_adapter":
            expected_output_config["boundary_residual_adapter"] = False
        if record["variant"] == "no_raw_position_anchor":
            expected_output_config["raw_anchor_output"] = "none"
        if record["variant"] == "no_quality_gate":
            expected_output_config["quality_gate"] = False
        if actual_output_config != expected_output_config:
            raise RuntimeError(
                f"{record['variant']}/seed{record['seed']}: output config "
                f"{actual_output_config} != {expected_output_config}"
            )
        signature = "\n".join(
            f"{key}|{tuple(value.shape)}|{str(value.dtype)}" for key, value in sorted(state.items())
        )
        structure = hashlib.sha256(signature.encode("utf-8")).hexdigest()
        structure_digests.setdefault(str(record["variant"]), set()).add(structure)
        removed_prefixes = DECLARED_REMOVED_PREFIXES.get(str(record["variant"]), ())
        expected_signature = {
            key: value
            for key, value in reference_signature.items()
            if not any(key.startswith(prefix) for prefix in removed_prefixes)
        }
        actual_signature = {
            key: (tuple(value.shape), str(value.dtype))
            for key, value in state.items()
        }
        if actual_signature != expected_signature:
            missing = sorted(set(expected_signature) - set(actual_signature))
            extra = sorted(set(actual_signature) - set(expected_signature))
            mismatched = sorted(
                key
                for key in set(expected_signature) & set(actual_signature)
                if expected_signature[key] != actual_signature[key]
            )
            raise RuntimeError(
                f"{record['variant']}/seed{record['seed']}: undeclared structure difference; "
                f"missing={missing}, extra={extra}, mismatched={mismatched}"
            )
        optical = {}
        for key in OPTICAL_KEYS:
            if key not in state:
                raise RuntimeError(f"{checkpoint}: missing optical tensor {key}")
            digest = tensor_digest(state[key])
            optical[key] = digest
            optical_digests[key].add(digest)
        records.append(
            {
                "variant": record["variant"],
                "seed": record["seed"],
                "checkpoint": str(checkpoint),
                "state_key_count": len(state),
                "structure_sha256": structure,
                "declared_removed_prefixes": list(removed_prefixes),
                "structure_matches_declared_architecture": True,
                "output_config": actual_output_config,
                "output_config_matches_declared_variant": True,
                "optical_tensor_sha256": optical,
                "checkpoint_epoch": int(payload.get("epoch", -1)),
            }
        )
    inconsistent_variants = {
        variant: sorted(digests)
        for variant, digests in structure_digests.items()
        if len(digests) != 1
    }
    if inconsistent_variants:
        raise RuntimeError(f"Structure differs across seeds: {inconsistent_variants}")
    optical_mismatches = {key: sorted(values) for key, values in optical_digests.items() if len(values) != 1}
    if optical_mismatches:
        raise RuntimeError(f"Optical tensor mismatch: {optical_mismatches}")
    result = {
        "record_count": len(records),
        "structure_matches_declared_architecture": True,
        "structure_sha256_by_variant": {
            variant: next(iter(digests)) for variant, digests in structure_digests.items()
        },
        "declared_removed_prefixes": {
            key: list(value) for key, value in DECLARED_REMOVED_PREFIXES.items()
        },
        "optical_tensors_identical": True,
        "optical_tensor_sha256": {key: next(iter(values)) for key, values in optical_digests.items()},
        "records": records,
    }
    output = EXPERIMENT_ROOT / "results" / "checkpoint_structure_audit.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("record_count", "structure_matches_declared_architecture", "optical_tensors_identical")}, indent=2))


if __name__ == "__main__":
    main()
