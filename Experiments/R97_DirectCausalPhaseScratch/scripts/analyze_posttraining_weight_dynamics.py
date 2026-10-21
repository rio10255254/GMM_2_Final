"""Measure how each R97 private tower and correction head changed across checkpoints."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / "weights" / "formal" / "seed_970043" / "R97_scratch_seed970043_20260813_200802" / "weights"
OUTPUT = ROOT / "results" / "posttraining_validation" / "weight_dynamics"
EPOCHS = [1, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48]
GROUP_PREFIXES = {
    "geometry": ("geometry_tower.", "geometry_head."),
    "nuisance": ("nuisance_tower.", "nuisance_head."),
    "radiometry": ("radiometry_tower.", "radiometry_head."),
    "local_contrast": ("local_contrast_tower.", "local_contrast_head."),
    "boundary": ("boundary_tower.", "boundary_head."),
    "texture": ("texture_tower.", "texture_head."),
}


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def selected(state: dict[str, torch.Tensor], prefixes: tuple[str, ...]) -> dict[str, torch.Tensor]:
    return {name: value.float() for name, value in state.items() if name.startswith(prefixes)}


def l2(state: dict[str, torch.Tensor]) -> float:
    return float(np.sqrt(sum(float(torch.sum(value.double() ** 2)) for value in state.values())))


def difference_l2(first: dict[str, torch.Tensor], second: dict[str, torch.Tensor]) -> float:
    return float(np.sqrt(sum(float(torch.sum((first[name].double() - second[name].double()) ** 2)) for name in first)))


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    previous: dict[str, dict[str, torch.Tensor]] = {}
    all_finite = True
    final_checkpoint = None
    for epoch in EPOCHS:
        checkpoint = torch.load(WEIGHTS / f"epoch_{epoch:03d}.pth.tar", map_location="cpu", weights_only=False)
        state = checkpoint["ema_state_dict"]
        all_finite = all_finite and all(bool(torch.isfinite(value).all()) for value in state.values())
        for group, prefixes in GROUP_PREFIXES.items():
            current = selected(state, prefixes)
            head = selected(state, tuple(prefix for prefix in prefixes if "head" in prefix))
            tower = selected(state, tuple(prefix for prefix in prefixes if "tower" in prefix))
            norm = l2(current)
            update = 0.0 if group not in previous else difference_l2(current, previous[group])
            rows.append({
                "epoch": epoch,
                "group": group,
                "group_l2": norm,
                "tower_l2": l2(tower),
                "head_l2": l2(head),
                "max_abs_head_parameter": max(float(value.abs().max()) for value in head.values()),
                "l2_change_from_previous_checkpoint": update,
                "relative_change_from_previous_checkpoint": update / max(norm, 1e-12),
            })
            previous[group] = {name: value.clone() for name, value in current.items()}
        final_checkpoint = checkpoint
        print(f"[weights] epoch {epoch}", flush=True)
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT / "group_trajectory.csv", index=False)
    if final_checkpoint is None:
        raise RuntimeError("No checkpoint loaded")
    online, ema = final_checkpoint["model_state_dict"], final_checkpoint["ema_state_dict"]
    online_vs_ema: list[dict] = []
    for group, prefixes in GROUP_PREFIXES.items():
        online_group = selected(online, prefixes)
        ema_group = selected(ema, prefixes)
        delta = difference_l2(online_group, ema_group)
        online_vs_ema.append({
            "group": group,
            "ema_l2": l2(ema_group),
            "online_l2": l2(online_group),
            "online_vs_ema_l2": delta,
            "online_vs_ema_relative": delta / max(l2(ema_group), 1e-12),
        })
    pd.DataFrame(online_vs_ema).to_csv(OUTPUT / "epoch048_online_vs_ema.csv", index=False)
    final_rows = table.loc[table["epoch"] == 48]
    result = {
        "status": "complete",
        "epochs": EPOCHS,
        "all_ema_parameters_finite": bool(all_finite),
        "final_group_statistics": final_rows.to_dict(orient="records"),
        "epoch048_online_vs_ema": online_vs_ema,
    }
    write_json(OUTPUT / "summary.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
