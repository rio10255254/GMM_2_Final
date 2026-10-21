"""Check that the readable reassessment table matches its unrounded result."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
report = (HERE / "WITHIN_SCAN_30_STEP_16_MODEL_REASSESSMENT.md").read_text(encoding="utf-8")
data = json.loads((HERE / "summary.json").read_text(encoding="utf-8"))

rows = [line.split("|")[1:-1] for line in report.splitlines() if re.match(r"^\| \d+ \|", line)]
assert len(rows) == data["models"] == 16
assert data["scans"] == 30 and data["adjacent_rows"] == 16 * 30 * 30
for rank, (cells, source) in enumerate(zip(rows, data["ranked_summary"]), 1):
    cells = [cell.strip().replace("**", "") for cell in cells]
    assert int(cells[0]) == source["point_rank"] == rank
    assert cells[1] == source["display"]
    assert abs(float(cells[2]) - source["mean_scan_sd_nm"]) <= .0005
    assert abs(float(cells[3]) - source["pooled_within_scan_sd_nm"]) <= .0005
    low, high = map(float, cells[4].split("～"))
    assert abs(low - source["per_scan_sd_min_nm"]) <= .0005
    assert abs(high - source["per_scan_sd_max_nm"]) <= .0005
    if cells[5].endswith("%") and "約" not in cells[5]:
        assert abs(float(cells[5][:-1]) - source["raw_reduction_pooled_percent"]) <= .05
    if re.fullmatch(r"\d+/30", cells[6]):
        assert int(cells[6].split("/")[0]) == source["improved_scans_vs_raw"]

for target in re.findall(r"\]\(([^)]+)\)", report):
    assert (HERE / target).exists(), target

print(f"PASS: {len(rows)} rankings, numbers, run counts, and report links match sources")
