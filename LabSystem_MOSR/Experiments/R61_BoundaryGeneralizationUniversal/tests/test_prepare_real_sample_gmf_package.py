from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prepare_real_sample_gmf_package.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_real_sample_gmf_package", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_bmp(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = np.full((12, 16), int(value), dtype=np.uint8)
    assert cv2.imwrite(str(path), img)


def test_build_infer_command_forces_all_images_and_fixed_psf(tmp_path: Path):
    module = load_module()

    command = module.build_infer_command(
        infer_script=tmp_path / "infer_runtime.py",
        weights=tmp_path / "candidate.pth.tar",
        input_dir=tmp_path / "input",
        recon_root=tmp_path / "recon",
        output_name="05_r61_r39_a970_candidate",
        device="cpu",
        psf_path=tmp_path / "psf.mat",
    )

    assert command[0] == sys.executable
    assert command[command.index("--select-mode") + 1] == "all"
    assert command[command.index("--exts") + 1] == ".bmp"
    assert "--no-psf-from-ckpt" in command
    assert "--weak-psf-disable" in command


def test_build_infer_command_forwards_optional_output_anchor(tmp_path: Path):
    module = load_module()

    command = module.build_infer_command(
        infer_script=tmp_path / "infer_runtime.py",
        weights=tmp_path / "candidate.pth.tar",
        input_dir=tmp_path / "input",
        recon_root=tmp_path / "recon",
        output_name="05_r61_r39_a970_candidate",
        device="cpu",
        psf_path=tmp_path / "psf.mat",
        anchor_output_mode="detail",
        anchor_alpha=0.10,
        anchor_sigma=2.0,
        anchor_detail_gain=0.35,
    )

    assert command[command.index("--anchor-output-mode") + 1] == "detail"
    assert command[command.index("--anchor-alpha") + 1] == "0.1"
    assert command[command.index("--anchor-sigma") + 1] == "2.0"
    assert command[command.index("--anchor-detail-gain") + 1] == "0.35"


def test_patch_infer_script_disables_manual_overrides(tmp_path: Path):
    module = load_module()
    source = tmp_path / "source_infer.py"
    source.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "SCRIPT_DIR = Path(__file__).resolve().parent",
                'MANUAL_SELECT_MODE = "odd"',
                'MANUAL_WEIGHTS_PATH = "__CURRENT_SELECTED_SEED__"',
            ]
        ),
        encoding="utf-8",
    )

    patched = module.prepare_infer_script(tmp_path / "package", source_script=source)
    text = patched.read_text(encoding="utf-8")

    assert f'SCRIPT_DIR = Path(r"{source.parent}")' in text
    assert "MANUAL_SELECT_MODE = None" in text
    assert "MANUAL_WEIGHTS_PATH = None" in text
    assert '"odd"' not in text
    assert "__CURRENT_SELECTED_SEED__" not in text


def test_sync_reconstruction_copies_bmps_with_original_names(tmp_path: Path):
    module = load_module()
    src = tmp_path / "recon_output"
    _write_bmp(src / "Image__001.bmp", 11)
    _write_bmp(src / "Image__002.bmp", 22)
    (src / "ignore.txt").write_text("x", encoding="utf-8")

    out_dir = tmp_path / "package" / "05_case" / "bmp"
    result = module.sync_reconstruction_to_case(src, out_dir)

    assert result["bmp_count"] == 2
    assert sorted(p.name for p in out_dir.glob("*.bmp")) == ["Image__001.bmp", "Image__002.bmp"]


def test_upsert_paths_tsv_preserves_existing_and_adds_candidate(tmp_path: Path):
    module = load_module()
    table = tmp_path / "paths_for_gmf_tool.tsv"
    table.write_text(
        "\n".join(
            [
                "case\trole\timage_folder\tscore_folder\timage_count\tnote",
                "00_raw_input\traw\told_img\told_score\t11\tkeep me",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    case = module.GmfCase(
        case="05_r61_r39_a970_candidate",
        role="r61_candidate",
        image_folder=tmp_path / "case" / "bmp",
        score_folder=tmp_path / "_gmf_scores" / "05_r61_r39_a970_candidate",
        image_count=11,
        note="candidate",
    )
    module.upsert_paths_tsv(table, case)
    module.upsert_paths_tsv(table, case)

    with table.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))

    assert [row["case"] for row in rows] == ["00_raw_input", "05_r61_r39_a970_candidate"]
    assert rows[0]["note"] == "keep me"
    assert rows[1]["image_count"] == "11"
