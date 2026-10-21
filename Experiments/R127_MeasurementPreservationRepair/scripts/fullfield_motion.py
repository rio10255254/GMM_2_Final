"""Same frozen weights, all full source frames, qualified readout scope explicit."""
import cv2,time,torch,pandas as pd
from common import *
sys.path.insert(0,str(R124));sys.path.insert(0,str(R125))
from model.calibration import load_observation
from prototype.factorized_observation import from_observation
from prototype.network import build_model
from inference.tiling import tiled_forward
from evaluate_real_motion import bidirectional

def main():
    torch.set_num_threads(8);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.backends.cudnn.allow_tf32=True;torch.backends.cuda.matmul.allow_tf32=False
    panel=json.loads((R125/'results/real_panel_v2/frozen_panel.json').read_text());previous=json.loads((ROOT/'results/real_motion_v4/measurements.json').read_text());raw={r['sequence']:r for r in previous['global_Raw']};out=ROOT/'results/fullfield_motion';out.mkdir(parents=True,exist_ok=False);rows=[];outputs=[];start=time.perf_counter()
    for arm in ['P','Q']:
        for seed in [1265001,1265002]:
            cp=R126/'runs'/f'photo_{arm}_s{seed}'/'step0128.pth';payload=torch.load(cp,map_location='cpu',weights_only=True);model=build_model(payload['model_config'],from_observation(load_observation(R125/'config/real_observation_v2.json'),checkpoint_ops=False));learned={k:v for k,v in payload['model_state'].items() if not k.startswith('observation.')};loaded=model.load_state_dict(learned,strict=False);assert not loaded.unexpected_keys and all(x.startswith('observation.') for x in loaded.missing_keys);model=model.cuda().eval()
            for item in panel['motion_pairs']:
                seq=item['sequence'];pair=[];core_errors=[]
                for frame,source in enumerate(item['sources']):
                    assert sha(source['path'])==source['sha256'];image=(cv2.imread(source['path'],0).astype(float)/255).astype(np.float32);tensor=torch.from_numpy(image)[None,None].cuda()
                    with torch.inference_mode():prediction=tiled_forward(model,tensor,core=256,halo=model.required_halo)[0,0].cpu().numpy()
                    path=out/f'{arm}_s{seed}'/seq/f'frame{frame}.npz';path.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(path,output=prediction);outputs.append(dict(arm=arm,seed=seed,sequence=seq,frame=frame,source=source,checkpoint=record(cp),output=record(path)))
                    x0,y0,x1,y1=item['core_xyxy'];lx,ly,ux,uy=item['core_in_context_xyxy'];saved=R126/'results'/f'real_{arm}_s{seed}_step0128'/'motion'/seq/f'frame{frame}/output_float.npz'
                    with np.load(saved) as d:old=d['output'][ly:uy,lx:ux]
                    err=float(np.max(np.abs(prediction[y0:y1,x0:x1]-old)));core_errors.append(err);pair.append(prediction.astype(float))
                    print(json.dumps(dict(arm=arm,seed=seed,sequence=seq,frame=frame,old_core_max_difference=err,seconds=time.perf_counter()-start)),flush=True)
                measurement=bidirectional(*pair);g=raw[seq];diff=float(np.hypot(measurement['forward']['dx']-g['forward']['dx'],measurement['forward']['dy']-g['forward']['dy'])) if measurement['valid'] and g['valid'] else None;valid=bool(diff is not None and diff<=.5);row=dict(arm=arm,seed=seed,sequence=seq,measurement=measurement,source_Raw=g,reportable_fullfield_translation=valid,fullfield_change_vs_Raw=diff,old_core_parity_max=max(core_errors),old_core_parity_passed=max(core_errors)<=3e-6,physical_accuracy_qualified=False);rows.append(row)
                save(out/'progress.json',dict(completed_pairs=len(rows),outputs=len(outputs),seconds=time.perf_counter()-start),False)
            del model
    save(out/'measurements.json',dict(rows=rows,outputs=outputs,source_Raw_measurements=record(ROOT/'results/real_motion_v4/measurements.json'),protocol=record(ROOT/'config/fullfield_motion_protocol.json')))
    flat=[dict(arm=r['arm'],seed=r['seed'],sequence=r['sequence'],accepted=r['reportable_fullfield_translation'],dx=r['measurement']['forward']['dx'],dy=r['measurement']['forward']['dy'],vs_Raw_px=r['fullfield_change_vs_Raw'],cycle_error=r['measurement']['cycle_error'],old_core_max_difference=r['old_core_parity_max']) for r in rows];pd.DataFrame(flat).to_csv(out/'summary.csv',index=False)
    result=dict(completed_model_pairs=len(rows),new_fullfield_outputs=len(outputs),accepted_pairs=sum(r['reportable_fullfield_translation'] for r in rows),maximum_accepted_Raw_difference=max((r['fullfield_change_vs_Raw'] for r in rows if r['reportable_fullfield_translation']),default=None),maximum_old_core_parity_error=max(r['old_core_parity_max'] for r in rows),all_old_core_parity_passed=all(r['old_core_parity_passed'] for r in rows),new_weights_or_optimizer_updates=False,new_acquisition=False,physical_stage_truth_available=False,model_adopted=False,seconds=time.perf_counter()-start)
    save(out/'verification.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
