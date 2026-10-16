"""Counterfactual gate selections on one fixed real frame, without changing saved model."""
import json,sys
from pathlib import Path
import cv2,numpy as np,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from utils import ROOT,load,sha
from model import Model
from utils import model_config

def main():
    index=int(sys.argv[1]) if len(sys.argv)>1 else 0
    record=load(ROOT/'runs/formal_8192/training_complete.json')['final_checkpoint']
    assert sha(record['path'])==record['sha256']
    cp=torch.load(record['path'],map_location='cpu',weights_only=False)
    model=Model(model_config(),ROOT).cuda().eval();model.load_state_dict(cp['model'],strict=True)
    frame=load(ROOT/'evaluation/capture_plan.json')['frames'][index]
    assert sha(frame['source']['path'])==frame['source']['sha256']
    raw=cv2.imread(frame['source']['path'],0)
    x=torch.from_numpy(raw.astype('float32')[None,None]/255).cuda()
    block=model.refiner.optics
    with torch.inference_mode():
        uniform=model(x)
        outputs=[]
        for selected in range(8):
            def force(module,args,out):
                v=torch.full_like(out,-30);v[:,selected,:,:]=30;return v
            h=block.gating.register_forward_hook(force)
            y=model(x);h.remove();outputs.append(y)
        pair=[]
        for i in range(8):
            for j in range(i):
                d=outputs[i]-outputs[j]
                pair.append(dict(i=i,j=j,rms_gray=float(d.square().mean().sqrt()*255),
                                 max_abs_gray=float(d.abs().max()*255)))
        relative=[]
        for i,y in enumerate(outputs):
            d=y-uniform
            relative.append(dict(i=i,rms_gray=float(d.square().mean().sqrt()*255),
                                 max_abs_gray=float(d.abs().max()*255)))
    result=dict(frame_index=index,run=frame['run'],position=frame['index'],
                checkpoint_sha256=record['sha256'],beta_effective=float(block.beta*block.beta_scale),
                max_candidate_pair_rms_gray=max(x['rms_gray'] for x in pair),
                max_candidate_pair_abs_gray=max(x['max_abs_gray'] for x in pair),
                max_single_vs_uniform_rms_gray=max(x['rms_gray'] for x in relative),
                pairwise=pair,relative_to_uniform=relative,no_saved_weights_modified=True)
    out=Path(__file__).with_name(f'psf_real_candidate_test{index:03d}.json')
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('pairwise','relative_to_uniform')},ensure_ascii=False))
if __name__=='__main__':main()
