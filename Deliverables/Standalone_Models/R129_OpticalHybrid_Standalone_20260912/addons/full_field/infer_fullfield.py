"""Full-field trained R129 inference using global optics and context-preserving local computation."""
import os,sys,argparse,time
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(PACKAGE))
import runtime as rt
import torch,numpy as np,cv2
from model.inference_policy import guard
from sequence_inference import predict
def main():
    p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,default=PACKAGE/'sample_inputs');p.add_argument('--output-name',default='full_'+str(time.time_ns()));p.add_argument('--checkpoint',type=Path,default=PACKAGE/'results/training/r129_long_01/checkpoints/step08192.pth');a=p.parse_args()
    if not a.output_name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in a.output_name):p.error('Use a simple new output name')
    manifest=rt.load(Path(__file__).parent/'ADDON_MANIFEST.json')
    for name,h in manifest['files'].items():
        if rt.sha(Path(__file__).parent/name)!=h:raise RuntimeError('Addon source changed')
    model,_=rt.create('cuda');state=torch.load(a.checkpoint,map_location='cuda');model.load_state_dict(state['model'],strict=True);model.eval()
    out=PACKAGE/'results/inference'/a.output_name;out.mkdir(parents=True,exist_ok=False)
    paths=sorted(x for x in a.input_dir.iterdir() if x.suffix.lower() in ['.bmp','.png','.tif','.tiff'])
    if not paths:raise ValueError('No input images')
    if len({x.stem.lower() for x in paths})!=len(paths):raise ValueError('Input names collide')
    for path in paths:
        raw=cv2.imdecode(np.fromfile(path,np.uint8),cv2.IMREAD_UNCHANGED)
        if raw is None or raw.ndim!=2 or raw.dtype!=np.uint8 or min(raw.shape)<193:raise ValueError('Use native 8-bit grayscale at least193x193')
        x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
        with torch.no_grad():result=guard(x,predict(model,x,512))[0,0].cpu().numpy()
        value=np.rint(result*255).clip(0,255).astype(np.uint8);ok,data=cv2.imencode('.png',value);assert ok
        output=out/(path.stem+'.png')
        with output.open('xb') as f:f.write(data.tobytes())
        rt.save(out/(path.stem+'.json'),dict(input_path=str(path.resolve()),input_sha256=rt.sha(path),output=rt.record(output),checkpoint_path=str(a.checkpoint.resolve()),checkpoint_sha256=rt.sha(a.checkpoint),full_native_shape=list(raw.shape),core=512,halo=16,global_optics_and_quality=True,addon_manifest_sha256=rt.sha(Path(__file__).parent/'ADDON_MANIFEST.json'),model_promoted=False))
        print('Reconstructed',path.name,flush=True)
if __name__=='__main__':main()
