from runtime import *
from data import Bank
from engine import update,checkpoint,restore
from verify_package import verify
from precision_io import write_values,read_values
from model.inference_policy import guard
import cv2
def equal(a,b):
    if torch.is_tensor(a):return torch.equal(a,b)
    if isinstance(a,dict):return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,(tuple,list)):return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a==b
def main():
    verify(True);cfg=load(ROOT/'config/training.json');bind=binding(cfg);out=ROOT/'results/preflight';out.mkdir(parents=True,exist_ok=False);bank=Bank();order=bank.order(0);m,o=create('cuda')
    for i in range(1,9):update(m,o,bank.batch('train',int(order[i-1]),'cuda',0),i,cfg)
    expected={k:v.detach().clone() for k,v in m.state_dict().items()};expectedopt=o.state_dict();n,no=create('cuda')
    for i in range(1,5):update(n,no,bank.batch('train',int(order[i-1]),'cuda',0),i,cfg)
    cp=checkpoint(out,n,no,4,bind);del n,no;torch.cuda.empty_cache();n,no=create('cuda');assert restore(cp,n,no,bind)==4
    for i in range(5,9):update(n,no,bank.batch('train',int(order[i-1]),'cuda',0),i,cfg)
    assert equal(expected,n.state_dict()) and equal(expectedopt,no.state_dict());del m,o,n,no,expected,expectedopt;torch.cuda.empty_cache();m,_=create('cuda');m.eval();cases=[]
    for item in load(ROOT/'verification/golden.json')['cases']:
        raw=cv2.imread(str(ROOT/item['input']),0);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
        with torch.no_grad():v=guard(x,m(x))[0,0].cpu().numpy()
        assert np.array_equal(v,np.load(ROOT/item['expected'],allow_pickle=False));path,_,_=write_values(out,item['name'],v);assert np.array_equal(read_values(path),v);cases.append(item['name'])
    checked=verify(True);save(out/'complete.json',dict(passed=True,training_config_sha256=sha(ROOT/'config/training.json'),discarded_test_updates=16,exact_model_resume=True,exact_optimizer_resume=True,exact_lossless_golden_cases=cases,package_verification=checked));print('Package precision/resume preflight passed',flush=True)
if __name__=='__main__':main()
