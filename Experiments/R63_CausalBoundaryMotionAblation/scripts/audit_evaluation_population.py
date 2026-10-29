"""Audit which R63 evaluation populations are independent of the training package."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_ROOT.parents[1]
PACKAGE_ROOT = (
    REPO_ROOT
    / "Deliverables"
    / "Standalone_Models"
    / "V42_SoftLabelSNR_FullStandalone_20260709"
)
MANIFEST_PATH = PACKAGE_ROOT / "training_data" / "manifest.json"
SPLIT_META_PATH = (
    PACKAGE_ROOT
    / "training_data"
    / "splits"
    / "grouped_seed1337_val120"
    / "split_meta.json"
)


def pair_text(pair: dict) -> str:
    return " ".join(str(value) for value in pair.values()).lower()


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pairs = list(manifest["pairs"])
    split_meta = json.loads(SPLIT_META_PATH.read_text(encoding="utf-8"))

    target_counts = Counter(str(pair.get("target_dataset", "unspecified")) for pair in pairs)
    role_counts = Counter(str(pair.get("role", "unspecified")) for pair in pairs)
    texts = [pair_text(pair) for pair in pairs]
    family_counts = {
        "20260702_100MG": sum("20260702_100mg" in text for text in texts),
        "20260704_20x_5x": sum("20260704_20x_5x" in text for text in texts),
        "20260618_100MG": sum("20260618_100mg" in text for text in texts),
    }

    populations = {
        "50x_static_sem_cd": {
            "capture_family": "20260618_100MG",
            "training_manifest_matches": family_counts["20260618_100MG"],
            "classification": "package-manifest-unseen capture family",
            "limitation": "the packaged manifest cannot prove absence from all earlier checkpoint ancestry",
        },
        "20x_frame49_sem_cd": {
            "capture_family": "20260704_20x_5x",
            "training_manifest_matches": family_counts["20260704_20x_5x"],
            "classification": "same capture family represented in training",
        },
        "four_real_displacement_sequences": {
            "capture_families": ["20260702_100MG", "20260704_20x_5x"],
            "training_manifest_matches": {
                "20260702_100MG": family_counts["20260702_100MG"],
                "20260704_20x_5x": family_counts["20260704_20x_5x"],
            },
            "classification": "same-domain mechanism evaluation",
        },
        "external_gmf": {
            "classification": "unavailable and excluded from the confirmatory verdict",
            "reason": "original Raw source folders were unavailable; earlier reconstructions are not reused as Raw inputs",
        },
    }
    if populations["50x_static_sem_cd"]["training_manifest_matches"] != 0:
        raise RuntimeError("The package-manifest-unseen 50x static capture appears in training")
    if family_counts["20260702_100MG"] <= 0 or family_counts["20260704_20x_5x"] <= 0:
        raise RuntimeError("Expected same-domain sequence families were not found in the training manifest")
    if int(split_meta.get("group_overlap_count", -1)) != 0:
        raise RuntimeError("Fixed train/validation split has group overlap")

    audit = {
        "training_pair_count": len(pairs),
        "training_target_dataset_counts": dict(target_counts),
        "training_role_counts": dict(role_counts),
        "capture_family_manifest_match_counts": family_counts,
        "fixed_split": {
            "train_count": split_meta["train_count"],
            "val_count": split_meta["val_count"],
            "train_group_count": split_meta["train_group_count"],
            "val_group_count": split_meta["val_group_count"],
            "group_overlap_count": split_meta["group_overlap_count"],
        },
        "evaluation_populations": populations,
        "claim_rule": (
            "Use the 50x static SEM comparison as package-manifest-unseen evidence, without claiming full checkpoint-ancestry independence. "
            "Use the 20x static frame and four displacement sequences for controlled same-domain mechanism attribution only. "
            "Exclude external GMF until the original Raw sources are restored."
        ),
    }
    output = EXPERIMENT_ROOT / "results" / "evaluation_population_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    print(output)


if __name__ == "__main__":
    main()
