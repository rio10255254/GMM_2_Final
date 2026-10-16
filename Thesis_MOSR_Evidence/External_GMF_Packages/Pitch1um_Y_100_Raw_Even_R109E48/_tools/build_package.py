"""Build the even-frame Raw versus R109 E48 external-GMF package."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F


PACKAGE = Path(__file__).resolve().parents[1]
SOURCE = Path(r"D:\NTU_ImageDataset\Pitch1um_Y_100\Raw")
MODEL_ROOT = Path(r"D:\GMM_2_Final\Experiments\R109_StagedMidpointWidthScratch")
CHECKPOINT = MODEL_ROOT / "weights" / "selected" / "R109.pth"
EXPECTED_CHECKPOINT_SHA256 = "77ff8611e764e1350d60592f5d8a25d6786db17897eadce189185cdc4dbc87fc"
RAW_DIR = PACKAGE / "pitch1um_y100_raw" / "bmp"
R109_DIR = PACKAGE / "pitch1um_y100_r109_e48" / "bmp"
SCORES = PACKAGE / "_gmf_scores"
RECORDS = PACKAGE / "_records"
CORE = 1024
HALO = 192

sys.path.insert(0, str(MODEL_ROOT / "model"))
from r109_model import build_model  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Cannot read image: {path}")
    return image


def write_bmp(path: Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(".bmp", image)
    if not ok:
        raise RuntimeError(f"Cannot encode image: {path}")
    encoded.tofile(str(path))


@torch.inference_mode()
def tiled(model: torch.nn.Module, image: np.ndarray, device: torch.device) -> np.ndarray:
    source = torch.from_numpy(image.astype(np.float32)[None, None] / 255.0).to(device)
    height, width = image.shape
    padded = F.pad(source, (HALO, HALO, HALO, HALO), mode="reflect")
    output = torch.zeros_like(source)
    for y in range(0, height, CORE):
        for x in range(0, width, CORE):
            core_h = min(CORE, height - y)
            core_w = min(CORE, width - x)
            tile = padded[..., y : y + core_h + 2 * HALO, x : x + core_w + 2 * HALO]
            value = model(tile)
            output[..., y : y + core_h, x : x + core_w] = value[
                ..., HALO : HALO + core_h, HALO : HALO + core_w
            ]
    return np.round(np.clip(output[0, 0].cpu().numpy(), 0.0, 1.0) * 255.0).astype(np.uint8)


def prepare_directories() -> None:
    for path in (RAW_DIR, R109_DIR, SCORES / "pitch1um_y100_raw", SCORES / "pitch1um_y100_r109_e48", RECORDS):
        path.mkdir(parents=True, exist_ok=True)


def link_raw(source: Path, destination: Path) -> None:
    if destination.exists():
        if destination.stat().st_size != source.stat().st_size:
            raise RuntimeError(f"Existing Raw file has wrong size: {destination}")
        return
    os.link(source, destination)


def write_text_artifacts(rows: list[dict[str, object]], elapsed_seconds: float) -> None:
    mapping_path = PACKAGE / "source_mapping.csv"
    with mapping_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    paths = [
        {
            "case": "pitch1um_y100_raw",
            "role": "raw_input",
            "image_folder": str(RAW_DIR),
            "score_folder": str(SCORES / "pitch1um_y100_raw"),
            "image_count": len(rows),
            "note": "Raw control; one even-position frame from every two-image position.",
        },
        {
            "case": "pitch1um_y100_r109_e48",
            "role": "r109_e48",
            "image_folder": str(R109_DIR),
            "score_folder": str(SCORES / "pitch1um_y100_r109_e48"),
            "image_count": len(rows),
            "note": "Selected R109 epoch 48 reconstruction; canonical core-only tiling.",
        },
    ]
    with (PACKAGE / "paths_for_gmf_tool.tsv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(paths[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(paths)

    changes = np.asarray([float(row["mean_abs_change_gray"]) for row in rows], dtype=np.float64)
    manifest = {
        "status": "ready_for_external_gmf",
        "package": PACKAGE.name,
        "source": str(SOURCE),
        "source_total_count": 202,
        "selected_count": len(rows),
        "selection": "sort original BMP filenames, then keep 1-based positions 2,4,6,...,202",
        "sequence_meaning": "101 physical positions; one retained image per two-image position; 100 adjacent displacement steps",
        "normalized_names": "frame_0000.bmp through frame_0100.bmp, identical across both arms",
        "image_shape": [5120, 5120],
        "model": {
            "name": "R109 E48",
            "checkpoint": str(CHECKPOINT),
            "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
            "core_size": CORE,
            "halo": HALO,
            "precision": "float32",
        },
        "verification": {
            "raw_byte_preserved_by_ntfs_hardlink": True,
            "identical_filenames_across_arms": True,
            "all_images_readable": True,
            "all_shapes_identical": True,
            "all_outputs_finite_uint8": True,
            "mean_abs_change_gray_median": float(np.median(changes)),
            "mean_abs_change_gray_p95": float(np.percentile(changes, 95)),
            "mean_abs_change_gray_max": float(np.max(changes)),
        },
        "coordinate_files": "pending; save each external GMF result as GMF_score.txt in its matching score_folder",
        "elapsed_seconds": elapsed_seconds,
        "artifacts": {
            "case_table": "paths_for_gmf_tool.tsv",
            "source_mapping": "source_mapping.csv",
            "score_root": "_gmf_scores",
        },
    }
    (PACKAGE / "package_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    readme = """Pitch1um_Y_100：Raw 與 R109 E48 外部 GMF 驗證包

