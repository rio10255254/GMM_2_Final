"""Use known generated optical references to separate restoration and damage."""
import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import *
from readouts import *
from training.data import Bank
from training.engine import create
import torch,pandas as pd

def main():
    out=ROOT/'results/structure_check';plan=load(out/'plan.json');bank=Bank();model,opt=create(1285002,'cuda',load(ROOT/'config/study.json'));cp=plan['checkpoint'];assert sha(cp['path'])==cp['sha256'];model.load_state_dict(torch.load(cp['path'],map_location='cpu')['model']);model.eval()
    rows=[];start=time.perf_counter()
    for entry in plan['generated_controls']:
        batch=bank.batch('test',entry['index'],'cuda')
        with torch.inference_mode():p=model(batch['source'])[0,0,96:224,96:224].cpu().numpy()
        raw=batch['source'][0,0,96:224,96:224].cpu().numpy();target=batch['target'][0,0,96:224,96:224].cpu().numpy()
        with np.load(bank.root/entry['arrays_path']) as d:material=d['material_core'][0]
        fg=material>.9;bg=material<.1
        if fg.sum()<16 or bg.sum()<16:raise ValueError('Reference lacks usable material regions; retain and investigate')
        foreground=float(np.median(target[fg]));background=float(np.median(target[bg]));bright=foreground>background;level=(foreground+background)/2
        reference=mask_diagnostics(target,raw,level,bright);candidate=mask_diagnostics(target,p,level,bright)
        row=dict(parent_id=entry['parent_id'],index=entry['index'],category=entry['category'],Raw_MAE_gray=float(np.mean(np.abs(raw-target))*255),candidate_MAE_gray=float(np.mean(np.abs(p-target))*255),maximum_change_gray=float(np.max(np.abs(p-raw))*255),threshold_gray=level*255,Raw=reference,candidate=candidate,reference_kind='known generated optical intensity, not real material qualification')
        rows.append(row)
        folder=out/'controls'/entry['parent_id'];folder.mkdir(parents=True,exist_ok=False);np.savez_compressed(folder/'core.npz',Raw=raw,target=target,output=p,material=material);save(folder/'measurements.json',row)
    save(out/'controls.json',rows)
    summaries=[]
    for category in sorted({x['category'] for x in rows}):
        g=[x for x in rows if x['category']==category]
        summaries.append(dict(category=category,parents=len(g),mean_Raw_MAE_gray=float(np.mean([x['Raw_MAE_gray'] for x in g])),mean_candidate_MAE_gray=float(np.mean([x['candidate_MAE_gray'] for x in g])),candidate_MAE_worse_parents=sum(x['candidate_MAE_gray']>x['Raw_MAE_gray'] for x in g),candidate_topology_mismatch_parents=sum(x['candidate']['reference_topology']!=x['candidate']['image_topology'] for x in g),Raw_topology_mismatch_parents=sum(x['Raw']['reference_topology']!=x['Raw']['image_topology'] for x in g),candidate_total_unmatched_lines=sum(x['candidate']['unmatched_reference_scanlines'] for x in g),worst_matched_crossing_error_px=max(x['candidate']['matched_crossing_error_px']['maximum_absolute'] or 0 for x in g)))
    save(out/'controls_summary.json',dict(completed=True,summaries=summaries,parents=len(rows),views_per_parent=1,training_updates=0,source=record(__file__),readout_source=record(Path(__file__).with_name('readouts.py')),seconds=time.perf_counter()-start))
    print(json.dumps(summaries),flush=True)

if __name__=='__main__':main()
