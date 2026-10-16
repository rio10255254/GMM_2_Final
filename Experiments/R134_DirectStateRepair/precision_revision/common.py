from pathlib import Path
import sys,json,os,time
P=Path(__file__).resolve().parent;E=P.parent;sys.path.insert(0,str(E));sys.path.insert(0,str(E/'scripts'))
from rt import load,sha,record,now,create,verify,np,torch

def plain(x):
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,dict):return {k:plain(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [plain(v) for v in x]
    return x

def save(path,value):
    text=json.dumps(plain(value),ensure_ascii=False,indent=2,allow_nan=False)
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:f.write(text)

def atomic(path,value):
    text=json.dumps(plain(value),ensure_ascii=False,indent=2,allow_nan=False);p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_name(p.name+'.writing')
    for _ in range(30):
        try:
            temp.write_text(text,encoding='utf-8');os.replace(temp,p);return
        except PermissionError:time.sleep(.1)
    raise RuntimeError('State remained locked')

def protected():
    verify()
    for r in load(P/'config/protocol.json')['protected']:
        if sha(r['path'])!=r['sha256']:raise RuntimeError('Original protected input changed: '+r['path'])

def status(phase,**extra):atomic(P/'results/status.json',dict(phase=phase,pid=os.getpid(),utc=now(),model_promoted=False,B_D_complete=False,**extra))
