"""Full201 endpoint readout. Reports adverse changes; never promotes a model."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from rt import *
from infer134 import predict
from motion134 import load_reader
import cv2,pandas as pd
from scipy.optimize import least_squares
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def main():
    pkg=Path(load(ROOT/'results/package_built.json')['path']);run=pkg/'results/training/r134_long_01';done=load(run/'completion.json');cp=pkg/done['final_checkpoint']['path'];assert sha(cp)==done['final_checkpoint']['sha256']
    state=torch.load(cp,map_location='cpu');assert state['step']==8192
    for rel,h in state['binding']['runtime_files'].items():assert sha(pkg/rel)==h
    seed=load(ROOT/'results/long_admission.json')['selected_seed'];m=create('C',seed);m.load_state_dict(state['model'],strict=True);m.eval()
    panel=load(ROOT/'config/motion_panel.json');plan=load(str(PROJECT_ROOT / panel['source_plan']['path']));cfg=load(str(PROJECT_ROOT / panel['configuration']['path']));core,scope=load_reader()(plan);out=ROOT/'results/long_final_comparison';out.mkdir(exist_ok=False);tables=[];errors=[];records=[]
    save(out/'started.json',dict(checkpoint=record(cp),source=record(__file__),plan=record(str(PROJECT_ROOT / panel['source_plan']['path'])),no_automatic_promotion=True))
    for j,f in enumerate(plan['frames']):
        source=Path(f['source']['path']);assert sha(source)==f['source']['sha256'];raw=cv2.imread(str(source),0);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda();value=predict(m,x)[0,0].cpu().numpy();im=np.rint(value*255).clip(0,255).astype(np.uint8)
        dest=out/f['sequence']/f"frame_{f['frame_index']:04d}";dest.mkdir(parents=True);assert cv2.imwrite(str(dest/'reconstruction.png'),im)
        t,p=scope['measure_frame'](core,scope,f['sequence'],f['frame_index'],cfg['sequences'][f['sequence']],raw.astype(float)/255,im.astype(float)/255,'R134_C_long8192');t.to_csv(dest/'centers.csv',index=False);np.savez_compressed(dest/'points.npz',**p);tables.append(t)
        for xy,row in zip(p['inflection_points'],t.itertuples()):
            o=xy.mean(0);z=xy-o
            def fun(c):r=np.linalg.norm(z-c,axis=1);return r-r.mean()
            center=least_squares(fun,np.zeros(2),xtol=1e-12,ftol=1e-12,gtol=1e-12).x+o;e=max(abs(center[0]-row.lsc_center_x_px),abs(center[1]-row.lsc_center_y_px));assert e<1e-4;errors.append(e)
        records.append(dict(source=f['source'],image=record(dest/'reconstruction.png'),centers=record(dest/'centers.csv'),points=record(dest/'points.npz')))
        atomic(out/'status.json',dict(frames=j+1,total=201));print('Final fullmotion',j+1,'/201',flush=True)
    ct=pd.concat(tables);assert len(ct)==1809;ct.to_csv(out/'centers.csv',index=False)
    sources={'Raw':ROOT.parent/'R129_OpticalPriorHybrid/results/continuous_lsc/measurements/Raw/centers.csv','R129_long_W16':ROOT.parent/'R132_BoundaryPolicyStudy/results/measurements/W16/centers.csv','R134_C_short512':ROOT/'results/full_motion/centers.csv','R134_C_long8192':out/'centers.csv'}
    adj=pd.read_csv(plan['adjacent_pairs']['path']);summaries=[];extremes=[]
    for method,path in sources.items():
        centers=pd.read_csv(path);assert len(centers)==1809
        for population,pairs in [('locked120',pd.read_csv(plan['locked_pairs']['path'])),('within_session194',adj[~adj.is_repositioning]),('repositioning3',adj[adj.is_repositioning])]:
            per,_=scope['pair_table'](centers,pairs,cfg,method);per.to_csv(out/f'{method}_{population}_pairs.csv',index=False)
            if population=='repositioning3':continue
            summary=scope['summarize_pairs'](per);summary['population']=population;summaries.append(summary)
            wrong=sum(int((np.sign(g.aggregate_dx_um)!=np.sign(cfg['sequences'][s]['expected_signed_dx_px'])).sum()) for s,g in per.groupby('sequence'))
            extremes.append(dict(method=method,population=population,max_nominal_nm=float(per.nominal_abs_error_nm.max()),max_cross_nm=float(per.cross_axis_abs_nm.max()),wrong_direction=wrong))
    pd.concat(summaries).to_csv(out/'summary.csv',index=False);pd.DataFrame(extremes).to_csv(out/'worst_cases.csv',index=False)
    # Check package endpoint and experimental inference remain identical on the
    # complete fixed24panel, not merely on a chosen crop.
    real=run/'evaluations/step08192/real'
    for f in panel['frames']:
        a=out/f['sequence']/f"frame_{f['frame_index']:04d}/reconstruction.png";b=real/f"{f['sequence']}_{f['frame_index']:04d}.png";assert np.array_equal(cv2.imread(str(a),0),cv2.imread(str(b),0))
    verify();save(out/'complete.json',dict(frames=201,centers=1809,independent_center_refits=len(errors),max_refit_error_px=max(errors),package_panel_exact_replays=24,checkpoint=record(cp),records=records,reference_centers={k:record(v) for k,v in sources.items()},SEM_endpoint=record(real/'complete.json'),summaries=record(out/'summary.csv'),worst_cases=record(out/'worst_cases.csv'),scope='Reused development comparison; different historical training budgets; not causal architecture-only or unseen confirmation',model_promoted=False))
if __name__=='__main__':main()
