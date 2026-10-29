from r135_common import *
from adapters_v2 import build,cached
from validation import reference_circle_core as core
from sem_metrics import score
from audit import refit,pair_audit
import readout as rd
import cv2,pandas as pd,subprocess,traceback,argparse
from scipy.io import savemat
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def main(tag):
    plan=load(ROOT/'config/plan.json');out=ROOT/'results'/tag;out.mkdir(exist_ok=False);verify();setup();predict=None;details={};preflight=[];timing=[]
    if tag!='Raw':predict,details=build(tag)
    source_files=[record(Path(__file__)),record(ROOT/'scripts/adapters_v2.py'),record(ROOT/'scripts/readout.py'),record(ROOT/'scripts/sem_metrics.py'),record(ROOT/'config/plan.json')]
    save(out/'started.json',dict(utc=now(),pid=os.getpid(),tag=tag,sources=source_files,checkpoint=plan['models'].get(tag,{}).get('checkpoint'),loader={k:v for k,v in details.items() if not callable(v)}))
    checked=set();tables=[];records=[];refits=[];cfg=plan['configuration']
    for j,f in enumerate(plan['frames']):
        assert sha(str(PROJECT_ROOT / f['source']['path']))==f['source']['sha256'];raw8=cv2.imread(str(PROJECT_ROOT / f['source']['path']),0);raw=raw8.astype(float)/255
        if tag=='Raw':value=raw;cache=None
        else:
            value,cache=cached(tag,f)
            if f['sequence'] not in checked:
                fresh=predict(raw8)
                if value is not None:assert np.array_equal(fresh,value),'Fresh native output differs from cached float'
                else:value=fresh
                if callable(details.get('verify_native')):details['verify_native'](str(PROJECT_ROOT / f['source']['path']),fresh,out/f"native_control_{f['sequence']}.png")
                historical=None
                if tag=='V42_old':historical=Path(PROJECT_ROOT / cfg['sequences'][f['sequence']]['v42_dir'])/Path(PROJECT_ROOT / f['source']['path']).name
                if tag=='R61':
                    oldplan=load(REPO/'Experiments/R128_SourceOnlyFullTraining/results/lsc_comparison/plan.json');old=next(x for x in oldplan['frames'] if x['sequence']==f['sequence'] and x['frame_index']==f['frame_index']);historical=Path(PROJECT_ROOT / old['R61']['path'])
                row=dict(sequence=f['sequence'],fresh_native_verified=True,cache_exact=cache is not None)
                if historical and historical.exists():
                    old=cv2.imread(str(historical),0);png=np.rint(fresh*255).clip(0,255).astype(np.uint8);row.update(historical=record(historical),historical_equal=bool(np.array_equal(old,png)),historical_different_pixels=int(np.count_nonzero(old!=png)),historical_max_gray=float(abs(old.astype(float)-png.astype(float)).max()))
                preflight.append(row);checked.add(f['sequence'])
                if not timing:
                    for k in range(4):
                        torch.cuda.synchronize();start=time.perf_counter();probe=predict(raw8);torch.cuda.synchronize();elapsed=time.perf_counter()-start;assert np.array_equal(probe,fresh)
                        if k:timing.append(elapsed)
            if value is None:value=predict(raw8)
        assert value.shape==raw8.shape and np.isfinite(value).all() and value.min()>=0 and value.max()<=1
        d=out/'motion'/f['sequence']/f"frame_{f['frame_index']:04d}";d.mkdir(parents=True);np.savez_compressed(d/'values.npz',image=value);loaded=np.load(d/'values.npz')['image'];assert np.array_equal(loaded,value);preview=np.rint(value*255).clip(0,255).astype(np.uint8);assert cv2.imwrite(str(d/'preview.png'),preview)
        t,p=rd.measure_frame(core,vars(rd),f['sequence'],f['frame_index'],cfg['sequences'][f['sequence']],raw,loaded.astype(float),tag);t.to_csv(d/'centers.csv',index=False);np.savez_compressed(d/'points.npz',**p);refits+=refit(p['inflection_points'],t);tables.append(t);records.append(dict(source=f['source'],values=record(d/'values.npz'),centers=record(d/'centers.csv'),points=record(d/'points.npz'),cache=cache));atomic(out/'status.json',dict(phase='motion',frames=j+1,total=201));print(tag,j+1,'/201',flush=True)
    ct=pd.concat(tables);ct.to_csv(out/'centers.csv',index=False);pop=plan['population'];adj=pd.read_csv(str(PROJECT_ROOT / pop['adjacent_pairs']['path']));summaries=[];pair_checks=0
    for label,pairs in [('locked120',pd.read_csv(str(PROJECT_ROOT / pop['locked_pairs']['path']))),('within_session194',adj[~adj.is_repositioning]),('repositioning3',adj[adj.is_repositioning])]:
        t,_=rd.pair_table(ct,pairs,cfg,tag);pair_checks+=pair_audit(ct,t,cfg);t.to_csv(out/(label+'_pairs.csv'),index=False);s=rd.summarize_pairs(t);s['population']=label;summaries.append(s)
    pd.concat(summaries).to_csv(out/'motion_summary.csv',index=False);d=out/'sem';d.mkdir();atomic(out/'status.json',dict(phase='SEM',frames=201,total=201));sem_inputs=[]
    for e in [13,14,15]:
        source=plan['SEM_sources'][str(e)];assert sha(str(PROJECT_ROOT / source['path']))==source['sha256'];raw8=cv2.imread(str(PROJECT_ROOT / source['path']),0);value=raw8.astype(float)/255 if tag=='Raw' else predict(raw8);np.savez_compressed(d/f'sem{e}_values.npz',image=value);restored=np.load(d/f'sem{e}_values.npz')['image'];assert np.array_equal(restored,value);savemat(d/f'sem{e}_values.mat',dict(image=restored));assert cv2.imwrite(str(d/f'sem{e}_preview.png'),np.rint(value*255).clip(0,255).astype(np.uint8));sem_inputs.append(dict(source=source,values=record(d/f'sem{e}_values.npz')))
    command=f"addpath('{(ROOT/'validation').as_posix()}');extract_sem_precise('{d.as_posix()}');"
    with (d/'matlab.log').open('xb') as log:r=subprocess.run([r'C:\Program Files\MATLAB\R2025b\bin\matlab.exe','-batch',command],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    if r.returncode:raise RuntimeError('SEM extraction failed; preserve all cases')
    sem,pts,info=score(d/'sem_masks.mat',ROOT/'validation/sem_reference.mat');sem.to_csv(d/'measurements.csv',index=False);np.savez_compressed(d/'points.npz',**pts);save(d/'complete.json',info);verify();assert len(ct)==len(refits)==1809 and len(sem)==108
    save(out/'complete.json',dict(tag=tag,completed_utc=now(),frames=201,SEM_rows=108,SEM=info['summary'],independent_motion_refits=len(refits),max_center_refit_px=max(refits),independent_SEM_refits=108,pair_checks=pair_checks,fresh_controls=preflight,timing_seconds=timing,median_inference_seconds=float(np.median(timing)) if timing else None,timing_scope='Same first1536x2048field,1warmup+3timed,FP32TF32off,includesmodelpre/postprocessing,excludesdisk and readout; not cross-hardware guarantee',records=records,sem_inputs=sem_inputs,sources=source_files,legacy_overlap_affected=tag=='V42_old',model_promoted=False));atomic(out/'status.json',dict(phase='complete',frames=201,total=201));print(tag,'complete',info['summary'],flush=True)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('tag');args=parser.parse_args()
    try:main(args.tag)
    except BaseException:
        save(ROOT/f'results/{args.tag}/failure.json',dict(error=traceback.format_exc(),utc=now()));raise
