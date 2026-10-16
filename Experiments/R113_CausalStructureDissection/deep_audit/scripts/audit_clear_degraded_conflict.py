"""Directly compare paired clear and degraded gradient directions."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "loss_gradients"
from audit_loss_gradients import (
    CONFIG, DEVICE, WEIGHTS, build_model, choose_records, flatten_items,
    gradient_vectors, loss_components, parameter_groups, cosine,
)


def main() -> int:
    selected = choose_records()
    records = [selected[name][0] for name in ("standard", "boundary_fade", "mixed_hard")]
    model = build_model().to(DEVICE)
    model.load_state_dict(torch.load(Path(CONFIG["sources"]["r109_checkpoint"]), map_location=DEVICE, weights_only=False)["model"])
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(True)
    all_groups = parameter_groups(model)
    groups = {name: all_groups[name] for name in ("renderer_backbone", "width_head", "shift_head")}
    names = ("contour", "contour_bce", "direct", "reconstruction", "gradient", "width_target")
    vectors = {}
    values = {}
    for observation in ("degraded", "clear"):
        batch = flatten_items(records, observation)
        _detector, renderer = loss_components(model, batch, include_auxiliary=False)
        vectors[observation] = {}
        values[observation] = {}
        for index, name in enumerate(names):
            vectors[observation][name] = gradient_vectors(WEIGHTS[name] * renderer[name], groups, retain_graph=index < len(names) - 1)
            values[observation][name] = float(renderer[name].detach())
    rows = []
    totals = {observation: {} for observation in vectors}
    for group_name in groups:
        for observation in vectors:
            total = torch.zeros_like(vectors[observation][names[0]][group_name])
            for name in names:
                total = total + vectors[observation][name][group_name]
            totals[observation][group_name] = total
        for name in names:
            degraded = vectors["degraded"][name][group_name]
            clear = vectors["clear"][name][group_name]
            rows.append({
                "parameter_group": group_name,
                "loss": name,
                "degraded_loss_value": values["degraded"][name],
                "clear_loss_value": values["clear"][name],
                "degraded_gradient_norm": float(degraded.norm()),
                "clear_gradient_norm": float(clear.norm()),
                "clear_over_degraded_norm": float(clear.norm()) / max(float(degraded.norm()), 1e-20),
                "clear_vs_degraded_cosine": cosine(clear, degraded),
            })
        rows.append({
            "parameter_group": group_name,
            "loss": "expected_sum_of_six_base_losses",
            "degraded_loss_value": None,
            "clear_loss_value": None,
            "degraded_gradient_norm": float(totals["degraded"][group_name].norm()),
            "clear_gradient_norm": float(totals["clear"][group_name].norm()),
            "clear_over_degraded_norm": float(totals["clear"][group_name].norm()) / max(float(totals["degraded"][group_name].norm()), 1e-20),
            "clear_vs_degraded_cosine": cosine(totals["clear"][group_name], totals["degraded"][group_name]),
        })
    frame = pd.DataFrame(rows)
    frame.to_csv(OUTPUT / "clear_degraded_gradient_conflict.csv", index=False, encoding="utf-8-sig")
    safe_records = json.loads(frame.to_json(orient="records"))
    safe_totals = [row for row in safe_records if row["loss"] == "expected_sum_of_six_base_losses"]
    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "records": [int(index) for _epoch, index in records],
        "comparisons": safe_records,
        "total_gradient_conflict": safe_totals,
    }
    (OUTPUT / "clear_degraded_conflict_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
