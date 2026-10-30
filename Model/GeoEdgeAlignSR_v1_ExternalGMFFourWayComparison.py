import json
import math
import os
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# Per-model pitch directory name mapping
# Each model maps logical pitch key -> actual subdirectory name under gmf_results/raw/
MODEL_SPECS = {
    "round18_baseline": {
        "root": str(PROJECT_ROOT / 'Experiments/Legacy/organized_20260316/external_compare_round18_round22/round18_baseline/gmf_results/raw'),
        "pitch_dirs": {
            "8px": "pitch1um_y_100",
            "0p8px": "pitch0p1um_y_60",
            "0p08px": "pitch0p01um_y_40",
        },
    },
    "round22_hold": {
        "root": str(PROJECT_ROOT / 'Experiments/Legacy/organized_20260316/external_compare_round18_round22/round22_hold/gmf_results/raw'),
        "pitch_dirs": {
            "8px": "pitch1um_y_100",
            "0p8px": "pitch0p1um_y_60",
            "0p08px": "pitch0p01um_y_40",
        },
    },
    "r25_sw010": {
        "root": str(PROJECT_ROOT / 'Experiments/Legacy/organized_20260316/external_compare_r18_r22_r25/r25_sw010/gmf_results/raw'),
        "pitch_dirs": {
            "8px": "pitch1um_y_100",
            "0p8px": "pitch0p1um_y_60",
            "0p08px": "pitch0p01um_y_40",
        },
    },
    "r26_sm035": {
        "root": str(PROJECT_ROOT / 'Experiments/Legacy/organized_20260316/external_compare_r18_r22_r25_r26/r26_sm035/gmf_results/raw'),
        "pitch_dirs": {
            "8px": "pitch8px",
            "0p8px": "pitch0p8px",
            "0p08px": "pitch0p08px",
        },
    },
}

PITCH_SPECS = {
    "8px": {
        "label": "8px (pitch1um)",
        "outlier_filter": False,
    },
    "0p8px": {
        "label": "0.8px (pitch0p1um)",
        "outlier_filter": True,
    },
    "0p08px": {
        "label": "0.08px (pitch0p01um)",
        "outlier_filter": False,
    },
}

BASE_DIR = str(PROJECT_ROOT / 'Experiments/Legacy/organized_20260316/external_compare_r18_r22_r25_r26')
REPORT_DIR = os.path.join(BASE_DIR, "reports")
SUMMARY_MD_PATH = os.path.join(REPORT_DIR, "EXTERNAL_COMPARE_R18_R22_R25_R26_SUMMARY.md")
SUMMARY_JSON_PATH = os.path.join(REPORT_DIR, "EXTERNAL_COMPARE_R18_R22_R25_R26_SUMMARY.json")
MAIN_PITCH = "0p8px"
STEP_STD_TARGET = 0.2120   # R25 adopted baseline value — R26 must beat this
ANCHOR_AUTOCORR_TARGET = 0.10


def mean(values):
    if not values:
        return None
    return sum(values) / float(len(values))


def stddev(values):
    if not values:
        return None
    avg = mean(values)
    accum = sum((v - avg) ** 2 for v in values)
    return math.sqrt(accum / float(len(values)))