這個資料夾已可直接交給外部 GMF 程式。

原始資料共有 202 張，也就是 101 個位置、每個位置連拍兩張。依時間戳
檔名排序後，本包只保留第 2、4、6、…、202 張，因此共有 101 張影像，
可計算 100 段相鄰位置位移。

請分別對以下兩個影像資料夾執行外部 GMF：

1. pitch1um_y100_raw\\bmp
2. pitch1um_y100_r109_e48\\bmp

兩邊檔名完全相同，從 frame_0000.bmp 到 frame_0100.bmp。請不要改名、
刪除或重新排序。

外部 GMF 跑完後，請把兩份座標結果都命名為 GMF_score.txt，分別放到
_gmf_scores 內對應的 Raw 與 R109 資料夾。paths_for_gmf_tool.tsv 已列出
兩組影像與結果資料夾的完整路徑；source_mapping.csv 則保留標準檔名、
原始時間戳檔名與每張檔案指紋的完整對照。
"""
    (PACKAGE / "README_EXTERNAL_GMF.txt").write_text(readme, encoding="utf-8")


def main() -> int:
    started = time.perf_counter()
    prepare_directories()

    if os.environ.get("R109_GMF_FORCE_REGENERATE") == "1":
        expected_generated = [R109_DIR / f"frame_{index:04d}.bmp" for index in range(101)]
        existing_generated = sorted(R109_DIR.glob("*.bmp"))
        if existing_generated and existing_generated != expected_generated:
            raise RuntimeError("Refusing regeneration because the R109 output folder has an unexpected file set")
        for path in existing_generated:
            path.unlink()
        print(json.dumps({"removed_noncanonical_outputs": len(existing_generated)}), flush=True)

    checkpoint_hash = sha256(CHECKPOINT)
    if checkpoint_hash != EXPECTED_CHECKPOINT_SHA256:
        raise RuntimeError(f"Checkpoint hash mismatch: {checkpoint_hash}")

    all_files = sorted(path for path in SOURCE.iterdir() if path.is_file() and path.suffix.lower() == ".bmp")
    if len(all_files) != 202:
        raise RuntimeError(f"Expected 202 source BMP files, found {len(all_files)}")
    selected = [path for position, path in enumerate(all_files, start=1) if position % 2 == 0]
    if len(selected) != 101:
        raise RuntimeError(f"Expected 101 selected files, found {len(selected)}")

    for index, source in enumerate(selected):
        link_raw(source, RAW_DIR / f"frame_{index:04d}.bmp")

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    payload = torch.load(CHECKPOINT, map_location=device, weights_only=False)
    model = build_model().to(device)
    model.load_state_dict(payload["model"])
    model.eval()
    for index, source in enumerate(selected):
        destination = R109_DIR / f"frame_{index:04d}.bmp"
        if destination.exists():
            existing = read_gray(destination)
            if existing.shape == (5120, 5120):
                print(json.dumps({"done": index + 1, "total": len(selected), "status": "verified_existing"}), flush=True)
                continue
        raw = read_gray(source)
        if raw.shape != (5120, 5120):
            raise RuntimeError(f"Unexpected source shape {raw.shape}: {source}")
        reconstruction = tiled(model, raw, device)
        write_bmp(destination, reconstruction)
        elapsed = time.perf_counter() - started
        eta = elapsed / (index + 1) * (len(selected) - index - 1)
        print(
            json.dumps(
                {"done": index + 1, "total": len(selected), "elapsed_seconds": round(elapsed, 1), "eta_seconds": round(eta, 1)}
            ),
            flush=True,
        )

    raw_names = sorted(path.name for path in RAW_DIR.glob("*.bmp"))
    r109_names = sorted(path.name for path in R109_DIR.glob("*.bmp"))
    expected_names = [f"frame_{index:04d}.bmp" for index in range(101)]
    if raw_names != expected_names or r109_names != expected_names:
        raise RuntimeError("The two GMF arms do not contain the exact expected filename set")

    rows: list[dict[str, object]] = []
    for index, source in enumerate(selected):
        raw_path = RAW_DIR / f"frame_{index:04d}.bmp"
        output_path = R109_DIR / f"frame_{index:04d}.bmp"
        raw = read_gray(raw_path)
        output = read_gray(output_path)
        if raw.shape != (5120, 5120) or output.shape != raw.shape:
            raise RuntimeError(f"Shape mismatch at frame {index}")
        source_hash = sha256(source)
        raw_hash = sha256(raw_path)
        if raw_hash != source_hash:
            raise RuntimeError(f"Raw byte preservation failed at frame {index}")
        rows.append(
            {
                "sequence_index": index,
                "source_sorted_position_1based": 2 * (index + 1),
                "frame_name": raw_path.name,
                "original_filename": source.name,
                "original_sha256": source_hash,
                "raw_sha256": raw_hash,
                "r109_sha256": sha256(output_path),
                "mean_abs_change_gray": float(np.mean(np.abs(output.astype(np.float32) - raw.astype(np.float32)))),
            }
        )
        print(json.dumps({"verify": index + 1, "total": len(selected)}), flush=True)

    elapsed = time.perf_counter() - started
    write_text_artifacts(rows, elapsed)
    state = {
        "status": "complete",
        "selected_images": len(rows),
        "displacement_steps": len(rows) - 1,
        "device": str(device),
        "elapsed_seconds": elapsed,
    }
    (RECORDS / "build_state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(json.dumps(state), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
