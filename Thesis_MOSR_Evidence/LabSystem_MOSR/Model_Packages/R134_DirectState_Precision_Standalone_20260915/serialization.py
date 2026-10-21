import json,os,time
from pathlib import Path
import numpy as np

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