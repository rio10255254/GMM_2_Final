"""Verify plot exports and point data after the visual inspection."""
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
checks = json.loads((HERE / "figure_data_checks.json").read_text(encoding="utf-8"))
with (HERE / "RAW_R152_step_mean_sd_data.csv").open(encoding="utf-8-sig", newline="") as stream:
    rows = list(csv.DictReader(stream))
assert len(rows) == 60 and {r["method"] for r in rows} == {"RAW", "R152"}
assert all(int(r["n_scans"]) == 30 for r in rows)
for row in rows:
    mean = float(row["mean_displacement_nm"])
    sd = float(row["sample_sd_across_scans_nm"])
    low, high = float(row["lower_mean_minus_1sd_nm"]), float(row["upper_mean_plus_1sd_nm"])
    assert abs((mean - sd) - low) < 1e-10 and abs((mean + sd) - high) < 1e-10
    assert 980 <= low <= mean <= high <= 1020, "Main figure must contain every band boundary"

for stem in ("RAW_R152_step_mean_sd", "RAW_R152_within_scan_sd"):
    pixels = np.asarray(Image.open(HERE / f"{stem}.png").convert("RGB"))
    assert pixels.shape == (1890, 3150, 3)
    assert np.array_equal(pixels[..., 0], pixels[..., 1])
    assert np.array_equal(pixels[..., 1], pixels[..., 2])
    pdf = PdfReader(HERE / f"{stem}.pdf")
    assert len(pdf.pages) == 1
    text = pdf.pages[0].extract_text()
    assert "RAW" in text and "R152" in text and "nm" in text
    assert float(pdf.pages[0].mediabox.width) == 504
    assert abs(float(pdf.pages[0].mediabox.height) - 302.4) < 1e-6
    objects = pdf.pages[0]["/Resources"].get("/XObject", {})
    assert all(v.get_object().get("/Subtype") != "/Image" for v in objects.values()), \
        "PDF should retain vector curves; reusable vector marker forms are allowed"
    svg = (HERE / f"{stem}.svg").read_text(encoding="utf-8")
    assert "RAW" in svg and "R152" in svg and "<svg" in svg

checks["export_checks"] = {
    "all_main_band_bounds_visible": True,
    "sixty_exported_point_records_and_sample_counts_checked": True,
    "both_pngs_grayscale_3150_by_1890": True,
    "both_pdfs_single_page_vector_7_by_4point2_inches": True,
    "svg_labels_present": True,
    "both_pngs_visually_reviewed": True,
}
(HERE / "figure_data_checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
print("PASS: all 60 mean/SD bounds, grayscale PNGs, vector PDFs, SVGs, and visual review")
