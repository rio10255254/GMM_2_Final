from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from analyze_isocontour_boundary_displacement import (
    MANIFEST_PATH,
    measure_feature,
    method_sequence_dir,
    read_gray,
)


EXPERIMENT = Path(__file__).resolve().parent
OUTPUT = (
    EXPERIMENT
    / "evaluation"
    / "isocontour_boundary_validation_20260724"
    / "qa_overlays"
)


def load_configs(path: Path, morphology: str) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))["sequences"]
    if morphology == "pillar":
        return payload
    converted: dict[str, dict] = {}
    for sequence_name, source in payload.items():
        item = dict(source)
        item["centers"] = [
            [index, center["x"], center["y"]]
            for index, center in enumerate(item["centers"], start=1)
        ]
        converted[sequence_name] = item
    return converted


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for morphology, config_key in (("pillar", "pillar_config"), ("via", "via_config")):
        configs = load_configs(Path(manifest[config_key]), morphology)
        for sequence_name in ("50x_x_0p5um", "20x_0p5um"):
            sequence = configs[sequence_name]
            raw_dir = Path(sequence["raw_dir"])
            centers = np.asarray(
                [[row[1], row[2]] for row in sequence["centers"]],
                dtype=float,
            )
            radius = float(sequence["radius_px"])
            for method in ("Raw", "EDSR", "MOSR"):
                directory = method_sequence_dir(
                    manifest,
                    method,
                    sequence_name,
                    raw_dir,
                )
                image = read_gray(directory / "frame_0000.bmp")
                rendered = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
                valid_count = 0
                for x_px, y_px in centers:
                    result = measure_feature(
                        image,
                        predicted_x_px=float(x_px),
                        predicted_y_px=float(y_px),
                        radius_px=radius,
                        search_radius_px=float(sequence["search_radius_px"]),
                    )
                    if not result.valid:
                        cv2.drawMarker(
                            rendered,
                            (round(x_px), round(y_px)),
                            (0, 0, 255),
                            cv2.MARKER_TILTED_CROSS,
                            12,
                            2,
                        )
                        continue
                    valid_count += 1
                    center_x = result.centers_by_level.get(0.50, result.x_px)
                    width = result.widths_by_level.get(0.50, 2.0 * radius)
                    left_x = center_x - 0.5 * width
                    right_x = center_x + 0.5 * width
                    y0 = round(y_px - 0.45 * radius)
                    y1 = round(y_px + 0.45 * radius)
                    cv2.line(
                        rendered,
                        (round(left_x), y0),
                        (round(left_x), y1),
                        (0, 255, 255),
                        1,
                    )
                    cv2.line(
                        rendered,
                        (round(right_x), y0),
                        (round(right_x), y1),
                        (0, 255, 255),
                        1,
                    )
                    cv2.line(
                        rendered,
                        (round(center_x), y0),
                        (round(center_x), y1),
                        (255, 255, 0),
                        1,
                    )

                margin = int(np.ceil(radius * 2.0))
                x0 = max(0, int(np.floor(centers[:, 0].min())) - margin)
                x1 = min(image.shape[1], int(np.ceil(centers[:, 0].max())) + margin)
                y0 = max(0, int(np.floor(centers[:, 1].min())) - margin)
                y1 = min(image.shape[0], int(np.ceil(centers[:, 1].max())) + margin)
                crop = rendered[y0:y1, x0:x1]
                label = (
                    f"{morphology} | {sequence['magnification']} | {method} | "
                    f"valid {valid_count}/9"
                )
                cv2.putText(
                    crop,
                    label,
                    (8, 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.48,
                    (40, 40, 230),
                    1,
                    cv2.LINE_AA,
                )
                path = (
                    OUTPUT
                    / f"{morphology}_{sequence['magnification']}_{method.lower()}_frame0000.png"
                )
                encoded_ok, encoded = cv2.imencode(".png", crop)
                if not encoded_ok:
                    raise OSError(path)
                encoded.tofile(path)
                print(path)


if __name__ == "__main__":
    main()
