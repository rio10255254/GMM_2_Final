from pathlib import Path
import os,sys,tempfile,json,copy,time
os.environ['CUDA_VISIBLE_DEVICES']='-1';os.environ['PYTHONWARNINGS']='ignore::FutureWarning'
P=Path(r'D:\GMM_2_Final\Experiments\R138_V42PSF8');sys.path.insert(0,str(P))
import torch
from utils import config,state_digest
from train_r138_psf import create,update,learning_rate
from dataset_r138_psf import Bank
cfg=config();torch.set_num_threads(24);m,opt=create(cfg);torch.set_num_threads(24);bank=Bank(cfg);b=bank.batch('train',0,'cpu',0)
update(m,opt,b,learning_rate(1,cfg),cfg)
with tempfile.TemporaryDirectory(prefix='r138_resume_test_') as td:
 p=Path(td)/'cp.pth';torch.save(dict(model=m.state_dict(),optimizer=opt.state_dict(),rng=torch.get_rng_state()),p)
 b2=bank.batch('train',1,'cpu',0);update(m,opt,b2,learning_rate(2,cfg),cfg);expected=state_digest(m)
 n,no=create(cfg);torch.set_num_threads(24);cp=torch.load(p,weights_only=False);n.load_state_dict(cp['model']);no.load_state_dict(cp['optimizer']);torch.set_rng_state(cp['rng']);update(n,no,b2,learning_rate(2,cfg),cfg);actual=state_digest(n)
 assert actual==expected
 for i,v in opt.state_dict()['state'].items():
  for k,t in v.items():
   other=no.state_dict()['state'][i][k];assert torch.equal(t,other) if torch.is_tensor(t) else t==other
result=dict(CPU_save_reload_next_update_bit_exact=True,optimizer_state_bit_exact=True,GPU_switch_executed=False,GPU_not_used=True,disposable_test_updates=3,formal_weights_used=False)
(P/'results/runtime_control/resume_test.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(result,flush=True)
