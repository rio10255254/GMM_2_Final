from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence")
SOURCE = ROOT / "Final_Data_Figures" / "20260708_v41_standalone_full_validation" / "scripts" / "analyze_boundary_sensitive_roi_v41_compare.py"
OUT = ROOT / "Final_Data_Figures" / "20260710_v42_full_validation" / "boundary_sensitive_roi"
V42_ROOT = ROOT / "Final_Data_Figures" / "20260710_v42_full_validation" / "reconstructions" / "reconstruct_progress_epoch_120_in_bmp_20260709_202713"


V42_FOLDERS = {
    ("20260702_100MG", "x_1um"): V42_ROOT / "50x_1um",
    ("20260702_100MG", "x_0p5um"): V42_ROOT / "50x_0p5um",
    ("20260704_20x_5x", "20x_1um"): V42_ROOT / "20x_1um",
    ("20260704_20x_5x", "20x_0p5um"): V42_ROOT / "20x_0p5um",
    ("20260704_20x_5x", "5x_1um"): V42_ROOT / "5x_1um",
    ("20260704_20x_5x", "5x_0p5um"): V42_ROOT / "5x_0p5um",
}


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("boundary_validation", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_report(module, comparison_rows, manifest) -> None:
    lines = [
        "# V42 Epoch 120: Fixed-ROI Boundary-Sensitive Displacement Validation",
        "",
        "All cases use the same raw-defined ROI, the same frame order, signed direction, and object-plane scale within each sequence.",
        "The all-step result is primary. Common-best30 and Raw-anchor-best30 are retained only as sensitivity analyses.",
        "",
    ]
    for selection in ("all_steps", "common_best30", "raw_anchor_best30"):
        lines += [
            f"## {selection}",
            "",
            "| Dataset | Sequence | Case | Steps | Step std (um) | Median abs. error (um) | Std. change vs Raw |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
        for row in comparison_rows:
            if row["selection"] != selection:
                continue
            lines.append(
                f"| {row['dataset']} | {row['group']} | {row['case_label']} | {row['n_steps']} | "
                f"{float(row['std_step_um']):.6f} | {float(row['median_abs_error_um']):.6f} | "
                f"{float(row['std_improvement_vs_raw_pct']):+.2f}% |"
            )
        lines.append("")
    lines += [
        "## Integrity",
        "",
        f"- Sequences: {len(manifest['groups'])}",
        "- Cases: Raw, V41 standalone, V42 epoch 120",
        "- Every case must have the identical BMP filename order before calculation.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    module = load_module(SOURCE)
    module.OUT = OUT
    module.CASES = ["raw", "v41_standalone", "v42_e120"]
    module.CASE_LABELS = {"raw": "Raw", "v41_standalone": "V41 standalone", "v42_e120": "V42 epoch 120"}
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(parents=True, exist_ok=True)

    source_rows = module.read_csv(module.SOURCE_TABLE)
    module.CASES = ["raw", "v41_standalone"]
    case_map = module.build_case_map(source_rows)
    for key, folder in V42_FOLDERS.items():
        if key not in case_map:
            raise RuntimeError(f"Missing source group {key}")
        case_map[key]["v42_e120"] = str(folder)
    module.CASES = ["raw", "v41_standalone", "v42_e120"]

    all_rows, summary_rows, direction_rows, integrity_rows = [], [], [], []
    group_configs = {}
    for (dataset, group), cases in case_map.items():
        cfg = module.load_roi_config(dataset, group)
        group_configs[f"{dataset}/{group}"] = cfg
        raw_files = module.list_images(Path(cases["raw"]))
        expected_signed_dx_px, diagnostics = module.choose_signed_dx(raw_files, cfg)
        direction_rows.extend(diagnostics)
        frame_names = {}
        for case in module.CASES:
            rows, summary, names = module.measure_case(dataset, group, case, Path(cases[case]), cfg, expected_signed_dx_px)
            all_rows.extend(rows)
            summary_rows.append(summary)
            frame_names[case] = names
            integrity_rows.append({
                "dataset": dataset, "group": group, "case": case,
                "image_count": len(names), "step_count": len(names) - 1,
                "input_dir": cases[case], "frame_order_matches_raw": names == frame_names["raw"],
            })
        if any(frame_names[case] != frame_names["raw"] for case in module.CASES):
            raise RuntimeError(f"Frame order mismatch: {dataset}/{group}")
        module.draw_roi_preview(dataset, group, Path(cases["raw"]), cfg["roi"])

    filtered_summaries, selected_rows, step_diag_rows = module.build_filtered_summaries(all_rows)
    summary_rows.extend(filtered_summaries)
    comparison_rows = module.build_comparison(summary_rows)
    module.plot_step_traces(all_rows, step_diag_rows)
    module.plot_summary(comparison_rows)
    manifest = {
        "algorithm": "fixed_raw_roi_sobel_edge_projection_profile_matching_subpixel_refinement",
        "cases": module.CASES,
        "groups": [f"{dataset}/{group}" for dataset, group in case_map],
        "group_configs": group_configs,
        "integrity_all_frame_orders_match": all(bool(row["frame_order_matches_raw"]) for row in integrity_rows),
        "row_counts": {"all_steps": len(all_rows), "summary": len(summary_rows), "comparison": len(comparison_rows), "selected_steps": len(selected_rows)},
    }
    module.write_csv(OUT / "tables" / "all_steps.csv", all_rows)
    module.write_csv(OUT / "tables" / "summary.csv", summary_rows)
    module.write_csv(OUT / "tables" / "comparison.csv", comparison_rows)
    module.write_csv(OUT / "tables" / "selected_steps.csv", selected_rows)
    module.write_csv(OUT / "tables" / "step_diagnostics.csv", step_diag_rows)
    module.write_csv(OUT / "tables" / "direction_diagnostics.csv", direction_rows)
    module.write_csv(OUT / "tables" / "integrity_checks.csv", integrity_rows)
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(module, comparison_rows, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
