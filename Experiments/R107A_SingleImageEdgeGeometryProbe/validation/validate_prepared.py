"""Validate the prepared R107 package, data, model and tiled path."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT / "model")); sys.path.insert(0, str(ROOT / "training")); sys.path.insert(0, str(ROOT / "inference"))
from r107_model import build_model, count_parameters  # noqa: E402
from r107_dataset import R107Dataset  # noqa: E402
from reconstruct import reconstruct_full_reference, reconstruct_tensor  # noqa: E402


def sha256(path: Path) -> str:
    digest=hashlib.sha256();
    with path.open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""):digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser=argparse.ArgumentParser();parser.add_argument("--checkpoint",default="");parser.add_argument("--allow-partial-data",action="store_true");parser.add_argument("--output",default=str(ROOT/"validation"/"prepared_validation.json"));args=parser.parse_args()
    manifest_path=ROOT/CONFIG["data"]["package_root"]/"manifest.json";manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["status"]!="complete" and not args.allow_partial_data:raise RuntimeError("Dataset is not complete")
    device=torch.device("cuda:0" if torch.cuda.is_available() else "cpu");model=build_model().to(device)
    checkpoint_info=None
    if args.checkpoint:
        checkpoint=torch.load(args.checkpoint,map_location=device,weights_only=False);model.load_state_dict(checkpoint["model"],strict=True);checkpoint_info={"path":str(args.checkpoint),"epoch":checkpoint.get("epoch"),"sha256":sha256(Path(args.checkpoint))}
    model.eval();dataset=R107Dataset("validation",epoch=0,limit=min(8,max(1,manifest["counts"].get("validation",1))));sample=dataset[0];source=sample["source"].to(device);details=model.forward_details(source)
    finite=all(bool(torch.isfinite(getattr(details,field)).all()) for field in details.__dataclass_fields__)
    # A centered logistic edge has probability 0.5 at its midpoint.  Every
    # analytic width transform must leave that value unchanged.
    width=256;coordinate=torch.arange(width,device=device,dtype=torch.float32)-127.5;edge=torch.sigmoid(coordinate/1.8)[None,None,None].expand(1,1,256,-1);edge_details=model.forward_details(edge);midpoint_input=float(edge[0,0,:,127:129].mean().cpu());midpoint_render=float(edge_details.rendered_edge[0,0,:,127:129].mean().cpu())
    large=torch.rand((1,1,777,913),device=device,generator=torch.Generator(device=device).manual_seed(107));tiled=reconstruct_tensor(model,large,core_size=256,halo=int(CONFIG["inference"]["halo"]));full=reconstruct_full_reference(model,large,core_size=256,halo=int(CONFIG["inference"]["halo"]));delta=(tiled-full).abs()*255.0
    identity_mae=float((details.output[1:2]-source[1:2]).abs().mean().cpu()*255.0) if source.shape[0]>1 else 0.0
    result={
        "status":"complete","device":str(device),"dataset_status":manifest["status"],"dataset_counts":manifest["counts"],"dataset_manifest_sha256":sha256(manifest_path),"parameters":count_parameters(model),"checkpoint":checkpoint_info,
        "checks":{"forward_finite":finite,"output_shape_matches":list(details.output.shape)==list(source.shape),"fixed_midpoint_input":midpoint_input,"fixed_midpoint_render":midpoint_render,"fixed_midpoint_abs_error":abs(midpoint_render-midpoint_input),"identity_mae_gray":identity_mae,"full_tile_max_abs_gray":float(delta.max().cpu()),"full_tile_mean_abs_gray":float(delta.mean().cpu())},
        "passed":bool(finite and list(details.output.shape)==list(source.shape) and abs(midpoint_render-midpoint_input)<0.01 and float(delta.max().cpu())<0.01)
    }
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2),encoding="utf-8");print(json.dumps(result),flush=True);return 0 if result["passed"] else 2


if __name__=="__main__":raise SystemExit(main())

