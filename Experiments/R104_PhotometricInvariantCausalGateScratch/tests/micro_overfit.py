"""Tiny repeat-batch learning test.  It never creates a formal checkpoint."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import torch
from torch.utils.data._utils.collate import default_collate


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT, ROOT / "model", ROOT / "training"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from model.r104_model import build_model  # noqa: E402
from training.losses import loss_components  # noqa: E402
from training.r104_dataset import R104Dataset  # noqa: E402


def main() -> None:
    torch.manual_seed(1040059)
    config = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    dataset = R104Dataset("validation", 128, 0, validation_limit=24)
    batch = default_collate([dataset[index] for index in (0, 1, 2, 3, 4, 5, 6, 12, 18)])
    scenes, views = batch["source"].shape[:2]

    def flat(key: str) -> torch.Tensor:
        value = batch[key]
        return value.reshape(scenes * views, *value.shape[2:]).to(device)

    source, target, mask, sdf, illumination = [
        flat(key) for key in ("source", "target", "mask", "sdf", "illumination_target")
    ]
    motion = flat("motion")
    identity = flat("identity")
    mode = batch["mode"].repeat_interleave(views).to(device)
    pair_type = batch["pair_type"].repeat_interleave(views).to(device)
    weights = config["training"]["loss_weights"]
    model = build_model(base=int(config["model"]["base_channels"])).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=4e-4, weight_decay=0.0, fused=device.type == "cuda")

    def evaluate() -> tuple[torch.Tensor, dict[str, float]]:
        details = model.forward_details(source)
        parts = loss_components(
            details, source, target, mask, sdf, illumination, identity,
            mode, pair_type, motion, core_size=96,
        )
        total = sum(parts[name] * float(weights[name]) for name in parts)
        return total, {name: float(value.detach()) for name, value in parts.items()}

    model.train()
    initial, initial_parts = evaluate()
    history = [float(initial.detach())]
    for _step in range(60):
        optimizer.zero_grad(set_to_none=True)
        total, _parts = evaluate()
        total.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 2.0)
        optimizer.step()
        history.append(float(total.detach()))
    final, final_parts = evaluate()
    with torch.no_grad():
        final_details = model.forward_details(source)
        gate_probability = 0.25 * (
            final_details.low_gate + final_details.illumination_gate
            + final_details.contour_gate + final_details.texture_gate
        ) / 1.15
        active_rows = (~identity) & (mode != 5)
        final_identity_gate_mean = float(gate_probability[identity].mean())
        final_active_gate_mean = float(gate_probability[active_rows].mean())
    final_value = float(final.detach())
    initial_value = float(initial.detach())
    if not final_value < initial_value * 0.90:
        raise AssertionError(f"micro-overfit did not learn enough: {initial_value} -> {final_value}")
    if not final_parts["high_frequency"] < initial_parts["high_frequency"] * 0.95:
        raise AssertionError("high-frequency reconstruction did not learn")
    if not final_parts["proposal_supervision"] < initial_parts["proposal_supervision"]:
        raise AssertionError("correction proposals did not learn")
    if not final_parts["gate_supervision"] < initial_parts["gate_supervision"] * 0.85:
        raise AssertionError("correction-need gates did not learn")
    if not final_active_gate_mean > final_identity_gate_mean:
        raise AssertionError("gates did not begin separating active and identity observations")
    result = {
        "status": "passed",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "formal_training_started": False,
        "steps": 60,
        "initial_total": initial_value,
        "final_total": final_value,
        "relative_reduction": 1.0 - final_value / initial_value,
        "final_identity_gate_mean": final_identity_gate_mean,
        "final_active_gate_mean": final_active_gate_mean,
        "history": history,
        "initial_components": initial_parts,
        "final_components": final_parts,
    }
    destination = ROOT / "reports" / "micro_overfit.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
