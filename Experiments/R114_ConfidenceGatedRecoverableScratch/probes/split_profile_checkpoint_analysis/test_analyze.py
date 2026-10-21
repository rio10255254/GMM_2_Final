from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import torch

from analyze import analyze_run, render_markdown


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fixed_stage_audit_skips_future_and_never_selects(tmp_path: Path) -> None:
    project = tmp_path / "project"
    run = project / "runs" / "probe"
    for folder in ("weights", "validation", "previews"):
        (run / folder).mkdir(parents=True, exist_ok=True)
    (project / "config").mkdir(parents=True)
    source = project / "source.py"
    source.write_text("source = 'scratch'\n", encoding="utf-8")
    source_hashes = {"source.py": _sha(source)}
    initial_hash = "a" * 64
    provenance = {
        "scratch": True,
        "resume_supported": False,
        "foreign_checkpoint_loaded": False,
        "initial_state_sha256": initial_hash,
        "dataset_manifest_sha256": "b" * 64,
        "source_sha256": source_hashes,
    }
    (run / "scratch_provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    (run / "run_state.json").write_text(
        json.dumps(
            {
                "status": "running",
                "run_id": "probe",
                "scratch": True,
                "foreign_checkpoint_loaded": False,
                "initial_state_sha256": initial_hash,
                "epochs": 28,
            }
        ),
        encoding="utf-8",
    )
    (project / "config" / "split_profile_training.json").write_text(
        json.dumps(
            {
                "checkpoint_every_epochs": 2,
                "validation_every_epochs": 4,
                "preview_every_epochs": 4,
            }
        ),
        encoding="utf-8",
    )

    fieldnames = [
        "epoch",
        "stage",
        "train_identity",
        "validation_mae",
        "validation_base_mae",
        "validation_delta_abs",
        "validation_profile_visibility_mean",
        "validation_canonical_tile_max_abs",
    ]
    rows = []
    for epoch in range(1, 13):
        stage = "reliability" if epoch <= 8 else "oracle_geometry"
        rows.append(
            {
                "epoch": epoch,
                "stage": stage,
                "train_identity": 1e-6,
                "validation_mae": 0.02 if epoch == 12 else "",
                "validation_base_mae": 0.02 if epoch == 12 else "",
                "validation_delta_abs": 0.0005 if epoch == 12 else "",
                "validation_profile_visibility_mean": 0.0 if epoch == 12 else "",
                "validation_canonical_tile_max_abs": 0.0 if epoch == 12 else "",
            }
        )
    with (run / "training_log.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    validation = {
        "summary": {
            "mae": 0.02,
            "base_mae": 0.02,
            "delta_abs": 0.0005,
            "profile_visibility_mean": 0.0,
            "scenes": 128,
            "canonical_tile_max_abs": 0.0,
        },
        "canonical_tile_only": True,
    }
    for epoch in (4, 8):
        (run / "validation" / f"epoch_{epoch:03d}.json").write_text(
            json.dumps(validation), encoding="utf-8"
        )
        assert cv2.imwrite(
            str(run / "previews" / f"epoch_{epoch:03d}.png"),
            np.zeros((8, 8), np.uint8),
        )
    (run / "validation" / "epoch_012.json").write_text(
        json.dumps(validation), encoding="utf-8"
    )
    assert cv2.imwrite(str(run / "previews" / "epoch_012.png"), np.zeros((8, 8), np.uint8))
    for epoch in range(2, 13, 2):
        stage = "reliability" if epoch <= 8 else "oracle_geometry"
        checkpoint_validation = validation["summary"] if epoch == 12 else {}
        torch.save(
            {
                "model": {"weight": torch.ones(1)},
                "epoch": epoch,
                "stage": stage,
                "campaign": "split_profile_probe",
                "run_id": "probe",
                "scratch": True,
                "resume_supported": False,
                "foreign_checkpoint_loaded": False,
                "initial_state_sha256": initial_hash,
                "source_sha256": source_hashes,
                "validation": checkpoint_validation,
            },
            run / "weights" / f"epoch_{epoch:03d}.pth",
        )

    report = analyze_run(run, project)
    assert report["provenance"]["pass"] is True
    assert report["run_file_integrity"]["complete_through_latest"] is True
    assert report["stages"][0]["availability"] == "complete"
    assert [item["availability"] for item in report["stages"][1:]] == [
        "pending",
        "pending",
        "pending",
    ]
    assert report["fixed_stage_policy"]["automatic_selection_performed"] is False
    assert report["fixed_stage_policy"]["selected_epoch"] is None
    markdown = render_markdown(report)
    assert "never selected automatically" in markdown
    assert "E20" in markdown


def test_source_drift_is_reported(tmp_path: Path) -> None:
    # Reuse the first test's builder without duplicating a full run: pytest's
    # tmp_path is isolated, so a minimal malformed source audit is sufficient.
    project = tmp_path / "project"
    run = project / "runs" / "probe"
    run.mkdir(parents=True)
    (project / "config").mkdir(parents=True)
    (project / "config" / "split_profile_training.json").write_text(
        json.dumps(
            {
                "checkpoint_every_epochs": 2,
                "validation_every_epochs": 4,
                "preview_every_epochs": 4,
            }
        ), encoding="utf-8"
    )
    source = project / "source.py"
    source.write_text("changed\n", encoding="utf-8")
    provenance = {
        "scratch": True,
        "resume_supported": False,
        "foreign_checkpoint_loaded": False,
        "initial_state_sha256": "a" * 64,
        "dataset_manifest_sha256": "b" * 64,
        "source_sha256": {"source.py": "0" * 64},
    }
    (run / "scratch_provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    (run / "run_state.json").write_text(
        json.dumps(
            {
                "run_id": "probe",
                "scratch": True,
                "foreign_checkpoint_loaded": False,
                "initial_state_sha256": "a" * 64,
                "epochs": 28,
            }
        ), encoding="utf-8"
    )
    (run / "training_log.csv").write_text("epoch,stage\n", encoding="utf-8")
    report = analyze_run(run, project)
    assert report["provenance"]["pass"] is False
    assert report["provenance"]["checks"]["all_declared_sources_match_current_workspace"] is False
