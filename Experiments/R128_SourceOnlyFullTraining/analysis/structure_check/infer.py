"""Run the frozen, preselected image list; reuse verified original outputs."""
import sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,torch
from training.engine import create
from train import verify_binding
from evaluation.real import read_image,predict

def main():
    out=ROOT/'results/structure_check';plan=load(out/'plan.json');verify_binding(load(ROOT/'config/frozen_training.json'))
    model,opt=create(1285002,'cuda',load(ROOT/'config/study.json'));cp=plan['checkpoint'];assert sha(cp['path'])==cp['sha256'];payload=torch.load(cp['path'],map_location='cpu');model.load_state_dict(payload['model']);model.eval()
    results=[];start=time.perf_counter()
    for source in plan['sources']:
        if source['reuse_output']:
            result=source['reuse_output'];assert sha(result['path'])==result['sha256']
            results.append(dict(key=source['key'],output=result,reused=True));continue
        raw=read_image(source['source']);applied,neural,w=predict(model,raw)
        folder=out/'images'/source['key'];folder.mkdir(parents=True,exist_ok=False)
        np.savez_compressed(folder/'output.npz',output=applied,neural_output=neural)
        result=dict(key=source['key'],output=record(folder/'output.npz'),reused=False,source=source['source'],shape=list(raw.shape))
        save(folder/'record.json',result);results.append(result)
        print(json.dumps(dict(image=source['key'],finished=len(results),total=len(plan['sources']),seconds=time.perf_counter()-start)),flush=True)
    verify_binding(load(ROOT/'config/frozen_training.json'))
    save(out/'inference.json',dict(completed=True,outputs=results,plan=record(out/'plan.json'),source=record(__file__),seconds=time.perf_counter()-start))

if __name__=='__main__':main()
