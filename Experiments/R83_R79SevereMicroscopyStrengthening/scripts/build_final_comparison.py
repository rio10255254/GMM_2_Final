"""Build an auditable R74 before/direct/safe/label comparison figure."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "results" / "final_confirmation" / "development_recheck" / "R74_hard_microscopy"
OUTPUT = ROOT / "reports" / "figures" / "r83_final_r74_comparison.png"


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image


def main() -> int:
    manifest = json.loads((SUITE / "results" / "inference_manifest.json").read_text(encoding="utf-8"))
    config = json.loads((SUITE / "config" / "experiment.json").read_text(encoding="utf-8"))
    table = pd.read_csv(SUITE / "results" / "tables" / "primary_contour_metrics.csv")
    table = table.loc[(table["alignment"] == "translation_only") & table["method"].isin(["R79", "R83Safe"])]
    pivot = table.pivot(index=["family", "filename"], columns="method", values="mean_boundary_distance_px").reset_index()
    pivot["improvement"] = pivot["R79"] - pivot["R83Safe"]
    chosen = pivot.sort_values(["family", "improvement"], ascending=[True, False]).groupby("family", as_index=False).first()
    family_order = [row["name"] for row in config["dataset"]["families"]]
    chosen["order"] = chosen["family"].map({name: i for i, name in enumerate(family_order)})
    chosen = chosen.sort_values("order")

    cell = 320
    header = 54
    row_label = 44
    columns = ["Raw input", "R79 direct", "R83 safe", "Clean label"]
    canvas = np.full((header + len(chosen) * (cell + row_label), cell * 4, 3), 245, np.uint8)
    for col, title in enumerate(columns):
        cv2.putText(canvas, title, (col * cell + 18, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.82, (20, 20, 20), 2, cv2.LINE_AA)

    dataset_root = Path(PROJECT_ROOT / config["dataset"]["root"])
    for row_index, row in enumerate(chosen.itertuples(index=False)):
        family = str(row.family)
        filename = str(row.filename)
        stage = next(item["stage"] for item in config["dataset"]["families"] if item["name"] == family)
        paths = [
            Path(manifest["output_dirs"]["Raw"][family]) / filename,
            Path(manifest["output_dirs"]["R79"][family]) / filename,
            Path(manifest["output_dirs"]["R83Safe"][family]) / filename,
            dataset_root / "lbl" / stage / filename,
        ]
        y0 = header + row_index * (cell + row_label)
        for col, path in enumerate(paths):
            image = cv2.resize(read_gray(path), (cell, cell), interpolation=cv2.INTER_NEAREST)
            canvas[y0:y0 + cell, col * cell:(col + 1) * cell] = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        caption = f"{family} / {filename}    ACM boundary: R79 {row.R79:.2f}px  ->  safe {row.R83Safe:.2f}px"
        cv2.putText(canvas, caption, (14, y0 + cell + 29), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (25, 25, 25), 1, cv2.LINE_AA)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", canvas)
    if not ok:
        raise OSError(OUTPUT)
    encoded.tofile(OUTPUT)
    selection = chosen[["family", "filename", "R79", "R83Safe", "improvement"]]
    selection.to_csv(OUTPUT.with_suffix(".csv"), index=False)
    print(OUTPUT)
    print(selection.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
