"""Build the LabSystem ring replay package from lab-generated data only."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from typing import Iterable


IMAGE_EXTENSIONS = {".bmp", ".png", ".tif", ".tiff"}
DEFAULT_TRAINING_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGES = (
    "stage_08_annulus_focus",
    "stage_09_annulus_non_overlap",
    "stage_10_annulus_overlap",
    "stage_13_curve_clean_general",
    "stage_14_annulus_edge_defect_focus",
    "stage_15_annulus_sparse_clean",
    "stage_16_annulus_sparse_defect_clean",
    "stage_17_annulus_microstep_clean",
    "stage_18_annulus_microstep_defect",
    "stage_19_annulus_microstep_sequence_clean",
    "stage_20_annulus_microstep_sequence_defect",
    "stage_21_annulus_gmf_sequence_clean",
    "stage_22_annulus_gmf_sequence_defect",
    "stage_23_annulus_gmf_sequence_mid_clean",
    "stage_24_annulus_gmf_sequence_mid_defect",
    "stage_25_annulus_gmf_sequence_macro_clean",
    "stage_26_annulus_gmf_sequence_macro_defect",
    "stage_27_annulus_gmf_sequence_midwide_clean",
    "stage_28_annulus_gmf_sequence_midwide_defect",
)


def _collect_images(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def _safe_remove_tree(path: Path, training_root: Path) -> None:
    resolved = path.resolve()
    root = training_root.resolve()
    if not str(resolved).lower().startswith(str(root).lower()):
        raise ValueError(f"refusing to remove outside training root: {resolved}")
    if resolved == root or len(resolved.parts) < 4:
        raise ValueError(f"refusing to remove suspicious path: {resolved}")
    shutil.rmtree(resolved)


def _place_file(src: Path, dst: Path, link_mode: str) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if link_mode not in {"auto", "hardlink", "copy"}:
        raise ValueError(f"unsupported link mode: {link_mode}")
    if link_mode in {"auto", "hardlink"}:
        try:
            os.link(src, dst)
            return "hardlink"
        except OSError:
            if link_mode == "hardlink":
                raise
    shutil.copy2(src, dst)
    return "copy"


def _selected_pairs(
    training_root: Path,
    stages: Iterable[str],
    max_pairs: int | None,
) -> list[tuple[str, Path, Path]]:
    pairs: list[tuple[str, Path, Path]] = []
    for stage in stages:
        src_dir = training_root / "generated_convolved" / stage
        lbl_dir = training_root / "generated" / stage
        src_files = _collect_images(src_dir)
        missing = [p.name for p in src_files if not (lbl_dir / p.name).exists()]
        if missing:
            examples = ", ".join(missing[:5])
            raise ValueError(f"{stage} has missing labels: {examples}")
        for src in src_files:
            pairs.append((stage, src, lbl_dir / src.name))
    if max_pairs is not None:
        pairs = pairs[: max(0, int(max_pairs))]
    if not pairs:
        raise ValueError("no ring pairs selected")
    return pairs


def build_ring_package(
    *,
    training_root: Path | str = DEFAULT_TRAINING_ROOT,
    stages: Iterable[str] = DEFAULT_STAGES,
    max_pairs: int | None = 1100,
    force: bool = False,
    link_mode: str = "auto",
) -> dict:
    root = Path(training_root).resolve()
    src_out = root / "tra_src_ring"
    lbl_out = root / "tra_lbl_ring"
    if src_out.exists():
        if not force:
            raise FileExistsError(f"output directory already exists: {src_out}")
        _safe_remove_tree(src_out, root)
    if lbl_out.exists():
        if not force:
            raise FileExistsError(f"output directory already exists: {lbl_out}")
        _safe_remove_tree(lbl_out, root)
    src_out.mkdir(parents=True, exist_ok=True)
    lbl_out.mkdir(parents=True, exist_ok=True)

    pairs = _selected_pairs(root, tuple(stages), max_pairs)
    link_counts: Counter[str] = Counter()
    stage_counts: Counter[str] = Counter()
    records = []
    for idx, (stage, src, lbl) in enumerate(pairs, start=1):
        out_name = f"{idx:04d}_{stage}_{src.name}"
        link_counts[_place_file(src, src_out / out_name, link_mode)] += 1
        link_counts[_place_file(lbl, lbl_out / out_name, link_mode)] += 1
        stage_counts[stage] += 1
        records.append(
            {
                "stage": stage,
                "src": str(src),
                "lbl": str(lbl),
                "package_src": f"tra_src_ring/{out_name}",
                "package_lbl": f"tra_lbl_ring/{out_name}",
            }
        )

    manifest = {
        "profile": "lab_ring_replay_v1",
        "training_root": str(root),
        "src_root": str(src_out),
        "lbl_root": str(lbl_out),
        "total_pairs": len(pairs),
        "max_pairs": max_pairs,
        "stages": list(stages),
        "count_by_stage": dict(stage_counts),
        "link_counts": dict(link_counts),
        "pairs": records,
    }
    (root / "tra_ring_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest


def _parse_stages(value: str | None) -> tuple[str, ...]:
    if value is None or value.strip() == "":
        return DEFAULT_STAGES
    return tuple(part.strip() for part in value.replace(";", ",").split(",") if part.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build LabSystem tra_src_ring/tra_lbl_ring from lab data.")
    parser.add_argument("--training-root", type=Path, default=DEFAULT_TRAINING_ROOT)
    parser.add_argument("--stages", default="")
    parser.add_argument("--max-pairs", type=int, default=1100)
    parser.add_argument("--all-pairs", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--link-mode", default="auto", choices=["auto", "hardlink", "copy"])
    args = parser.parse_args(argv)

    manifest = build_ring_package(
        training_root=args.training_root,
        stages=_parse_stages(args.stages),
        max_pairs=None if args.all_pairs else args.max_pairs,
        force=args.force,
        link_mode=args.link_mode,
    )
    print(json.dumps({k: v for k, v in manifest.items() if k != "pairs"}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
