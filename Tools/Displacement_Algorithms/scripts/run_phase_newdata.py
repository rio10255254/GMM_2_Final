from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from displacement_common import IMAGE_EXTENSIONS, natural_key, read_gray_u8, write_json


DEFAULT_ROOTS = [
    Path(r"D:\GMM_2_Final\20260702_100MG_位移"),
]
DEFAULT_OUTPUT_ROOT = Path(r"D:\GMM_2_Final\20260702_100MG_phase_dft_analysis")


def parse_roi(value: str | None) -> tuple[int, int, int, int] | None:
    if not value:
        return None
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("ROI must be x,y,width,height")
    x, y, width, height = parts
    if width <= 0 or height <= 0:
        raise ValueError("ROI width and height must be positive")
    return x, y, width, height


def image_files_in(folder: Path) -> list[Path]:
    files = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    files.sort(key=natural_key)
    return files


def discover_sequence_dirs(roots: list[Path]) -> list[Path]:
    sequence_dirs: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            print(f"Skip missing root: {root}")
            continue
        direct_files = image_files_in(root)
        if len(direct_files) >= 2:
            sequence_dirs.append(root)
            seen.add(root.resolve())
        for image_path in root.rglob("*"):
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            parent = image_path.parent.resolve()
            if parent in seen:
                continue
            if len(image_files_in(image_path.parent)) >= 2:
                sequence_dirs.append(image_path.parent)
                seen.add(parent)
    sequence_dirs.sort(key=natural_key)
    return sequence_dirs


def safe_name(path: Path, roots: list[Path]) -> str:
    for root in roots:
        try:
            rel = path.relative_to(root)
            rel_text = str(rel).replace(":", "").replace("\\", "__").replace("/", "__")
            return f"{root.name}__{rel_text}"
        except ValueError:
            pass
    return str(path).replace(":", "").replace("\\", "__").replace("/", "__")


