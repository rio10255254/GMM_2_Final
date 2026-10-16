"""Matched small scratch experiment for the learnability of distance sign."""
from pathlib import Path
import json
import sys
import torch
from torch.utils.data._utils.collate import default_collate
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from training.dataset import Scenes,flatten
from training.objectives import geometry_terms,per_scene
from model.network import build_model

def orient_batch(dataset,indices,oriented):
    batch=flatten(default_collate([dataset[i] for i in indices]),'cuda')
    if oriented:
        signs=torch.tensor([dataset.records[i]['polarity'] for i in indices],device='cuda').repeat_interleave(2)
        batch['sdf']=batch['sdf']*signs[:,None,None,None]
    return batch

def run():
    torch.set_num_threads(4)
    train=Scenes('train',limit=128,distance_orientation='foreground');validation=Scenes('validation',limit=48,distance_orientation='foreground')
    config=json.loads((ROOT/'config/experiment.json').read_text())
    result=[]
    for oriented in (False,True):
        torch.manual_seed(1185001);model=build_model().cuda()
        for name,parameters in model.groups().items():
            for p in parameters:p.requires_grad_(name=='geometry')
        optimizer=torch.optim.AdamW(model.groups()['geometry'],lr=.0003)
        for step in range(128):
            indices=[(step*4+j)%len(train) for j in range(4)]
            batch=orient_batch(train,indices,oriented)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast('cuda',dtype=torch.bfloat16):
                d=model.forward_details(batch['source']);terms=geometry_terms(d,batch)
                loss=sum(config['training']['weights'][k]*v for k,v in terms.items())
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);optimizer.step()
        values=[]
        with torch.inference_mode():
            for start in range(0,len(validation),4):
                b=orient_batch(validation,list(range(start,min(len(validation),start+4))),oriented)
                d=model.forward_details(b['source'])
                values.extend(per_scene((d.sdf-b['sdf'].clamp(-16,16)).abs(),torch.exp(-b['sdf'].abs()/3)).tolist())
        result.append({'brightness_oriented_distance':oriented,'updates':128,'validation_sdf_mae_px':sum(values)/len(values)})
        del model,optimizer;torch.cuda.empty_cache()
        print(json.dumps(result[-1]),flush=True)
    (ROOT/'validation/orientation_probe.json').write_text(json.dumps({'status':'complete','matched_seed':1185001,'results':result},indent=2))
if __name__=='__main__':run()
