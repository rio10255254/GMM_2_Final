from pathlib import Path
import sys,time,shutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from rt import *
from infer134 import predict
from motion134 import load_reader
from tiled import tiled_prior
from scipy.optimize import least_squares
import cv2,pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def main():
    while not (ROOT/'results/motion_screen.json').exists():
        if (ROOT/'results/motion_not_triggered.json').exists():return
        time.sleep(5)
    screen=load(ROOT/'results/motion_screen.json')
    while not (ROOT/'results/motion_audit.json').exists():time.sleep(5)
    motion_audit=load(ROOT/'results/motion_audit.json')
    if not screen['passed'] or not motion_audit['passed']:
        save(ROOT/'results/long_admission.json',dict(eligible=False,reason='12pairmotion screen failed'));return
    panel=load(ROOT/'config/motion_panel.json');plan=load(str(PROJECT_ROOT / panel['source_plan']['path']));cfg=load(plan['configuration']['path']);core,scope=load_reader()(plan);seed=screen['selected_seed'];tag=f'C_s{seed}';cp=ROOT/f'runs/R134_C_s{seed}/step0512.pth';payload=torch.load(cp,map_location='cpu');m=create('C',seed);m.load_state_dict(payload['model']);m.eval();out=ROOT/'results/full_motion';out.mkdir(exist_ok=False);tables=[];refits=[];reused=0
    save(out/'started.json',dict(seed=seed,checkpoint=record(cp),rules=record(ROOT/'config/full_motion_admission.json'),source=record(__file__)))
    for j,f in enumerate(plan['frames']):
        case=f"{f['sequence']}/frame_{f['frame_index']:04d}";dest=out/case;dest.mkdir(parents=True);old=ROOT/'results/motion'/tag/case
        if (old/'centers.csv').exists():
            evidence=next(r for r in motion_audit['records'] if r['tag']==tag and r['case']==case)
            for k in ['image','centers','points']:assert sha(evidence[k]['path'])==evidence[k]['sha256']
            for name in ['centers.csv','points.npz','reconstruction.png']:shutil.copy2(old/name,dest/name)
            t=pd.read_csv(dest/'centers.csv');reused+=1
        else:
            raw8=cv2.imread(f['source']['path'],0);assert sha(f['source']['path'])==f['source']['sha256'];x=torch.from_numpy(raw8.astype(np.float32)/255)[None,None].cuda();v=predict(m,x)[0,0].cpu().numpy();image=np.rint(v*255).clip(0,255).astype(np.uint8);assert cv2.imwrite(str(dest/'reconstruction.png'),image);t,p=scope['measure_frame'](core,scope,f['sequence'],f['frame_index'],cfg['sequences'][f['sequence']],raw8.astype(float)/255,image.astype(float)/255,tag);t.to_csv(dest/'centers.csv',index=False);np.savez_compressed(dest/'points.npz',**p)
        points=np.load(dest/'points.npz')['inflection_points']
        for xy,row in zip(points,t.itertuples()):
            origin=xy.mean(0);z=xy-origin
            def fun(c):r=np.linalg.norm(z-c,axis=1);return r-r.mean()
            c=least_squares(fun,np.zeros(2),xtol=1e-12,ftol=1e-12,gtol=1e-12).x+origin;e=max(abs(c[0]-row.lsc_center_x_px),abs(c[1]-row.lsc_center_y_px));assert e<1e-4;refits.append(e)
        tables.append(t);atomic(out/'status.json',dict(frames=j+1,total=201));print('fullmotion',j+1,'/201',flush=True)
    ct=pd.concat(tables);assert len(ct)==1809;ct.to_csv(out/'centers.csv',index=False);adj=pd.read_csv(plan['adjacent_pairs']['path']);rawcenters=pd.read_csv(ROOT.parent/'R129_OpticalPriorHybrid/results/continuous_lsc/measurements/Raw/centers.csv');checks=[];summaries=[]
    for population,pairs in [('locked120',pd.read_csv(plan['locked_pairs']['path'])),('within_session194',adj[~adj.is_repositioning]),('repositioning3',adj[adj.is_repositioning])]:
        candidate,_=scope['pair_table'](ct,pairs,cfg,tag);raw,_=scope['pair_table'](rawcenters,pairs,cfg,'Raw');candidate.to_csv(out/(population+'_pairs.csv'),index=False);raw.to_csv(out/(population+'_Raw_pairs.csv'),index=False)
        if population=='repositioning3':continue
        a=scope['summarize_pairs'](candidate);b=scope['summarize_pairs'](raw);a['population']=population;summaries.append(a)
        for row in a[a.scope=='per_sequence'].itertuples():
            rv=b[(b.scope=='per_sequence')&(b.sequence==row.sequence)].iloc[0];checks.append(dict(population=population,metric='per_sequence_stepSD',sequence=row.sequence,ratio=float(row.step_sd_nm/rv.step_sd_nm),passed=row.step_sd_nm<=1.05*rv.step_sd_nm))
        av=a[a.scope=='all_four_sequences'].iloc[0];bv=b[b.scope=='all_four_sequences'].iloc[0]
        for k in ['mean_nominal_abs_error_nm','median_within_grid_sd_nm','median_cross_axis_abs_nm']:checks.append(dict(population=population,metric=k,ratio=float(av[k]/bv[k]),passed=bool(av[k]<=1.05*bv[k])))
        for k in ['nominal_abs_error_nm','cross_axis_abs_nm']:checks.append(dict(population=population,metric='maximum_'+k,ratio=float(candidate[k].max()/raw[k].max()),passed=bool(candidate[k].max()<=1.1*raw[k].max())))
        def wrong(t):return sum(int((np.sign(g.aggregate_dx_um)!=np.sign(cfg['sequences'][s]['expected_signed_dx_px'])).sum()) for s,g in t.groupby('sequence'))
        checks.append(dict(population=population,metric='wrong_direction',candidate=wrong(candidate),Raw=wrong(raw),passed=wrong(candidate)<=wrong(raw)))
    pd.concat(summaries).to_csv(out/'summary.csv',index=False);verify();passed=all(c['passed'] for c in checks)
    save(out/'complete.json',dict(frames=201,centers=1809,reused_frames=reused,independent_center_refits=len(refits),max_refit_error_px=max(refits),checks=checks))
    save(ROOT/'results/long_admission.json',dict(eligible=passed,selected_seed=seed,arm='C',checkpoint=record(cp),stage1=record(ROOT/'results/screening_decision.json'),motion12=record(ROOT/'results/motion_screen.json'),motion201=record(out/'complete.json'),scope='Long research training admission only; physicalB/Dqualification still pending',reason='All prospective screens passed' if passed else 'Full201 safety screen failed; no longtraining package'))
if __name__=='__main__':main()
