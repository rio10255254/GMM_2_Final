import argparse,time
import numpy as np,torch,cv2
from utils import ROOT,load,config,setup,sha
from model_r130_clean import Model

def predict_tensor(model,x,mode='full',core=512,halo=96):
    if halo<model.dependency_radius:raise ValueError('Insufficient inference halo')
    if mode=='full':return model(x)
    if mode!='tiled':raise ValueError('Unknown inference mode')
    n,c,h,w=x.shape;out=torch.empty_like(x)
    for y in range(0,h,core):
        for xx in range(0,w,core):
            y1=min(h,y+core);x1=min(w,xx+core);a=max(0,y-halo);b=min(h,y1+halo);l=max(0,xx-halo);r=min(w,x1+halo)
            patch=x[...,a:b,l:r];v=model(patch)
            out[...,y:y1,xx:x1]=v[...,y-a:y1-a,xx-l:x1-l]
    return out

def load_own_model(path,device='cuda'):
    cfg=config();p=torch.load(path,map_location='cpu')
    if p.get('model_name')!='R130-Clean' or p.get('initialization')!='scratch' or p.get('optical_mode')!='off':raise ValueError('Not a valid own clean checkpoint')
    model=Model(cfg['model']);model.load_state_dict(p['model'],strict=True);return model.to(device).eval(),p

def main():
    a=argparse.ArgumentParser();a.add_argument('--input',required=True);a.add_argument('--output',required=True);a.add_argument('--checkpoint',required=True);a.add_argument('--mode',choices=['full','tiled'],default='full');args=a.parse_args()
    setup(1309001);model,_=load_own_model(args.checkpoint);raw=cv2.imread(args.input,0)
    if raw is None:raise ValueError('Unreadable image')
    x=torch.from_numpy(raw.astype('float32')[None,None]/255).cuda()
    with torch.inference_mode():out=predict_tensor(model,x,args.mode).cpu().numpy()[0,0]
    if not args.output.endswith('.npz'):raise ValueError('Use .npz to retain FP32 measurements')
    np.savez_compressed(args.output,output=out)
if __name__=='__main__':main()
