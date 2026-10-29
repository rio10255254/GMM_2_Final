"""Run audited R103 validation protocols against R104 without changing the protocols."""
from __future__ import annotations

import argparse
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]


R103 = Path(str(PROJECT_ROOT / 'Experiments/R103_RecoverableDetailScratch/analysis'))
R104 = Path(__file__).resolve().parents[1]
ALLOWED = {
    "external_acm": "evaluate_external_acm.py",
    "sem_contour": "evaluate_sem_contour.py",
    "real_sequences": "evaluate_real_sequences.py",
    "large_tile_parity": "evaluate_large_frame_tile_parity.py",
}


def adapt(source: str) -> str:
    replacements = (
        ('from r103_model import build_model', 'from r104_model import build_model'),
        ('bounds["contour"]', 'bounds["contour_proposal"]'),
        ('bounds["texture"]', 'bounds["texture_proposal"]'),
        ('halo=128', 'halo=160'),
        ('R103', 'R104'),
        ('r103', 'r104'),
    )
    for old, new in replacements:
        source = source.replace(old, new)
    return source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("protocol", choices=tuple(ALLOWED))
    args = parser.parse_args()
    source_path = R103 / ALLOWED[args.protocol]
    source = adapt(source_path.read_text(encoding="utf-8"))
    virtual_path = R104 / "analysis" / ALLOWED[args.protocol]
    namespace = {"__file__": str(virtual_path), "__name__": "__main__", "__package__": None}
    exec(compile(source, str(virtual_path), "exec"), namespace)


if __name__ == "__main__":
    main()
