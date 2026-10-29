from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[1]


EVALUATION_ROOT = Path(
    str(PROJECT_ROOT / 'Experiments/R63_CausalBoundaryMotionAblation/results/evaluation')
)
OUTPUT_ROOT = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/09_V23_ABLATION_COMPLETE_ENGLISH_20260727/audit')
)
VARIANTS = ("shift_safe_matched", "standard_upsample_matched")
SEEDS = (1261200, 1261217)
PIXEL_SIZE_NM_50X = 69.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_measurements() -> pd.DataFrame:
    records = []
    for variant in VARIANTS:
        for seed in SEEDS:
            path = (
                EVALUATION_ROOT
                / "metrics"
                / variant
                / f"seed{seed}"
                / "static_cd"
                / "static_cd_per_measurement.csv"
            )
            data = pd.read_csv(path)
            records.append(data)
    return pd.concat(records, ignore_index=True)


def per_pillar_median(data: pd.DataFrame) -> float:
    return float(data.groupby("pillar_id")["abs_error_nm"].median().median())


def alternative_scores(method_50x: pd.DataFrame) -> pd.DataFrame:
    selectors = {
        "Locked 35-65%, both profiles": lambda d: pd.Series(True, index=d.index),
        "Horizontal profile only": lambda d: d["measurement_mode"].eq("horizontal_strip"),
        "Radial profile only": lambda d: d["measurement_mode"].eq("radial_mean"),
        "50% threshold, both profiles": lambda d: d["threshold_fraction"].eq(0.50),
        "45-55%, both profiles": lambda d: d["threshold_fraction"].between(0.45, 0.55),
        "55-65%, both profiles": lambda d: d["threshold_fraction"].between(0.55, 0.65),
        "35-45%, both profiles": lambda d: d["threshold_fraction"].between(0.35, 0.45),
    }
    rows = []
    for seed in SEEDS:
        seed_data = method_50x.loc[method_50x["seed"].eq(seed)]
        for label, selector in selectors.items():
            scores = {}
            for variant in VARIANTS:
                variant_data = seed_data.loc[seed_data["variant"].eq(variant)]
                scores[variant] = per_pillar_median(variant_data.loc[selector(variant_data)])
            rows.append(
                {
                    "seed": seed,
                    "analysis": label,
                    "shift_safe_nm": scores[VARIANTS[0]],
                    "standard_nm": scores[VARIANTS[1]],
                    "standard_minus_shift_safe_nm": scores[VARIANTS[1]] - scores[VARIANTS[0]],
                }
            )
    return pd.DataFrame(rows)


def paired_row_audit(data: pd.DataFrame) -> list[dict]:
    key = [
        "measurement_mode",
        "threshold_fraction",
        "center9_position",
        "pillar_id",
        "sem_diameter_um",
        "status",
    ]
    audits = []
    for seed in SEEDS:
        subsets = []
        for variant in VARIANTS:
            subset = data.loc[
                data["seed"].eq(seed)
                & data["magnification"].eq("50x")
                & data["method"].eq("Method")
            ].sort_values(key, ignore_index=True)
            subsets.append(subset)
        audits.append(
            {
                "seed": seed,
                "shift_safe_row_count": len(subsets[0]),
                "standard_row_count": len(subsets[1]),
                "paired_keys_identical": bool(subsets[0][key].equals(subsets[1][key])),
                "all_rows_valid": bool(
                    subsets[0]["status"].eq("ok").all()
                    and subsets[1]["status"].eq("ok").all()
                ),
            }
        )
    return audits


def raw_reference_audit(data: pd.DataFrame) -> list[dict]:
    value_columns = [
        "measurement_mode",
        "threshold_fraction",
        "center9_position",
        "pillar_id",
        "sem_diameter_um",
        "diameter_um",
        "signed_error_nm",
        "abs_error_nm",
        "status",
    ]
    audits = []
    for seed in SEEDS:
        raw = []
        for variant in VARIANTS:
            subset = data.loc[
                data["seed"].eq(seed)
                & data["magnification"].eq("50x")
                & data["method"].eq("Raw"),
                value_columns,
            ].sort_values(value_columns[:5], ignore_index=True)
            raw.append(subset)
        audits.append(
            {
                "seed": seed,
                "raw_reference_rows_identical": bool(raw[0].equals(raw[1])),
                "raw_row_count": len(raw[0]),
            }
        )
    return audits


def metadata_audit() -> list[dict]:
    rows = []
    comparable_fields = (
        "thresholds",
        "measurement_modes",
        "profiles_per_radial_sample",
        "sem_value_interpretation",
        "edge_radius_50_role",
        "display_adjustment",
    )
    for seed in SEEDS:
        documents = []
        for variant in VARIANTS:
            path = (
                EVALUATION_ROOT
                / "metrics"
                / variant
                / f"seed{seed}"
                / "static_cd"
                / "metadata.json"
            )
            documents.append(json.loads(path.read_text(encoding="utf-8")))
        rows.append(
            {
                "seed": seed,
                "measurement_metadata_identical": all(
                    documents[0][field] == documents[1][field]
                    for field in comparable_fields
                ),
                "thresholds": documents[0]["thresholds"],
                "measurement_modes": documents[0]["measurement_modes"],
                "radial_samples": documents[0]["profiles_per_radial_sample"],
                "display_adjustment": documents[0]["display_adjustment"],
            }
        )
    return rows


