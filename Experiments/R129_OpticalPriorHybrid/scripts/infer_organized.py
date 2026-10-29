"""Run the organized R129 with the same fixed D weights and output policy."""
import os,sys,argparse
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from common import *
import cv2,numpy as np,torch
from model.organized import Hybrid
from model.organized.inference_policy import guard
from run_pilot import setup
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--device',choices=['cuda','cpu'],default='cuda')
    args=parser.parse_args()
    if args.output.suffix.lower()!='.png':parser.error('Output must be PNG')
    if args.output.exists() or args.output.with_suffix('.json').exists():parser.error('Output already exists')
    raw=cv2.imdecode(np.fromfile(args.input,np.uint8),cv2.IMREAD_UNCHANGED)
    if raw is None or raw.ndim!=2 or raw.dtype!=np.uint8 or min(raw.shape)<193:parser.error('Use 8-bit grayscale, at least 193 by 193')
    pilot=load(ROOT/'config/plan.json');organization=load(ROOT/'config/organization_plan.json')
    assert load(ROOT/'results/organization/verification.json')['passed']
    cp=load(ROOT/'runs/D/summary.json')['checkpoint']
    for item in [cp,pilot['calibration'],*organization['organized_files']]:
        if sha(str(PROJECT_ROOT / item['path']))!=item['sha256']:raise RuntimeError('Recorded source changed: '+str(PROJECT_ROOT / item['path']))
    setup(pilot['common_seed']);bank=np.load(str(PROJECT_ROOT / pilot['calibration']['path']))
    model=Hybrid(torch.from_numpy(bank['mean']),torch.from_numpy(bank['candidates'])).to(args.device)
    model.load_state_dict(torch.load(cp['path'],map_location=args.device)['model'],strict=True);model.eval()
    x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].to(args.device)
    with torch.no_grad():output=guard(x,model(x))[0,0].cpu().numpy()
    ok,encoded=cv2.imencode('.png',np.rint(output*255).clip(0,255).astype(np.uint8));assert ok
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb') as f:f.write(encoded.tobytes())
    save(args.output.with_suffix('.json'),dict(created_utc=now(),source=record(__file__),input=record(args.input),output=record(args.output),checkpoint=cp,organized_modules=organization['organized_files'],device=args.device,shape=list(raw.shape),status='Behavior-preserving organization of the 24-update R129 D prototype; no model promotion'))
    print('Saved organized R129 output:',args.output)

if __name__=='__main__':main()
