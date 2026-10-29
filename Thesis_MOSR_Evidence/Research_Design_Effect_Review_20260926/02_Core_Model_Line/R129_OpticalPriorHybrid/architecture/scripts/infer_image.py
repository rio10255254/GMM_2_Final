"""Run the one retained R129 D prototype on an 8-bit grayscale image."""
import os, sys, argparse
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from common import *
import cv2,numpy as np,torch
from model.hybrid_v2 import Hybrid
from run_pilot import setup
from evaluate_real import guard
PROJECT_ROOT = Path(__file__).resolve().parents[6]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--device',default='cuda',choices=['cuda','cpu'])
    args=parser.parse_args()
    if args.output.suffix.lower()!='.png':parser.error('Output must be a PNG file')
    if args.output.exists() or args.output.with_suffix('.json').exists():parser.error('Output already exists; choose a new path')
    raw=cv2.imdecode(np.fromfile(args.input,np.uint8),cv2.IMREAD_UNCHANGED)
    if raw is None or raw.ndim!=2 or raw.dtype!=np.uint8 or min(raw.shape)<193:
        parser.error('Use an 8-bit grayscale input at least 193 by 193 pixels')
    plan=load(ROOT/'config/plan.json');impl=load(ROOT/'config/implementation_v2.json')
    cp=load(ROOT/'runs/D/summary.json')['checkpoint']
    for item in [cp,plan['calibration'],impl['active_implementation']]:
        if sha(str(PROJECT_ROOT / item['path']))!=item['sha256']:raise RuntimeError('Source mismatch: '+str(PROJECT_ROOT / item['path']))
    setup(plan['common_seed']);bank=np.load(str(PROJECT_ROOT / plan['calibration']['path']))
    model=Hybrid(torch.from_numpy(bank['mean']),torch.from_numpy(bank['candidates'])).to(args.device)
    model.load_state_dict(torch.load(cp['path'],map_location=args.device)['model']);model.eval()
    x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].to(args.device)
    with torch.no_grad():out=guard(x,model(x))[0,0].cpu().numpy()
    output=np.rint(out*255).clip(0,255).astype(np.uint8)
    ok,encoded=cv2.imencode('.png',output);assert ok
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb') as f:f.write(encoded.tobytes())
    save(args.output.with_suffix('.json'),dict(created_utc=now(),input=record(args.input),output=record(args.output),checkpoint=cp,implementation=impl['active_implementation'],device=args.device,status='24-update prototype; not a qualified replacement',guard='Raw within distance 80; transition 16',shape=list(raw.shape)))
    print('Saved R129 D prototype output: '+str(args.output))

if __name__=='__main__':main()
