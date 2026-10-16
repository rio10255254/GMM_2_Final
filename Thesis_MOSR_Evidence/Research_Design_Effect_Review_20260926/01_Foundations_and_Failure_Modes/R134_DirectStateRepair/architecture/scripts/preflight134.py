from pathlib import Path
import sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rt import *
from dataset134 import Bank
from train_core import objective

def main():
    verify();cfg=load(ROOT/'config/study.json');bank=Bank();rows=[];torch.set_num_threads(4)
    for seed in cfg['seeds']:
        a=create('A',seed);c=create('C',seed);assert model_digest(a)==model_digest(c)
        x=torch.rand(1,1,193,201,device='cuda')
        c.eval()
        with torch.no_grad():assert torch.equal(c(x),x)
        rows.append(dict(seed=seed,matched_initialization=True,C_initial_exact_Raw=True))
        del a,c;torch.cuda.empty_cache()
    c=create('C',cfg['seeds'][0]);b=bank.batch('train',0,epoch=0);initial=model_digest(c);opt=torch.optim.AdamW(c.parameters(),lr=.001,weight_decay=1e-5);losses=[];start=time.perf_counter()
    for step in range(8):
        c.train();opt.zero_grad(set_to_none=True);loss,terms,_=objective(c,b);loss.backward();assert torch.isfinite(loss);norm=torch.nn.utils.clip_grad_norm_(c.parameters(),5,error_if_nonfinite=True);opt.step();losses.append(float(loss.detach()))
    assert model_digest(c)!=initial
    c.eval()
    with torch.no_grad():
        y=c(b['source']);c.optical_enabled=False;off=c(b['source']);c.optical_enabled=True
        optics_change=float((y-off).abs().max());assert optics_change>0
    active={name:float(p.grad.norm()) for name,p in c.named_parameters() if p.grad is not None};assert active['prior.stem.weight']>0 and active['prior.head.weight']>0
    # Exact data replay from independent arrays, no reader implementation reuse.
    for index in [0,127,511]:
        b=bank.batch('train',index,'cpu',epoch=0);entry=bank.entries['train',index];data=np.load(bank.root/entry['arrays_path']);meta=load(bank.root/entry['metadata_path']);rng=np.random.default_rng(np.random.SeedSequence([cfg['noise_seed'],0,index]));src=np.rint(np.clip(data['noiseless'].astype(np.float64)+rng.normal(0,meta['noise_sigma_gray']/255,data['source'].shape),0,1)*255).astype(np.uint8);x=np.ascontiguousarray(src[:,None,32:352,32:352].astype(np.float32)/np.float32(255));assert digest(x)==b['input_sha256']
    save(ROOT/'results/preflight.json',dict(passed=True,initialization=rows,discarded_probe_updates=8,probe_losses=losses,seconds=time.perf_counter()-start,peak_reserved_gib=torch.cuda.max_memory_reserved()/1024**3,active_optics_output_change=optics_change,stem_gradient=active['prior.stem.weight'],head_gradient=active['prior.head.weight'],independent_input_replays=3,source=record(__file__)))
    print('Preflight passed',losses,'seconds',time.perf_counter()-start,flush=True)
if __name__=='__main__':main()