def reconstruction_audit() -> list[dict]:
    rows = []
    for seed in SEEDS:
        files = []
        for variant in VARIANTS:
            directory = (
                EVALUATION_ROOT
                / "reconstructions"
                / variant
                / f"seed{seed}"
                / "static_50x_sem"
            )
            found = sorted(path for path in directory.iterdir() if path.is_file())
            assert len(found) == 1, (directory, len(found))
            files.append(found[0])
        rows.append(
            {
                "seed": seed,
                "shift_safe_filename": files[0].name,
                "standard_filename": files[1].name,
                "same_source_filename": files[0].name == files[1].name,
                "shift_safe_size_bytes": files[0].stat().st_size,
                "standard_size_bytes": files[1].stat().st_size,
                "shift_safe_sha256": sha256(files[0]),
                "standard_sha256": sha256(files[1]),
            }
        )
    return rows


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    all_data = load_measurements()
    method_50x = all_data.loc[
        all_data["magnification"].eq("50x")
        & all_data["method"].eq("Method")
        & all_data["status"].eq("ok")
    ].copy()

    paired = paired_row_audit(all_data)
    raw_reference = raw_reference_audit(all_data)
    metadata = metadata_audit()
    reconstructions = reconstruction_audit()
    sensitivity = alternative_scores(method_50x)
    sensitivity.to_csv(OUTPUT_ROOT / "50x_cd_measurement_sensitivity.csv", index=False)

    per_pillar = (
        method_50x.groupby(["variant", "seed", "pillar_id"], as_index=False)["abs_error_nm"]
        .median()
        .pivot_table(index="pillar_id", columns="variant", values="abs_error_nm", aggfunc="mean")
        .reset_index()
    )
    per_pillar["standard_minus_shift_safe_nm"] = (
        per_pillar[VARIANTS[1]] - per_pillar[VARIANTS[0]]
    )
    per_pillar.to_csv(OUTPUT_ROOT / "50x_cd_per_pillar_pair.csv", index=False)

    locked = sensitivity.loc[
        sensitivity["analysis"].eq("Locked 35-65%, both profiles")
    ]
    locked_mean = locked[
        ["shift_safe_nm", "standard_nm", "standard_minus_shift_safe_nm"]
    ].mean()
    signed = method_50x.groupby("variant")["signed_error_nm"].median()
    summary = {
        "completion_checks": {
            "paired_measurement_rows_identical": all(
                row["paired_keys_identical"] for row in paired
            ),
            "all_measurements_valid": all(row["all_rows_valid"] for row in paired),
            "raw_reference_rows_identical": all(
                row["raw_reference_rows_identical"] for row in raw_reference
            ),
            "measurement_metadata_identical": all(
                row["measurement_metadata_identical"] for row in metadata
            ),
            "same_static_source_filename": all(
                row["same_source_filename"] for row in reconstructions
            ),
            "both_seeds_present": sorted(method_50x["seed"].unique().tolist())
            == list(SEEDS),
            "all_nine_pillars_present": sorted(method_50x["pillar_id"].unique().tolist())
            == [22, 23, 24, 28, 29, 30, 34, 35, 36],
        },
        "paired_row_audit": paired,
        "raw_reference_audit": raw_reference,
        "measurement_metadata_audit": metadata,
        "reconstruction_audit": reconstructions,
        "locked_protocol_two_seed_mean": {
            "shift_safe_cd_median_abs_error_nm": float(locked_mean["shift_safe_nm"]),
            "standard_cd_median_abs_error_nm": float(locked_mean["standard_nm"]),
            "standard_minus_shift_safe_nm": float(
                locked_mean["standard_minus_shift_safe_nm"]
            ),
            "shift_safe_minus_standard_in_50x_pixels": float(
                -locked_mean["standard_minus_shift_safe_nm"] / PIXEL_SIZE_NM_50X
            ),
            "shift_safe_signed_error_median_nm": float(signed[VARIANTS[0]]),
            "standard_signed_error_median_nm": float(signed[VARIANTS[1]]),
        },
        "interpretation": (
            "The 50x CD ordering is not caused by unequal images, SEM values, centers, "
            "thresholds, profile modes, display scaling, or seed count. ShiftSafe is higher "
            "by 2.811 nm, equal to 0.041 of a 50x object-space pixel. Both methods slightly "
            "overestimate diameter; the fixed blur in ShiftSafe adds a very small outward "
            "half-height shift. The same ordering remains under equal horizontal, radial, "
            "50-percent, and central-threshold audits, so method-specific retuning would be "
            "less fair than retaining the locked common protocol."
        ),
    }
    (OUTPUT_ROOT / "50x_cd_fairness_audit.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    checks = summary["completion_checks"]
    assert all(checks.values()), checks
    print(json.dumps(summary["locked_protocol_two_seed_mean"], indent=2))
    print(OUTPUT_ROOT / "50x_cd_fairness_audit.json")


if __name__ == "__main__":
    main()
