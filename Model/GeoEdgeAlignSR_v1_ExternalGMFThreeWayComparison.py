import json
import math
import os
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]


MODEL_SPECS = {
    "round18_baseline": {
        "root": str(PROJECT_ROOT / 'Experiments/Legacy/organized_20260316/external_compare_round18_round22/round18_baseline/gmf_results/raw'),
    },
    "round22_hold": {
        "root": str(PROJECT_ROOT / 'Experiments/Legacy/organized_20260316/external_compare_round18_round22/round22_hold/gmf_results/raw'),
    },
    "r25_sw010": {
        "root": str(PROJECT_ROOT / 'Experiments/Legacy/organized_20260316/external_compare_r18_r22_r25/r25_sw010/gmf_results/raw'),
    },
}

PITCH_SPECS = {
    "pitch1um_y_100": {
        "label": "8px (pitch1um)",
        "outlier_filter": False,
    },
    "pitch0p1um_y_60": {
        "label": "0.8px (pitch0p1um)",
        "outlier_filter": True,
    },
    "pitch0p01um_y_40": {
        "label": "0.08px (pitch0p01um)",
        "outlier_filter": False,
    },
}

REPORT_DIR = str(PROJECT_ROOT / 'Experiments/Legacy/organized_20260316/external_compare_r18_r22_r25/reports')
SUMMARY_MD_PATH = os.path.join(REPORT_DIR, "EXTERNAL_COMPARE_R18_R22_R25_SUMMARY.md")
SUMMARY_JSON_PATH = os.path.join(REPORT_DIR, "EXTERNAL_COMPARE_R18_R22_R25_SUMMARY.json")
MAIN_PITCH = "pitch0p1um_y_60"
STEP_STD_TARGET = 0.2855
ANCHOR_AUTOCORR_TARGET = 0.10


def mean(values):
    if not values:
        return None
    total = 0.0
    for value in values:
        total += value
    return total / float(len(values))


def stddev(values):
    if not values:
        return None
    avg = mean(values)
    accum = 0.0
    for value in values:
        diff = value - avg
        accum += diff * diff
    return math.sqrt(accum / float(len(values)))


