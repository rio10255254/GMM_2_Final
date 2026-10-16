from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ANALYSIS_ROOT = Path(r"D:\GMM_2_Final\20260704_20x_5x_analysis")
PREPARE_SCRIPT = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R61_BoundaryGeneralizationUniversal\scripts\prepare_real_sample_gmf_package.py"
)
WEIGHTS = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Traing_Progress\training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_full_e8_20260623_20260623_200020\weights\best_tradeoff.pth.tar"
)
GROUPS = ["20x_0p5um", "20x_1um", "5x_0p5um", "5x_1um"]


def main() -> None:
    results = []
    for group in GROUPS:
        case_name = f"r61_v16_psfoff_{group}"
        command = [
            sys.executable,
            str(PREPARE_SCRIPT),
            "--package-root",
            str(ANALYSIS_ROOT),
            "--weights",
            str(WEIGHTS),
            "--input-dir",
            str(ANALYSIS_ROOT / "raw_inputs" / group / "bmp"),
            "--recon-root",
            str(ANALYSIS_ROOT / "reconstructions"),
            "--case-name",
            case_name,
            "--role",
            "r61_v16_psfoff",
            "--device",
            "cuda:0",
            "--note",
            f"R61 v16 PSF-off reconstruction for 20260704 {group}.",
        ]
        print(f"RUN {case_name}", flush=True)
        proc = subprocess.run(command, text=True, capture_output=True)
        log_path = ANALYSIS_ROOT / f"{case_name}_prepare_stdout.log"
        log_path.write_text(proc.stdout + "\nSTDERR:\n" + proc.stderr, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            raise RuntimeError(f"{case_name} failed with code {proc.returncode}; see {log_path}")
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            result = {"case_name": case_name, "stdout_log": str(log_path)}
        result["prepare_stdout_log"] = str(log_path)
        results.append(result)

    summary_path = ANALYSIS_ROOT / "r61_v16_reconstruction_summary.json"
    summary_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {summary_path}")
    for result in results:
        print(f"{result.get('case', {}).get('case', result.get('case_name'))}: {result.get('bmp_count')} BMP")


if __name__ == "__main__":
    main()
