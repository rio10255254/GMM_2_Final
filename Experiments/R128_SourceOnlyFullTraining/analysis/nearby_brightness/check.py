"""One frozen candidate, prospectively named nearby brightness observations."""
import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,pandas as pd,torch
from training.engine import create
from evaluation.real import read_image,predict,sem_rows
from train import verify_binding

def main():
    out=ROOT/'results/nearby_brightness';out.mkdir(parents=True,exist_ok=False)
    verify_binding(load(ROOT/'config/frozen_training.json'))
    cp=ROOT/'runs/P_s1285002/checkpoints/step8192.pth'
    paths=[EXPS/f'R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack/{e}.bmp' for e in [13,14,15]]
    sources=[record(p) for p in paths]
    # This record precedes every new candidate output. No operating threshold
    # or performance-based definition of "normal" is introduced here.
    plan=dict(created_utc=now(),checkpoint=record(cp),sources=sources,exposures=[13,14,15],selection_reason='13is the existing normal-brightness anchor;14/15are the two immediately adjacent lower-brightness observations by historical ordering, selected without R128outcomes',study_role='Development sensitivity check, not qualification of all normal acquisitions or unseen confirmation',unchanged_readout=record(ROOT/'evaluation/real.py'),source=record(__file__),all36objects_retained=True,boundary_and_interior_reported_separately=True,automatic_rejection_threshold_defined=False,training_updates=0)
    save(out/'plan.json',plan)
    cfg=load(ROOT/'config/study.json');model,opt=create(1285002,'cuda',cfg)
    payload=torch.load(cp,map_location='cpu');assert payload['step']==8192;model.load_state_dict(payload['model']);model.eval()
    rows=[];summaries=[];start=time.perf_counter()
    for exp,source in zip([13,14,15],sources):
        raw=read_image(source);prediction,neural,w=predict(model,raw)
        folder=out/f'exposure{exp}';folder.mkdir()
        np.savez_compressed(folder/'output.npz',output=prediction,neural_output=neural)
        result=sem_rows(raw,prediction,exp)
        assert len(result)==36 and len({r['pillar'] for r in result})==36
        df=pd.DataFrame(result);df.to_csv(folder/'SEM_measurements.csv',index=False);rows+=result
        groups=[]
        for context,g in df.groupby('context_stratum'):
            groups.append(dict(context=context,objects=len(g),improved=int((g.direction=='improves').sum()),worsened=int((g.direction=='worsens').sum()),unmeasurable=int((g.direction=='unmeasurable').sum()),median_half_contrast_radius_change_px=float(g['level_0.5_median_radius_change_px'].median())))
        q=np.percentile(raw*255,[5,50,95])
        summary=dict(exposure=exp,objects=36,improved=int((df.direction=='improves').sum()),worsened=int((df.direction=='worsens').sum()),unmeasurable=int((df.direction=='unmeasurable').sum()),input_gray_p05_p50_p95=q.tolist(),groups=groups,source=source,output=record(folder/'output.npz'))
        if exp==13:
            old=ROOT/'runs/P_s1285002/evaluations/real_step8192/full_images/sem_optical_exposure13/output_float.npz'
            with np.load(old) as f:parity=float(np.max(np.abs(prediction-f['output'])))
            assert parity<2e-6;summary['old_final_output_parity_max']=parity
        summaries.append(summary);print(json.dumps(summary),flush=True)
    pd.DataFrame(rows).to_csv(out/'all_measurements.csv',index=False)
    verify_binding(load(ROOT/'config/frozen_training.json'))
    save(out/'summary.json',dict(completed=True,completed_utc=now(),plan=record(out/'plan.json'),summaries=summaries,total_rows=108,independent_physical_objects=36,training_updates=0,source_only_inputs=True,normal_operating_range_qualified=False,physical_accuracy_qualified=False,seconds=time.perf_counter()-start))

if __name__=='__main__':main()
