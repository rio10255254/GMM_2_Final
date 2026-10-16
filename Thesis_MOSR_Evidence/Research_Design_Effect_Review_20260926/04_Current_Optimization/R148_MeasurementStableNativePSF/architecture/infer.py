from __future__ import annotations
import argparse
from pathlib import Path
import cv2,numpy as np,torch
from model import Model
from utils import ROOT,load,model_config,setup,sha,save,now
def main():
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--checkpoint');p.add_argument('--device',default='cuda');a=p.parse_args();setup(1481001);complete=load(ROOT/'runs/formal_8192/training_complete.json');rec=complete['checkpoint'];path=Path(a.checkpoint) if a.checkpoint else Path(rec['path'])
 if not a.checkpoint and sha(path)!=rec['sha256']:raise RuntimeError('Formal checkpoint hash mismatch')
 cp=torch.load(path,map_location='cpu',weights_only=False);cfg=model_config();assert cp['model_config']==cfg and cp['checkpoint_kind']=='trained_model';m=Model(cfg,ROOT).to(a.device).eval();m.load_state_dict(cp['model']);raw=cv2.imread(a.input,cv2.IMREAD_UNCHANGED)
 if raw is None or raw.ndim!=2 or raw.dtype not in (np.uint8,np.uint16):raise ValueError('Use 8/16-bit grayscale input')
 scale=255 if raw.dtype==np.uint8 else 65535;x=torch.from_numpy(raw.astype(np.float32)[None,None]/scale).to(a.device)
 with torch.inference_mode():y=m.forward_tiled(x).cpu().numpy()[0,0]
 if not a.output.lower().endswith('.npz'):raise ValueError('Use .npz for FP32 output')
 with open(a.output,'xb') as h:np.savez_compressed(h,output=y)
 save(Path(a.output).with_suffix('.json'),dict(model=cfg['model_name'],checkpoint_sha256=sha(path),psf_mode='fixed_mean_at_inference',native_output=True,postprocessing=False,source=str(Path(a.input).resolve()),output_sha256=sha(a.output),completed_utc=now()));print('SAVED',a.output,flush=True)
if __name__=='__main__':main()
