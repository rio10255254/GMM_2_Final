from pathlib import Path
import sys,time,json,os
os.environ['CUDA_VISIBLE_DEVICES']='-1';os.environ['PYTHONWARNINGS']='ignore::FutureWarning'
P=Path(r'D:\GMM_2_Final\Experiments\R138_V42PSF8');sys.path.insert(0,str(P))
import torch,numpy as np
from utils import config
from train_r138_psf import create,update,learning_rate
from dataset_r138_psf import Bank
cfg=config();m,opt=create(cfg);bank=Bank(cfg);batch=bank.batch('train',0,'cpu',0);rows=[]
for threads in [8,16,24,16,8,24]:
 torch.set_num_threads(threads)
 times=[]
 for repeat in range(2):
  tick=time.perf_counter();r=update(m,opt,batch,learning_rate(1,cfg),cfg);times.append(time.perf_counter()-tick)
 rows.append(dict(threads=threads,seconds=times));print(rows[-1],flush=True)
means={n:float(np.median([s for r in rows if r['threads']==n for s in r['seconds']])) for n in [8,16,24]};choice=min(means,key=means.get)
(P/'results/runtime_control/thread_benchmark.json').write_text(json.dumps(dict(rows=rows,median_seconds=means,recommended_threads=choice,scope='same synthetic pair forward/backward/AdamW, disposable model, CPU8/16/24 interleaved',training_weights_discarded=True),indent=2),encoding='utf-8');print('SELECTED',choice,means,flush=True)