def pearson_correlation(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = mean(xs)
    mean_y = mean(ys)
    if mean_x is None or mean_y is None:
        return None
    num = den_x = den_y = 0.0
    for x, y in zip(xs, ys):
        dx, dy = x - mean_x, y - mean_y
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
            tokens = [t.strip() for t in line.split(",")]
            if len(tokens) < 2:
                raise ValueError(f"Malformed line {line_number} in {path}")
            record = {}
            for i in range(len(tokens) // 2):
                k = tokens[i * 2].strip()
                v = tokens[i * 2 + 1].strip()
                if k:
                    record[k] = v
            filename = record.get("FileName")
            pos_y_text = record.get("PosY")
            if not filename or pos_y_text is None:
                raise ValueError(f"Missing FileName/PosY at line {line_number} in {path}")
            try:
                data[filename] = float(pos_y_text)
            except ValueError as exc:
                raise ValueError(f"Non-numeric PosY at line {line_number} in {path}") from exc
    if not data:
        raise ValueError(f"No valid records found in {path}")
    return data


def compute_steps(posy_series):
    return [posy_series[i + 1] - posy_series[i] for i in range(len(posy_series) - 1)]


def filter_step_outliers(steps):
    if not steps:
        return steps[:], [], None, None
    step_mean = mean(steps)
    step_std = stddev(steps)
    if step_mean is None or step_std is None or step_std <= 0.0:
        return steps[:], [], step_mean, step_std
    threshold = 3.0 * step_std
    filtered, removed = [], []
    for i, v in enumerate(steps):
        if abs(v - step_mean) > threshold:
            removed.append(i)
        else:
            filtered.append(v)
    return filtered, removed, step_mean, step_std


def detrend_linear(posy_series):
    n = len(posy_series)
    if n < 2:
        return posy_series[:], None, None
    indices = list(range(n))
    mi = mean(indices)
    mp = mean(posy_series)
    num = den = 0.0
    for i, p in zip(indices, posy_series):
        dx = i - mi
        num += dx * (p - mp)
        den += dx * dx
    slope = num / den if den > 0.0 else 0.0
    intercept = mp - slope * mi
    residuals = [p - (intercept + slope * i) for i, p in zip(indices, posy_series)]
    return residuals, slope, intercept


def analyze_model_pitch(posy_series, apply_outlier_filter):
    steps_raw = compute_steps(posy_series)
    steps_filtered = steps_raw[:]
    removed_indices = []
    raw_step_mean = mean(steps_raw)
    raw_step_std = stddev(steps_raw)
    if apply_outlier_filter:
        steps_filtered, removed_indices, raw_step_mean, raw_step_std = filter_step_outliers(steps_raw)
    anchor_residuals, trend_slope, trend_intercept = detrend_linear(posy_series)
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
    for pitch_key in PITCH_SPECS:
        records_by_model = {}
        common_filenames = None
        for model_name, spec in MODEL_SPECS.items():
            pitch_dir = spec["pitch_dirs"][pitch_key]
            path = os.path.join(spec["root"], pitch_dir, "GMF_score.txt")
            parsed = parse_score_file(path)
            records_by_model[model_name] = parsed
            filenames = set(parsed.keys())
            common_filenames = filenames if common_filenames is None else common_filenames & filenames
        aligned_filenames = sorted(common_filenames) if common_filenames else []
        if len(aligned_filenames) < 2:
            raise ValueError(f"Insufficient aligned frames for pitch {pitch_key}")
        aligned[pitch_key] = {
            "filenames": aligned_filenames,
            "models": {m: [records_by_model[m][f] for f in aligned_filenames] for m in MODEL_SPECS},
        }
    return aligned


def build_summary(aligned_data):
    summary = {
        "title": "External GMF Four-Way Comparison: R18 vs R22h vs R25sw010 vs R26sm035",
        "method": {
            "posy_source": "GMF_score.txt -> PosY",
            "step_definition": "step[i] = PosY[i+1] - PosY[i]",
            "outlier_rule_for_0p8px": "|step - mean(step)| > 3 * std(step)",
            "anchor_autocorr_definition": "lag-1 Pearson correlation of PosY residual after per-sequence linear detrending",
        },
        "models": list(MODEL_SPECS.keys()),
        "pitches": {},
    }

    for pitch_key, pitch_spec in PITCH_SPECS.items():
        pitch_entry = {
            "label": pitch_spec["label"],
            "n_aligned_frames": len(aligned_data[pitch_key]["filenames"]),
            "models": {},
        }
        for model_name in MODEL_SPECS:
            pitch_entry["models"][model_name] = analyze_model_pitch(
                aligned_data[pitch_key]["models"][model_name],
                pitch_spec["outlier_filter"],
            )
        r18_std = pitch_entry["models"]["round18_baseline"]["step_std"]
        r25_std = pitch_entry["models"]["r25_sw010"]["step_std"]
        r26_std = pitch_entry["models"]["r26_sm035"]["step_std"]
        pitch_entry["comparisons"] = {
            "r26_vs_r18_step_std_delta": None if r26_std is None or r18_std is None else r26_std - r18_std,
            "r26_vs_r25_step_std_delta": None if r26_std is None or r25_std is None else r26_std - r25_std,
        }
        summary["pitches"][pitch_key] = pitch_entry

    main = summary["pitches"][MAIN_PITCH]
    r25_main = main["models"]["r25_sw010"]
    r26_main = main["models"]["r26_sm035"]
    summary["conclusion"] = {
        "main_pitch": MAIN_PITCH,
        "step_std_target_vs_r25": STEP_STD_TARGET,
        "r26_main_step_std": r26_main["step_std"],
        "r26_beats_r25": (
            r26_main["step_std"] is not None
            and r25_main["step_std"] is not None
            and r26_main["step_std"] < r25_main["step_std"]
        ),
        "r26_main_anchor_autocorr": r26_main["anchor_lag1_autocorr"],
    }
    r26_beats = summary["conclusion"]["r26_beats_r25"]
    if r26_beats:
        summary["conclusion"]["recommendation"] = "升級 R26 sm035 為新 baseline"
    else:
        summary["conclusion"]["recommendation"] = "維持 R25 sw010 baseline"
    return summary


def build_markdown(summary):
    lines = []
    lines.append("# External GMF Four-Way Comparison: R18 vs R22h vs R25sw010 vs R26sm035")
    lines.append("")
    lines.append("## Step Std（主要指標）")
    lines.append("| 尺度 | round18_baseline | round22_hold | r25_sw010 | r26_sm035 | vs R25 | vs R18 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for pitch_key, pitch_spec in PITCH_SPECS.items():
        pe = summary["pitches"][pitch_key]
        lines.append(
            f"| {pitch_spec['label']} "
            f"| {format_number(pe['models']['round18_baseline']['step_std'])} "
            f"| {format_number(pe['models']['round22_hold']['step_std'])} "
            f"| {format_number(pe['models']['r25_sw010']['step_std'])} "
            f"| {format_number(pe['models']['r26_sm035']['step_std'])} "
            f"| {format_delta(pe['comparisons']['r26_vs_r25_step_std_delta'])} "
            f"| {format_delta(pe['comparisons']['r26_vs_r18_step_std_delta'])} |"
        )
    lines.append("")
    lines.append("## Lag-1 Autocorrelation（anchor 穩定性）")
    lines.append("| 尺度 | round18_baseline | round22_hold | r25_sw010 | r26_sm035 |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for pitch_key, pitch_spec in PITCH_SPECS.items():
        pe = summary["pitches"][pitch_key]
        lines.append(
            f"| {pitch_spec['label']} "
            f"| {format_number(pe['models']['round18_baseline']['anchor_lag1_autocorr'])} "
            f"| {format_number(pe['models']['round22_hold']['anchor_lag1_autocorr'])} "
            f"| {format_number(pe['models']['r25_sw010']['anchor_lag1_autocorr'])} "
            f"| {format_number(pe['models']['r26_sm035']['anchor_lag1_autocorr'])} |"
        )
    lines.append("")
    lines.append("## 結論")
    c = summary["conclusion"]
    r26_std = c["r26_main_step_std"]
    r25_std = summary["pitches"][MAIN_PITCH]["models"]["r25_sw010"]["step_std"]
    lines.append(f"- 主戰場（0.8px）r26_sm035 step std = {format_number(r26_std)}")
    lines.append(f"- r25_sw010 step std = {format_number(r25_std)}")
    lines.append(f"- R26 是否優於 R25？ {'是' if c['r26_beats_r25'] else '否'}")
    lines.append(f"- anchor lag-1 autocorr（R26）= {format_number(c['r26_main_anchor_autocorr'])}")
    lines.append(f"- 建議：{c['recommendation']}")
    lines.append("")
    lines.append("## Outlier Summary（0.8px）")
    lines.append("| 模型 | 移除 step 數 | 原始 step std | 過濾後 step std |")
    lines.append("| --- | ---: | ---: | ---: |")
    for model_name in MODEL_SPECS:
        me = summary["pitches"][MAIN_PITCH]["models"][model_name]
        lines.append(
            f"| {model_name} | {me['outlier_removed']} "
            f"| {format_number(me['step_std_raw'])} "
            f"| {format_number(me['step_std'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_outputs(summary):
    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(SUMMARY_MD_PATH, "w", encoding="utf-8") as f:
        f.write(build_markdown(summary))
    with open(SUMMARY_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


def main():
    aligned_data = collect_aligned_posy()
    summary = build_summary(aligned_data)
    write_outputs(summary)
    print(build_markdown(summary))
    print(f"\nJSON: {SUMMARY_JSON_PATH}")
    print(f"MD:   {SUMMARY_MD_PATH}")


if __name__ == "__main__":
    main()
