import os
import math
from datetime import datetime
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]


BASE_DIR = str(PROJECT_ROOT / 'Traing_Progress/organized_20260316/external_compare_round18_round22')
MODELS = ["round18_baseline", "round22_stepguard", "round22_hold"]
PITCHES = ["pitch1um_y_100", "pitch0p1um_y_60", "pitch0p01um_y_40"]
OUTLIER_PITCH = "pitch0p1um_y_60"
REPORT_DIR = BASE_DIR + r"\reports"

BASELINE_MODEL = "round18_baseline"
STEPGUARD_MODEL = "round22_stepguard"
HOLD_MODEL = "round22_hold"


def format_number(value, digits=6):
    if value is None:
        return "N/A"
    return f"{value:.{digits}f}"


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
    if avg is None:
        return None
    accum = 0.0
    for value in values:
        diff = value - avg
        accum += diff * diff
    return math.sqrt(accum / float(len(values)))


def max_abs(values):
    if not values:
        return None
    current = 0.0
    for value in values:
        absolute = abs(value)
        if absolute > current:
            current = absolute
    return current


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


def build_score_path(model_name, pitch_name):
    return os.path.join(BASE_DIR, model_name, "gmf_results", "raw", pitch_name, "GMF_score.txt")


def parse_score_file(path):
    data = {}

    if not os.path.isfile(path):
        print(f"WARNING: Missing GMF_score.txt: {path}")
        return None

    with open(path, "r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            tokens = [token.strip() for token in line.split(",")]
            if len(tokens) < 2:
                print(f"WARNING: Skipping malformed line {line_number} in {path}")
                continue

            record = {}
            pair_count = len(tokens) // 2
            for index in range(pair_count):
                key = tokens[index * 2].strip()
                value = tokens[index * 2 + 1].strip()
                if key:
                    record[key] = value

            filename = record.get("FileName")
            pos_x_text = record.get("PosX")
            pos_y_text = record.get("PosY")
            score0_text = record.get("Score0")

            if not filename or pos_x_text is None or pos_y_text is None or score0_text is None:
                print(f"WARNING: Missing required fields on line {line_number} in {path}")
                continue

            try:
                pos_x = float(pos_x_text)
                pos_y = float(pos_y_text)
                score0 = float(score0_text)
            except ValueError:
                print(f"WARNING: Non-numeric value on line {line_number} in {path}")
                continue

            data[filename] = {
                "posx": pos_x,
                "posy": pos_y,
                "score0": score0,
            }

    return data


def align_pitch_records(records_by_model, pitch_name):
    required_models = [BASELINE_MODEL, STEPGUARD_MODEL, HOLD_MODEL]
    for model_name in required_models:
        if records_by_model.get(model_name) is None:
            print(f"WARNING: Skipping pitch {pitch_name}: missing data for {model_name}")
            return None

    common_filenames = None
    for model_name in required_models:
        filename_set = set(records_by_model[model_name].keys())
        if common_filenames is None:
            common_filenames = filename_set
        else:
            common_filenames &= filename_set

    if not common_filenames or len(common_filenames) < 2:
        print(f"WARNING: Skipping pitch {pitch_name}: fewer than 2 aligned frames")
        return None

    aligned_filenames = sorted(common_filenames)
    aligned = {}
    for model_name in required_models:
        aligned[model_name] = []
        for filename in aligned_filenames:
            aligned[model_name].append(records_by_model[model_name][filename])

    return aligned_filenames, aligned


def compute_steps(posy_series):
    steps = []
    for index in range(len(posy_series) - 1):
        steps.append(posy_series[index + 1] - posy_series[index])
    return steps


def compute_outliers(filenames, steps_baseline, steps_stepguard):
    outliers = []
    if len(steps_baseline) != len(steps_stepguard) or not steps_baseline:
        return outliers, None

    abs_diffs = []
    for base_step, sg_step in zip(steps_baseline, steps_stepguard):
        abs_diffs.append(abs(sg_step - base_step))

    threshold_mean = mean(abs_diffs)
    threshold_std = stddev(abs_diffs)
    if threshold_mean is None or threshold_std is None:
        return outliers, None

    threshold = threshold_mean + 2.0 * threshold_std

    for index, (base_step, sg_step, abs_diff) in enumerate(zip(steps_baseline, steps_stepguard, abs_diffs)):
        if abs_diff > threshold:
            outliers.append(
                {
                    "index": index,
                    "filename": filenames[index + 1],
                    "r18_step": base_step,
                    "r22sg_step": sg_step,
                    "diff": sg_step - base_step,
                    "abs_diff": abs_diff,
                }
            )

    return outliers, threshold


def analyze_variant(residuals, steps):
    indices = list(range(len(residuals)))
    return {
        "n_frames": len(residuals),
        "mean_residual": mean(residuals),
        "std_residual": stddev(residuals),
        "max_abs_residual": max_abs(residuals),
        "drift_r": pearson_correlation(indices, residuals),
        "std_steps": stddev(steps),
        "lag1_autocorr": pearson_correlation(residuals[1:], residuals[:-1]) if len(residuals) >= 2 else None,
    }


def print_pitch_summary(pitch_name, result):
    print("")
    print(f"Pitch: {pitch_name}")
    print(f"  n_frames aligned: {result['n_frames']}")
    print(
        "  residual stats sg: "
        f"mean={format_number(result['sg']['mean_residual'])}, "
        f"std={format_number(result['sg']['std_residual'])}, "
        f"max_abs={format_number(result['sg']['max_abs_residual'])}"
    )
    print(
        "  residual stats h:  "
        f"mean={format_number(result['hold']['mean_residual'])}, "
        f"std={format_number(result['hold']['std_residual'])}, "
        f"max_abs={format_number(result['hold']['max_abs_residual'])}"
    )
    print(
        "  drift Pearson r:   "
        f"sg={format_number(result['sg']['drift_r'])}, "
        f"h={format_number(result['hold']['drift_r'])}"
    )
    print(
        "  std(steps):        "
        f"R18={format_number(result['std_steps']['round18_baseline'])}, "
        f"R22sg={format_number(result['std_steps']['round22_stepguard'])}, "
        f"R22h={format_number(result['std_steps']['round22_hold'])}"
    )
    print(
        "  lag-1 autocorr:    "
        f"sg={format_number(result['sg']['lag1_autocorr'])}, "
        f"h={format_number(result['hold']['lag1_autocorr'])}"
    )


def answer_q1(results):
    if not results:
        return "Insufficient data: no pitches were analyzed successfully."

    for result in results.values():
        sg_r = result["sg"]["drift_r"]
        hold_r = result["hold"]["drift_r"]
        if sg_r is not None and abs(sg_r) > 0.3:
            return "Drift tendency detected: at least one pitch has |Pearson r| > 0.3."
        if hold_r is not None and abs(hold_r) > 0.3:
            return "Drift tendency detected: at least one pitch has |Pearson r| > 0.3."
    return "Residual looks more random than drifting: no pitch exceeds |Pearson r| > 0.3."


def answer_q2(results):
    result = results.get(OUTLIER_PITCH)
    if result is None:
        return f"Insufficient data: {OUTLIER_PITCH} was skipped."

    outliers = result["outliers"]
    n_frames = result["n_frames"]
    if not outliers:
        return f"No outlier steps detected for {OUTLIER_PITCH}."
    if len(outliers) < 2:
        return f"Too few outliers to judge clustering for {OUTLIER_PITCH}."

    indices = [item["index"] for item in outliers]
    max_gap = 0
    for index in range(len(indices) - 1):
        gap = indices[index + 1] - indices[index]
        if gap > max_gap:
            max_gap = gap

    if max_gap < (n_frames / 3.0):
        return f"Outlier frames appear clustered in {OUTLIER_PITCH} (max gap {max_gap} < n_frames/3)."
    return f"Outlier frames appear spread out in {OUTLIER_PITCH} (max gap {max_gap} >= n_frames/3)."


def answer_q3(results):
    if not results:
        return "Insufficient data: no pitches were analyzed successfully."

    for pitch_name, result in results.items():
        mean_gap = None
        std_gap = None

        sg_mean = result["sg"]["mean_residual"]
        hold_mean = result["hold"]["mean_residual"]
        sg_std = result["sg"]["std_residual"]
        hold_std = result["hold"]["std_residual"]

        if sg_mean is not None and hold_mean is not None:
            mean_gap = abs(sg_mean - hold_mean)
        if sg_std is not None and hold_std is not None:
            std_gap = abs(sg_std - hold_std)

        if (mean_gap is not None and mean_gap > 0.1) or (std_gap is not None and std_gap > 0.1):
            return (
                "R22_hold and R22_stepguard show different residual patterns: "
                f"{pitch_name} exceeds the 0.1 threshold."
            )

    return "R22_hold and R22_stepguard show broadly similar residual patterns by the 0.1 thresholds."


def build_report(timestamp_text, results):
    lines = []
    lines.append(f"# GMF Residual Analysis — {timestamp_text}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    if not results:
        lines.append("No pitches were analyzed successfully.")
        lines.append("")
    else:
        lines.append(f"- Pitches analyzed: {len(results)}")
        for pitch_name, result in results.items():
            lines.append(
                f"- {pitch_name}: {result['n_frames']} aligned frames, "
                f"sg drift={format_number(result['sg']['drift_r'])}, "
                f"h drift={format_number(result['hold']['drift_r'])}"
            )
        lines.append("")

    lines.append("## Per-Pitch Results")
    lines.append("")

    for pitch_name, result in results.items():
        lines.append(f"### {pitch_name}")
        lines.append("")
        lines.append("| Metric | R22_stepguard | R22_hold |")
        lines.append("|--------|--------------|----------|")
        lines.append(f"| N frames | {result['sg']['n_frames']} | {result['hold']['n_frames']} |")
        lines.append(
            f"| Mean residual (px) | {format_number(result['sg']['mean_residual'])} | {format_number(result['hold']['mean_residual'])} |"
        )
        lines.append(
            f"| Std residual (px) | {format_number(result['sg']['std_residual'])} | {format_number(result['hold']['std_residual'])} |"
        )
        lines.append(
            f"| Max \\|residual\\| (px) | {format_number(result['sg']['max_abs_residual'])} | {format_number(result['hold']['max_abs_residual'])} |"
        )
        lines.append(
            f"| Drift (Pearson r) | {format_number(result['sg']['drift_r'])} | {format_number(result['hold']['drift_r'])} |"
        )
        lines.append(
            f"| Std(steps) | {format_number(result['sg']['std_steps'])} | {format_number(result['hold']['std_steps'])} |"
        )
        lines.append(
            f"| Lag-1 autocorr | {format_number(result['sg']['lag1_autocorr'])} | {format_number(result['hold']['lag1_autocorr'])} |"
        )
        lines.append("")

        if pitch_name == OUTLIER_PITCH:
            lines.append(f"Outlier frames (only for {OUTLIER_PITCH}, max 10):")
            lines.append("")
            lines.append("| FileName | R18 step | R22sg step | diff |")
            lines.append("|----------|----------|------------|------|")
            shown = 0
            for item in result["outliers"]:
                if shown >= 10:
                    break
                lines.append(
                    f"| {item['filename']} | {format_number(item['r18_step'])} | {format_number(item['r22sg_step'])} | {format_number(item['diff'])} |"
                )
                shown += 1
            if shown == 0:
                lines.append("| None | N/A | N/A | N/A |")
            lines.append("")

    lines.append("## Core Questions")
    lines.append("")
    lines.append(f"Q1: Is residual random or drift?  {answer_q1(results)}")
    lines.append("")
    lines.append(f"Q2: Are outlier frames clustered or uniformly distributed?  {answer_q2(results)}")
    lines.append("")
    lines.append(f"Q3: Do R22h and R22sg show different residual patterns?  {answer_q3(results)}")
    lines.append("")
    return "\n".join(lines)


def main():
    records = {}
    for pitch_name in PITCHES:
        records[pitch_name] = {}
        for model_name in MODELS:
            score_path = build_score_path(model_name, pitch_name)
            records[pitch_name][model_name] = parse_score_file(score_path)

    results = {}

    for pitch_name in PITCHES:
        aligned_data = align_pitch_records(records[pitch_name], pitch_name)
        if aligned_data is None:
            continue

        filenames, aligned = aligned_data

        baseline_posy = [item["posy"] for item in aligned[BASELINE_MODEL]]
        stepguard_posy = [item["posy"] for item in aligned[STEPGUARD_MODEL]]
        hold_posy = [item["posy"] for item in aligned[HOLD_MODEL]]

        residual_sg = []
        residual_hold = []
        for index in range(len(filenames)):
            residual_sg.append(stepguard_posy[index] - baseline_posy[index])
            residual_hold.append(hold_posy[index] - baseline_posy[index])

        steps_baseline = compute_steps(baseline_posy)
        steps_stepguard = compute_steps(stepguard_posy)
        steps_hold = compute_steps(hold_posy)

        outliers, threshold = compute_outliers(filenames, steps_baseline, steps_stepguard)

        sg_stats = analyze_variant(residual_sg, steps_stepguard)
        hold_stats = analyze_variant(residual_hold, steps_hold)

        results[pitch_name] = {
            "n_frames": len(filenames),
            "filenames": filenames,
            "sg": sg_stats,
            "hold": hold_stats,
            "std_steps": {
                BASELINE_MODEL: stddev(steps_baseline),
                STEPGUARD_MODEL: stddev(steps_stepguard),
                HOLD_MODEL: stddev(steps_hold),
            },
            "outliers": outliers,
            "outlier_threshold": threshold,
        }

        print_pitch_summary(pitch_name, results[pitch_name])

    os.makedirs(REPORT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(REPORT_DIR, f"GMF_RESIDUAL_ANALYSIS_{timestamp}.md")
    report_text = build_report(timestamp, results)

    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write(report_text)

    print("")
    print(f"Report written to: {report_path}")


if __name__ == "__main__":
    main()
