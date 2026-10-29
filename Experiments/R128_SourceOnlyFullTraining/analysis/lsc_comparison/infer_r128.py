"""Full-field inference for the frozen LSC frame list; no training."""
import os,sys,time
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import cv2,numpy as np,torch
from model.network import Model
from training.engine import setup
from train import verify_binding
from evaluation.real import read_image,predict
PROJECT_ROOT = Path(__file__).resolve().parents[4]

def main():
    out=ROOT/'results/lsc_comparison';plan=load(out/'plan.json');verify_binding(load(ROOT/'config/frozen_training.json'))
    cp=plan['checkpoint_R128'];assert sha(str(PROJECT_ROOT / cp['path']))==cp['sha256'];setup(1285002)
    payload=torch.load(str(PROJECT_ROOT / cp['path']),map_location='cpu');assert payload['step']==8192 and payload['seed']==1285002 and payload['arm']=='P'
    model=Model(payload['model_config']).to('cuda');model.load_state_dict(payload['model']);model.eval()
    save(out/'inference_started.json',dict(started_utc=now(),plan=record(out/'plan.json'),source=record(__file__),checkpoint=cp,pid=os.getpid()))
    start=time.perf_counter();records=[]
    for n,frame in enumerate(plan['frames'],1):
        folder=out/'R128_images'/frame['sequence']/f"frame_{frame['frame_index']:04d}";folder.mkdir(parents=True,exist_ok=False)
        raw=read_image(frame['source']);reused=frame['R128_reuse']
        if reused:
            assert sha(str(PROJECT_ROOT / reused['path']))==reused['sha256']
            with np.load(str(PROJECT_ROOT / reused['path'])) as f:applied=f['output'];neural=f['neural_output']
            npz=reused
        else:
            applied,neural,w=predict(model,raw)
            np.savez_compressed(folder/'output_float.npz',output=applied,neural_output=neural)
            npz=record(folder/'output_float.npz')
        assert applied.shape==raw.shape and np.isfinite(applied).all()
        u8=np.rint(applied*255).clip(0,255).astype(np.uint8)
        assert cv2.imwrite(str(folder/'reconstruction.png'),u8)
        assert np.array_equal(cv2.imread(str(folder/'reconstruction.png'),0),u8)
        result=dict(sequence=frame['sequence'],frame_index=frame['frame_index'],source=frame['source'],image=record(folder/'reconstruction.png'),output_float=npz,reused=bool(reused),shape=list(raw.shape))
        save(folder/'record.json',result);records.append(result)
        print(json.dumps(dict(finished=n,total=len(plan['frames']),sequence=frame['sequence'],frame=frame['frame_index'],reused=bool(reused),elapsed_seconds=round(time.perf_counter()-start,1))),flush=True)
    verify_binding(load(ROOT/'config/frozen_training.json'))
    save(out/'inference_complete.json',dict(completed_utc=now(),outputs=records,plan=record(out/'plan.json'),source=record(__file__),seconds=time.perf_counter()-start))

if __name__=='__main__':main()
