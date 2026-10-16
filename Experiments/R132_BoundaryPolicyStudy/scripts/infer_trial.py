"""Research-only R129 with explicit output-retention width; original package unchanged."""
from common132 import *
import argparse

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--output',required=True);parser.add_argument('--width',type=int,choices=WIDTHS,default=16);args=parser.parse_args()
    src=Path(args.input).resolve();out=Path(args.output).resolve();side=out.with_suffix('.json');mapfile=out.with_name(out.stem+'_model_fraction.png')
    if any(p.exists() for p in [out,side,mapfile]):raise FileExistsError('Use new output paths; original files are never overwritten')
    verify();raw,x=base.tensor(src)
    if min(raw.shape)<193:raise ValueError('This trial retains the original minimum input dimension193')
    m=base.model();before=base.runtime.state_digest(m)
    with torch.no_grad():pred=base.original_predict(m,x)[0,0].cpu().numpy()
    output=blend(raw.astype(np.float32)/255,pred,args.width);written=write_image(out,output)
    h,w=raw.shape;y,z=np.mgrid[:h,:w];d=np.minimum.reduce([y,z,h-1-y,w-1-z]);fraction=np.ones(raw.shape,np.float32) if args.width==0 else np.clip((d-args.width)/16,0,1).astype(np.float32)
    maprec=write_image(mapfile,fraction);assert base.runtime.state_digest(m)==before
    save(side,dict(utc=now(),input=rec(src),output=written,model_fraction_map=maprec,checkpoint=PLAN['checkpoint'],width=args.width,transition=0 if args.width==0 else 16,steps=4,scope='Research candidate on previously used normal microscopy; not dimensional certification or unseen qualification',map_meaning='Fraction of final neural output retained, NOT confidence or correctness',measurement_region='The whole measurement window and its necessary context should lie outside the transition; no automatic object or validity detection is implemented',original_model_unchanged=True,source=rec(__file__)))
    print('Trial image written',str(out),flush=True)

if __name__=='__main__':main()
