"""Use only the fresh V42 endpoint for a reproducible native-image reconstruction."""
import sys,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import cv2
from output_guard import guard
def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    verify_frozen();cp=ROOT/'runs/v42_clean/checkpoints/step04096.pth';m,_=create();payload=torch.load(cp,map_location='cuda');assert payload['step']==4096;m.load_state_dict(payload['model']);m.eval()
    raw=cv2.imdecode(np.fromfile(a.input,np.uint8),cv2.IMREAD_UNCHANGED)
    if raw.ndim!=2 or raw.dtype!=np.uint8:raise ValueError('Use8bitgrayscale')
    x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
    with torch.no_grad():output=guard(x,m(x))[0,0].cpu().numpy()
    a.output.parent.mkdir(parents=True,exist_ok=True);ok,encoded=cv2.imencode('.png',np.rint(output*255).clip(0,255).astype(np.uint8));assert ok
    with a.output.open('xb') as f:f.write(encoded.tobytes())
    save(a.output.with_suffix('.json'),dict(utc=now(),source=record(__file__),checkpoint=record(cp),input=record(a.input),output=record(a.output),epoch=32,no_R129_change=True))
    print('Saved',a.output)
if __name__=='__main__':main()
