"""σ̂ + b decomposition from external GMF position sequences.

Verifies thesis main claim C1+C2:
- C1: σ̂ (random component) decreases from R30 -> COMBO across the training history
- C2: b (systematic component) is structured (non-trivial lag-1 autocorr of step - s*)

Outputs:
- results/sigma_b_table.csv
- prints per-candidate summary to stdout

This first-pass script does not draw plots; once numbers look sane,
extend to include trend plots and lag-1 panels.
"""

from __future__ import annotations

import csv
from pathlib import Path
import numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(str(PROJECT_ROOT))
OUT_ROOT = ROOT / "Thesis_MOSR_Evidence/error_type_transformation/sigma_hat_decomposition"


CANDIDATES = [
    {
        "tag": "R30",
        "model": "r30_b1_dironly",
        "role": "Former baseline (starting point)",
        "paths": {
            "8px": ROOT / "Experiments/Legacy/organized_20260316/round30/gmf_results/raw/r30_b1_dironly/pitch8px/GMF_score.txt",
            "0p8px": ROOT / "Experiments/Legacy/organized_20260316/round30/gmf_results/raw/r30_b1_dironly/pitch0p8px/GMF_score.txt",
            "0p08px": ROOT / "Experiments/Legacy/organized_20260316/round30/gmf_results/raw/r30_b1_dironly/pitch0p08px/GMF_score.txt",
        },
    },
    {
        "tag": "R33",
        "model": "r33_robust_p95",
        "role": "GMF extreme alternate (visual soft)",
        "paths": {
            "8px": ROOT / "Experiments/R33RobustLoss/results/external_gmf/pitch8px/GMF_score.txt",
            "0p8px": ROOT / "Experiments/R33RobustLoss/results/external_gmf/pitch0p8px/GMF_score.txt",
            "0p08px": ROOT / "Experiments/R33RobustLoss/results/external_gmf/pitch0p08px/GMF_score.txt",
        },
    },
    {
        "tag": "R38v2",
        "model": "r38v2_8px_gate",
        "role": "Visual priority alternate",
        "paths": {
            "8px": ROOT / "Experiments/R38v2SeqFixed/results/external_gmf/pitch8px/GMF_score.txt",
            "0p8px": ROOT / "Experiments/R38v2SeqFixed/results/external_gmf/pitch0p8px/GMF_score.txt",
            "0p08px": ROOT / "Experiments/R38v2SeqFixed/results/external_gmf/pitch0p08px/GMF_score.txt",
        },
    },
    {
        "tag": "COMBO",
        "model": "r38v2_8px_gate_p95",
        "role": "Formal baseline (most balanced)",
        "paths": {
            "8px": ROOT / "Experiments/R38v2SeqFixed/results/external_gmf_combo/pitch8px/GMF_score.txt",
            "0p8px": ROOT / "Experiments/R38v2SeqFixed/results/external_gmf_combo/pitch0p8px/GMF_score.txt",
            "0p08px": ROOT / "Experiments/R38v2SeqFixed/results/external_gmf_combo/pitch0p08px/GMF_score.txt",
        },
    },
    {
        "tag": "a030",
        "model": "r39_combo_strong_avg_a030",
        "role": "Shape generalization alternate-grade pending",
        "paths": {
            "8px": ROOT / "Experiments/R39_ShapeGeneralization/results/external_gmf_a030/pitch8px/GMF_score.txt",
            "0p8px": ROOT / "Experiments/R39_ShapeGeneralization/results/external_gmf_a030/pitch0p8px/GMF_score.txt",
            "0p08px": ROOT / "Experiments/R39_ShapeGeneralization/results/external_gmf_a030/pitch0p08px/GMF_score.txt",
        },
    },
    {
        "tag": "a025",
        "model": "r39r40_complementary_avg_a025",
        "role": "Balanced full-spectrum approved alternate (2026-05-11)",
        "paths": {
            "8px": ROOT / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a025/external_gmf/pitch8px/GMF_score.txt",
            "0p8px": ROOT / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a025/external_gmf/pitch0p8px/GMF_score.txt",
            "0p08px": ROOT / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a025/external_gmf/pitch0p08px/GMF_score.txt",
        },
    },
    {
        "tag": "R40_a045",
        "model": "r40_combo_best_avg_a045",
        "role": "Microscopy capacity research-only",
        "paths": {
            "8px": ROOT / "Experiments/R40_MicroscopyFeatureCoverage/results/external_gmf/pitch8px/GMF_score.txt",
            "0p8px": ROOT / "Experiments/R40_MicroscopyFeatureCoverage/results/external_gmf/pitch0p8px/GMF_score.txt",
            "0p08px": ROOT / "Experiments/R40_MicroscopyFeatureCoverage/results/external_gmf/pitch0p08px/GMF_score.txt",
        },
    },
    {
        "tag": "R42_r41best",
        "model": "r42_r41_best",
        "role": "Boundary fidelity research-only (R42 best external)",
        "paths": {
            "8px": ROOT / "Experiments/R42_MicroscopyBoundaryFidelity/results/external_gmf/r42_r41_best/pitch8px/GMF_score.txt",
            "0p8px": ROOT / "Experiments/R42_MicroscopyBoundaryFidelity/results/external_gmf/r42_r41_best/pitch0p8px/GMF_score.txt",
            "0p08px": ROOT / "Experiments/R42_MicroscopyBoundaryFidelity/results/external_gmf/r42_r41_best/pitch0p08px/GMF_score.txt",
        },
    },
    {
        "tag": "R46",
        "model": "r46_a025_corner_finetune",
        "role": "Corner-aware research-only (ring guard FAIL)",
        "paths": {
            "8px": ROOT / "Experiments/R46_CornerAwareFineTune/results/external_gmf/pitch8px/GMF_score.txt",
            "0p8px": ROOT / "Experiments/R46_CornerAwareFineTune/results/external_gmf/pitch0p8px/GMF_score.txt",
            "0p08px": ROOT / "Experiments/R46_CornerAwareFineTune/results/external_gmf/pitch0p08px/GMF_score.txt",
        },
    },
    # ===== 4 method-component ablations (paths predefined; populated after =====
    # ===== external GMF tool runs against _ablation_recon BMPs)         =====
    {
        "tag": "ABLA_NO_SEQ",
        "model": "r38v2_8px_gate_p95_ABLA_NO_SEQ",
        "role": "Ablation A: SEQ_ENABLE=False (4.6 causal evidence)",
        "paths": {
            "8px": ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_external_gmf/NO_SEQ/pitch8px/GMF_score.txt",
            "0p8px": ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_external_gmf/NO_SEQ/pitch0p8px/GMF_score.txt",
            "0p08px": ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_external_gmf/NO_SEQ/pitch0p08px/GMF_score.txt",
        },
    },
    {
        "tag": "ABLA_NO_EQ",
        "model": "r38v2_8px_gate_p95_ABLA_NO_EQ",
        "role": "Ablation B1: EQ_PROB=0 (4.5.1 causal evidence)",
        "paths": {
            "8px": ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_external_gmf/NO_EQ/pitch8px/GMF_score.txt",
            "0p8px": ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_external_gmf/NO_EQ/pitch0p8px/GMF_score.txt",
            "0p08px": ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_external_gmf/NO_EQ/pitch0p08px/GMF_score.txt",
        },
    },
    {
        "tag": "ABLA_NO_EDGE",
        "model": "r38v2_8px_gate_p95_ABLA_NO_EDGE",
        "role": "Ablation B2: W_GRADMAG=W_EDGE_ORI_SIMPLE=W_EDGELOCAL_LAP=0 (4.5.3 causal evidence)",
        "paths": {
            "8px": ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_external_gmf/NO_EDGE/pitch8px/GMF_score.txt",
            "0p8px": ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_external_gmf/NO_EDGE/pitch0p8px/GMF_score.txt",
            "0p08px": ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_external_gmf/NO_EDGE/pitch0p08px/GMF_score.txt",
        },
    },
    {
        "tag": "ABLA_NO_FREQ",
        "model": "r38v2_8px_gate_p95_ABLA_NO_FREQ",
        "role": "Ablation B3: W_HF_LAP=0, FFT_W_PHASE=0 (4.5.2 causal evidence)",
        "paths": {
            "8px": ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_external_gmf/NO_FREQ/pitch8px/GMF_score.txt",
            "0p8px": ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_external_gmf/NO_FREQ/pitch0p8px/GMF_score.txt",
            "0p08px": ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_external_gmf/NO_FREQ/pitch0p08px/GMF_score.txt",
        },
    },
]


