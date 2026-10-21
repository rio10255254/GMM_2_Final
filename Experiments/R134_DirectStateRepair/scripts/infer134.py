from pathlib import Path
import sys,argparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rt import *
from tiled import tiled_prior
import cv2

def predict(model,x):
    with torch.no_grad():value=model(x,prior_runner=lambda p,f:tiled_prior(p,f,512,16))
    h,w=x.shape[-2:];y=torch.arange(h,device=x.device)[:,None];z=torch.arange(w,device=x.device)[None,:];d=torch.minimum(torch.minimum(y,h-1-y),torch.minimum(z,w-1-z));weight=((d-16)/16).clamp(0,1)
    return x+(value-x)*weight

def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args();cp=Path(a.checkpoint).resolve();src=Path(a.input).resolve();out=Path(a.output).resolve()
    if out.exists() or out.with_suffix('.json').exists():raise FileExistsError('Use new output files')
    verify();payload=torch.load(cp,map_location='cpu');assert payload['arm'] in ['A','C'];m=create(payload['arm'],payload['seed']);m.load_state_dict(payload['model'],strict=True);m.eval()
    raw=cv2.imdecode(np.fromfile(src,np.uint8),0);assert raw is not None and min(raw.shape)>=193;x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda();value=predict(m,x)[0,0].cpu().numpy();image=np.rint(value*255).clip(0,255).astype(np.uint8);out.parent.mkdir(parents=True,exist_ok=True);ok,b=cv2.imencode('.png',image);assert ok
    with out.open('xb') as f:f.write(b.tobytes())
    save(out.with_suffix('.json'),dict(checkpoint=record(cp),source=record(src),image=record(out),arm=payload['arm'],training_step=payload['step'],guard=16,transition=16,scope='Research checkpoint; this entry does not certify model eligibility'))
    print('R134 inference written',str(out),flush=True)
if __name__=='__main__':main()
