"""step0_setup.py — 建立輸出目錄並複製精選圖表與資料"""
import shutil
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[5]

PKG        = Path(str(PROJECT_ROOT / 'Deliverables/Company_Packages/GeoEdge_R26_使用包'))
DEST       = PKG / "輸出結果" / "驗證分析" / "R26_validation_complete"
SRC_SINGLE = PKG / "輸出結果" / "驗證分析" / "R26_external_single_bundle"
SRC_BATCH  = PKG / "輸出結果" / "驗證分析" / "R26_external_batch_bundle"

(DEST / "figures").mkdir(parents=True, exist_ok=True)
(DEST / "data").mkdir(parents=True, exist_ok=True)

# 複製精選圖表（既有）
copies = [
    (SRC_BATCH  / "batch_contact_sheet.png",          DEST / "figures" / "01_batch_contact_sheet.png"),
    (SRC_SINGLE / "histogram_comparison.png",          DEST / "figures" / "06_histogram_comparison.png"),
    (SRC_SINGLE / "frequency_spectrum_comparison.png", DEST / "figures" / "07_frequency_spectrum.png"),
    (SRC_SINGLE / "ssim_analysis.png",                 DEST / "figures" / "08_ssim_map.png"),
    (SRC_SINGLE / "mtf_comparison.png",                DEST / "figures" / "09_mtf_comparison.png"),
    (SRC_SINGLE / "difference_spatial_analysis.png",   DEST / "figures" / "10_difference_spatial_analysis.png"),
]
for src, dst in copies:
    shutil.copy2(src, dst)
    print(f"copied: {dst.name}")

# 複製資料檔
data_copies = [
    (SRC_BATCH  / "batch_metrics.csv",         DEST / "data" / "batch_metrics.csv"),
    (SRC_BATCH  / "batch_summary.json",         DEST / "data" / "batch_summary.json"),
    (SRC_SINGLE / "basic_metrics.json",         DEST / "data" / "basic_metrics.json"),
    (SRC_SINGLE / "input_integrity_check.json", DEST / "data" / "input_integrity_check.json"),
]
for src, dst in data_copies:
    shutil.copy2(src, dst)
    print(f"copied: {dst.name}")

print("Task 0 完成")
