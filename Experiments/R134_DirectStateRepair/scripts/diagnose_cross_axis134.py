"""Post-hoc mechanism diagnostics for the failed16->17pair; not a new holdout or admission."""
from pathlib import Path
import sys,types
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from rt import *
from motion134 import load_reader
from tiled import tiled_prior
from torch.nn import functional as F
import cv2,pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]

OUT=ROOT/'results/cross_axis_diagnosis';SEQ='20x_0p5um'

def main():
    OUT.mkdir(exist_ok=False);panel=load(ROOT/'config/motion_panel.json');plan=load(str(PROJECT_ROOT / panel['source_plan']['path']));cfg=load(str(PROJECT_ROOT / panel['configuration']['path']));spec=cfg['sequences'][SEQ];core,scope=load_reader()(plan)
    protected=[record(ROOT/'results/long_admission.json'),record(ROOT/'config/full_motion_admission.json'),*load(ROOT/'config/packaging_source_binding.json')['sources']]
    save(OUT/'plan.json',dict(scope='Post-hoc explanation of failed pair; cannot change original admission',sequence=SEQ,frames=[16,17],models=['A_s1342001','A_s1342002','C_s1342001','C_s1342002'],interventions=['C_s1342001 frozen prefixes1to4','C_s1342001 optical cue off','float versus exported8bit','matched reader settings','known horizontal translations of captured frame16'],virtual_horizontal_shifts_px=[-3.,float(spec['expected_signed_dx_px']),-2.5],protected_sources=protected,completion='Repeat measured failure; quantify per-pillar/neighbor contributions, interface/seed/optics/rounding/reader sensitivity and known-motion response; preserve negative qualification'))
    raws={};inputs={};rows=[];parity=[]
    for index in [16,17]:
        f=next(f for f in plan['frames'] if f['sequence']==SEQ and f['frame_index']==index);assert sha(f['source']['path'])==f['source']['sha256'];raws[index]=cv2.imread(f['source']['path'],0).astype(np.float32)/255;inputs[index]=f['source']
    def measure(name,index,image,raw=None,reader=None):
        raw=raws[index] if raw is None else raw;d=OUT/'measurements'/name/f'frame_{index:04d}';d.mkdir(parents=True,exist_ok=False)
        t,p=scope['measure_frame'](reader or core,scope,SEQ,index,spec,raw.astype(float),image.astype(float),name);t.to_csv(d/'centers.csv',index=False);np.savez_compressed(d/'points.npz',**p);rows.append(t);return t
    def output(name,index,value,save_float=False):
        d=OUT/'images'/name;d.mkdir(parents=True,exist_ok=True);png=np.rint(value*255).clip(0,255).astype(np.uint8);assert cv2.imwrite(str(d/f'{index:04d}.png'),png)
        measure(name+'_8bit',index,png.astype(np.float64)/255);measure(name+'_float',index,value)
        if save_float:np.savez_compressed(d/f'{index:04d}.npz',image=value)
        return png
    def guard(x,y):
        h,w=x.shape[-2:];a=torch.arange(h,device=x.device)[:,None];b=torch.arange(w,device=x.device)[None,:];d=torch.minimum(torch.minimum(a,h-1-a),torch.minimum(b,w-1-b));return x+(y-x)*((d-16)/16).clamp(0,1)
    for i in raws:measure('Raw',i,raws[i].astype(np.float64))
    for arm,seed in [('C',1342001),('A',1342001),('A',1342002),('C',1342002)]:
        name=f'{arm}_s{seed}';cp=ROOT/f'runs/R134_{arm}_s{seed}/step0512.pth';m=create(arm,seed);m.load_state_dict(torch.load(cp,map_location='cpu')['model']);m.eval()
        for index,raw in raws.items():
            x=torch.from_numpy(raw)[None,None].cuda();prefix={}
            with torch.no_grad():
                if name=='C_s1342001':
                    original=x.repeat_interleave(4,-2).repeat_interleave(4,-1)
                    def capture(i,state):prefix[i+1]=guard(x,(x+F.avg_pool2d(state-original,4)).clamp(0,1))[0,0].cpu().numpy()
                    value=guard(x,m(x,prior_runner=lambda p,f:tiled_prior(p,f,512,16),trace=capture))[0,0].cpu().numpy();del original
                else:value=guard(x,m(x,prior_runner=lambda p,f:tiled_prior(p,f,512,16)))[0,0].cpu().numpy()
            png=output(name,index,value,save_float=True)
            if name=='C_s1342001':
                old=ROOT/f'results/full_motion/{SEQ}/frame_{index:04d}/reconstruction.png';assert np.array_equal(png,cv2.imread(str(old),0));assert np.array_equal(prefix[4],value);parity.append(index)
                for n in [1,2,3]:output(name+f'_prefix{n}',index,prefix[n])
            print('Measured',name,index,flush=True)
        if name=='C_s1342001':
            m.optical_enabled=False
            for index,raw in raws.items():
                x=torch.from_numpy(raw)[None,None].cuda()
                with torch.no_grad():value=guard(x,m(x,prior_runner=lambda p,f:tiled_prior(p,f,512,16)))[0,0].cpu().numpy()
                output(name+'_no_optics',index,value);print('Measured optical-cue intervention',index,flush=True)
        del m;torch.cuda.empty_cache()
    # Use precisely the same reader variants on Raw and the same reconstructed images.
    for count in [128,256,720]:
        reader=types.SimpleNamespace(crop_around=core.crop_around)
        def alternative(*args,**kwargs):kwargs['sample_count']=count;return core.measure_inflection_lsc(*args,**kwargs)
        reader.measure_inflection_lsc=alternative
        for index,raw in raws.items():
            recon=cv2.imread(str(OUT/f'images/C_s1342001/{index:04d}.png'),0).astype(float)/255
            measure(f'Raw_reader{count}',index,raw,reader=reader);measure(f'C_reader{count}',index,recon,reader=reader)
    # Shift already captured input: image-space equivariance control, not a
    # calibrated physical acquisition or independent-noise sequence.
    m=create('C',1342001);m.load_state_dict(torch.load(ROOT/'runs/R134_C_s1342001/step0512.pth',map_location='cpu')['model']);m.eval();base=raws[16]
    for dx in [-3.,float(spec['expected_signed_dx_px']),-2.5]:
        name='virtual_x'+str(dx).replace('-','m').replace('.','p');shifted=cv2.warpAffine(base,np.float32([[1,0,dx],[0,1,0]]),(base.shape[1],base.shape[0]),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REFLECT_101)
        measure(name+'_Raw_float',17,shifted,raw=shifted);x=torch.from_numpy(shifted)[None,None].cuda()
        with torch.no_grad():value=guard(x,m(x,prior_runner=lambda p,f:tiled_prior(p,f,512,16)))[0,0].cpu().numpy()
        measure(name+'_C_float',17,value,raw=shifted);np.savez_compressed(OUT/(name+'.npz'),raw=shifted,reconstructed=value,dx=np.array(dx));print('Measured known horizontal input shift',dx,flush=True)
    pd.concat(rows).to_csv(OUT/'centers.csv',index=False);assert all(sha(str(PROJECT_ROOT / r['path']))==r['sha256'] for r in protected);verify()
    save(OUT/'forward_complete.json',dict(exact_original_fullfield_replays=parity,measurement_rows=sum(len(t) for t in rows),protected_sources_unchanged=True,source=record(__file__),inputs=inputs))
    print('Diagnostic forward and readout probes complete',flush=True)
if __name__=='__main__':main()
