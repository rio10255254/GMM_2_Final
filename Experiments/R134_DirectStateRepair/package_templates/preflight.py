from runtime import *
from data import Bank
from engine import update,checkpoint,restore
from verify_package import verify
from model.inference_policy import guard
import cv2

def equal(a,b):
    if torch.is_tensor(a):return torch.equal(a,b)
    if isinstance(a,dict):return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)):return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a==b

def main():
    checked=verify(True);cfg=load(ROOT/'config/training.json');bind=binding(cfg);out=ROOT/'results/preflight';out.mkdir(parents=True,exist_ok=False);bank=Bank();order=bank.order(0)
    m,opt=create('cuda')
    for step in range(1,9):update(m,opt,bank.batch('train',int(order[step-1]),'cuda',0),step,cfg)
    expected={k:v.detach().clone() for k,v in m.state_dict().items()};expected_opt=opt.state_dict();save(out/'continuous8.json',dict(model_digest=state_digest(m)))
    n,no=create('cuda')
    for step in range(1,5):update(n,no,bank.batch('train',int(order[step-1]),'cuda',0),step,cfg)
    cp=checkpoint(out,n,no,4,bind);del n,no;torch.cuda.empty_cache();n,no=create('cuda');assert restore(cp,n,no,bind)==4
    for step in range(5,9):update(n,no,bank.batch('train',int(order[step-1]),'cuda',0),step,cfg)
    assert equal(expected,n.state_dict()) and equal(expected_opt,no.state_dict())
    del m,opt,n,no,expected,expected_opt;torch.cuda.empty_cache();m,_=create('cuda');m.eval();parity=[]
    for item in load(ROOT/'verification/golden.json')['cases']:
        raw=cv2.imread(str(ROOT/item['input']),0);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
        with torch.no_grad():a=guard(x,m(x))[0,0].cpu().numpy()
        image=np.rint(a*255).clip(0,255).astype(np.uint8);assert np.array_equal(image,cv2.imread(str(ROOT/item['expected']),0));parity.append(item['name'])
    checked_after=verify(True)
    save(out/'complete.json',dict(passed=True,training_config_sha256=sha(ROOT/'config/training.json'),package_verification=checked_after,discarded_test_updates=16,exact_model_resume=True,exact_optimizer_resume=True,golden_cases=parity,old_initial_weight_unchanged=True))
    print('Package preflight passed: source,data,resume andrealoutput parity',flush=True)
if __name__=='__main__':main()
