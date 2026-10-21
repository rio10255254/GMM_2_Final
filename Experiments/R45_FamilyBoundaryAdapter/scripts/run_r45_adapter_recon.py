"""Run R45 adapter reconstructions on R44 motion validation packages."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import torch


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from r45_adapter_data import DEFAULT_DATA_ROOT, IMAGE_EXTENSIONS, load_manifest  # noqa: E402
from r45_adapter_model import build_wrapper_from_checkpoint, family_from_stage  # noqa: E402


EXPERIMENT_ROOT = REPO_ROOT / "Experiments" / "R45_FamilyBoundaryAdapter"
DEFAULT_ADAPTER = EXPERIMENT_ROOT / "results" / "checkpoints" / "r45_oracle_adapter_large_mixed.pth"
DEFAULT_RECON_ROOT = EXPERIMENT_ROOT / "results" / "motion_recon"


def resolve_device(device: str) -> torch.device:
    if device == "auto":
        return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    return torch.device(device)


def read_gray01(path: Path) -> tuple[np.ndarray, np.dtype]:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"failed to read image: {path}")
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    dtype = img.dtype
    if dtype == np.uint16:
        arr = img.astype(np.float32) / 65535.0
    elif dtype == np.uint8:
        arr = img.astype(np.float32) / 255.0
    else:
        arr = img.astype(np.float32)
        maxv = float(np.nanmax(arr)) if arr.size else 1.0
        if maxv > 1.5:
            arr = arr / maxv
    return arr, dtype


def pad_to_multiple(img: np.ndarray, factor: int) -> tuple[np.ndarray, int, int]:
    h, w = img.shape[:2]
    new_h = int(np.ceil(h / factor) * factor)
    new_w = int(np.ceil(w / factor) * factor)
    if new_h == h and new_w == w:
        return img, h, w
    return np.pad(img, ((0, new_h - h), (0, new_w - w)), mode="reflect"), h, w


def write_gray(path: Path, pred01: np.ndarray, dtype: np.dtype) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if dtype == np.uint16:
        out = np.clip(np.rint(pred01 * 65535.0), 0, 65535).astype(np.uint16)
    else:
        out = np.clip(np.rint(pred01 * 255.0), 0, 255).astype(np.uint8)
    if not cv2.imwrite(str(path), out):
        raise OSError(f"failed to write image: {path}")


@torch.inference_mode()
def run_one(wrapper, device: torch.device, in_path: Path, out_path: Path, family: str, align_factor: int) -> None:
    x01, dtype = read_gray01(in_path)
    x_pad, h0, w0 = pad_to_multiple(x01, int(align_factor))
    src = torch.from_numpy(x_pad).float().unsqueeze(0).unsqueeze(0).to(device)
    pred = wrapper(src, family=family).clamp(0.0, 1.0)
    pred_np = pred[0, 0].detach().cpu().numpy()[:h0, :w0]
    write_gray(out_path, pred_np, dtype)


def stage_names(profile_dir: Path, requested: str) -> list[str]:
    manifest = load_manifest(profile_dir / "manifest.json")
    available = sorted(manifest["count_by_stage"])
    if requested == "all":
        return available
    wanted = [x.strip() for x in requested.split(",") if x.strip()]
    missing = sorted(set(wanted) - set(available))
    if missing:
        raise ValueError(f"unknown stages: {missing}")
    return wanted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run R45 adapter reconstructions.")
    parser.add_argument("--profile", default="motion_val_unseen")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--adapter-checkpoint", type=Path, default=DEFAULT_ADAPTER)
    parser.add_argument("--recon-root", type=Path, default=DEFAULT_RECON_ROOT)
    parser.add_argument("--tag", default="r45_oracle_adapter_large_mixed")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--stages", default="all")
    parser.add_argument("--align-factor", type=int, default=16)
    parser.add_argument("--limit-per-stage", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.adapter_checkpoint.exists():
        raise FileNotFoundError(f"adapter checkpoint not found: {args.adapter_checkpoint}")
    profile_dir = args.data_root / args.profile
    stages = stage_names(profile_dir, args.stages)
    tag_root = args.recon_root / args.tag
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    jobs = []
    for stage in stages:
        in_dir = profile_dir / "src" / stage
        images = sorted(p for p in in_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
        if int(args.limit_per_stage) > 0:
            images = images[: int(args.limit_per_stage)]
        run_dir = tag_root / f"reconstruct_progress_{args.tag}_in_{stage}_{timestamp}"
        out_dir = run_dir / f"{args.profile}_{stage}_{args.tag}"
        jobs.append({"stage": stage, "family": family_from_stage(stage), "input_count": len(images), "output_dir": str(out_dir)})
    print(json.dumps({"adapter": str(args.adapter_checkpoint), "jobs": jobs}, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0

    device = resolve_device(args.device)
    wrapper = build_wrapper_from_checkpoint(base_checkpoint="", adapter_checkpoint=args.adapter_checkpoint, device=device)
    wrapper.eval()
    for job in jobs:
        stage = job["stage"]
        family = job["family"]
        in_dir = profile_dir / "src" / stage
        out_dir = Path(job["output_dir"])
        images = sorted(p for p in in_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
        if int(args.limit_per_stage) > 0:
            images = images[: int(args.limit_per_stage)]
        print(f"[R45][recon] stage={stage} family={family} count={len(images)}")
        for idx, path in enumerate(images, start=1):
            run_one(wrapper, device, path, out_dir / path.name, family, args.align_factor)
            if idx == 1 or idx == len(images) or idx % 50 == 0:
                print(f"  {idx}/{len(images)} {path.name}")
    manifest_path = tag_root / f"{args.tag}_recon_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "tag": args.tag,
                "profile": args.profile,
                "adapter_checkpoint": str(args.adapter_checkpoint),
                "jobs": jobs,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[R45] recon manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
