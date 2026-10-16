"""Sanity-check the 12 ablation GMF_score.txt files (4 ablations x 3 pitches).

Reports: which exist, which are missing, and whether each existing file
parses correctly (right number of rows + parseable PosX/PosY columns).

Once all 12 exist and parse, this script triggers a small reminder
of what to invoke next:
    1. python sigma_hat_decomposition/scripts/decompose_sigma_b.py
    2. python sigma_hat_decomposition/scripts/make_plots.py
    3. (manual) write ablation_external_gmf_verdict.md

Usage:
    python Thesis_MOSR_Evidence/method_ablations/check_ablation_gmf_ready.py
"""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
EXT_GMF_ROOT = REPO_ROOT / "Thesis_MOSR_Evidence/method_ablations/_ablation_external_gmf"

EXPECTED = [
    # (tag, pitch, expected_n_rows)
    # GMF tool outputs N-1 rows from N BMPs (matches existing R30/R33/COMBO format).
    ("NO_SEQ",  "pitch8px",  100),
    ("NO_SEQ",  "pitch0p8px", 60),
    ("NO_SEQ",  "pitch0p08px", 40),
    ("NO_EQ",   "pitch8px",  100),
    ("NO_EQ",   "pitch0p8px", 60),
    ("NO_EQ",   "pitch0p08px", 40),
    ("NO_EDGE", "pitch8px",  100),
    ("NO_EDGE", "pitch0p8px", 60),
    ("NO_EDGE", "pitch0p08px", 40),
    ("NO_FREQ", "pitch8px",  100),
    ("NO_FREQ", "pitch0p8px", 60),
    ("NO_FREQ", "pitch0p08px", 40),
]


def parse_gmf_score(path: Path) -> tuple[int, bool]:
    """Return (n_rows, has_PosY)."""
    n_rows = 0
    has_pos = True
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n_rows += 1
            parts = [p.strip() for p in line.split(",")]
            kv = {}
            for i in range(0, len(parts) - 1, 2):
                kv[parts[i]] = parts[i + 1]
            if "PosY" not in kv or "PosX" not in kv:
                has_pos = False
    return n_rows, has_pos


def main():
    print(f"\n{'='*70}")
    print(f"Checking 12 ablation GMF_score.txt under {EXT_GMF_ROOT}")
    print(f"{'='*70}")

    n_ok = n_missing = n_bad = 0
    print(f"\n{'tag':<10} {'pitch':<12} {'status':<10} {'n_rows':>7} {'expected':>9}")
    print("-" * 60)
    for tag, pitch, expected_n in EXPECTED:
        path = EXT_GMF_ROOT / tag / pitch / "GMF_score.txt"
        if not path.exists():
            print(f"{tag:<10} {pitch:<12} {'MISSING':<10} {'-':>7} {expected_n:>9}")
            n_missing += 1
            continue
        try:
            n_rows, has_pos = parse_gmf_score(path)
        except Exception as e:
            print(f"{tag:<10} {pitch:<12} {'PARSE_ERR':<10} {str(e)[:30]}")
            n_bad += 1
            continue
        if not has_pos:
            print(f"{tag:<10} {pitch:<12} {'NO_POS':<10} {n_rows:>7} {expected_n:>9}  <- missing PosX/PosY")
            n_bad += 1
        elif n_rows != expected_n:
            print(f"{tag:<10} {pitch:<12} {'ROW_DIFF':<10} {n_rows:>7} {expected_n:>9}  <- row count mismatch")
            n_bad += 1
        else:
            print(f"{tag:<10} {pitch:<12} {'OK':<10} {n_rows:>7} {expected_n:>9}")
            n_ok += 1

    print(f"\n{'='*70}")
    print(f"Summary:  OK={n_ok}  MISSING={n_missing}  BAD={n_bad}  (total={len(EXPECTED)})")
    print(f"{'='*70}")

    if n_ok == len(EXPECTED):
        print(f"\nAll 12 ready. Next steps:")
        print(f"  1. /c/Users/Rio/anaconda3/envs/myenv/python.exe \\")
        print(f"        Thesis_MOSR_Evidence/error_type_transformation/sigma_hat_decomposition/scripts/decompose_sigma_b.py")
        print(f"  2. /c/Users/Rio/anaconda3/envs/myenv/python.exe \\")
        print(f"        Thesis_MOSR_Evidence/error_type_transformation/sigma_hat_decomposition/scripts/make_plots.py")
        print(f"  3. (Claude) write reports/ablation_external_gmf_verdict.md")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
