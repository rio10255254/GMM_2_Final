"""Quantify R109 training composition, loss budget, and checkpoint trajectory."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
R109 = Path(PROJECT_ROOT / CONFIG["sources"]["r109_root"])
OUTPUT = ROOT / "results" / "training_contract"
OUTPUT.mkdir(parents=True, exist_ok=True)
R109_CONFIG = json.loads((R109 / "config" / "experiment.json").read_text(encoding="utf-8"))
HISTORY_PATH = R109 / "runs" / "r109_formal_scratch_continuous_b8_20260826" / "training_history.json"
PROFILE_PATH = ROOT / "results" / "data_profile" / "per_record_profile.csv"


def main() -> int:
    history = pd.DataFrame(json.loads(HISTORY_PATH.read_text(encoding="utf-8")))
    profile = pd.read_csv(PROFILE_PATH)
    train_profile = profile.loc[profile.split.eq("train")]
    weights = {name: float(value) for name, value in R109_CONFIG["training"]["renderer_loss_weights"].items()}
    frequencies = {
        "translation": 1 / float(R109_CONFIG["training"]["auxiliary_frequency"]["translation_every_steps"]),
        "exposure": 1 / float(R109_CONFIG["training"]["auxiliary_frequency"]["exposure_every_steps"]),
        "tile": 1 / float(R109_CONFIG["training"]["auxiliary_frequency"]["tile_every_steps"]),
    }
    renderer = history.loc[history.stage.eq("renderer")].copy()
    contribution_rows = []
    for row in renderer.itertuples(index=False):
        expected_sum = 0.0
        current = []
        for loss, weight in weights.items():
            column = f"train_{loss}"
            if column not in renderer.columns or pd.isna(getattr(row, column)):
                continue
            frequency = frequencies.get(loss, 1.0)
            contribution = float(getattr(row, column)) * weight * frequency
            expected_sum += contribution
            current.append((loss, contribution, float(getattr(row, column)), weight, frequency))
        for loss, contribution, raw, weight, frequency in current:
            contribution_rows.append({
                "epoch": int(row.epoch), "loss": loss, "raw_value": raw,
                "configured_weight": weight, "effective_frequency": frequency,
                "expected_weighted_contribution": contribution,
                "fraction_of_expected_sum": contribution / max(expected_sum, 1e-12),
            })
    contribution_frame = pd.DataFrame(contribution_rows)
    contribution_frame.to_csv(OUTPUT / "per_epoch_loss_budget.csv", index=False, encoding="utf-8-sig")

    family = train_profile.groupby("family", as_index=False).agg(
        records=("scene_id", "size"),
        edge_weight_sum=("training_edge_weight_sum", "sum"),
        perimeter_sum=("perimeter_px", "sum"),
    )
    family["record_share"] = family.records / family.records.sum()
    family["edge_weight_share"] = family.edge_weight_sum / family.edge_weight_sum.sum()
    family["perimeter_share"] = family.perimeter_sum / family.perimeter_sum.sum()
    family.to_csv(OUTPUT / "family_effective_boundary_weight.csv", index=False, encoding="utf-8-sig")

    roles = train_profile.role.value_counts()
    record_identity_fraction = float(roles.get("identity", 0) / len(train_profile))
    effective_identity_fraction = 0.5 + 0.5 * record_identity_fraction
    structural_degraded_fraction = float((roles.get("edge", 0) + roles.get("textured_edge", 0)) / (2 * len(train_profile)))
    flat_degraded_fraction = float(roles.get("flat_negative", 0) / (2 * len(train_profile)))
    detector = history.loc[history.stage.eq("detector")]
    peak_width_row = renderer.loc[renderer.validation_width_gain_mean.idxmax()]
    final = renderer.iloc[-1]
    first = renderer.iloc[0]
    final_budget = contribution_frame.loc[contribution_frame.epoch.eq(int(final.epoch))].sort_values("fraction_of_expected_sum", ascending=False)
    dense = family.set_index("family").loc["dense_array"]
    summary = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "training_samples": {
            "records": len(train_profile),
            "flattened_observations_per_epoch": 2 * len(train_profile),
            "record_identity_role_fraction": record_identity_fraction,
            "effective_clear_identity_fraction": effective_identity_fraction,
            "effective_structural_degraded_fraction": structural_degraded_fraction,
            "effective_flat_degraded_fraction": flat_degraded_fraction,
        },
        "boundary_complexity_imbalance": {
            "dense_array_record_share": float(dense.record_share),
            "dense_array_edge_weight_share": float(dense.edge_weight_share),
            "dense_array_perimeter_share": float(dense.perimeter_share),
            "probability_batch8_contains_dense_array": float(1 - (1 - dense.record_share) ** 8),
        },
        "detector_stage": {
            "epochs": detector.epoch.astype(int).tolist(),
            "boundary_bce_start": float(detector.iloc[0].train_boundary_bce),
            "boundary_bce_end": float(detector.iloc[-1].train_boundary_bce),
            "boundary_dice_loss_start": float(detector.iloc[0].train_boundary_dice),
            "boundary_dice_loss_end": float(detector.iloc[-1].train_boundary_dice),
            "stalled_after_epoch": int(detector.loc[detector.train_total <= detector.train_total.min() * 1.001].epoch.min()),
            "frozen_for_renderer_epochs": int(len(renderer)),
            "necessity_target_computed_but_loss_zero": True,
        },
        "renderer_stage": {
            "epochs": len(renderer),
            "width_gain_first": float(first.validation_width_gain_mean),
            "width_gain_peak": float(peak_width_row.validation_width_gain_mean),
            "width_gain_peak_epoch": int(peak_width_row.epoch),
            "width_gain_final": float(final.validation_width_gain_mean),
            "width_gain_drop_from_peak_pct": float((1 - final.validation_width_gain_mean / peak_width_row.validation_width_gain_mean) * 100),
            "shift_abs_first": float(first.validation_normal_shift_abs_mean),
            "shift_abs_final": float(final.validation_normal_shift_abs_mean),
            "tile_loss_max": float(renderer.train_tile.max()),
            "translation_raw_final": float(final.train_translation),
            "exposure_raw_final": float(final.train_exposure),
        },
        "final_expected_loss_budget": final_budget.to_dict(orient="records"),
        "contract_findings": [
            "Every record contributes one clear companion, so more than half of flattened training observations are identity-like.",
            "Dense arrays are balanced by record count but dominate boundary-weighted pixels and therefore the edge-focused losses.",
            "The detector is frozen before renderer learning, so correction support cannot adapt to renderer errors.",
            "The necessity target is calculated but every necessity loss is exactly zero.",
            "The width target is one scalar per image derived only from Gaussian sigma and is broadcast spatially; it does not describe motion blur, halo, ghosting, fade, or local uncertainty.",
            "Translation and exposure terms are both low-magnitude and sparse; the tile term is identically zero for this already-local model.",
        ],
    }
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
