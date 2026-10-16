from common import *
import torch,cv2,numpy as np,time
from reconstruct import setup
setup();plan=load(ROOT/'config/plan.json');info=plan['models']['R129'];pkg=Path(info['package']);sys.path.insert(0,str(pkg))
runtime=module('r136_bench_runtime',pkg/'runtime.py');m,_=runtime.create();m.load_state_dict(torch.load(info['checkpoint']['path'],map_location='cpu')['model']);m.eval()
tile=module('r136_bench_tile',REPO/'Experiments/R129_OpticalPriorHybrid/scripts/sequence_inference.py');guard=module('r136_bench_guard',pkg/'model/inference_policy.py').guard
f=plan['frames'][0];raw=cv2.imread(f['source']['path'],0);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda();ref=np.load(ROOT/'results/R129'/f['run']/'01.npz')['output']
m.prior.to(memory_format=torch.channels_last)
hook=m.prior.register_forward_pre_hook(lambda mod,inputs:(inputs[0].contiguous(memory_format=torch.channels_last),))
rows=[]
for core in [512,384]:
    torch.cuda.synchronize();start=time.perf_counter()
    with torch.inference_mode():v=guard(x,tile.predict(m,x,core))[0,0].cpu().numpy()
    sec=time.perf_counter()-start;err=float(np.abs(v-ref).max());rows.append(dict(core=core,seconds=sec,max_error=err));print(rows[-1],flush=True)
save(ROOT/'results/r129_execution_benchmark.json',dict(records=rows,fp32=True,tf32=False,only_memory_layout_changed=True))
