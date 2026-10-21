"""Localize the observed native driver failure without changing selected weights."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch,cv2,numpy as np
from study import read,MOSR_SOURCE
from inference_methods import load_method,native_forward
torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False


def mark(value):
    print(value,flush=True)


def main():
    mark('INIT');torch.cuda.init();mark(('GPU_FREE',torch.cuda.mem_get_info()))
    model,optics,identity=load_method('USRNet-x1');mark(('LOADED',identity))
    frame=read(MOSR_SOURCE/'evaluation/capture_plan.json')['frames'][0]
    values=cv2.imread(frame['source']['path'],cv2.IMREAD_UNCHANGED).astype(np.float32)/255
    x=torch.from_numpy(values[None,None]).cuda();torch.cuda.synchronize();mark(('INPUT',tuple(x.shape)))
    if '--crop' in sys.argv:x=x[...,:896,:896].contiguous()
    for name in ['d','p','h']:
        module=getattr(model.net,name,None)
        if module is not None:
            module.register_forward_pre_hook(lambda m,a,n=name:mark('ENTER '+n))
            module.register_forward_hook(lambda m,a,o,n=name:(torch.cuda.synchronize(),mark('EXIT '+n))[-1])
    with torch.inference_mode():
        mark('FFT_INPUT');f=torch.fft.fftn(x,dim=(-2,-1));torch.cuda.synchronize();mark('FFT_INPUT_DONE');del f
        mark('FULL_FORWARD');out=native_forward('USRNet-x1',model,optics,x);torch.cuda.synchronize()
        mark(('FORWARD_DONE',tuple(out.shape),bool(torch.isfinite(out).all())))


if __name__=='__main__':main()
