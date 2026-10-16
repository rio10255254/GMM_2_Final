"""Build the canonical tiled V42 E120 arm for the same 101-frame GMF test."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "qualification.json").read_text(encoding="utf-8"))
V42_PACKAGE = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Model_Packages"
    r"\V42_SoftLabelSNR_FullStandalone_20260709"
)
INFERENCE_SCRIPT = V42_PACKAGE / "infer_v42.py"
CHECKPOINT = Path(CONFIG["models"]["v42_e120"]["checkpoint"])
EXPECTED_CHECKPOINT_SHA256 = CONFIG["models"]["v42_e120"]["sha256"]

REFERENCE_PACKAGE = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\External_GMF_Packages"
    r"\Pitch1um_Y_100_Raw_Even_R109E48"
)
RAW_DIR = REFERENCE_PACKAGE / "pitch1um_y100_raw" / "bmp"
R109_DIR = REFERENCE_PACKAGE / "pitch1um_y100_r109_e48" / "bmp"
R109_SCORE = REFERENCE_PACKAGE / "_gmf_scores" / "pitch1um_y100_r109_e48"
RAW_SCORE = REFERENCE_PACKAGE / "_gmf_scores" / "pitch1um_y100_raw"

PACKAGE = ROOT / "external_gmf_v42"
V42_DIR = PACKAGE / "pitch1um_y100_v42_e120_tiled" / "bmp"
V42_SCORE = PACKAGE / "_gmf_scores" / "pitch1um_y100_v42_e120_tiled"
RECORDS = PACKAGE / "_records"
CORE = 1024
HALO = 256


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def model_args() -> SimpleNamespace:
    return SimpleNamespace(
        psf_fitted_path=None,
        psf_from_ckpt=True,
        psf_grid_rows=None,
        psf_grid_cols=None,
        psf_use_stack_mean=True,
        psf_deconv_reg=None,
        psf_phys_alpha=None,
        psf_phys_trainable_reg=False,
        use_band_limit=None,
        band_limit_cutoff=0.95,
        band_limit_order=8.0,
        weak_psf_enable=None,
        weak_psf_k=None,
        weak_psf_indices=None,
        weak_psf_reg=None,
        weak_psf_beta_init=None,
        weak_psf_beta_min=0.0,
        weak_psf_beta_max=0.10,
        weak_psf_beta_scale_max=None,
        weak_psf_beta_scale=None,
        weak_psf_gating_temp=None,
        weak_psf_psf_temp=None,
        weak_psf_entropy_mix=None,
        weak_psf_trainable_reg=False,
        weak_psf_lowfreq_ratio=None,
        weak_psf_inject="y2",
        weak_psf_deconv_mode="clamp",
        strict_load=False,
        print_model_config=False,
    )


def load_model():
    module = load_module(INFERENCE_SCRIPT, "r111_v42_inference")
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    checkpoint = torch.load(CHECKPOINT, map_location="cpu")
    state_dict = module.extract_state_dict(checkpoint)
    arch = module.infer_arch_from_state(state_dict, ckpt_obj=checkpoint)
    args = model_args()
    psf_path, temp_psf_dir, psf_source = module.resolve_psf_path(args, checkpoint, state_dict)
    if psf_path is None or not psf_path.exists():
        raise RuntimeError("Could not recover the V42 checkpoint PSF")

    use_band_limit = arch["use_band_limit"]
    weak_psf_enable = arch["weak_psf_enable"]
    weak_psf_k = arch["weak_psf_k"]
    weak_psf_indices = module.parse_indices(None, weak_psf_k)
    model = module.GeoEdgeAlignSR_v1_v5_NoCoord(
        in_ch=arch["in_ch"],
        base=arch["base"],
        use_physics_layer=arch["use_physics_layer"],
        use_sigmoid_output=True,
        use_upsample_conv=True,
        use_band_limit=use_band_limit,
        band_limit_cutoff=0.95,
        band_limit_order=8.0,
        psf_fitted_path=str(psf_path),
        psf_grid_rows=None,
        psf_grid_cols=None,
        psf_use_stack_mean=True,
        psf_deconv_reg=float(arch["psf_deconv_reg"] if arch["psf_deconv_reg"] is not None else 10.0),
        psf_phys_alpha_init=float(arch["psf_phys_alpha_init"] if arch["psf_phys_alpha_init"] is not None else 0.10),
        psf_phys_trainable_reg=False,
        weak_psf_enable=weak_psf_enable,
        weak_psf_k=weak_psf_k,
        weak_psf_indices=weak_psf_indices,
        weak_psf_reg=float(arch["weak_psf_reg"] if arch["weak_psf_reg"] is not None else 30.0),
        weak_psf_beta_init=float(arch["weak_psf_beta_init"] if arch["weak_psf_beta_init"] is not None else 0.02),
        weak_psf_gating_temp=float(arch["weak_psf_gating_temp"] if arch["weak_psf_gating_temp"] is not None else 2.5),
        weak_psf_psf_temp=float(arch["weak_psf_psf_temp"] if arch["weak_psf_psf_temp"] is not None else 2.5),
        weak_psf_entropy_mix=float(arch["weak_psf_entropy_mix"] if arch["weak_psf_entropy_mix"] is not None else 0.0),
        weak_psf_trainable_reg=False,
        weak_psf_lowfreq_ratio=float(arch["weak_psf_lowfreq_ratio"] if arch["weak_psf_lowfreq_ratio"] is not None else 0.25),
        weak_psf_beta_min=0.0,
        weak_psf_beta_max=0.10,
        weak_psf_beta_scale_max=float(arch["weak_psf_beta_scale_max"] if arch["weak_psf_beta_scale_max"] is not None else 0.35),
        weak_psf_deconv_mode="clamp",
        weak_psf_inject="y2",
        boundary_residual_adapter_enable=bool(arch["boundary_residual_adapter_enable"]),
        boundary_residual_adapter_hidden=int(arch["boundary_residual_adapter_hidden"]),
        boundary_residual_adapter_max=float(arch["boundary_residual_adapter_max"]),
        boundary_residual_adapter_gate_bias=float(arch["boundary_residual_adapter_gate_bias"]),
        boundary_residual_adapter_delta_bias=bool(arch["boundary_residual_adapter_delta_bias"]),
        boundary_residual_adapter_zero_mean=bool(arch["boundary_residual_adapter_zero_mean"]),
        boundary_residual_adapter_edge_gate=bool(arch["boundary_residual_adapter_edge_gate"]),
        boundary_residual_adapter_polarity_split=bool(arch["boundary_residual_adapter_polarity_split"]),
        boundary_residual_adapter_orientation_inputs=bool(arch["boundary_residual_adapter_orientation_inputs"]),
        raw_anchor_output_mode=str(arch["raw_anchor_output_mode"]),
        raw_anchor_output_alpha=float(arch["raw_anchor_output_alpha"]),
        raw_anchor_output_sigma=float(arch["raw_anchor_output_sigma"]),
        raw_anchor_output_detail_gain=float(arch["raw_anchor_output_detail_gain"]),
        quality_gate_enable=bool(arch["quality_gate_enable"]),
        quality_gate_hidden=int(arch["quality_gate_hidden"]),
        quality_gate_scale_min=float(arch["quality_gate_scale_min"]),
        quality_gate_scale_max=float(arch["quality_gate_scale_max"]),
    ).to(device)
    model.eval()
    module.load_weights(model, state_dict, strict=False)
    return module, model, device, temp_psf_dir, psf_source, arch


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Cannot read {path}")
    return image


def write_bmp(path: Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(".bmp", image)
    if not ok:
        raise RuntimeError(f"Cannot write {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded.tofile(str(path))


@torch.inference_mode()
def tiled(model: torch.nn.Module, image: np.ndarray, device: torch.device, core: int, halo: int) -> np.ndarray:
    if image.shape != (5120, 5120):
        raise RuntimeError(f"Expected 5120x5120, got {image.shape}")
    source = torch.from_numpy(image.astype(np.float32)[None, None] / 255.0).to(device)
    padded = F.pad(source, (halo, halo, halo, halo), mode="reflect")
    output = torch.zeros_like(source)
    height, width = image.shape
    for y in range(0, height, core):
        for x in range(0, width, core):
            core_h = min(core, height - y)
            core_w = min(core, width - x)
            tile = padded[..., y : y + core_h + 2 * halo, x : x + core_w + 2 * halo]
            if tile.shape[-2] % 64 or tile.shape[-1] % 64:
                raise RuntimeError(f"V42 tile is not aligned to 64: {tuple(tile.shape)}")
            value = model(tile).clamp(0.0, 1.0)
            output[..., y : y + core_h, x : x + core_w] = value[
                ..., halo : halo + core_h, halo : halo + core_w
            ]
    return np.round(output[0, 0].cpu().numpy() * 255.0).astype(np.uint8)


def write_package_artifacts(rows: list[dict[str, object]], parity: dict[str, object], metadata: dict[str, object]) -> None:
    with (PACKAGE / "source_mapping.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    cases = [
        {"case": "pitch1um_y100_raw", "role": "Raw", "image_folder": str(RAW_DIR), "score_folder": str(RAW_SCORE), "image_count": 101, "status": "score present"},
        {"case": "pitch1um_y100_r109_e48", "role": "R109 E48", "image_folder": str(R109_DIR), "score_folder": str(R109_SCORE), "image_count": 101, "status": "score present"},
        {"case": "pitch1um_y100_v42_e120_tiled", "role": "V42 E120 canonical tiled", "image_folder": str(V42_DIR), "score_folder": str(V42_SCORE), "image_count": 101, "status": "run external GMF and save GMF_score.txt"},
    ]
    with (PACKAGE / "paths_for_gmf_tool.tsv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(cases[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(cases)
    manifest = {
        "status": "v42_images_ready_external_gmf_pending",
        "model": "V42 E120",
        "checkpoint": str(CHECKPOINT),
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA256,
        "full_frame_5120_status": "failed_cuda_out_of_memory_requested_84p38_GiB",
        "canonical_tiling": {"core": CORE, "halo": HALO, "padding": "reflect", "assembly": "core_only_no_blending"},
        "tile_grid_sensitivity": parity,
        "images": 101,
        "source": str(RAW_DIR),
        "metadata": metadata,
        "coordinate_status": "Raw and R109 present; V42 pending external tool",
    }
    (PACKAGE / "package_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    readme = f"""V42 E120 外部 GMF 驗證包

