from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R62_TargetSampleBoost\scripts"
)
sys.path.insert(0, str(SCRIPTS_DIR))


def test_build_prepare_command_uses_requested_weights_and_case_prefix() -> None:
    from run_r62_reconstruction_for_new_displacement_sets import DATASETS, build_prepare_command

    weights = Path(r"D:\models\v8\best_tradeoff.pth.tar")
    command, log_path = build_prepare_command(
        DATASETS[0],
        "x_1um",
        weights=weights,
        case_prefix="r62_v8_gmfgate_psfoff",
        role="r62_v8_gmfgate_psfoff",
        device="cuda:0",
        note_prefix="V8 GMF-gated reconstruction",
    )

    joined = "\n".join(command)
    assert str(weights) in command
    assert "r62_v8_gmfgate_psfoff_x_1um" in command
    assert "--case-name" in command
    assert "--role" in command
    assert "V8 GMF-gated reconstruction for 20260702_100MG x_1um." in joined
    assert log_path.name == "r62_v8_gmfgate_psfoff_x_1um_prepare_stdout.log"


def test_build_prepare_command_forwards_infer_anchor_output() -> None:
    from run_r62_reconstruction_for_new_displacement_sets import DATASETS, build_prepare_command

    command, _ = build_prepare_command(
        DATASETS[0],
        "x_1um",
        weights=Path(r"D:\models\v29\best_tradeoff.pth.tar"),
        case_prefix="r62_v29_detail35_psfoff",
        role="r62_v29_detail35_psfoff",
        device="cuda:0",
        note_prefix="V29 detail-anchor reconstruction",
        infer_anchor_output_mode="detail",
        infer_anchor_alpha=0.10,
        infer_anchor_sigma=2.0,
        infer_anchor_detail_gain=0.35,
    )

    assert command[command.index("--anchor-output-mode") + 1] == "detail"
    assert command[command.index("--anchor-alpha") + 1] == "0.1"
    assert command[command.index("--anchor-sigma") + 1] == "2.0"
    assert command[command.index("--anchor-detail-gain") + 1] == "0.35"


def test_parser_accepts_custom_weights_prefix_and_dry_run() -> None:
    from run_r62_reconstruction_for_new_displacement_sets import build_parser

    args = build_parser().parse_args(
        [
            "--weights",
            r"D:\models\v8\best_tradeoff.pth.tar",
            "--case-prefix",
            "r62_v8_gmfgate_psfoff",
            "--role",
            "r62_v8_gmfgate_psfoff",
            "--dry-run",
        ]
    )

    assert args.weights == r"D:\models\v8\best_tradeoff.pth.tar"
    assert args.case_prefix == "r62_v8_gmfgate_psfoff"
    assert args.role == "r62_v8_gmfgate_psfoff"
    assert args.dry_run is True


def test_parser_defaults_to_gentle_anchor_detail_gain() -> None:
    from run_r62_reconstruction_for_new_displacement_sets import build_parser

    args = build_parser().parse_args([])

    assert args.anchor_detail_gain == 0.35


def test_parser_accepts_infer_anchor_output_options() -> None:
    from run_r62_reconstruction_for_new_displacement_sets import build_parser

    args = build_parser().parse_args(
        [
            "--infer-anchor-output-mode",
            "detail",
            "--infer-anchor-alpha",
            "0.10",
            "--infer-anchor-sigma",
            "2.0",
            "--infer-anchor-detail-gain",
            "0.35",
        ]
    )

    assert args.infer_anchor_output_mode == "detail"
    assert args.infer_anchor_alpha == 0.10
    assert args.infer_anchor_sigma == 2.0
    assert args.infer_anchor_detail_gain == 0.35


def test_anchor_fusion_plan_uses_raw_and_reconstruction_case_paths() -> None:
    from run_r62_reconstruction_for_new_displacement_sets import (
        DATASETS,
        build_anchor_fusion_plan,
    )

    plan = build_anchor_fusion_plan(
        DATASETS[0],
        "x_1um",
        case_prefix="r62_v7_seqgeom_noamp_lr3e7_psfoff",
        anchor_variant="anchor_blend10",
        mode="blend",
        alpha=0.10,
        sigma=2.0,
        detail_gain=1.0,
    )

    assert plan["case_name"] == "r62_v7_anchor_blend10_x_1um"
    assert str(plan["raw_dir"]).endswith(r"raw_inputs\x_1um\bmp")
    assert str(plan["recon_dir"]).endswith(r"r62_v7_seqgeom_noamp_lr3e7_psfoff_x_1um\bmp")
    assert str(plan["output_dir"]).endswith(r"r62_v7_anchor_blend10_x_1um\bmp")
    assert plan["mode"] == "blend"
    assert plan["alpha"] == 0.10
