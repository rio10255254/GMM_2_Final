"""Exact-output inference wrapper for R63 architecture and output-path ablations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_ROOT.parents[1]
DEFAULT_PACKAGE_ROOT = (
    REPO_ROOT
    / "Thesis_MOSR_Evidence"
    / "LabSystem_MOSR"
    / "Model_Packages"
    / "V42_SoftLabelSNR_FullStandalone_20260709"
)


def parse_local_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--variant",
        required=True,
        choices=(
            "full_control",
            "no_geometry_anchor",
            "no_motion_consistency",
            "no_geometry_no_motion",
            "no_shape_geometry",
            "no_global_boundary_position",
            "no_identity_boundary_guard",
            "no_region_boundary_teacher",
            "no_sequence_consistency",
            "no_known_shift_motion",
            "no_shift_equivariance",
            "no_boundary_residual_adapter",
            "no_raw_position_anchor",
            "no_quality_gate",
            "shift_safe_matched",
            "standard_upsample_matched",
            "final_reference",
        ),
    )
    parser.add_argument(
        "--output-protection",
        default="full",
        choices=("full", "no_boundary", "no_anchor", "no_gate", "no_all"),
    )
    parser.add_argument("--exact-output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=DEFAULT_PACKAGE_ROOT)
    return parser.parse_known_args()


def apply_runtime_ablation(args: argparse.Namespace) -> None:
    import torch
    import model_v42

    if args.variant == "standard_upsample_matched":
        def forward_without_antialias(self, x):
            return self.conv(self.up(x))

        model_v42.ShiftSafeUpsample.forward = forward_without_antialias

    if args.output_protection in {"no_boundary", "no_all"}:
        def boundary_identity(self, features, base_out):
            return base_out

        model_v42.BoundaryResidualAdapter.forward = boundary_identity

    if args.output_protection in {"no_anchor", "no_all"}:
        def anchor_identity(self, raw, pred):
            return pred

        model_v42.RawAnchorOutputAdapter.forward = anchor_identity

    if args.output_protection in {"no_gate", "no_all"}:
        def gate_identity(self, x):
            scale = torch.ones((x.shape[0], 1, 1, 1), device=x.device, dtype=x.dtype)
            self.last_quality_score = scale.detach()
            return scale

        model_v42.ImageQualityGate.forward = gate_identity


def main() -> None:
    args, remaining = parse_local_args()
    package_root = args.package_root.resolve()
    if not package_root.is_dir():
        raise FileNotFoundError(package_root)
    sys.path.insert(0, str(package_root))
    import infer_v42

    apply_runtime_ablation(args)
    exact_output = args.exact_output_dir.resolve()
    exact_output.mkdir(parents=True, exist_ok=True)

    def exact_build_output_dir(*_args, **_kwargs):
        return exact_output

    infer_v42.build_output_dir = exact_build_output_dir
    sys.argv = [str(package_root / "infer_v42.py"), *remaining]
    infer_v42.main()


if __name__ == "__main__":
    main()
