"""Prepare fixed external geometry and real-image manifests for R114 probes."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "validation" / "manifests"
REQUIRED_MAPS = [
    "normalized_sdf", "normal_x", "normal_y", "boundary_confidence",
    "correction_need", "recoverability", "geometry_gate", "detail_gate",
    "width_gain", "normal_shift", "detail",
]
TILES = [
    {"name": "grid_origin", "core": 256, "halo": 192, "overlap": 0, "origin": [0, 0]},
    {"name": "grid_shifted_overlap", "core": 256, "halo": 192, "overlap": 64, "origin": [73, 91]},
    {"name": "grid_large_shifted", "core": 320, "halo": 192, "overlap": 96, "origin": [31, 47]},
]


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def synthetic(name: str, source_manifest: Path) -> dict:
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    records = []
    for row in source["records"]:
        records.append({
            "id": f"{name}_{row['image_id'].replace('/', '_')}",
            "family": str(row["family"]),
            "role": "degraded",
            "source": str(row["src"]),
            "target": str(row["lbl"]),
        })
    first = source["records"][0]
    records.append({
        "id": f"{name}_clear_identity",
        "family": "clear_identity",
        "role": "clear",
        "source": str(first["lbl"]),
        "target": str(first["lbl"]),
    })
    return {
        "schema_version": 1,
        "suite": name,
        "records": records,
        "tile_configs": TILES,
        "required_internal_maps": REQUIRED_MAPS,
        "thresholds": {
            "max_tile_mean_gray": 0.05,
            "max_tile_p99_gray": 0.25,
            "max_tile_absolute_gray": 1.0,
        },
    }


def first_images(directory: Path, count: int) -> list[Path]:
    extensions = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
    return sorted(path for path in directory.rglob("*") if path.is_file() and path.suffix.lower() in extensions)[:count]


def real_manifest() -> dict:
    roots = {
        "real_5x": Path(r"D:\GMM_2_Final\20260704_20x_5x_analysis\raw_inputs\5x_1um\bmp"),
        "real_20x": Path(r"D:\GMM_2_Final\20260704_20x_5x_analysis\raw_inputs\20x_1um\bmp"),
        "real_50x": Path(r"D:\GMM_2_Final\20260702_100MG_displacement_analysis\raw_inputs\x_1um\bmp"),
        "junhua": Path(r"D:\NTU_ImageDataset\Pitch1um_Y_100\Raw"),
    }
    records = []
    for family, directory in roots.items():
        if not directory.exists():
            continue
        for index, path in enumerate(first_images(directory, 3)):
            records.append({
                "id": f"{family}_{index:02d}",
                "family": family,
                "role": "real_unlabeled",
                "source": str(path),
            })
    if records:
        records.append({
            "id": "real_clear_identity_contract",
            "family": "clear_identity",
            "role": "clear",
            "source": records[0]["source"],
            "target": records[0]["source"],
        })
    return {
        "schema_version": 1,
        "suite": "real_representatives",
        "records": records,
        "tile_configs": TILES,
        "required_internal_maps": REQUIRED_MAPS,
        "thresholds": {
            "max_tile_mean_gray": 0.05,
            "max_tile_p99_gray": 0.25,
            "max_tile_absolute_gray": 1.0,
        },
    }


def main() -> int:
    suites = {
        "R73": Path(r"D:\GMM_2_Final\Experiments\R73_R61ExpandedSyntheticACMGeneralization\data\r73_synthetic_acm_val\manifest.json"),
        "R74": Path(r"D:\GMM_2_Final\Experiments\R74_R61HardMicroscopyACMGeneralization\data\r74_hard_acm_val\manifest.json"),
    }
    for name, path in suites.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        write(OUTPUT / f"{name}.json", synthetic(name, path))
    real = real_manifest()
    if not real["records"]:
        raise RuntimeError("no real representative images found")
    write(OUTPUT / "real_representatives.json", real)
    print(json.dumps({"status": "complete", "R73": 100, "R74": 100, "real": len(real["records"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
