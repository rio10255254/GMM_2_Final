"""Local motion-consistency probe for real-sample reconstruction packages."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import median

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PACKAGE_ROOT = PROJECT_ROOT / "Analyses" / "Reconstruct_Progress" / "20260603_external_gmf_prepare"
DEFAULT_PATHS_TSV = DEFAULT_PACKAGE_ROOT / "paths_for_gmf_tool.tsv"
DEFAULT_OUT_JSON = DEFAULT_PACKAGE_ROOT / "local_motion_probe_summary.json"
DEFAULT_OUT_CSV = DEFAULT_PACKAGE_ROOT / "local_motion_probe_steps.csv"
DEFAULT_OUT_MD = DEFAULT_PACKAGE_ROOT / "local_motion_probe_summary.md"


def _as_gray_float(image: np.ndarray) -> np.ndarray:
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    arr = image.astype(np.float32)
    if arr.size == 0:
        raise ValueError("empty image")
    return arr


def _edge_enhance(image: np.ndarray) -> np.ndarray:
    gray = _as_gray_float(image)
    blur = cv2.GaussianBlur(gray, (0, 0), 1.0)
    gx = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    mag -= float(np.mean(mag))
    std = float(np.std(mag))
    if std > 1e-6:
        mag /= std
    return mag.astype(np.float32)


def estimate_pair_shift(image0: np.ndarray, image1: np.ndarray) -> dict[str, float]:
    a = _edge_enhance(image0)
    b = _edge_enhance(image1)
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch: {a.shape} vs {b.shape}")
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(a, b, window)
    return {"dx": float(dx), "dy": float(dy), "response": float(response)}


def _std_pop(values: list[float]) -> float | None:
    finite = [float(v) for v in values if math.isfinite(float(v))]
    if not finite:
        return None
    mean = sum(finite) / len(finite)
    return float(math.sqrt(sum((v - mean) ** 2 for v in finite) / len(finite)))


def _mean(values: list[float]) -> float | None:
    finite = [float(v) for v in values if math.isfinite(float(v))]
    if not finite:
        return None
    return float(sum(finite) / len(finite))


def _median(values: list[float]) -> float | None:
    finite = [float(v) for v in values if math.isfinite(float(v))]
    if not finite:
        return None
    return float(median(finite))


def _bmp_files(path: Path) -> list[Path]:
    return sorted(p for p in Path(path).glob("*.bmp") if p.is_file())


def compute_case_motion_stats(case_name: str, image_folder: Path) -> dict[str, object]:
    paths = _bmp_files(Path(image_folder))
    if len(paths) < 2:
        raise ValueError(f"need at least two BMP images for {case_name}: {image_folder}")

    steps: list[dict[str, object]] = []
    prev = cv2.imread(str(paths[0]), cv2.IMREAD_UNCHANGED)
    if prev is None:
        raise OSError(f"failed to read image: {paths[0]}")
    for idx, path in enumerate(paths[1:]):
        cur = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if cur is None:
            raise OSError(f"failed to read image: {path}")
        shift = estimate_pair_shift(prev, cur)
        steps.append(
            {
                "case": case_name,
                "step_index": idx,
                "from": paths[idx].name,
                "to": path.name,
                **shift,
            }
        )
        prev = cur

    dy = [float(row["dy"]) for row in steps]
    dx = [float(row["dx"]) for row in steps]
    response = [float(row["response"]) for row in steps]
    tail_dy = dy[1:]
    tail_dx = dx[1:]
    tail_response = response[1:]

    return {
        "case": case_name,
        "image_folder": str(image_folder),
        "n_frames": len(paths),
        "n_steps": len(steps),
        "first_filename": paths[0].name,
        "last_filename": paths[-1].name,
        "mean_dx_px": _mean(dx),
        "mean_dy_px": _mean(dy),
        "median_dx_px": _median(dx),
        "median_dy_px": _median(dy),
        "std_dx_px": _std_pop(dx),
        "std_dy_px": _std_pop(dy),
        "mean_response": _mean(response),
        "tail_n_steps": len(tail_dy),
        "tail_mean_dx_px": _mean(tail_dx),
        "tail_mean_dy_px": _mean(tail_dy),
        "tail_median_dx_px": _median(tail_dx),
        "tail_median_dy_px": _median(tail_dy),
        "tail_std_dx_px": _std_pop(tail_dx),
        "tail_std_dy_px": _std_pop(tail_dy),
        "tail_mean_response": _mean(tail_response),
        "steps": steps,
    }


def load_cases_from_tsv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    return [row for row in rows if row.get("case") and row.get("image_folder") and Path(row["image_folder"]).is_dir()]


def write_steps_csv(path: Path, case_stats: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["case", "step_index", "from", "to", "dx", "dy", "response"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for stats in case_stats:
            for row in stats["steps"]:
                writer.writerow({field: row.get(field, "") for field in fieldnames})


def _fmt(value: object) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return str(value)


def write_markdown(path: Path, payload: dict[str, object]) -> None:
    lines = [
        "# 20260603 Local Motion Probe",
        "",
        "This is a local image-only probe. It does not replace the external GMF tool.",
        "",
        "| case | frames | median dy px | std dy px | tail median dy px | tail std dy px | response |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["cases"]:
        lines.append(
            "| {case} | {n_frames} | {median_dy} | {std_dy} | {tail_median_dy} | {tail_std_dy} | {response} |".format(
                case=row["case"],
                n_frames=row["n_frames"],
                median_dy=_fmt(row["median_dy_px"]),
                std_dy=_fmt(row["std_dy_px"]),
                tail_median_dy=_fmt(row["tail_median_dy_px"]),
                tail_std_dy=_fmt(row["tail_std_dy_px"]),
                response=_fmt(row["mean_response"]),
            )
        )
    lines.append("")
    lines.append("Tail values remove only the first interval, matching the earlier warm-up-step caveat.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe local motion consistency for a real-sample GMF package.")
    parser.add_argument("--paths-tsv", type=Path, default=DEFAULT_PATHS_TSV)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUT_CSV)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUT_MD)
    return parser


def run_probe(args: argparse.Namespace) -> dict[str, object]:
    cases = load_cases_from_tsv(Path(args.paths_tsv))
    case_stats = [compute_case_motion_stats(row["case"], Path(row["image_folder"])) for row in cases]
    payload = {
        "scope": "20260603 local image-only motion consistency probe",
        "formal_comparable_to_external_gmf": False,
        "method": "OpenCV phase correlation on Sobel-gradient magnitude between filename-sorted consecutive frames",
        "paths_tsv": str(Path(args.paths_tsv)),
        "cases": [{key: value for key, value in stats.items() if key != "steps"} for stats in case_stats],
    }
    Path(args.output_json).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_steps_csv(Path(args.output_csv), case_stats)
    write_markdown(Path(args.output_md), payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = run_probe(args)
    print(json.dumps({"cases": len(payload["cases"]), "output_json": str(args.output_json)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