EXPECTED_STEP_PX = {"8px": 8.0, "0p8px": 0.8, "0p08px": 0.08}


def parse_gmf_score(path: Path):
    """Parse GMF_score.txt with comma-separated key/value pairs per line.

    Returns (PosX array, PosY array). Both are numpy arrays of float.
    """
    xs, ys = [], []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            kv = {}
            for i in range(0, len(parts) - 1, 2):
                kv[parts[i]] = parts[i + 1]
            if "PosX" not in kv or "PosY" not in kv:
                continue
            xs.append(float(kv["PosX"]))
            ys.append(float(kv["PosY"]))
    return np.asarray(xs), np.asarray(ys)


def decompose(pos_y: np.ndarray, expected_step: float) -> dict:
    """Decompose step sequence into mu_hat, sigma_hat, b, lag1 autocorr.

    Calibrated against existing r39_external_compare.py:
    - sigma_hat = np.std(np.diff(PosY))  (no abs; population std with ddof=0 to
      match existing `_stddev_pop` used in r39_external_compare).
    - signed_step retains direction so that lag-1 autocorr reflects true
      sequential structure, not artifacts from abs() flipping negative noise.
    - PosY sequence is typically monotonic decreasing (median_step < 0),
      so |median_step| ~ expected_step. b is computed against the absolute
      magnitude of the median step to keep direction-independent.
    """
    steps_raw = np.diff(pos_y)  # signed, no abs
    n_steps_raw = len(steps_raw)
    if n_steps_raw < 2:
        return {
            "n_steps": n_steps_raw,
            "mu_hat": float("nan"),
            "sigma_hat": float("nan"),
            "expected_step": expected_step,
            "b": float("nan"),
            "b_pct": float("nan"),
            "lag1_autocorr_centered": float("nan"),
        }
    # Filter |z|>5 GMF failure outliers (consistent with existing
    # r39_external_compare.py / PROJECT_STATE methodology). Z is computed
    # against the median to be robust to the outliers themselves.
    raw_std = float(np.std(steps_raw, ddof=0))
    median_raw = float(np.median(steps_raw))
    if raw_std > 0:
        z = (steps_raw - median_raw) / raw_std
        mask = np.abs(z) <= 5
    else:
        mask = np.ones_like(steps_raw, dtype=bool)
    steps = steps_raw[mask]
    n_outliers = int((~mask).sum())
    n_steps = len(steps)
    sigma_hat = float(np.std(steps, ddof=0))
    median_step = float(np.median(steps))
    mu_hat = float(np.mean(steps))
    # bias: |median_step| - expected_step  (direction-independent comparison)
    b = abs(median_step) - expected_step
    # lag-1 autocorr of (step - median_step), measuring structure beyond
    # the systematic offset (this is what C2 actually wants to detect)
    centered = steps - median_step
    a, c = centered[:-1], centered[1:]
    if np.std(a) > 1e-12 and np.std(c) > 1e-12:
        lag1 = float(np.corrcoef(a, c)[0, 1])
    else:
        lag1 = 0.0
    return {
        "n_steps": n_steps,
        "n_outliers": n_outliers,
        "mu_hat": mu_hat,
        "median_step": median_step,
        "sigma_hat": sigma_hat,
        "raw_std": raw_std,
        "expected_step": expected_step,
        "b": b,
        "b_pct": (b / expected_step) * 100.0,
        "lag1_autocorr_centered": lag1,
    }


