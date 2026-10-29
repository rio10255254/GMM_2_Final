"""Fixed real-pillar panel: full SEM field and source-defined motion ROIs."""
import os,sys,time,importlib.util,ast
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import cv2,numpy as np,pandas as pd,torch
from torch.nn import functional as F
from model.hybrid_v2 import Hybrid
from run_pilot import setup
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def guard(raw,pred):
    h,w=raw.shape[-2:];y=torch.arange(h,device=raw.device)[:,None];x=torch.arange(w,device=raw.device)[None,:];d=torch.minimum(torch.minimum(y,h-1-y),torch.minimum(x,w-1-x)).float();weight=((d-80)/16).clamp(0,1)
    return raw+(pred-raw)*weight

def prepare_panel():
    p=load(ROOT/'config/plan.json');cfgpath=REPO/'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/config/sequence_center9_50x20x.json';cfg=load(cfgpath)
    sys.path.insert(0,str(R128/'analysis/lsc_comparison'));from measure import reader
    core,scope=reader(load(R128/'results/lsc_comparison/plan.json'))
    frames=[]
    for pair in p['motion_pairs']:
        s=cfg['sequences'][pair['sequence']];base=np.asarray(s['centers'],float);preds=[scope['session_prediction'](pair['sequence'],i,base,s['expected_signed_dx_px']) for i in [pair['start'],pair['end']]];pts=np.concatenate(preds)
        paths=[Path(s['raw_dir'])/f'frame_{i:04d}.bmp' for i in [pair['start'],pair['end']]];shape=cv2.imread(str(paths[0]),0).shape;h,w=shape
        box=[max(0,int(np.floor(pts[:,1].min()))-160),max(0,int(np.floor(pts[:,2].min()))-160),min(w,int(np.ceil(pts[:,1].max()))+161),min(h,int(np.ceil(pts[:,2].max()))+161)]
        for i,path in zip([pair['start'],pair['end']],paths):frames.append(dict(sequence=pair['sequence'],frame_index=i,source=record(path),box=box))
    sem=[dict(exposure=s['exposure'],source=s['Raw']) for s in load(R128/'results/full_contour/plan.json')['sources']]
    save(ROOT/'config/real_panel.json',dict(created_utc=now(),motion=frames,sem=sem,sequence_config=record(cfgpath),motion_plan=p['motion_pairs'],scope='fixed pilot ROIs,not thesis fullFOV120pairs',guard='Rawthroughdistance80,transition16,common all arms/reference',source=record(__file__)))

def main():
    assert load(ROOT/'results/pilot_training.json')['total_updates']==96
    if not (ROOT/'config/real_panel.json').exists():prepare_panel()
    panel=load(ROOT/'config/real_panel.json');p=load(ROOT/'config/plan.json');cfg=load(str(PROJECT_ROOT / panel['sequence_config']['path']));bank=np.load(ROOT/'data/measured_psf_bank.npz');setup(p['common_seed'])
    sys.path.insert(0,str(R128/'analysis/lsc_comparison'));from measure import reader
    core,scope=reader(load(R128/'results/lsc_comparison/plan.json'))
    methods=[(arm,step) for arm in p['arms'] for step in [0,24]];results=[];motionrows=[]
    for arm,step in methods:
        m=Hybrid(torch.from_numpy(bank['mean']),torch.from_numpy(bank['candidates']),**p['arms'][arm]).to('cuda');ck=ROOT/'runs'/arm/('initial.pth' if step==0 else 'step24.pth');m.load_state_dict(torch.load(ck,map_location='cuda')['model']);m.eval();tag=f'{arm}_{step}';folder=ROOT/'results/real'/tag;folder.mkdir(parents=True,exist_ok=False);t0=time.perf_counter()
        for item in panel['sem']:
            src=item['source'];assert sha(str(PROJECT_ROOT / src['path']))==src['sha256'];raw=cv2.imread(str(PROJECT_ROOT / src['path']),0);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].to('cuda')
            with torch.no_grad():d=m.forward_details(x,trace=True);out=guard(x,d.output)[0,0].cpu().numpy()
            path=folder/f"sem{item['exposure']}.png";assert cv2.imwrite(str(path),np.rint(out*255).clip(0,255).astype(np.uint8));np.savez_compressed(folder/f"sem{item['exposure']}.npz",output=out)
            results.append(dict(tag=tag,arm=arm,step=step,exposure=item['exposure'],image=record(path),source=src,checkpoint=record(ck),optical_weights=d.optical['weights'].detach().cpu().tolist() if p['arms'][arm]['optical'] else None))
        for item in panel['motion']:
            s=cfg['sequences'][item['sequence']];src=item['source'];assert sha(str(PROJECT_ROOT / src['path']))==src['sha256'];rawfull=cv2.imread(str(PROJECT_ROOT / src['path']),0);x0,y0,x1,y1=item['box'];raw=rawfull[y0:y1,x0:x1];x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].to('cuda')
            with torch.no_grad():output=guard(x,m(x))[0,0].cpu().numpy()
            image=np.rint(output*255).clip(0,255).astype(np.uint8);path=folder/f"{item['sequence']}_{item['frame_index']:04d}.png";assert cv2.imwrite(str(path),image)
            predicted=scope['session_prediction'](item['sequence'],item['frame_index'],np.asarray(s['centers'],float),s['expected_signed_dx_px'])
            for pid,cx,cy in predicted:
                patch,center,origin=core.crop_around(image.astype(float)/255,(float(cx-x0),float(cy-y0)),int(np.ceil(.46*s['pitch_px'])));scope['reset_curvature_cycle']()
                v=core.measure_inflection_lsc(patch,center,s['radius_px'],sample_count=64 if s['magnification']=='20x' else 96,acm_iterations=13 if s['magnification']=='20x' else 15,normal_half_width_px=2.4 if s['magnification']=='20x' else 4.,polarity='dark')
                motionrows.append(dict(tag=tag,sequence=item['sequence'],frame_index=item['frame_index'],pillar_id=int(pid),cx=v.lsc.cx+origin[0]+x0,cy=v.lsc.cy+origin[1]+y0,scale=s['object_um_per_px']))
        print(__import__('json').dumps(dict(tag=tag,sem=3,motion=8,seconds=round(time.perf_counter()-t0,1))),flush=True)
        save(folder/'complete.json',dict(tag=tag,sem3=True,motion8=True,checkpoint=record(ck)));del m;torch.cuda.empty_cache()
    pd.DataFrame(motionrows).to_csv(ROOT/'results/motion_centers.csv',index=False)
    save(ROOT/'results/real_inference.json',dict(completed_utc=now(),sem_images=results,motion_center_rows=len(motionrows),source=record(__file__),panel=record(ROOT/'config/real_panel.json')))
    print('Realpilotpanelcomplete',flush=True)
if __name__=='__main__':main()
