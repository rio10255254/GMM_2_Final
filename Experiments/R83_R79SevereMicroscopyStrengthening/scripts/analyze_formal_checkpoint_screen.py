"""Select and freeze the formal R83 checkpoint using developmental evidence only."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCREEN = ROOT / "results" / "formal_checkpoint_screen"
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def external(suite: str, prefix: str, methods: list[str]) -> pd.DataFrame:
    table = pd.read_csv(SCREEN / suite / "results" / "tables" / "primary_contour_metrics.csv")
    table = table.loc[(table["alignment"] == "translation_only") & table["method"].isin(methods)]
    return table.groupby("method", as_index=False).agg(**{
        f"{prefix}_boundary_px": ("mean_boundary_distance_px", "median"),
        f"{prefix}_iou": ("iou", "median"),
        f"{prefix}_acm_success": ("acm_success", "mean"),
    })


def sem(methods: list[str]) -> pd.DataFrame:
    table = pd.read_csv(SCREEN / "SEM" / "results" / "acm_sem" / "tables" / "primary_contour_metrics.csv")
    allowed = set(CONFIG["locked_confirmation"]["sem_acm"]["development_pillar_ids"])
    actual = set(int(value) for value in table["pillar_id"].unique())
    if actual != allowed:
        raise RuntimeError(f"SEM screen processed unexpected pillar IDs: {sorted(actual)}")
    table = table.loc[table["method"].isin(methods)]
    return table.groupby("method", as_index=False).agg(
        sem_dev_boundary_pitch_pct=("mean_boundary_distance_pitch_pct", "median"),
        sem_dev_iou=("iou", "median"),
    )


def main() -> int:
    manifest = json.loads((SCREEN / "inference_manifest.json").read_text(encoding="utf-8"))
    records = manifest["checkpoint_records"]
    methods = ["R79", *[record["method"] for record in records]]
    merged = external("R73_novel_shapes", "r73", methods).merge(
        external("R74_hard_microscopy", "r74", methods), on="method"
    ).merge(sem(methods), on="method")
    baseline = merged.loc[merged["method"] == "R79"].iloc[0]
    rules = CONFIG["formal_checkpoint_selection"]["eligibility_rules"]
    merged["epoch"] = merged["method"].str.extract(r"E(\d+)$")[0].fillna("0").astype(int)
    merged["beats_r79_r74"] = merged["r74_boundary_px"] < float(baseline["r74_boundary_px"])
    merged["r73_safe"] = (
        (merged["r73_boundary_px"] <= float(rules["r73_boundary_px_max"]))
        & (merged["r73_boundary_px"] <= float(baseline["r73_boundary_px"]) * float(rules["r73_boundary_px_relative_to_r79_max"]))
    )
    merged["sem_dev_safe"] = merged["sem_dev_boundary_pitch_pct"] <= (
        float(baseline["sem_dev_boundary_pitch_pct"])
        * float(rules["sem_development_boundary_pitch_pct_relative_to_r79_max"])
    )
    merged["eligible"] = (
        merged["beats_r79_r74"]
        & merged["r73_safe"]
        & merged["sem_dev_safe"]
        & (merged["r73_acm_success"] == float(rules["acm_success_required"]))
        & (merged["r74_acm_success"] == float(rules["acm_success_required"]))
    )
    candidates = merged.loc[(merged["method"] != "R79") & merged["eligible"]].sort_values(
        ["r74_boundary_px", "sem_dev_boundary_pitch_pct", "r73_boundary_px", "epoch"]
    )
    promoted = not candidates.empty
    selected_method = str(candidates.iloc[0]["method"]) if promoted else "R79"
    if promoted:
        record = next(item for item in records if item["method"] == selected_method)
        source = Path(record["checkpoint"])
        source_state_key = record["state_key"]
        selected_epoch = int(record["epoch"])
    else:
        source = ROOT / CONFIG["parent_model"]["seed_checkpoint"]
        source_state_key = "ema_state_dict"
        selected_epoch = 0
    selected_dir = ROOT / "weights" / "selected"
    selected_dir.mkdir(parents=True, exist_ok=True)
    destination = selected_dir / "r83_model.pth.tar"
    shutil.copy2(source, destination)
    frozen = {
        "experiment_id": CONFIG["experiment_id"],
        "status": "checkpoint_frozen_pending_reserved_confirmation",
        "selected_method": selected_method,
        "selected_epoch": selected_epoch,
        "fine_tune_promoted_over_r79": promoted,
        "source_checkpoint": str(source),
        "source_checkpoint_sha256": sha256(source),
        "frozen_checkpoint": str(destination),
        "frozen_checkpoint_sha256": sha256(destination),
        "state_key": source_state_key,
        "selection_used_only_developmental_evidence": True,
        "reserved_confirmation_processed": False,
        "frozen_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "safety_policy": CONFIG["frozen_output_safety_policy"],
    }
    (selected_dir / "selection_manifest.json").write_text(
        json.dumps(frozen, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    decision = {
        **frozen,
        "rows": merged.sort_values("epoch").where(pd.notna(merged), None).to_dict(orient="records"),
    }
    merged.sort_values("epoch").to_csv(SCREEN / "formal_checkpoint_summary.csv", index=False)
    (SCREEN / "decision.json").write_text(
        json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(decision, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
