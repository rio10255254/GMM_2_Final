"""Run the unchanged full R73/R74 ACM protocol for the R116 shortlist."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "detailed_validation" / "01_locked_acm"
RUNNER = ROOT / "validation" / "run_locked_acm.py"
CANDIDATES = {
    24: ROOT / "runs" / "r116_formal_scratch_20260903_202052" / "weights" / "epoch_024.pth",
    28: ROOT / "runs" / "r116_formal_scratch_20260903_202052" / "weights" / "epoch_028.pth",
    40: ROOT / "runs" / "r116_formal_scratch_20260903_202052" / "weights" / "epoch_040.pth",
    42: ROOT / "runs" / "r116_formal_scratch_20260903_202052" / "failure_snapshot.pth",
    48: ROOT / "runs" / "r116_calibration_from_e42_20260903_235500" / "weights" / "epoch_048.pth",
}


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = []
    run_records = []
    for epoch, checkpoint in CANDIDATES.items():
        destination = OUTPUT / f"E{epoch:03d}"
        summary_path = destination / "analysis_summary.json"
        if not summary_path.is_file():
            command = [
                sys.executable, str(RUNNER),
                "--checkpoint", str(checkpoint),
                "--output", str(destination),
                "--method-name", f"R116E{epoch:03d}",
                "--suite", "R73", "R74",
                "--device", "cuda:0",
                "--tile-core", "768",
            ]
            completed = subprocess.run(
                command, cwd=ROOT, text=True, capture_output=True,
                encoding="utf-8", errors="replace",
            )
            (destination / "runner_stdout.log").write_text(completed.stdout, encoding="utf-8")
            (destination / "runner_stderr.log").write_text(completed.stderr, encoding="utf-8")
            if completed.returncode != 0:
                raise RuntimeError(
                    f"E{epoch:03d} locked ACM failed with code {completed.returncode}: "
                    f"{completed.stderr[-1200:]}"
                )
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("status") != "complete" or len(summary.get("results", [])) != 2:
            raise RuntimeError(f"E{epoch:03d} locked ACM summary is incomplete")
        for result in summary["results"]:
            audit = result["zero_failure_audit"]
            if audit["status"] != "pass" or any(audit["failure_counts"].values()):
                raise RuntimeError(f"E{epoch:03d} {result['suite']} failed zero-failure audit")
            rows.append({
                "epoch": epoch,
                "suite": result["suite"],
                "raw_iou": result["raw"]["iou"],
                "model_iou": result["model"]["iou"],
                "iou_delta": result["effect"]["overall_iou_delta"],
                "raw_boundary_px": result["raw"]["mean_boundary_distance_px"],
                "model_boundary_px": result["model"]["mean_boundary_distance_px"],
                "boundary_change_pct": result["effect"]["overall_boundary_change_pct"],
                "raw_hd95_px": result["raw"]["hd95_px"],
                "model_hd95_px": result["model"]["hd95_px"],
                "hd95_change_pct": result["effect"]["overall_hd95_change_pct"],
                "area_error_pct": result["model"]["area_error_pct"],
                "perimeter_error_pct": result["model"]["perimeter_error_pct"],
                "families_improved_boundary": sum(
                    row["boundary_change_pct"] < 0 for row in result["effect"]["families"]
                ),
                "families_total": len(result["effect"]["families"]),
                "zero_failures": True,
            })
        run_records.append({
            "epoch": epoch,
            "checkpoint": str(checkpoint),
            "output": str(destination),
            "status": "complete",
        })
        print(json.dumps({"epoch": epoch, "status": "complete"}), flush=True)
    with (OUTPUT / "shortlist_summary.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    payload = {
        "status": "complete",
        "protocol": "unchanged locked Chan-Vese ACM; translation-only primary comparison",
        "candidates": run_records,
        "rows": rows,
        "all_zero_failure": all(row["zero_failures"] for row in rows),
        "single_aggregate_score_used": False,
    }
    (OUTPUT / "shortlist_summary.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8",
    )
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
