from pathlib import Path
import sys

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = REPO_ROOT / "Model"
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))


def _write_pair(root: Path, rel: str) -> None:
    src_path = root / "src" / rel
    lbl_path = root / "lbl" / rel
    src_path.parent.mkdir(parents=True, exist_ok=True)
    lbl_path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.full((16, 16), 128, dtype=np.uint8)
    cv2.imwrite(str(src_path), arr)
    cv2.imwrite(str(lbl_path), arr)


def test_paired_folder_returns_role_ids_for_r41_package(tmp_path):
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    _write_pair(tmp_path, "ring/ring_000.bmp")
    _write_pair(tmp_path, "stage_01_triangles/shape_000.bmp")
    _write_pair(tmp_path, "stage_29_micro_lines_grid/micro_000.bmp")

    ds = trainer.PairedGrayFolder(
        str(tmp_path / "src"),
        str(tmp_path / "lbl"),
        crop_size=8,
        random_crop=False,
    )

    roles = [int(ds[i][2].item()) for i in range(len(ds))]
    assert sorted(roles) == [
        trainer.DATA_ROLE_RING,
        trainer.DATA_ROLE_SHAPE,
        trainer.DATA_ROLE_MICRO,
    ]


def test_paired_folder_keeps_two_tuple_for_legacy_flat_package(tmp_path):
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    _write_pair(tmp_path, "legacy_000.bmp")
    ds = trainer.PairedGrayFolder(
        str(tmp_path / "src"),
        str(tmp_path / "lbl"),
        crop_size=8,
        random_crop=False,
    )

    assert len(ds[0]) == 2
