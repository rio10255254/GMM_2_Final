"""Independent completeness and visual QA for the bounded profile oracle probe."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "geometry_probe" / "E020" / "profile_action_probe"
SOURCE = Path(r"D:\GMM_2_Final\Experiments\R74_R61HardMicroscopyACMGeneralization\data\r74_hard_acm_val")


def read(path: str | Path) -> np.ndarray:
    value = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(path)
    return value


def make_montage(records: list[dict]) -> None:
    rows = []
    for family in ("asymmetric_blur_halo", "boundary_fade", "low_contrast", "mixed_hard", "uneven_illumination"):
        record = next(row for row in records if row["family"] == family)
        stage, filename = record["stage"], record["filename"]
        raw = read(record["src"])
        full = read(OUT / "inputs" / "Full" / stage / filename)
        profile = read(OUT / "inputs" / "FullPlusProfile" / stage / filename)
        change = np.clip(np.abs(profile.astype(np.int16) - full.astype(np.int16)) * 6, 0, 255).astype(np.uint8)
        images = [raw, full, profile, change]
        row = np.concatenate([cv2.resize(image, (320, 320), interpolation=cv2.INTER_AREA) for image in images], axis=1)
        cv2.putText(row, f"{family}: Raw | Full | Full+Profile | action x6", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, .65, 255, 2, cv2.LINE_AA)
        rows.append(row)
    montage = np.concatenate(rows, axis=0)
    if not cv2.imwrite(str(OUT / "representative_montage.png"), montage):
        raise RuntimeError("failed to write montage")


def main() -> int:
    summary = json.loads((OUT / "analysis_summary.json").read_text(encoding="utf-8"))
    action = pd.read_csv(OUT / "tables" / "profile_action_per_image.csv")
    primary = pd.read_csv(OUT / "locked_acm_contract" / "results" / "tables" / "primary_contour_metrics.csv")
    sensitivity = pd.read_csv(OUT / "locked_acm_contract" / "results" / "tables" / "acm_sensitivity_metrics.csv")
    records = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))["records"]
    full_files = list((OUT / "inputs" / "Full").rglob("*.bmp"))
    profile_files = list((OUT / "inputs" / "FullPlusProfile").rglob("*.bmp"))
    conclusion = summary["conclusion"]
    checks = {
        "summary_complete": summary.get("status") == "complete",
        "source_records_100": len(records) == 100,
        "full_inputs_100": len(full_files) == 100,
        "profile_inputs_100": len(profile_files) == 100,
        "action_rows_100": len(action) == 100,
        "primary_rows_600": len(primary) == 600,
        "sensitivity_rows_135": len(sensitivity) == 135,
        "full_copy_exact": float(summary["maximum_full_copy_error_gray"]) == 0.0,
        "action_bounded_48_gray": float(action["maximum_abs_change_gray"].max()) <= 48.001,
        "no_outside_band_action": float(action["maximum_outside_band_change_gray"].max()) == 0.0,
        "all_acm_success": all(int(value) == 0 for value in summary["acm_failures"].values()),
        "repairs_all_failure_families": bool(conclusion["new_action_repairs_all_three_failure_families_over_full"]),
        "all_failure_families_beat_raw": bool(conclusion["all_three_failure_families_beat_raw_on_both"]),
        "preserves_success_families": bool(conclusion["halo_and_uneven_preserved"]),
        "explicit_oracle_only": bool(conclusion["oracle_upper_bound_only"]) and not bool(conclusion["deployable_model_claim"]),
    }
    make_montage(records)
    result = {"status": "pass" if all(checks.values()) else "fail", "checks": checks}
    (OUT / "validation_report.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
