"""Reconstruct all Raw-locked LSC frames for one shortlist checkpoint."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import torch
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from inference.run import load,tiled,read,write
PROJECT_ROOT = Path(__file__).resolve().parents[3]

CONFIG=Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/config/sequence_center9_50x20x.json'))
SEQUENCE_MAP={"50x_x_0p5um":"50x_0p5um","50x_x_1um":"50x_1um","20x_0p5um":"20x_0p5um","20x_1um":"20x_1um"}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',required=True);parser.add_argument('--output',required=True);parser.add_argument('--method',required=True);parser.add_argument('--device',default='cuda');args=parser.parse_args(); config=json.loads(CONFIG.read_text(encoding='utf-8-sig')); model=load(args.checkpoint,args.device if args.device!='auto' else ('cuda' if torch.cuda.is_available() else 'cpu')); root=Path(args.output).resolve(); root.mkdir(parents=True,exist_ok=False); records=[]
    for sequence,subfolder in SEQUENCE_MAP.items():
        raw_dir=Path(PROJECT_ROOT / config['sequences'][sequence]['raw_dir']); dest=root/subfolder;dest.mkdir(parents=True,exist_ok=True); files=sorted(raw_dir.glob('frame_*.bmp'))
        for index,source in enumerate(files,1):
            raw=read(source); tensor=torch.from_numpy(raw.astype(np.float32)/255)[None,None].to(next(model.parameters()).device)
            with torch.inference_mode(): output=tiled(model,tensor)[0,0].cpu().numpy()
            target=dest/source.name; write(target,np.rint(np.clip(output,0,1)*255).astype(np.uint8)); records.append({'sequence':sequence,'frame':source.name,'raw_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'recon_sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
        print(json.dumps({'sequence':sequence,'frames':len(files)}),flush=True)
    manifest={'schema_version':1,'status':'complete','method':args.method,'checkpoint':str(Path(args.checkpoint).resolve()),'checkpoint_sha256':hashlib.sha256(Path(args.checkpoint).read_bytes()).hexdigest(),'config_sha256':hashlib.sha256(CONFIG.read_bytes()).hexdigest(),'frame_count':len(records),'records':records,'population':'Raw-locked LSC development; no candidate frame selection'}; (root/'reconstruction_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');return 0


if __name__=='__main__':raise SystemExit(main())
