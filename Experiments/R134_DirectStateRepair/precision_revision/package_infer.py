"""Separate exact measurement values from viewing images."""
from runtime import *
from precision_io import write_values
from model.inference_policy import guard
from verify_package import verify
import argparse,cv2
def main():
    p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,default=ROOT/'sample_inputs');p.add_argument('--output-name',default='trial');p.add_argument('--checkpoint',type=Path,default=ROOT/'weights/initial_r134p.pth');p.add_argument('--device',default='cuda');a=p.parse_args()
    if not a.output_name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in a.output_name):raise ValueError('Use a simple new output name')
    out=ROOT/'results/inference'/a.output_name
    if out.exists():raise FileExistsError('Output already exists')
    verify(False);state=torch.load(a.checkpoint,map_location='cpu')
    if 'binding' in state:verify_binding(state['binding'])
    elif sha(a.checkpoint)!=sha(ROOT/'weights/initial_r134p.pth'):raise ValueError('Checkpoint is not this packaged generation')
    m,_=create(a.device);m.load_state_dict(state['model'],strict=True);m.eval();sources=sorted(x for x in a.input_dir.iterdir() if x.suffix.lower() in ['.png','.bmp','.tif','.tiff']);assert sources and len({x.stem.lower() for x in sources})==len(sources);out.mkdir(parents=True)
    for source in sources:
        raw=cv2.imdecode(np.fromfile(source,np.uint8),cv2.IMREAD_UNCHANGED)
        if raw is None or raw.ndim!=2 or raw.dtype!=np.uint8 or min(raw.shape)<193:raise ValueError('Input must be original uint8 grayscale at least193pixels across')
        x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].to(a.device)
        with torch.no_grad():v=guard(x,m(x))[0,0].cpu().numpy()
        exact,preview,high=write_values(out,source.stem,v);save(out/(source.stem+'.json'),dict(input_path=str(source.resolve()),input_sha256=sha(source),checkpoint_path=str(a.checkpoint.resolve()),checkpoint_sha256=sha(a.checkpoint),measurement=record(exact),preview_only=record(preview),approximate_high_precision_view=record(high),model_promoted=False));print('Written measurement values and previews',source.name,flush=True)
if __name__=='__main__':main()
