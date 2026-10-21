from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import analysis_core


ROOT = Path(__file__).resolve().parents[2]


def load_config(config_path: Path | None) -> dict[str, Any]:
    if config_path is None:
        config_path = Path(__file__).with_name("analysis_config.json")
    return json.loads(config_path.read_text(encoding="utf-8"))


def _prepare_output_dirs(out_dir: Path) -> dict[str, Path]:
    paths = {
        "root": out_dir,
        "figures": out_dir / "figures",
        "tables": out_dir / "tables",
        "logs": out_dir / "logs",
        "draft": out_dir / "draft",
        "scripts": out_dir / "scripts",
    }
    for path in paths.values():
        analysis_core.ensure_dir(path)
    return paths


def _merge_rows(*row_maps: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    merged = {"RAW": {}, "R26": {}}
    for row_map in row_maps:
        for image_name, values in row_map.items():
            merged[image_name].update(values)
    return merged


def run_analysis(raw_path: Path, r26_path: Path, out_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    out_paths = _prepare_output_dirs(out_dir)
    raw = analysis_core.load_grayscale_image(raw_path)
    r26 = analysis_core.load_grayscale_image(r26_path)
    ref = analysis_core.detect_ring_reference(raw, config)
    rois, roi_log = analysis_core.select_rois(raw, r26, ref, config)
    spatial_rows, profile_plot_data, profile_log = analysis_core.compute_spatial_metrics(raw, r26, ref, rois, config)
    fft_rows, fft_plot_data = analysis_core.compute_fft_metrics(raw, r26, ref, config)
    geo_rows, geo_log = analysis_core.compute_geometry_proxy(raw, r26, ref, config)

    merged_rows = _merge_rows(spatial_rows, fft_rows, geo_rows)
    row_dicts = analysis_core.rows_to_dicts(merged_rows)

    overall_path = out_paths["figures"] / "01_overall_compare_raw_vs_r26.png"
    roi_path = out_paths["figures"] / "02_roi_compare_raw_vs_r26.png"
    profile_path = out_paths["figures"] / "03_edge_profiles_raw_vs_r26.png"
    frequency_path = out_paths["figures"] / "04_frequency_validation_raw_vs_r26.png"
    csv_path = out_paths["tables"] / "single_image_metrics.csv"
    table_md_path = out_paths["tables"] / "single_image_metrics_report.md"
    plan_path = out_paths["root"] / "single_image_analysis_plan.md"
    draft_path = out_paths["draft"] / "single_image_recon_result_draft_zh.md"

    analysis_core.render_overall_compare(raw, r26, config, overall_path)
    analysis_core.render_roi_compare(raw, r26, rois, config, roi_path)
    analysis_core.render_edge_profiles(profile_plot_data, profile_path)
    analysis_core.render_frequency_validation(fft_plot_data, frequency_path)
    analysis_core.write_metrics_csv(row_dicts, csv_path)
    analysis_core.write_metrics_markdown(row_dicts, table_md_path)

    source_selection = {
        "raw_path": str(raw_path),
        "r26_path": str(r26_path),
        "raw_hash": analysis_core.sha256_file(raw_path),
        "r26_hash": analysis_core.sha256_file(r26_path),
        "ignored_candidates": ["_smoketest_*"],
        "selected_weight": "r26_sm035_best_tradeoff.pth.tar",
        "reference_summary": {
            "cx": ref["cx"],
            "cy": ref["cy"],
            "inner_edge_r": ref["inner_edge_r"],
            "outer_edge_r": ref["outer_edge_r"],
            "peak_r": ref["peak_r"],
        },
    }
    analysis_core.dump_json(out_paths["logs"] / "source_selection.json", source_selection)
    analysis_core.dump_json(out_paths["logs"] / "roi_selection.json", {"rois": rois, **roi_log})
    analysis_core.dump_json(out_paths["logs"] / "profile_processing.json", profile_log)
    analysis_core.dump_json(out_paths["logs"] / "run_summary.json", {"rows": row_dicts, "geometry": geo_log, "fft": {
        "raw_crop_rect": fft_plot_data["RAW"]["crop_rect"],
        "r26_crop_rect": fft_plot_data["R26"]["crop_rect"],
    }})

    plan_context = {
        "raw_path": str(raw_path),
        "r26_path": str(r26_path),
        "raw_hash": source_selection["raw_hash"],
        "r26_hash": source_selection["r26_hash"],
    }
    plan_path.write_text(analysis_core.build_plan_markdown(plan_context), encoding="utf-8")
    draft_path.write_text(analysis_core.build_result_draft(plan_context, row_dicts), encoding="utf-8")

    return {
        "figures": {
            "overall": overall_path,
            "roi": roi_path,
            "profiles": profile_path,
            "frequency": frequency_path,
        },
        "tables": {
            "csv": csv_path,
            "markdown": table_md_path,
        },
        "logs": {
            "source_selection": out_paths["logs"] / "source_selection.json",
            "roi_selection": out_paths["logs"] / "roi_selection.json",
            "profile_processing": out_paths["logs"] / "profile_processing.json",
            "run_summary": out_paths["logs"] / "run_summary.json",
        },
        "plan": plan_path,
        "draft": draft_path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run RAW vs R26 single image analysis.")
    parser.add_argument("--input", dest="raw_path", type=Path, default=None)
    parser.add_argument("--output", dest="r26_path", type=Path, default=None)
    parser.add_argument("--config", dest="config_path", type=Path, default=None)
    parser.add_argument("--out-dir", dest="out_dir", type=Path, default=ROOT / "analysis_single_image_recon")
    args = parser.parse_args(argv)

    config = load_config(args.config_path)
    raw_path = args.raw_path or Path(config["paths"]["raw"])
    r26_path = args.r26_path or Path(config["paths"]["r26"])
    run_analysis(raw_path, r26_path, args.out_dir, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
