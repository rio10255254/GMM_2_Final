from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
SOURCE = Path(CONFIG["source"])
RESULTS = ROOT / "results"
REPORTS = ROOT / "reports"


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Cannot read {path}")
    return image


def feature(image: np.ndarray) -> np.ndarray:
    value = image.astype(np.float32)
    return value - cv2.GaussianBlur(value, (0, 0), 3.0, borderType=cv2.BORDER_REFLECT_101)


def phase_shift(reference: np.ndarray, moving: np.ndarray, scale: int = 5) -> tuple[float, float, float]:
    size = (reference.shape[1] // scale, reference.shape[0] // scale)
    a = cv2.resize(reference, size, interpolation=cv2.INTER_AREA)
    b = cv2.resize(moving, size, interpolation=cv2.INTER_AREA)
    fa, fb = feature(a), feature(b)
    window = cv2.createHanningWindow((fa.shape[1], fa.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(fa, fb, window)
    return float(dx * scale), float(dy * scale), float(response)


def photometric_fit(reference: np.ndarray, moving: np.ndarray) -> tuple[float, float]:
    a = cv2.resize(reference, (512, 512), interpolation=cv2.INTER_AREA).astype(np.float64).reshape(-1)
    b = cv2.resize(moving, (512, 512), interpolation=cv2.INTER_AREA).astype(np.float64).reshape(-1)
    low, high = np.percentile(a, [2.0, 98.0])
    valid = (a >= low) & (a <= high) & (b >= np.percentile(b, 2.0)) & (b <= np.percentile(b, 98.0))
    a, b = a[valid], b[valid]
    gain = float(np.cov(a, b, bias=True)[0, 1] / max(np.var(a), 1e-9))
    offset = float(np.mean(b) - gain * np.mean(a))
    return gain, offset


def sharpness(image: np.ndarray) -> float:
    small = cv2.resize(image, (1024, 1024), interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(small, cv2.CV_32F).var())


def structural_edge_energy(image: np.ndarray) -> float:
    value = image.astype(np.float32)
    value = cv2.GaussianBlur(value, (0, 0), 1.5, borderType=cv2.BORDER_REFLECT_101)
    gx = cv2.Sobel(value, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(value, cv2.CV_32F, 0, 1, ksize=3)
    return float(np.mean(np.sqrt(gx * gx + gy * gy)))


def robust_limits(values: np.ndarray, multiplier: float = 6.0) -> tuple[float, float]:
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    scale = max(1.4826 * mad, 1e-9)
    return median - multiplier * scale, median + multiplier * scale


def make_preview(files: list[Path], rows: list[dict]) -> None:
    indices = sorted(set([0, 20, 40, 60, 80, 100] + [int(row["position_index"]) for row in rows if row["flagged"]][:3]))
    indices = [index for index in indices if index < len(rows)]
    panel, gap, label_height, row_height = 220, 12, 34, 260
    columns = ["First", "Second", "Mean", "Absolute difference x16"]
    canvas = Image.new("RGB", (gap + len(columns) * (panel + gap), label_height + len(indices) * row_height + gap), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for column, label in enumerate(columns):
        draw.text((gap + column * (panel + gap), 10), label, fill="black", font=font)
    for row_number, position in enumerate(indices):
        first = read_gray(files[2 * position])
        second = read_gray(files[2 * position + 1])
        height, width = first.shape
        crop_size = min(1536, height, width)
        top, left = (height - crop_size) // 2, (width - crop_size) // 2
        first = first[top : top + crop_size, left : left + crop_size]
        second = second[top : top + crop_size, left : left + crop_size]
        mean = ((first.astype(np.uint16) + second.astype(np.uint16) + 1) // 2).astype(np.uint8)
        difference = np.clip(np.abs(first.astype(np.int16) - second.astype(np.int16)) * 16, 0, 255).astype(np.uint8)
        values = [first, second, mean, difference]
        top_px = label_height + row_number * row_height
        for column, value in enumerate(values):
            image = Image.fromarray(value, "L").convert("RGB").resize((panel, panel), Image.Resampling.BICUBIC)
            canvas.paste(image, (gap + column * (panel + gap), top_px))
        record = rows[position]
        draw.text(
            (gap, top_px + panel + 8),
            f"position {position:03d} | shift ({record['within_dx_px']:+.3f}, {record['within_dy_px']:+.3f}) px | response {record['within_response']:.3f} | flagged {record['flagged']}",
            fill="black",
            font=font,
        )
    REPORTS.mkdir(parents=True, exist_ok=True)
    canvas.save(REPORTS / "R105C_PAIR_PREVIEW.png", optimize=True)


def main() -> int:
    files = sorted(SOURCE.glob("*.bmp"))
    if len(files) != 202:
        raise RuntimeError(f"Expected 202 BMP files, found {len(files)}")
    rows = []
    inter_position = []
    previous_second = None
    for position in range(len(files) // 2):
        first_path, second_path = files[2 * position], files[2 * position + 1]
        first, second = read_gray(first_path), read_gray(second_path)
        if first.shape != second.shape:
            raise RuntimeError(f"Shape mismatch at position {position}")
        dx, dy, response = phase_shift(first, second)
        gain, offset = photometric_fit(first, second)
        first_small = cv2.resize(first, (1024, 1024), interpolation=cv2.INTER_AREA).astype(np.float32)
        second_small = cv2.resize(second, (1024, 1024), interpolation=cv2.INTER_AREA).astype(np.float32)
        difference_std = float(np.std(second_small - first_small))
        mean_small = 0.5 * (first_small + second_small)
        sharp_first, sharp_second = sharpness(first), sharpness(second)
        sharp_mean = float(cv2.Laplacian(mean_small, cv2.CV_32F).var())
        structural_first = structural_edge_energy(first_small)
        structural_second = structural_edge_energy(second_small)
        structural_mean = structural_edge_energy(mean_small)
        saturation = float(np.mean((first <= 1) | (first >= 254) | (second <= 1) | (second >= 254)))
        record = {
            "position_index": position,
            "first_file": first_path.name,
            "second_file": second_path.name,
            "width": first.shape[1],
            "height": first.shape[0],
            "within_dx_px": dx,
            "within_dy_px": dy,
            "within_shift_magnitude_px": math.hypot(dx, dy),
            "within_response": response,
            "gain_second_from_first": gain,
            "offset_second_from_first_gray": offset,
            "pair_difference_std_gray": difference_std,
            "sharpness_first": sharp_first,
            "sharpness_second": sharp_second,
            "sharpness_mean": sharp_mean,
            "mean_laplacian_ratio_noise_sensitive": sharp_mean / max(0.5 * (sharp_first + sharp_second), 1e-9),
            "mean_structural_edge_ratio": structural_mean / max(0.5 * (structural_first + structural_second), 1e-9),
            "estimated_single_frame_noise_std_gray": difference_std / math.sqrt(2.0),
            "estimated_pair_mean_noise_std_gray": difference_std / 2.0,
            "saturation_fraction": saturation,
        }
        rows.append(record)
        if previous_second is not None:
            step_dx, step_dy, step_response = phase_shift(previous_second, first)
            inter_position.append(
                {
                    "from_position": position - 1,
                    "to_position": position,
                    "content_shift_dx_px": step_dx,
                    "content_shift_dy_px": step_dy,
                    "content_shift_response": step_response,
                    "warning": "Periodic sample content can create phase-correlation aliases; this is descriptive, not independent stage truth."
                }
            )
        previous_second = second
        if position % 10 == 0 or position == len(files) // 2 - 1:
            print(json.dumps({"stage": "pair_audit", "position": position, "total": len(files) // 2}), flush=True)

    shift_values = np.asarray([row["within_shift_magnitude_px"] for row in rows])
    response_values = np.asarray([row["within_response"] for row in rows])
    gain_values = np.asarray([row["gain_second_from_first"] for row in rows])
    difference_values = np.asarray([row["pair_difference_std_gray"] for row in rows])
    laplacian_ratios = np.asarray([row["mean_laplacian_ratio_noise_sensitive"] for row in rows])
    structural_ratios = np.asarray([row["mean_structural_edge_ratio"] for row in rows])
    shift_limit = robust_limits(shift_values)[1]
    response_limit = robust_limits(response_values)[0]
    gain_low, gain_high = robust_limits(gain_values)
    difference_limit = robust_limits(difference_values)[1]
    structural_limit = min(0.995, robust_limits(structural_ratios)[0])
    for row in rows:
        reasons = []
        if row["within_shift_magnitude_px"] > max(1.0, shift_limit):
            reasons.append("within_pair_shift")
        if row["within_response"] < response_limit:
            reasons.append("low_registration_response")
        if not (gain_low <= row["gain_second_from_first"] <= gain_high):
            reasons.append("photometric_gain_outlier")
        if row["pair_difference_std_gray"] > difference_limit:
            reasons.append("pair_difference_outlier")
        if row["mean_structural_edge_ratio"] < structural_limit:
            reasons.append("mean_blur_risk")
        row["flagged"] = bool(reasons)
        row["flag_reasons"] = reasons

    summary = {
        "status": "complete",
        "source": str(SOURCE),
        "source_files": len(files),
        "positions": len(rows),
        "shape": [rows[0]["height"], rows[0]["width"]],
        "within_pair": {
            "shift_magnitude_px_median": float(np.median(shift_values)),
            "shift_magnitude_px_p95": float(np.percentile(shift_values, 95)),
            "shift_magnitude_px_max": float(np.max(shift_values)),
            "response_median": float(np.median(response_values)),
            "response_p05": float(np.percentile(response_values, 5)),
            "gain_median": float(np.median(gain_values)),
            "gain_p05": float(np.percentile(gain_values, 5)),
            "gain_p95": float(np.percentile(gain_values, 95)),
            "difference_std_gray_median": float(np.median(difference_values)),
            "difference_std_gray_p95": float(np.percentile(difference_values, 95)),
            "mean_laplacian_ratio_noise_sensitive_median": float(np.median(laplacian_ratios)),
            "mean_laplacian_ratio_noise_sensitive_p05": float(np.percentile(laplacian_ratios, 5)),
            "mean_structural_edge_ratio_median": float(np.median(structural_ratios)),
            "mean_structural_edge_ratio_p05": float(np.percentile(structural_ratios, 5)),
            "estimated_single_frame_noise_std_gray_median": float(np.median(difference_values) / math.sqrt(2.0)),
            "estimated_pair_mean_noise_std_gray_median": float(np.median(difference_values) / 2.0),
        },
        "flagged_positions": [int(row["position_index"]) for row in rows if row["flagged"]],
        "flagged_count": sum(int(row["flagged"]) for row in rows),
        "interpretation": "Even/odd pairs are the honest N=2 grouping. They are nearly co-located and mainly provide repeated-noise evidence; cross-position N=4 remains research-only because outputs would share frames and phase correlation is ambiguous on periodic content."
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "pair_manifest.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (RESULTS / "inter_position_content_shift.json").write_text(json.dumps(inter_position, indent=2), encoding="utf-8")
    (RESULTS / "sequence_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (RESULTS / "pair_manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            value = dict(row)
            value["flag_reasons"] = ";".join(value["flag_reasons"])
            writer.writerow(value)
    make_preview(files, rows)
    report = "\n".join(
        [
            "# R105C 均華雙張序列稽核",
            "",
            f"來源影像：{summary['source_files']} 張；名義位置：{summary['positions']} 組；尺寸：{summary['shape'][1]} x {summary['shape'][0]}。",
            "",
            "## 同位置雙張",
            "",
            f"- 位移中位數：{summary['within_pair']['shift_magnitude_px_median']:.4f} px",
            f"- 位移 95 百分位：{summary['within_pair']['shift_magnitude_px_p95']:.4f} px",
            f"- 最大位移：{summary['within_pair']['shift_magnitude_px_max']:.4f} px",
            f"- 對位反應中位數：{summary['within_pair']['response_median']:.4f}",
            f"- 亮度增益中位數：{summary['within_pair']['gain_median']:.6f}",
            f"- 雙張差異標準差中位數：{summary['within_pair']['difference_std_gray_median']:.4f} 灰階",
            f"- 雜訊敏感的 Laplacian 能量比例中位數：{summary['within_pair']['mean_laplacian_ratio_noise_sensitive_median']:.6f}",
            f"- 去除高頻雜訊後的結構邊緣比例中位數：{summary['within_pair']['mean_structural_edge_ratio_median']:.6f}",
            f"- 推估單張雜訊標準差：{summary['within_pair']['estimated_single_frame_noise_std_gray_median']:.4f} 灰階",
            f"- 推估雙張平均雜訊標準差：{summary['within_pair']['estimated_pair_mean_noise_std_gray_median']:.4f} 灰階",
            f"- 自動標記位置：{summary['flagged_positions'] or '無'}",
            "",
            "## 結論",
            "",
            "檔名排序後的偶數／奇數影像可以作為 101 個互不共用來源的 N=2 組。這些雙張幾乎同位置，主要提供獨立雜訊證據，而不是明顯的次像素超解析取樣。",
            "",
            "目前不把相鄰位置合成 N=4 正式 GMF 輸出：相鄰結果會共用來源影像，可能人為降低位移波動；另外週期樣品會使純影像相關出現多個等價位移峰。",
            "",
            "原始資料夾全程唯讀，沒有寫入或更名。",
        ]
    )
    (REPORTS / "R105C_PAIR_AUDIT_ZH.md").write_text(report, encoding="utf-8")
    print(json.dumps({"status": "complete", "flagged_count": summary["flagged_count"], "summary": summary["within_pair"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
