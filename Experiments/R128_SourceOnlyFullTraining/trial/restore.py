"""Single-candidate research inference; no model-choice menu or training."""
import os,sys,json,argparse,time
from pathlib import Path
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('MKL_NUM_THREADS','1')
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import load,save,sha,record,now
import numpy as np,cv2,torch,importlib.util
from model.network import Model,boundary_guard
from training.engine import setup
from train import verify_binding
spec=importlib.util.spec_from_file_location('r128_trial_verified_tiling',ROOT.parent/'R124_RealFirstPrototype/inference/tiling.py')
tiling=importlib.util.module_from_spec(spec);spec.loader.exec_module(tiling)

def main(input_path,output_dir,device='cuda'):
    input_path=Path(input_path).resolve();output_dir=Path(output_dir).resolve()
    if output_dir.exists():raise FileExistsError('Choose a new output folder; existing results are never replaced.')
    manifest=load(ROOT/'trial/manifest.json')
    for item in manifest['required_records']:
        if sha(item['path'])!=item['sha256']:raise RuntimeError('Trial model or implementation identity changed')
    verify_binding(load(ROOT/'config/frozen_training.json'))
    if input_path.suffix.lower() not in ['.bmp','.png']:raise ValueError('This trial accepts native8bit grayscale BMP/PNG optical images.')
    pixels=cv2.imread(str(input_path),cv2.IMREAD_UNCHANGED)
    if pixels is None or pixels.ndim!=2 or pixels.dtype!=np.uint8:raise ValueError('Expected an8bit grayscale optical image; no automatic color or bit-depth conversion.')
    if min(pixels.shape)<=160:raise ValueError('Image is too small for the validated context. Use the original full image.')
    before=sha(input_path);setup(1285002)
    if device=='cuda' and not torch.cuda.is_available():raise RuntimeError('CUDA unavailable; explicitly choose --device cpu if needed.')
    payload=torch.load(manifest['checkpoint']['path'],map_location='cpu')
    if payload['step']!=8192 or payload['arm']!='P' or payload['seed']!=1285002:raise RuntimeError('Wrong selected model')
    model=Model(payload['model_config']).to(device);model.load_state_dict(payload['model']);model.eval()
    raw=pixels.astype(np.float32)/np.float32(255);tensor=torch.from_numpy(raw)[None,None].to(device);start=time.perf_counter()
    with torch.inference_mode():
        neural=tiling.tiled_forward(model,tensor,core=256,halo=model.required_halo)
        applied,weight=boundary_guard(tensor,neural,model.required_halo,16)
    output=applied[0,0].cpu().numpy();unrestricted=neural[0,0].cpu().numpy();w=weight.cpu().numpy()
    assert output.shape==pixels.shape and np.isfinite(output).all()
    if sha(input_path)!=before:raise RuntimeError('Input changed during inference')
    output_dir.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(output_dir/'output_float.npz',output=output,neural_output=unrestricted)
    if not cv2.imwrite(str(output_dir/'reconstruction.png'),np.rint(output*255).clip(0,255).astype(np.uint8)):raise OSError('Image output failed')
    save(output_dir/'run_record.json',dict(created_utc=now(),role='normal_acquisition_research_trial_not_certified_measurement',input=record(input_path),checkpoint=manifest['checkpoint'],trial_manifest=record(ROOT/'trial/manifest.json'),output_shape=list(output.shape),output=record(output_dir/'output_float.npz'),preview=record(output_dir/'reconstruction.png'),device=device,seconds=time.perf_counter()-start,Raw_retained_fraction=float(np.mean(w==0)),fully_neural_fraction=float(np.mean(w==1)),automatic_brightness_qualification=False,source_unchanged=True,physical_accuracy_qualified=False))
    print(json.dumps(dict(output=str(output_dir/'reconstruction.png'),record=str(output_dir/'run_record.json'),research_trial=True)),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Restore one optical image with the single retained R128research candidate.')
    parser.add_argument('--input',required=True);parser.add_argument('--output-dir',required=True);parser.add_argument('--device',choices=['cuda','cpu'],default='cuda')
    args=parser.parse_args();main(args.input,args.output_dir,args.device)
