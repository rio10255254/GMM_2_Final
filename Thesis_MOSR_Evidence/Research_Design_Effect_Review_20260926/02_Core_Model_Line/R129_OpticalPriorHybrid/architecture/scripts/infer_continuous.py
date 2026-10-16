"""Reconstruct all201 native fields with the frozen trained R129 and validated execution."""
import os,sys,time,traceback,shutil
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from continuous_common import *
from sequence_inference import predict
import torch,cv2

def main():
    plan=load(OUT/'plan.json');checked=load(OUT/'staged_inference_verification.json');assert checked['passed']
    for item in plan['protected_sources']+[plan['checkpoint']]:assert sha(item['path'])==item['sha256'],item['path']
    assert sha(ROOT/'scripts/sequence_inference.py')==load(OUT/'staged_inference_plan.json')['implementation']['sha256']
    pkg=Path(plan['package']);sys.path.insert(0,str(pkg));import runtime
    from model.inference_policy import guard
    payload=torch.load(plan['checkpoint']['path'],map_location='cpu');runtime.verify_binding(payload['binding'])
    model,_=runtime.create('cuda');model.load_state_dict(payload['model'],strict=True);model.eval();start=time.perf_counter();records=[]
    save(OUT/'inference_started.json',dict(started_utc=now(),source=record(__file__),plan=record(OUT/'plan.json'),verification=record(OUT/'staged_inference_verification.json'),pid=os.getpid()))
    try:
        for n,frame in enumerate(plan['frames'],1):
            atomic(OUT/'inference_status.json',dict(status='running',finished=n-1,total=201,sequence=frame['sequence'],frame_index=frame['frame_index'],updated_utc=now(),pid=os.getpid()))
            assert sha(frame['source']['path'])==frame['source']['sha256']
            folder=OUT/'images'/frame['sequence']/f"frame_{frame['frame_index']:04d}";folder.mkdir(parents=True,exist_ok=False)
            tick=time.perf_counter();raw=cv2.imread(frame['source']['path'],0)
            reuse=frame['source']==checked['full_field_source']
            if reuse:
                assert sha(checked['probe']['path'])==checked['probe']['sha256'];d=np.load(checked['probe']['path']);value=d['output'];neural=d['neural_output'];npz=checked['probe']
            else:
                x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
                with torch.no_grad():result=predict(model,x,512);neural=result[0,0].cpu().numpy();value=guard(x,result)[0,0].cpu().numpy()
                assert value.shape==raw.shape and np.isfinite(value).all()
                np.savez_compressed(folder/'output_float.npz',output=value,neural_output=neural);npz=record(folder/'output_float.npz')
            image=np.rint(value*255).clip(0,255).astype(np.uint8);assert cv2.imwrite(str(folder/'reconstruction.png'),image)
            assert np.array_equal(cv2.imread(str(folder/'reconstruction.png'),0),image)
            rec=dict(sequence=frame['sequence'],frame_index=frame['frame_index'],source=frame['source'],shape=list(raw.shape),image=record(folder/'reconstruction.png'),output_float=npz,reused_validated_probe=reuse,seconds=time.perf_counter()-tick)
            save(folder/'record.json',rec);records.append(rec)
            print(n,'/201',frame['sequence'],frame['frame_index'],round(rec['seconds'],1),'seconds',flush=True)
            if shutil.disk_usage(OUT).free<10*2**30:raise RuntimeError('Storage reserve reached')
        runtime.verify_binding(payload['binding'])
        for item in plan['protected_sources']:assert sha(item['path'])==item['sha256']
        save(OUT/'inference_complete.json',dict(completed_utc=now(),source=record(__file__),plan=record(OUT/'plan.json'),frames=201,records=records,seconds=time.perf_counter()-start,no_training=True))
        atomic(OUT/'inference_status.json',dict(status='complete',finished=201,total=201,updated_utc=now()))
    except BaseException:
        atomic(OUT/'inference_status.json',dict(status='failed',finished=len(records),total=201,error=traceback.format_exc(),updated_utc=now()));raise
if __name__=='__main__':main()