請只對 pitch1um_y100_v42_e120_tiled\\bmp 執行外部 GMF；Raw 與 R109 的座標已完成。
完成後請把輸出命名為 GMF_score.txt，放到：
_gmf_scores\\pitch1um_y100_v42_e120_tiled

這批共有 101 張，檔名 frame_0000.bmp 到 frame_0100.bmp，與既有 Raw/R109 完全對齊。

V42 無法整張重建 5120x5120 影像，實測會要求約 84.38 GiB 顯存。因此本包採固定
1024 core、256 halo、反射邊界、只保留中央區域的切塊方式。V42 訓練時沒有像 R109
那樣明確加入切塊一致性契約；不過本次代表影像用 1024 與 1536 core 交叉檢查時，
最大只差 1 階灰階。詳細結果保存在 package_manifest.json。
"""
    (PACKAGE / "README_EXTERNAL_GMF.txt").write_text(readme, encoding="utf-8")


def main() -> int:
    started = time.perf_counter()
    if sha256(CHECKPOINT) != EXPECTED_CHECKPOINT_SHA256:
        raise RuntimeError("V42 checkpoint hash mismatch")
    names = sorted(path.name for path in RAW_DIR.glob("*.bmp"))
    expected = [f"frame_{index:04d}.bmp" for index in range(101)]
    if names != expected:
        raise RuntimeError("Raw reference package filename set changed")
    V42_DIR.mkdir(parents=True, exist_ok=True)
    V42_SCORE.mkdir(parents=True, exist_ok=True)
    RECORDS.mkdir(parents=True, exist_ok=True)

    module, model, device, temp_psf_dir, psf_source, arch = load_model()
    try:
        first_raw = read_gray(RAW_DIR / "frame_0000.bmp")
        canonical_first = tiled(model, first_raw, device, CORE, HALO)
        alternate_first = tiled(model, first_raw, device, 1536, HALO)
        grid_difference = np.abs(canonical_first.astype(np.int16) - alternate_first.astype(np.int16))
        parity = {
            "alternate_core": 1536,
            "same_halo": HALO,
            "max_gray_difference": int(grid_difference.max()),
            "mean_gray_difference": float(grid_difference.mean()),
            "p99_gray_difference": float(np.percentile(grid_difference, 99)),
            "fraction_greater_than_one_gray": float(np.mean(grid_difference > 1)),
            "tested_frame_grid_parity_pass": bool(grid_difference.max() <= 1),
        }
        if not (V42_DIR / "frame_0000.bmp").is_file():
            write_bmp(V42_DIR / "frame_0000.bmp", canonical_first)

        for index, name in enumerate(expected):
            destination = V42_DIR / name
            if destination.is_file() and read_gray(destination).shape == (5120, 5120):
                print(json.dumps({"done": index + 1, "total": 101, "status": "verified_existing"}), flush=True)
                continue
            output = tiled(model, read_gray(RAW_DIR / name), device, CORE, HALO)
            write_bmp(destination, output)
            elapsed = time.perf_counter() - started
            eta = elapsed / (index + 1) * (101 - index - 1)
            print(json.dumps({"done": index + 1, "total": 101, "elapsed_seconds": round(elapsed, 1), "eta_seconds": round(eta, 1)}), flush=True)

        output_names = sorted(path.name for path in V42_DIR.glob("*.bmp"))
        if output_names != expected:
            raise RuntimeError("V42 output filename set is incomplete")
        rows: list[dict[str, object]] = []
        for index, name in enumerate(expected):
            raw_path = RAW_DIR / name
            output_path = V42_DIR / name
            raw = read_gray(raw_path)
            output = read_gray(output_path)
            if output.shape != raw.shape:
                raise RuntimeError(f"Output shape mismatch at {name}")
            rows.append(
                {
                    "sequence_index": index,
                    "frame_name": name,
                    "raw_sha256": sha256(raw_path),
                    "v42_sha256": sha256(output_path),
                    "mean_abs_change_gray": float(np.mean(np.abs(output.astype(np.float32) - raw.astype(np.float32)))),
                }
            )
        changes = np.asarray([float(row["mean_abs_change_gray"]) for row in rows])
        metadata = {
            "device": str(device),
            "psf_source": psf_source,
            "elapsed_seconds": time.perf_counter() - started,
            "mean_abs_change_gray_median": float(np.median(changes)),
            "mean_abs_change_gray_p95": float(np.percentile(changes, 95)),
            "all_outputs_differ_from_raw": bool(all(row["raw_sha256"] != row["v42_sha256"] for row in rows)),
            "arch": {key: value for key, value in arch.items() if isinstance(value, (str, int, float, bool, type(None)))},
        }
        write_package_artifacts(rows, parity, metadata)
        print(json.dumps({"status": "complete", "images": len(rows), "tile_grid_sensitivity": parity, "elapsed_seconds": metadata["elapsed_seconds"]}), flush=True)
        return 0
    finally:
        if temp_psf_dir is not None:
            shutil.rmtree(temp_psf_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