def pearson_correlation(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2:
        return None

    mean_x = mean(xs)
    mean_y = mean(ys)
    if mean_x is None or mean_y is None:
        return None

    num = 0.0
    den_x = 0.0
    den_y = 0.0
    for x_value, y_value in zip(xs, ys):
        dx = x_value - mean_x
        dy = y_value - mean_y
        num += dx * dy
        den_x += dx * dx
        den_y += dy * dy

    if den_x <= 0.0 or den_y <= 0.0:
        return None
    return num / math.sqrt(den_x * den_y)


def format_number(value, digits=6):
    if value is None:
        return "N/A"
    return f"{value:.{digits}f}"


def format_delta(value):
    if value is None:
        return "N/A"
    return f"{value:+.6f}"


def parse_score_file(path):
    data = {}

    with open(path, "r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            tokens = [token.strip() for token in line.split(",")]
            if len(tokens) < 2:
                raise ValueError(f"Malformed line {line_number} in {path}")

            record = {}
            pair_count = len(tokens) // 2
            for index in range(pair_count):
                key = tokens[index * 2].strip()
                value = tokens[index * 2 + 1].strip()
                if key:
                    record[key] = value

            filename = record.get("FileName")
            pos_y_text = record.get("PosY")
            if not filename or pos_y_text is None:
                raise ValueError(f"Missing FileName/PosY at line {line_number} in {path}")

            try:
                pos_y = float(pos_y_text)
            except ValueError as exc:
                raise ValueError(f"Non-numeric PosY at line {line_number} in {path}") from exc

            data[filename] = pos_y

    if not data:
        raise ValueError(f"No valid records found in {path}")
    return data


def compute_steps(posy_series):
    steps = []
    for index in range(len(posy_series) - 1):
        steps.append(posy_series[index + 1] - posy_series[index])
    return steps


def filter_step_outliers(steps):
    if not steps:
        return steps[:], [], None, None

    step_mean = mean(steps)
    step_std = stddev(steps)
    if step_mean is None or step_std is None:
        return steps[:], [], step_mean, step_std

    if step_std <= 0.0:
        return steps[:], [], step_mean, step_std

    filtered_steps = []
    removed_indices = []
    threshold = 3.0 * step_std
    for index, value in enumerate(steps):
        if abs(value - step_mean) > threshold:
            removed_indices.append(index)
        else:
            filtered_steps.append(value)

    return filtered_steps, removed_indices, step_mean, step_std


def detrend_with_linear_fit(posy_series):
    n_points = len(posy_series)
    if n_points < 2:
        return posy_series[:], None, None

    indices = list(range(n_points))
    mean_index = mean(indices)
    mean_posy = mean(posy_series)

    num = 0.0
    den = 0.0
    for index_value, posy_value in zip(indices, posy_series):
        dx = index_value - mean_index
        num += dx * (posy_value - mean_posy)
        den += dx * dx

    slope = num / den if den > 0.0 else 0.0
    intercept = mean_posy - slope * mean_index

    residuals = []
    for index_value, posy_value in zip(indices, posy_series):
        trend_value = intercept + slope * index_value
        residuals.append(posy_value - trend_value)

    return residuals, slope, intercept


def analyze_model_pitch(posy_series, apply_outlier_filter):
    steps_raw = compute_steps(posy_series)
    steps_filtered = steps_raw[:]
    removed_indices = []
    raw_step_mean = mean(steps_raw)
    raw_step_std = stddev(steps_raw)

    if apply_outlier_filter:
        steps_filtered, removed_indices, raw_step_mean, raw_step_std = filter_step_outliers(steps_raw)

    anchor_residuals, trend_slope, trend_intercept = detrend_with_linear_fit(posy_series)
    lag1_autocorr = None
    if len(anchor_residuals) >= 2:
        lag1_autocorr = pearson_correlation(anchor_residuals[1:], anchor_residuals[:-1])

    return {
        "n_frames": len(posy_series),
        "n_steps_raw": len(steps_raw),
        "n_steps_used": len(steps_filtered),
        "step_mean_raw": raw_step_mean,
        "step_std_raw": raw_step_std,
        "step_std": stddev(steps_filtered),
        "outlier_removed": len(removed_indices),
        "outlier_step_indices": removed_indices,
        "anchor_lag1_autocorr": lag1_autocorr,
        "anchor_residual_std": stddev(anchor_residuals),
        "trend_slope_per_frame": trend_slope,
        "trend_intercept": trend_intercept,
    }


def collect_aligned_posy():
    aligned = {}
    for pitch_name in PITCH_SPECS:
        records_by_model = {}
        common_filenames = None

        for model_name, spec in MODEL_SPECS.items():
            path = os.path.join(spec["root"], pitch_name, "GMF_score.txt")
            parsed = parse_score_file(path)
            records_by_model[model_name] = parsed
            filenames = set(parsed.keys())
            if common_filenames is None:
                common_filenames = filenames
            else:
                common_filenames &= filenames

        aligned_filenames = sorted(common_filenames) if common_filenames else []
        if len(aligned_filenames) < 2:
            raise ValueError(f"Insufficient aligned frames for {pitch_name}")

        aligned[pitch_name] = {
            "filenames": aligned_filenames,
            "models": {},
        }
        for model_name in MODEL_SPECS:
            aligned[pitch_name]["models"][model_name] = [
                records_by_model[model_name][filename] for filename in aligned_filenames
            ]

    return aligned


def build_summary(aligned_data):
    summary = {
        "title": "External GMF Three-Way Comparison: R18 vs R22h vs R25sw010",
        "method": {
            "posy_source": "GMF_score.txt -> PosY",
            "step_definition": "step[i] = PosY[i+1] - PosY[i]",
            "outlier_rule_for_pitch0p1um_y_60": "|step - mean(step)| > 3 * std(step)",
            "anchor_autocorr_definition": "lag-1 Pearson correlation of PosY residual after per-sequence linear detrending",
        },
        "models": list(MODEL_SPECS.keys()),
        "pitches": {},
    }

    for pitch_name, pitch_spec in PITCH_SPECS.items():
        pitch_entry = {
            "label": pitch_spec["label"],
            "n_aligned_frames": len(aligned_data[pitch_name]["filenames"]),
            "filenames": aligned_data[pitch_name]["filenames"],
            "models": {},
        }

        for model_name in MODEL_SPECS:
            model_result = analyze_model_pitch(
                aligned_data[pitch_name]["models"][model_name],
                pitch_spec["outlier_filter"],
            )
            pitch_entry["models"][model_name] = model_result

        r18_std = pitch_entry["models"]["round18_baseline"]["step_std"]
        r22_std = pitch_entry["models"]["round22_hold"]["step_std"]
        r25_std = pitch_entry["models"]["r25_sw010"]["step_std"]
        pitch_entry["comparisons"] = {
            "r25_vs_r18_step_std_delta": None if r25_std is None or r18_std is None else r25_std - r18_std,
            "r25_vs_r22_hold_step_std_delta": None if r25_std is None or r22_std is None else r25_std - r22_std,
        }
        summary["pitches"][pitch_name] = pitch_entry

    main_pitch = summary["pitches"][MAIN_PITCH]
    r25_main = main_pitch["models"]["r25_sw010"]
    summary["conclusion"] = {
        "main_pitch": MAIN_PITCH,
        "step_std_target": STEP_STD_TARGET,
        "anchor_autocorr_target": ANCHOR_AUTOCORR_TARGET,
        "r25_main_step_std_is_below_target": (
            r25_main["step_std"] is not None and r25_main["step_std"] < STEP_STD_TARGET
        ),
        "r25_main_anchor_autocorr_is_above_target": (
            r25_main["anchor_lag1_autocorr"] is not None
            and r25_main["anchor_lag1_autocorr"] >= ANCHOR_AUTOCORR_TARGET
        ),
    }

    step_ok = summary["conclusion"]["r25_main_step_std_is_below_target"]
    autocorr_ok = summary["conclusion"]["r25_main_anchor_autocorr_is_above_target"]
    if step_ok and autocorr_ok:
        recommendation = "升級 baseline"
    elif step_ok:
        recommendation = "維持 R22h"
    else:
        recommendation = "需要進一步改善"
    summary["conclusion"]["recommendation"] = recommendation
    return summary


def build_markdown(summary):
    lines = []
    lines.append("# External GMF Three-Way Comparison: R18 vs R22h vs R25sw010")
    lines.append("")
    lines.append("## Step Std（主要指標）")
    lines.append("| 尺度 | round18_baseline | round22_hold | r25_sw010 | vs R18 | vs R22h |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")

    for pitch_name, pitch_spec in PITCH_SPECS.items():
        pitch_entry = summary["pitches"][pitch_name]
        row = [
            pitch_spec["label"],
            format_number(pitch_entry["models"]["round18_baseline"]["step_std"]),
            format_number(pitch_entry["models"]["round22_hold"]["step_std"]),
            format_number(pitch_entry["models"]["r25_sw010"]["step_std"]),
            format_delta(pitch_entry["comparisons"]["r25_vs_r18_step_std_delta"]),
            format_delta(pitch_entry["comparisons"]["r25_vs_r22_hold_step_std_delta"]),
        ]
        lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} |")

    lines.append("")
    lines.append("## Lag-1 Autocorrelation（anchor 穩定性）")
    lines.append("| 尺度 | round18_baseline | round22_hold | r25_sw010 |")
    lines.append("| --- | ---: | ---: | ---: |")

    for pitch_name, pitch_spec in PITCH_SPECS.items():
        pitch_entry = summary["pitches"][pitch_name]
        row = [
            pitch_spec["label"],
            format_number(pitch_entry["models"]["round18_baseline"]["anchor_lag1_autocorr"]),
            format_number(pitch_entry["models"]["round22_hold"]["anchor_lag1_autocorr"]),
            format_number(pitch_entry["models"]["r25_sw010"]["anchor_lag1_autocorr"]),
        ]
        lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |")

    lines.append("")
    lines.append("## 結論")

    main_pitch_entry = summary["pitches"][MAIN_PITCH]
    r25_main = main_pitch_entry["models"]["r25_sw010"]
    lines.append(
        "- 主戰場（0.8px）r25_sw010 step std "
        f"{format_number(r25_main['step_std'])} 是否 < 0.2855（R18/R22h 水準）？ "
        + ("是" if summary["conclusion"]["r25_main_step_std_is_below_target"] else "否")
    )
    lines.append(
        "- anchor lag-1 autocorr "
        f"{format_number(r25_main['anchor_lag1_autocorr'])} 是否 ≥ 0.10？ "
        + ("是" if summary["conclusion"]["r25_main_anchor_autocorr_is_above_target"] else "否")
    )
    lines.append(f"- 建議：{summary['conclusion']['recommendation']}")
    lines.append("")
    lines.append("## 方法註記")
    lines.append("- `PosY` 直接由 `GMF_score.txt` 解析。")
    lines.append("- `pitch0p1um_y_60` 的 outlier 規則為 `|step - mean(step)| > 3 * std(step)`。")
    lines.append("- `lag-1 autocorr` 以每個模型自身 `PosY` 經線性去趨勢後的 anchor residual 計算，作為單模型版本的 anchor 穩定性指標。")
    lines.append("")
    lines.append("## Outlier Summary（0.8px）")
    lines.append("| 模型 | 移除 step 數 | 原始 step std | 過濾後 step std |")
    lines.append("| --- | ---: | ---: | ---: |")
    for model_name in MODEL_SPECS:
        model_entry = main_pitch_entry["models"][model_name]
        lines.append(
            f"| {model_name} | {model_entry['outlier_removed']} | "
            f"{format_number(model_entry['step_std_raw'])} | {format_number(model_entry['step_std'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_outputs(summary):
    os.makedirs(REPORT_DIR, exist_ok=True)
    markdown_text = build_markdown(summary)
    with open(SUMMARY_MD_PATH, "w", encoding="utf-8") as handle:
        handle.write(markdown_text)

    with open(SUMMARY_JSON_PATH, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)


def main():
    aligned_data = collect_aligned_posy()
    summary = build_summary(aligned_data)
    write_outputs(summary)
    print(SUMMARY_MD_PATH)
    print(SUMMARY_JSON_PATH)


if __name__ == "__main__":
    main()
