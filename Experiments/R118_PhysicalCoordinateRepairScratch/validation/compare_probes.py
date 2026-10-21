"""Compare finished probes on the same physical development observations."""
from pathlib import Path
import json
import sys
import numpy as np
import torch
from torch.utils.data._utils.collate import default_collate
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from inference.run import load
from training.dataset import Scenes,flatten
from training.objectives import location_xy,gradient,per_scene

def main():
    torch.set_num_threads(4);ds=Scenes('validation',epoch=0,limit=96)
    candidates={'with_detail':ROOT/'runs/repaired_position_with_detail/weights/epoch_012.pth',
                'without_detail':ROOT/'runs/matched_without_detail/weights/epoch_012.pth',
                'final_physical_repair':ROOT/'runs/verified_physical_repair/weights/epoch_012.pth'}
    summary={}
    for name,checkpoint in candidates.items():
        if not checkpoint.is_file():continue
        model=load(checkpoint,'cuda');rows=[]
        with torch.inference_mode():
            for start in range(0,len(ds),4):
                b=flatten(default_collate([ds[i] for i in range(start,min(start+4,len(ds)))]),'cuda')
                out=model(b['source']);raw_xy,confidence=location_xy(b['source'],b['target']);pred_xy,_=location_xy(out,b['target'])
                pair_raw=(raw_xy[1::2]-raw_xy[0::2]);pair_pred=(pred_xy[1::2]-pred_xy[0::2])
                error=per_scene((out-b['target']).abs())*255;raw_error=per_scene((b['source']-b['target']).abs())*255
                rg=gradient(b['source']-b['target']);pg=gradient(out-b['target'])
                ge=per_scene(pg[0].abs()+pg[1].abs());gr=per_scene(rg[0].abs()+rg[1].abs())
                for i in range(b['scenes']):
                    record=ds.records[start+i]
                    if record['role'] in ('flat_negative','identity'):continue
                    rows.append({'scene':record['scene_index'],'family':record['family'],
                                 'raw_pair_dx_error':float(pair_raw[i,0]),'raw_pair_dy_error':float(pair_raw[i,1]),
                                 'model_pair_dx_error':float(pair_pred[i,0]),'model_pair_dy_error':float(pair_pred[i,1]),
                                 'raw_mae_gray':float(raw_error[i*2:i*2+2].mean()),'model_mae_gray':float(error[i*2:i*2+2].mean()),
                                 'raw_gradient_error':float(gr[i*2:i*2+2].mean()),'model_gradient_error':float(ge[i*2:i*2+2].mean())})
        def mean(k):return float(np.mean([r[k] for r in rows]))
        summary[name]={'scenes':len(rows),'raw_mae_gray':mean('raw_mae_gray'),'model_mae_gray':mean('model_mae_gray'),
                       'raw_gradient_error':mean('raw_gradient_error'),'model_gradient_error':mean('model_gradient_error'),
                       'raw_pair_dx_sd_px':float(np.std([r['raw_pair_dx_error'] for r in rows],ddof=1)),
                       'model_pair_dx_sd_px':float(np.std([r['model_pair_dx_error'] for r in rows],ddof=1)),
                       'raw_pair_dy_sd_px':float(np.std([r['raw_pair_dy_error'] for r in rows],ddof=1)),
                       'model_pair_dy_sd_px':float(np.std([r['model_pair_dy_error'] for r in rows],ddof=1)),
                       'rows':rows}
        del model;torch.cuda.empty_cache()
    out=ROOT/'results/probe_comparison.json';out.parent.mkdir(exist_ok=True)
    payload={'status':'complete','same_seed_data_and_update_budget':True,'final_arm_additional_change':'physical fine-reliability weighting',
             'numerical_determinism':'GPU kernels may not be bit-identical',
             'scope':'Synthetic two-observation repeatability, not real-sequence LSC or external GMF','results':summary}
    out.write_text(json.dumps(payload,indent=2,allow_nan=False))
    print(json.dumps({k:{a:b for a,b in v.items() if a!='rows'} for k,v in summary.items()},indent=2))
if __name__=='__main__':main()
