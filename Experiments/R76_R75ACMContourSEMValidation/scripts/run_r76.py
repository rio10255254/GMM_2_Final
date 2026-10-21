from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import pandas as pd
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
MODEL = CONFIG["model"]
EVIDENCE = CONFIG["paired_evidence"]
INFERENCE = CONFIG["inference"]
R69 = Path(EVIDENCE["r69_root"])
RAW_DIR = Path(EVIDENCE["raw_input_dir"])
RECON_DIR = Path(INFERENCE["reconstruction_dir"])
PYTHON = Path(INFERENCE["python"])
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
SHARED_ACM = R69 / "scripts" / "run_acm_extraction.m"
AUDIT_PATH = ROOT / "results" / "input_audit.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str]) -> None:
    print("RUN:", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def find_checkpoint(wait_minutes: float = 0.0) -> tuple[Path, Path]:
    deadline = time.monotonic() + max(0.0, wait_minutes) * 60.0
    expected_run_name = Path(MODEL["training_run_dir"]).name
    weights_root = Path(MODEL["formal_weights_root"])
    while True:
        export_dir = weights_root / expected_run_name
        manifest_path = export_dir / "export_manifest.json"
        checkpoint = export_dir / "best_tradeoff.pth.tar"
        if manifest_path.is_file() and checkpoint.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (
                manifest.get("profile") == MODEL["expected_profile"]
                and int(manifest.get("seed", -1)) == int(MODEL["expected_seed"])
                and manifest.get("checkpoint_loaded") is False
                and manifest.get("teacher_loaded") is False
            ):
                return checkpoint, manifest_path
        if time.monotonic() >= deadline:
            raise RuntimeError(
                "R75 的 100 epoch 正式訓練尚未完成或權重尚未匯出；"
                "請稍後重跑，或使用 --wait-training-minutes。"
            )
        print("R75 尚在訓練，15 秒後再檢查……", flush=True)
        time.sleep(15)


def audit_sources(checkpoint: Path, export_manifest_path: Path) -> dict:
    exposures = [int(value) for value in EVIDENCE["optical_exposures"]]
    raw_source = Path(EVIDENCE["raw_source_dir"])
    raw_checks = []
    for exposure in exposures:
        source = raw_source / f"{exposure}.bmp"
        locked = RAW_DIR / f"{exposure}.bmp"
        if not source.is_file() or not locked.is_file():
            raise FileNotFoundError(source if not source.is_file() else locked)
        source_hash = sha256(source)
        locked_hash = sha256(locked)
        if source_hash != locked_hash:
            raise RuntimeError(f"光學配對影像不是原始檔的相同副本：{exposure}.bmp")
        raw_checks.append({"exposure": exposure, "sha256": source_hash, "identical": True})

    sem_dir = Path(EVIDENCE["sem_dir"])
    legacy_sem_dir = Path(EVIDENCE["legacy_sem_dir"])
    ordering_manifest_path = Path(EVIDENCE["ordering_manifest"])
    ordering_manifest = json.loads(ordering_manifest_path.read_text(encoding="utf-8"))
    if ordering_manifest.get("status") != "verified" or ordering_manifest.get("exact_copy_count") != 18:
        raise RuntimeError("SEM 排序驗證紀錄不完整。")
    sem_checks = []
    for prefix in ("P", "V"):
        for index in range(1, 10):
            name = f"{prefix}-{index:02d}.tiff"
            current = sem_dir / name
            legacy = legacy_sem_dir / name
            current_hash = sha256(current)
            legacy_hash = sha256(legacy)
            if current_hash != legacy_hash:
                raise RuntimeError(f"目前 SEM 與舊配對資料不同：{name}")
            sem_checks.append({"file": name, "sha256": current_hash, "identical": True})

    ordering = pd.read_csv(Path(EVIDENCE["ordering_mapping"])).rename(
        columns={
            "global_pillar_id": "pillar_id",
            "grid_row_1_to_6": "grid_row",
            "grid_col_1_to_6": "grid_col",
            "pillar_sem_file": "sem_file",
            "local_corner": "sem_corner",
        }
    )
    prior_mapping = pd.read_csv(R69 / "results" / "tables" / "pillar_mapping.csv")
    columns = ["pillar_id", "grid_row", "grid_col", "sem_file", "sem_corner"]
    ordering = ordering[columns].sort_values("pillar_id").reset_index(drop=True)
    prior_mapping = prior_mapping[columns].sort_values("pillar_id").reset_index(drop=True)
    if not ordering.equals(prior_mapping):
        raise RuntimeError("排序資料與 R69 的 36 顆實體對應表不一致。")
    if (
        len(ordering) != 36
        or ordering["pillar_id"].nunique() != 36
        or ordering[["grid_row", "grid_col"]].drop_duplicates().shape[0] != 36
        or not (ordering.groupby("sem_file").size() == 4).all()
    ):
        raise RuntimeError("36 顆 SEM 對應表的完整性檢查失敗。")

    legacy_code = Path(EVIDENCE["legacy_pairing_code"])
    code_text = legacy_code.read_text(encoding="utf-8", errors="replace")
    if "image_cropped" not in code_text or "SEM\\P-0" not in code_text:
        raise RuntimeError("舊研究程式缺少預期的光學/SEM 配對記錄。")

    export_manifest = json.loads(export_manifest_path.read_text(encoding="utf-8"))
    training_run_dir = Path(MODEL["training_run_dir"])
    final_epoch_path = training_run_dir / f"epoch_{int(MODEL['expected_epochs']):03d}.pth.tar"
    if not final_epoch_path.is_file():
        raise RuntimeError(
            f"找不到 epoch {MODEL['expected_epochs']} 的完成紀錄；不執行 SEM 驗證。"
        )
    checkpoint_hash = sha256(checkpoint)
    file_record = next(
        (row for row in export_manifest.get("files", []) if row.get("filename") == checkpoint.name),
        None,
    )
    if file_record is None or file_record.get("sha256") != checkpoint_hash:
        raise RuntimeError("R75 權重與訓練匯出紀錄不一致。")
    import torch

    checkpoint_payload = torch.load(checkpoint, map_location="cpu")
    selected_epoch = int(checkpoint_payload.get("epoch", -1))
    if selected_epoch < 1 or selected_epoch > int(MODEL["expected_epochs"]):
        raise RuntimeError(f"R75 內部選出的 epoch 不合理：{selected_epoch}")
    if not checkpoint_payload.get("ema_state_dict"):
        raise RuntimeError("R75 正式權重缺少 EMA 權重。")

    audit = {
        "status": "passed",
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": checkpoint_hash,
        "checkpoint_selection": MODEL["checkpoint_selection"],
        "selected_checkpoint_epoch": selected_epoch,
        "selected_checkpoint_state": "ema_state_dict",
        "sem_used_for_checkpoint_selection": False,
        "training_profile": export_manifest["profile"],
        "training_seed": export_manifest["seed"],
        "training_completed_epochs": int(MODEL["expected_epochs"]),
        "final_epoch_checkpoint": str(final_epoch_path),
        "final_epoch_checkpoint_sha256": sha256(final_epoch_path),
        "checkpoint_loaded_during_training": export_manifest["checkpoint_loaded"],
        "teacher_loaded_during_training": export_manifest["teacher_loaded"],
        "dataset_content_sha256": export_manifest["dataset_content_sha256"],
        "optical_files_verified": len(raw_checks),
        "sem_files_verified": len(sem_checks),
        "physical_pillars_verified": len(ordering),
        "mapping_matches_r69": True,
        "legacy_pairing_code_sha256": sha256(legacy_code),
        "ordering_manifest_sha256": sha256(ordering_manifest_path),
        "optical_checks": raw_checks,
        "sem_checks": sem_checks,
    }
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    ordering.to_csv(ROOT / "results" / "tables" / "verified_pillar_mapping.csv", index=False)
    print("已確認 12 張光學影像、18 張 SEM 與 36 顆實體對應。")
    return audit


def reconstruction_complete(checkpoint_hash: str | None = None) -> bool:
    expected = [RECON_DIR / f"{exposure}.bmp" for exposure in EVIDENCE["optical_exposures"]]
    manifest_path = RECON_DIR / "inference_manifest.json"
    if not all(path.is_file() for path in expected) or not manifest_path.is_file():
        return False
    for path in expected:
        with Image.open(path) as image:
            if image.size != (821, 821):
                return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return (
        int(manifest.get("image_count", -1)) == 12
        and (checkpoint_hash is None or manifest.get("checkpoint_sha256") == checkpoint_hash)
    )


def reconstruct(checkpoint: Path, audit: dict) -> None:
    checkpoint_hash = audit["checkpoint_sha256"]
    if reconstruction_complete(checkpoint_hash):
        print("已確認 12 張 R75 重建影像，略過重複推論。")
        return
    run(
        [
            str(PYTHON),
            MODEL["inference_script"],
            "--checkpoint",
            str(checkpoint),
            "--input",
            str(RAW_DIR),
            "--output",
            str(RECON_DIR),
            "--device",
            INFERENCE["device"],
            "--tile-size",
            str(INFERENCE["tile_size"]),
            "--overlap",
            str(INFERENCE["tile_overlap"]),
        ]
    )
    if not reconstruction_complete(checkpoint_hash):
        raise RuntimeError("R75 推論沒有產生 12 張完整且來源正確的 821×821 影像。")


def contour_outputs_complete() -> bool:
    primary_path = ROOT / "results" / "tables" / "primary_contour_metrics.csv"
    sensitivity_path = ROOT / "results" / "tables" / "acm_sensitivity_metrics.csv"
    masks = ROOT / "results" / "masks" / "acm_primary_masks.mat"
    if not (primary_path.is_file() and sensitivity_path.is_file() and masks.is_file()):
        return False
    primary = pd.read_csv(primary_path)
    sensitivity = pd.read_csv(sensitivity_path)
    return (
        len(primary) == 864
        and len(sensitivity) == 648
        and set(primary["method"]) == {"Raw", "R75"}
        and set(sensitivity["method"]) == {"Raw", "R75"}
        and not primary.isna().any().any()
        and not sensitivity.isna().any().any()
    )


def contours(force: bool = False) -> None:
    if contour_outputs_complete() and not force:
        print("已確認既有 R75 ACM 表格，略過重複擷取。")
        return
    expression = (
        f"addpath('{SHARED_ACM.parent.as_posix()}'); "
        f"run_acm_extraction('{ROOT.as_posix()}',"
        f"'{RAW_DIR.as_posix()}',"
        f"'{RECON_DIR.as_posix()}',"
        "'R75');"
    )
    run([str(MATLAB), "-batch", expression])
    if not contour_outputs_complete():
        raise RuntimeError("ACM 沒有產生完整的主要與敏感度表格。")


def analyze() -> None:
    run([str(PYTHON), str(ROOT / "scripts" / "analyze_r76.py")])


def test() -> None:
    run(
        [
            str(PYTHON),
            "-m",
            "unittest",
            "discover",
            "-s",
            str(ROOT / "tests"),
            "-p",
            "test_*.py",
            "-v",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run R75 paired SEM ACM contour validation.")
    parser.add_argument(
        "--stage",
        choices=["audit", "reconstruct", "contours", "analysis", "test", "all"],
        default="all",
    )
    parser.add_argument("--wait-training-minutes", type=float, default=0.0)
    parser.add_argument("--force-contours", action="store_true")
    args = parser.parse_args()

    checkpoint, export_manifest = find_checkpoint(args.wait_training_minutes)
    audit = audit_sources(checkpoint, export_manifest)
    if args.stage in {"reconstruct", "all"}:
        reconstruct(checkpoint, audit)
    if args.stage in {"contours", "all"}:
        if not reconstruction_complete(audit["checkpoint_sha256"]):
            raise RuntimeError("請先完成相同權重的 R75 重建。")
        contours(force=args.force_contours)
    if args.stage in {"analysis", "all"}:
        analyze()
    if args.stage in {"test", "all"}:
        test()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
