"""Generate a trade-off PNG for the R39 weight averaging sweep."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SUMMARY_JSON = (
    _REPO_ROOT
    / "Experiments"
    / "R39_ShapeGeneralization"
    / "results"
    / "weight_sweep"
    / "sweep_summary.json"
)


def plot(summary_json: Path, output_png: Path) -> None:
    payload = json.loads(summary_json.read_text(encoding="utf-8"))
    rows = payload["rows"]
    alphas = [r["alpha"] for r in rows]
    psnr = [r["shape_overall_psnr"] for r in rows]
    s8 = [r["ring_8px_step_std"] for r in rows]
    s08 = [r["ring_0p8px_step_std"] for r in rows]
    s008 = [r["ring_0p08px_step_std"] for r in rows]

    thr = payload["thresholds"]
    verdict = payload["verdict"]

    fig, (ax_shape, ax_ring) = plt.subplots(1, 2, figsize=(13, 5), sharex=True)

    ax_shape.plot(alphas, psnr, "o-", color="#1f77b4", label="shape_val_unseen PSNR")
    ax_shape.axhline(thr["min_shape_psnr"], color="#1f77b4", linestyle=":", alpha=0.5,
                     label=f"min PSNR cap = {thr['min_shape_psnr']}")
    ax_shape.set_xlabel("alpha (0=COMBO, 1=R39_strong)")
    ax_shape.set_ylabel("shape PSNR")
    ax_shape.set_title("Shape generalization (held-out)")
    ax_shape.grid(True, alpha=0.3)
    ax_shape.legend(loc="lower right")

    ax_ring.plot(alphas, s8, "o-", label="8px step_std", color="#d62728")
    ax_ring.plot(alphas, s08, "s-", label="0.8px step_std", color="#2ca02c")
    ax_ring.plot(alphas, s008, "^-", label="0.08px step_std", color="#9467bd")
    ax_ring.axhline(thr["max_8px"], color="#d62728", linestyle=":", alpha=0.5,
                    label=f"8px cap = {thr['max_8px']}")
    ax_ring.axhline(thr["max_0p8px"], color="#2ca02c", linestyle=":", alpha=0.5,
                    label=f"0.8px cap = {thr['max_0p8px']}")
    ax_ring.axhline(thr["max_0p08px"], color="#9467bd", linestyle=":", alpha=0.5,
                    label=f"0.08px cap = {thr['max_0p08px']}")
    ax_ring.set_xlabel("alpha (0=COMBO, 1=R39_strong)")
    ax_ring.set_ylabel("local ring step_std")
    ax_ring.set_title("Local ring guard (lower is better)")
    ax_ring.grid(True, alpha=0.3)
    ax_ring.legend(loc="upper left", fontsize=8)

    if verdict.get("found") and verdict.get("best") is not None:
        a_best = verdict["best"]["alpha"]
        for ax in (ax_shape, ax_ring):
            ax.axvline(a_best, color="orange", linestyle="--", alpha=0.6)
        fig.suptitle(
            f"R39 weight averaging sweep — sweet spot at α={a_best:.2f}",
            fontsize=12,
        )
    else:
        fig.suptitle(
            "R39 weight averaging sweep — no alpha satisfies all caps",
            fontsize=12,
        )

    fig.tight_layout()
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_png, dpi=140)
    plt.close(fig)
    print(f"[plot] wrote {output_png}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plot R39 weight sweep trade-off")
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--output-png", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.output_png is None:
        args.output_png = args.summary_json.parent / "sweep_tradeoff.png"
    plot(args.summary_json, args.output_png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