def main():
    rows = []
    print(f"{'tag':<6} {'scale':<7} {'n':>4} {'noutl':>5} {'median':>10} {'sigma_hat':>10} {'b':>10} {'b_pct':>8} {'lag1':>7}")
    print("-" * 78)
    for cand in CANDIDATES:
        for scale, path in cand["paths"].items():
            row_base = {"tag": cand["tag"], "model": cand["model"], "scale": scale}
            if not path.exists():
                print(f"[WARN] missing: {cand['tag']:<6} {scale:<7} -> {path}")
                rows.append({**row_base, "status": "MISSING_DATA"})
                continue
            try:
                _, pos_y = parse_gmf_score(path)
            except Exception as e:
                print(f"[ERR ] parse {cand['tag']:<6} {scale:<7}: {e}")
                rows.append({**row_base, "status": f"PARSE_ERROR:{e}"})
                continue
            stats = decompose(pos_y, EXPECTED_STEP_PX[scale])
            print(
                f"{cand['tag']:<6} {scale:<7} {stats['n_steps']:>4d} "
                f"{stats['n_outliers']:>5d} "
                f"{stats['median_step']:>+10.4f} {stats['sigma_hat']:>10.4f} "
                f"{stats['b']:>+10.4f} {stats['b_pct']:>+7.2f}% "
                f"{stats['lag1_autocorr_centered']:>+7.3f}"
            )
            rows.append({**row_base, "status": "OK", **stats})

    out_csv = OUT_ROOT / "results" / "sigma_b_table.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "tag", "model", "scale", "status",
        "n_steps", "n_outliers", "expected_step",
        "mu_hat", "median_step", "sigma_hat", "raw_std", "b", "b_pct",
        "lag1_autocorr_centered",
    ]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"\nwrote {out_csv}")


if __name__ == "__main__":
    main()
