from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from skimage.registration import phase_cross_correlation

from displacement_common import (
    list_images,
    parse_crop,
    read_gray_float,
    summarize_steps,
    write_csv,
    write_json,
)


def prepare_phase_image(
    path: Path,
    crop: tuple[int, int, int, int] | None,
    use_hann: bool,
) -> np.ndarray:
    image = read_gray_float(path, crop)
    image = image - float(np.mean(image))
    if use_hann:
        wy = np.hanning(image.shape[0]).astype(np.float32)
        wx = np.hanning(image.shape[1]).astype(np.float32)
        image = image * np.outer(wy, wx)
    return image.astype(np.float32, copy=False)


def register_displacement(
    reference: np.ndarray,
    moving: np.ndarray,
    upsample_factor: int,
) -> tuple[float, float, float, float]:
    shift, error, phase_diff = phase_cross_correlation(
        reference,
        moving,
        upsample_factor=upsample_factor,
        normalization="phase",
    )
    # phase_cross_correlation returns the shift needed to move "moving" back to
    # "reference"; displacement from reference to moving is the opposite sign.
    dy_px = -float(shift[0])
    dx_px = -float(shift[1])
    return dx_px, dy_px, float(error), float(phase_diff)


def measure(args: argparse.Namespace) -> tuple[list[dict[str, object]], dict[str, object]]:
    input_dir = Path(args.input)
    crop = parse_crop(args.crop)
    files = list_images(input_dir, args.pattern)

    first = prepare_phase_image(files[0], crop, not args.no_hann)
    prev = first
    cumulative_dx = 0.0
    cumulative_dy = 0.0
    rows: list[dict[str, object]] = [
        {
            "frame_index": 0,
            "filename": files[0].name,
            "ref_filename": "",
            "dx_px": 0.0,
            "dy_px": 0.0,
            "cumulative_dx_px": 0.0,
            "cumulative_dy_px": 0.0,
            "direct_first_dx_px": 0.0,
            "direct_first_dy_px": 0.0,
            "registration_error": 0.0,
            "phase_diff": 0.0,
            "status": "reference",
            "message": "",
        }
    ]

    for index, path in enumerate(files[1:], start=1):
        moving = prepare_phase_image(path, crop, not args.no_hann)
        if moving.shape != prev.shape:
            raise ValueError(f"Image size mismatch at {path}: {moving.shape} vs {prev.shape}")

        if args.reference in {"consecutive", "both"}:
            ref_image = prev
            ref_name = files[index - 1].name
        else:
            ref_image = first
            ref_name = files[0].name

        dx_px, dy_px, error, phase_diff = register_displacement(
            ref_image, moving, args.upsample_factor
        )

        if args.reference == "first":
            cumulative_dx = dx_px
            cumulative_dy = dy_px
        else:
            cumulative_dx += dx_px
            cumulative_dy += dy_px

        direct_first_dx = ""
        direct_first_dy = ""
        if args.reference == "both":
            direct_first_dx, direct_first_dy, _, _ = register_displacement(
                first, moving, args.upsample_factor
            )

        rows.append(
            {
                "frame_index": index,
                "filename": path.name,
                "ref_filename": ref_name,
                "dx_px": dx_px,
                "dy_px": dy_px,
                "cumulative_dx_px": cumulative_dx,
                "cumulative_dy_px": cumulative_dy,
                "direct_first_dx_px": direct_first_dx,
                "direct_first_dy_px": direct_first_dy,
                "registration_error": error,
                "phase_diff": phase_diff,
                "status": "ok",
                "message": "",
            }
        )
        prev = moving

    summary: dict[str, object] = {
        "algorithm": "phase_correlation_dft",
        "input_dir": str(input_dir),
        "image_count": len(files),
        "reference": args.reference,
        "upsample_factor": args.upsample_factor,
        "crop": crop,
        "hann_window": not args.no_hann,
    }
    summary.update(summarize_steps(rows))
    return rows, summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure image displacement with subpixel DFT phase correlation."
    )
    parser.add_argument("--input", required=True, help="Folder containing ordered images.")
    parser.add_argument("--output-csv", required=True, help="CSV output path.")
    parser.add_argument("--output-json", help="Optional summary JSON output path.")
    parser.add_argument("--pattern", default="*", help="Input file glob pattern.")
    parser.add_argument("--crop", help="Optional ROI crop as x,y,width,height.")
    parser.add_argument("--upsample-factor", type=int, default=100)
    parser.add_argument(
        "--reference",
        choices=["consecutive", "first", "both"],
        default="consecutive",
        help="Use previous frame, first frame, or previous frame plus first-frame check.",
    )
    parser.add_argument("--no-hann", action="store_true", help="Disable Hann windowing.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows, summary = measure(args)
    fields = [
        "frame_index",
        "filename",
        "ref_filename",
        "dx_px",
        "dy_px",
        "cumulative_dx_px",
        "cumulative_dy_px",
        "direct_first_dx_px",
        "direct_first_dy_px",
        "registration_error",
        "phase_diff",
        "status",
        "message",
    ]
    write_csv(Path(args.output_csv), rows, fields)
    if args.output_json:
        summary["output_csv"] = str(Path(args.output_csv))
        write_json(Path(args.output_json), summary)
    print(f"Wrote {args.output_csv}")
    if args.output_json:
        print(f"Wrote {args.output_json}")


if __name__ == "__main__":
    main()
