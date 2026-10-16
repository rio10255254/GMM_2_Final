"""Measure throughput on the actual two-view objective, without saving weights."""
from pathlib import Path
import json
import sys
import time
import torch
from torch.utils.data._utils.collate import default_collate
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from training.dataset import Scenes,flatten
from training.objectives import objective
from model.network import build_model

def main():
    torch.set_num_threads(4);config=json.loads((ROOT/'config/experiment.json').read_text());ds=Scenes('train',limit=32)
    results=[]
    for batch_size in (12,24):
        torch.cuda.empty_cache();torch.manual_seed(118)
        model=build_model().cuda();batch=flatten(default_collate([ds[i] for i in range(batch_size)]),'cuda')
        times=[];torch.cuda.reset_peak_memory_stats()
        for step in range(5):
            model.zero_grad(set_to_none=True);torch.cuda.synchronize();start=time.perf_counter()
            with torch.autocast('cuda',dtype=torch.bfloat16):
                d=model.forward_details(batch['source']);loss,_=objective(model,d,batch,config['training']['weights'])
            loss.backward();torch.cuda.synchronize()
            if not torch.isfinite(loss):raise FloatingPointError('benchmark')
            if step>1:times.append(time.perf_counter()-start)
        result={'batch_scenes':batch_size,'views':batch_size*2,'seconds_per_step':sum(times)/len(times),
                'scenes_per_second':batch_size/(sum(times)/len(times)),
                'peak_reserved_gib':torch.cuda.max_memory_reserved()/2**30}
        print(json.dumps(result),flush=True);results.append(result)
        del model,batch,d,loss;torch.cuda.empty_cache()
    (ROOT/'validation/throughput.json').write_text(json.dumps({'status':'complete','results':results},indent=2))
if __name__=='__main__':main()
