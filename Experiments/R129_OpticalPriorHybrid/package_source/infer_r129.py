"""Single model, same-size reconstruction; default preserves the supplied initial model."""
import argparse
import numpy as np,cv2,torch
from runtime import *
from model.inference_policy import guard
def main():
    p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,default=ROOT/'sample_inputs');p.add_argument('--output-name',default='trial');p.add_argument('--checkpoint',type=Path,default=ROOT/'weights/initial_r129.pth');p.add_argument('--device',default='cuda');a=p.parse_args()
    if not a.output_name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in a.output_name):p.error('Use a simple new output name')
    out=ROOT/'results/inference'/a.output_name;out.mkdir(parents=True,exist_ok=False)
    m,_=create(a.device);state=torch.load(a.checkpoint,map_location=a.device);m.load_state_dict(state['model'],strict=True);m.eval()
    inputs=sorted(x for x in a.input_dir.iterdir() if x.suffix.lower() in ['.png','.bmp','.tif','.tiff'])
    if not inputs:raise ValueError('No images in input folder')
    if len({x.stem.lower() for x in inputs})!=len(inputs):raise ValueError('Input names would collide')
    for path in inputs:
        raw=cv2.imdecode(np.fromfile(path,np.uint8),cv2.IMREAD_UNCHANGED)
        if raw is None or raw.ndim!=2 or raw.dtype!=np.uint8 or min(raw.shape)<193:raise ValueError('Use 8-bit grayscale images at least 193 by 193')
        x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].to(a.device)
        with torch.no_grad():value=guard(x,m(x))[0,0].cpu().numpy()
        ok,data=cv2.imencode('.png',np.rint(value*255).clip(0,255).astype(np.uint8));assert ok
        target=out/(path.stem+'.png')
        with target.open('xb') as f:f.write(data.tobytes())
        save(out/(path.stem+'.json'),dict(input_path=str(path.resolve()),input_sha256=sha(path),output=record(target),checkpoint_path=str(a.checkpoint.resolve()),checkpoint_sha256=sha(a.checkpoint),same_size=True,model_promoted=False))
        print('Reconstructed',path.name,flush=True)
if __name__=='__main__':main()
