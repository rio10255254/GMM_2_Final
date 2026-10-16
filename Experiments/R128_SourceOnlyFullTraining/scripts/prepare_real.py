"""Verify actual real evaluator integration before any full-training updates."""
import sys,time,traceback
from common import *
sys.path.insert(0,str(ROOT))
import torch,numpy as np,cv2,pandas as pd
from training.engine import create,checkpoint,state_digest
from evaluation.real import evaluate,read_image,sem_rows,crossing_radii,predict,bidirectional

def main():
    cfg=load(ROOT/'config/study.json');start=time.perf_counter();identities={}
    out=ROOT/'results/initialization';out.mkdir(parents=True,exist_ok=False)
    # CPU initialization is identical to GPU initialization; the device transfer
    # occurs only after random parameter initialization in engine.create.
    for seed in cfg['model_seeds']:
        model,opt=create(seed,'cpu',cfg);model.eval()
        sample=torch.from_numpy(np.random.default_rng(seed).random((1,1,96,96)).astype(np.float32))
        with torch.inference_mode():assert torch.equal(model(sample),sample)
        identities[str(seed)]=dict(parameter_sha256=state_digest(model),neutral_output_exact=True,parameters=sum(p.numel() for p in model.parameters()),checkpoint=record(out/f'seed{seed}.pth') if (out/f'seed{seed}.pth').exists() else None)
        checkpoint(out/f'seed{seed}.pth',model,opt,0,'initialization_reference',seed,{'role':'fresh_initialization_preflight'})
        identities[str(seed)]['checkpoint']=record(out/f'seed{seed}.pth')
    save(ROOT/'config/initial_states.json',identities)
    # Baseline evaluator uses the actual fixed reader, all sources and all SEM
    # objects. Zero-update equivalence avoids redundant full-network tile runs.
    seed=cfg['model_seeds'][0];model,opt=create(seed,'cpu',cfg)
    summary=evaluate(model,ROOT/'results/real_baseline',identities[str(seed)]['checkpoint'],neutral=True)
    assert summary['SEM_rows']==72 and summary['motion_pairs']==6 and summary['motion_consistent']==6 and summary['maximum_motion_change_vs_Raw_px']==0.
    # Compare our exact copied native readout numerics to the existing Raw
    # results on source-only ray populations; no protected record is changed.
    table=pd.read_csv(R127/'results/native_size_comparison/measurements.csv')
    baseline=pd.read_csv(ROOT/'results/real_baseline/SEM_measurements.csv')
    old=table[table.method=='Raw'].drop_duplicates(['exposure','pillar'])
    joined=baseline.merge(old,on=['exposure','pillar'],suffixes=('_new','_old'))
    # Old common-ray masks could depend on all R126 candidates; only compare
    # populations that are actually identical in size.
    same=joined[joined.fixed_source_SEM_rays==joined.common_rays]
    error=float(np.max(np.abs(same.Raw_diameter_pitch_ratio_new-same.Raw_diameter_pitch_ratio_old))) if len(same) else None
    assert len(same)>0 and error<1e-6
    result=dict(passed=True,full_real_baseline=record(ROOT/'results/real_baseline/verification.json'),initial_states=record(ROOT/'config/initial_states.json'),same_population_R127_Raw_comparisons=len(same),maximum_R127_Raw_ratio_difference=error,all36_SEM_objects_per_exposure_retained=True,physical_accuracy_qualified=False,full_training_updates=0,seconds=time.perf_counter()-start,sources={str(p):sha(p) for p in [ROOT/'evaluation/real.py',R127/'scripts/motion_reader.py',R127/'scripts/motion_reader_v2.py',R127/'scripts/motion_reader_v3.py',R124/'inference/tiling.py']})
    save(ROOT/'results/real_evaluator_preflight.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