def select_roi_on_image(
    image: np.ndarray,
    title: str,
    max_display_width: int,
    max_display_height: int,
) -> tuple[int, int, int, int]:
    height, width = image.shape[:2]
    scale = min(max_display_width / width, max_display_height / height, 1.0)
    if scale < 1.0:
        shown = cv2.resize(image, (round(width * scale), round(height * scale)))
    else:
        shown = image
    display = cv2.cvtColor(shown, cv2.COLOR_GRAY2BGR)
    cv2.putText(
        display,
        "Drag ROI, press ENTER/SPACE. Press C to cancel.",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
    x, y, w, h = cv2.selectROI(title, display, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow(title)
    if w <= 0 or h <= 0:
        raise RuntimeError("ROI selection cancelled")
    return (
        int(round(x / scale)),
        int(round(y / scale)),
        int(round(w / scale)),
        int(round(h / scale)),
    )


def center_roi_for(image: np.ndarray, size: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = size
    img_h, img_w = image.shape[:2]
    if width <= 0 or height <= 0:
        raise ValueError("--auto-center-roi must be width,height")
    if width > img_w or height > img_h:
        raise ValueError(f"Requested ROI {size} is larger than image {img_w}x{img_h}")
    x = (img_w - width) // 2
    y = (img_h - height) // 2
    return x, y, width, height


def draw_roi_preview(
    image: np.ndarray,
    roi: tuple[int, int, int, int],
    output_path: Path,
) -> None:
    x, y, w, h = roi
    preview = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 0, 255), 3)
    ok, data = cv2.imencode(".png", preview)
    if not ok:
        raise RuntimeError(f"Cannot encode ROI preview: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data.tofile(str(output_path))


def load_roi_json(path: Path) -> dict[str, tuple[int, int, int, int]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    roi_map = payload.get("roi_by_sequence", {})
    return {key: tuple(value) for key, value in roi_map.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the selected DFT phase algorithm on current displacement data."
    )
    parser.add_argument(
        "--roots",
        nargs="*",
        default=[str(path) for path in DEFAULT_ROOTS],
        help="Dataset roots. Defaults to 20260702_100MG_位移.",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Folder where per-sequence CSV/JSON outputs are written.",
    )
    parser.add_argument("--select-roi", action="store_true", help="Open ROI selector.")
    parser.add_argument("--roi", help="Reuse one ROI for all sequences: x,y,width,height.")
    parser.add_argument("--roi-json", help="Load saved ROI selections.")
    parser.add_argument(
        "--save-roi-json",
        help="Save ROI selections. Defaults to output_root/selected_rois.json when selecting.",
    )
    parser.add_argument(
        "--auto-center-roi",
        help="Non-interactive test mode: use centered width,height ROI.",
    )
    parser.add_argument("--upsample-factor", type=int, default=100)
    parser.add_argument(
        "--reference",
        choices=["consecutive", "first", "both"],
        default="both",
    )
    parser.add_argument("--no-hann", action="store_true")
    parser.add_argument("--max-sequences", type=int, default=0)
    parser.add_argument("--max-display-width", type=int, default=1200)
    parser.add_argument("--max-display-height", type=int, default=900)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    roots = [Path(path) for path in args.roots]
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    sequences = discover_sequence_dirs(roots)
    if args.max_sequences > 0:
        sequences = sequences[: args.max_sequences]
    if not sequences:
        raise RuntimeError("No image sequences found.")

    fixed_roi = parse_roi(args.roi)
    auto_center = None
    if args.auto_center_roi:
        parts = [int(part.strip()) for part in args.auto_center_roi.split(",")]
        if len(parts) != 2:
            raise ValueError("--auto-center-roi must be width,height")
        auto_center = (parts[0], parts[1])

    roi_map: dict[str, tuple[int, int, int, int]] = {}
    if args.roi_json:
        roi_map.update(load_roi_json(Path(args.roi_json)))

    measure_script = Path(__file__).with_name("measure_phase_dft.py")
    results: list[dict[str, object]] = []
    selected_rois: dict[str, tuple[int, int, int, int]] = {}

    for sequence in sequences:
        files = image_files_in(sequence)
        if len(files) < 2:
            continue
        case_name = safe_name(sequence, roots)
        first_image = read_gray_u8(files[0])

        roi = fixed_roi or roi_map.get(str(sequence)) or roi_map.get(case_name)
        if roi is None and auto_center is not None:
            roi = center_roi_for(first_image, auto_center)
        if roi is None and args.select_roi:
            roi = select_roi_on_image(
                first_image,
                f"Select ROI: {case_name}",
                args.max_display_width,
                args.max_display_height,
            )
        if roi is None:
            raise RuntimeError(
                f"No ROI for {sequence}. Use --select-roi, --roi, --roi-json, or --auto-center-roi."
            )

        selected_rois[case_name] = roi
        case_dir = output_root / case_name
        case_dir.mkdir(parents=True, exist_ok=True)
        draw_roi_preview(first_image, roi, case_dir / "roi_preview.png")

        csv_path = case_dir / "phase_dft_steps.csv"
        json_path = case_dir / "phase_dft_summary.json"
        command = [
            sys.executable,
            str(measure_script),
            "--input",
            str(sequence),
            "--output-csv",
            str(csv_path),
            "--output-json",
            str(json_path),
            "--crop",
            ",".join(str(value) for value in roi),
            "--upsample-factor",
            str(args.upsample_factor),
            "--reference",
            args.reference,
        ]
        if args.no_hann:
            command.append("--no-hann")
        subprocess.run(command, check=True)
        results.append(
            {
                "case": case_name,
                "sequence_dir": str(sequence),
                "image_count": len(files),
                "roi": list(roi),
                "steps_csv": str(csv_path),
                "summary_json": str(json_path),
                "roi_preview": str(case_dir / "roi_preview.png"),
            }
        )

    roi_save_path = Path(args.save_roi_json) if args.save_roi_json else output_root / "selected_rois.json"
    if args.select_roi or args.roi or args.auto_center_roi:
        write_json(
            roi_save_path,
            {
                "roi_by_sequence": {key: list(value) for key, value in selected_rois.items()},
                "note": "ROI format is x,y,width,height in original image pixels.",
            },
        )

    write_json(
        output_root / "phase_dft_run_manifest.json",
        {
            "algorithm_entry": str(measure_script),
            "roots": [str(path) for path in roots],
            "output_root": str(output_root),
            "upsample_factor": args.upsample_factor,
            "reference": args.reference,
            "hann_window": not args.no_hann,
            "sequence_count": len(results),
            "roi_file": str(roi_save_path),
            "results": results,
        },
    )
    print(f"Processed {len(results)} sequences.")
    print(f"Manifest: {output_root / 'phase_dft_run_manifest.json'}")
    print(f"ROI file: {roi_save_path}")


if __name__ == "__main__":
    main()
