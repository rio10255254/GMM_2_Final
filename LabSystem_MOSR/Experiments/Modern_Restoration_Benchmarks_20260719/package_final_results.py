from __future__ import annotations

import json
import shutil
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]


EXPERIMENT = Path(__file__).resolve().parent
EVALUATION = EXPERIMENT / "evaluation"
TARGET = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/modern_baseline_three_morphology_20260719')
)


def copy_file(source: Path, destination: Path) -> Path:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def copy_glob(source_dir: Path, pattern: str, destination_dir: Path) -> list[Path]:
    copied: list[Path] = []
    for source in sorted(source_dir.glob(pattern)):
        if source.is_file():
            copied.append(copy_file(source, destination_dir / source.name))
    return copied


def main() -> None:
    qa = json.loads((EVALUATION / "QA_REPORT.json").read_text(encoding="utf-8"))
    if qa.get("status") != "PASS":
        raise RuntimeError("Only a QA-passed benchmark can be copied into Final_Data_Figures")
    TARGET.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []

    copied += copy_glob(EVALUATION / "figures_matlab", "*.png", TARGET / "figures")
    copied += copy_glob(EVALUATION / "images", "*_scale_bar.png", TARGET / "images" / "scale_bar")
    copied += copy_glob(EVALUATION / "images", "*_native.png", TARGET / "images" / "native_intensity")
    copied += copy_glob(EVALUATION / "images", "*.csv", TARGET / "tables" / "image_intensity_audit")
    copied += copy_glob(EVALUATION / "images", "*.json", TARGET / "tables" / "image_intensity_audit")
    copied += copy_glob(EVALUATION / "via_reference", "*_overlay_crop.png", TARGET / "images" / "via_reference")
    copied += copy_glob(EVALUATION / "via_reference", "*.csv", TARGET / "tables" / "via_reference")
    copied += copy_glob(EVALUATION / "circular_cd_sharpness", "*.csv", TARGET / "tables" / "circular_cd_sharpness")
    copied += copy_glob(EVALUATION / "displacement", "*.csv", TARGET / "tables" / "displacement")
    copied += copy_glob(EVALUATION / "line" / "tables", "*.csv", TARGET / "tables" / "line")
    copied += copy_glob(EVALUATION / "runtime", "*.csv", TARGET / "tables" / "runtime")
    copied += copy_glob(EVALUATION / "runtime", "*.json", TARGET / "tables" / "runtime")

    for name in (
        "RESULTS_REPORT_ZH_TW.md",
        "QA_REPORT.json",
        "artifact_sha256.csv",
        "thesis_result_overview.csv",
    ):
        copied.append(copy_file(EVALUATION / name, TARGET / name))
    copied.append(copy_file(EXPERIMENT / "evaluation_manifest.json", TARGET / "source_manifest.json"))
    copied.append(
        copy_file(
            EVALUATION / "via_reference" / "via_center9_reference.json",
            TARGET / "tables" / "via_reference" / "via_center9_reference.json",
        )
    )

    training_files = {
        "base_unet_training_summary.json": (
            EXPERIMENT.parent
            / "BaseUNet_Baseline_20260718"
            / "results_full_data_fixed_psf_tiled_e30"
            / "training_summary.json"
        ),
        "nafnet_training_summary.json": EXPERIMENT / "results" / "nafnet" / "training_summary.json",
        "edsr_training_summary.json": EXPERIMENT / "results" / "edsr" / "training_summary.json",
        "nafnet_training_history.csv": EXPERIMENT / "results" / "nafnet" / "training_history.csv",
        "edsr_training_history.csv": EXPERIMENT / "results" / "edsr" / "training_history.csv",
        "nafnet_run_manifest.json": EXPERIMENT / "results" / "nafnet" / "run_manifest.json",
        "edsr_run_manifest.json": EXPERIMENT / "results" / "edsr" / "run_manifest.json",
    }
    for destination_name, source in training_files.items():
        copied.append(copy_file(source, TARGET / "training" / destination_name))

    scripts = (
        "models_modern.py",
        "train_modern_baseline.py",
        "infer_modern_baseline.py",
        "prepare_via_reference.py",
        "analyze_circular_cd_sharpness.py",
        "analyze_multimethod_displacement.py",
        "analyze_line_multimethod.py",
        "benchmark_models.py",
        "export_method_crops.py",
        "plot_benchmark_results.m",
        "validate_final_benchmark.py",
        "build_result_report.py",
    )
    for name in scripts:
        copied.append(copy_file(EXPERIMENT / name, TARGET / "source_scripts" / name))

    manifest = {
        "purpose": "Curated thesis figures and tables for the three-morphology modern baseline benchmark",
        "source_experiment": str(EXPERIMENT),
        "qa_status": qa["status"],
        "methods": ["Raw", "Base U-Net", "NAFNet", "EDSR", "MOSR"],
        "morphologies": ["pillar", "via", "line"],
        "claim_scope": (
            "Cross-morphology measurement transfer on the same HS-100MG sample and microscope; "
            "not cross-sample or cross-system generalization"
        ),
        "copied_file_count": len(copied),
        "copied_files": [str(path.relative_to(TARGET)) for path in copied],
        "large_reconstruction_source": {
            "nafnet": str(EXPERIMENT / "results" / "nafnet" / "real_inference" / "sequences"),
            "edsr": str(EXPERIMENT / "results" / "edsr" / "real_inference" / "sequences"),
            "note": "Full reconstructed sequences remain in the experiment folder to avoid duplicating large data.",
        },
    }
    (TARGET / "PACKAGE_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    readme = """# 三形貌現代模型比較成果

此資料夾保存可直接用於論文的單張英文圖、原生灰階影像、數值表與完整結果報告。

- `figures`：MATLAB 產生的正式英文圖。
- `images/scale_bar`：各方法的單張影像，保留原生灰階並加正確比例尺。
- `images/native_intensity`：完全未調整對比的原生灰階裁切。
- `tables`：pillar、via、line、位移與速度的明細及摘要。
- `RESULTS_REPORT_ZH_TW.md`：結果解讀與教授意見的補強程度。
- `QA_REPORT.json`：正式檢查結果。

大型 NAFNet 與 EDSR 完整序列不重複複製；其來源位置記錄在 `PACKAGE_MANIFEST.json`。
"""
    (TARGET / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
