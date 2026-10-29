"""Create the complete preassigned bank, retaining every attempted parent."""
import os
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
import sys,time,json,traceback,shutil
from concurrent.futures import ProcessPoolExecutor,as_completed
from collections import Counter
from pathlib import Path
from common import *
sys.path.insert(0,str(ROOT))
from data.generator import generate,parameters,categories

def main(workers=4):
    cfg=load(ROOT/'config/study.json');out=ROOT/'data/package'
    if out.exists():raise FileExistsError('Bank already exists; inspect explicitly before any recovery')
    if shutil.disk_usage(ROOT).free<30*2**30:raise RuntimeError('Insufficient reserved working space')
    recipe={k:cfg[k] for k in ['splits','split_seeds','categories','category_weights','native_field','supervised_core','render_factor','latent_factor','data_admission']}
    recipe['sources']={str(p):sha(p) for p in [ROOT/'data/generator.py',R125/'data/generator_v2.py']}
    plan=[]
    for split,n in cfg['splits'].items():
        for i in range(n):
            m,_=parameters(split,i)
            plan.append({k:m[k] for k in ['parent_id','split','index','category','geometry_sha256']})
    shapes={}
    for p in plan:
        if p['category']=='flat_negative':continue
        h=p['geometry_sha256']
        if h in shapes:raise ValueError(f'Duplicate parent geometry: {p} and {shapes[h]}')
        shapes[h]=p
    out.mkdir(parents=True)
    save(out/'plan.json',dict(created_utc=now(),recipe=recipe,parents=plan))
    start=time.perf_counter();entries=[]
    status=ROOT/'runs/launcher_logs/data_progress.json'
    atomic(status,dict(status='generating',pid=os.getpid(),total=len(plan),completed=0,started_utc=now(),workers=workers))
    try:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            jobs={pool.submit(generate,(p['split'],p['index'],str(out))):p for p in plan}
            for job in as_completed(jobs):
                entry=job.result();entries.append(entry)
                with (out/'generation.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(entry,allow_nan=False)+'\n')
                atomic(status,dict(status='generating',pid=os.getpid(),total=len(plan),completed=len(entries),bytes=sum(e['bytes'] for e in entries),seconds=time.perf_counter()-start,last_parent=entry['parent_id']))
                print(json.dumps(dict(completed=len(entries),total=len(plan),parent=entry['parent_id'],seconds=round(time.perf_counter()-start,1))),flush=True)
        for p,h in recipe['sources'].items():
            if sha(p)!=h:raise RuntimeError('Generator changed during bank generation')
        limits=cfg['data_admission'];fail=[]
        for e in entries:
            for c in e['checks']:
                if c['model_fit_rms_sigma']>limits['model_render_rms_noise_units_max'] or c['model_fit_p99_sigma']>limits['model_render_p99_noise_units_max'] or c['area_target_error']>limits['area_target_max_error'] or max(map(abs,c['PSF_centroid_xy']))>1e-8:
                    fail.append(dict(parent=e['parent_id'],check=c))
            if sha(out/e['arrays_path'])!=e['arrays_sha256'] or sha(out/e['metadata_path'])!=e['metadata_sha256']:raise RuntimeError('Bank identity changed')
        entries.sort(key=lambda e:(e['split'],e['index']))
        save(out/'manifest.json',dict(created_utc=now(),plan=record(out/'plan.json'),entries=entries,external_sources=[],real_or_SEM_training_inputs=False))
        check=dict(passed=not fail,parents=len(entries),counts={s:dict(Counter(e['category'] for e in entries if e['split']==s)) for s in cfg['splits']},unique_nonflat_geometries=len(shapes),parent_splits_disjoint=True,formation_failed_parents=fail,maximum_model_fit_rms_sigma=max(c['model_fit_rms_sigma'] for e in entries for c in e['checks']),maximum_model_fit_p99_sigma=max(c['model_fit_p99_sigma'] for e in entries for c in e['checks']),maximum_area_error=max(c['area_target_error'] for e in entries for c in e['checks']),saturated_core_pixels=sum(c['core_saturation_count'] for e in entries for c in e['checks']),bytes=sum(e['bytes'] for e in entries),seconds=time.perf_counter()-start,manifest=record(out/'manifest.json'))
        save(ROOT/'results/data_audit.json',check)
        if fail:raise RuntimeError('Physical data admission failed; retain every parent for investigation')
        atomic(status,dict(status='complete',pid=os.getpid(),completed=len(entries),total=len(plan),audit=record(ROOT/'results/data_audit.json'),seconds=time.perf_counter()-start))
    except BaseException:
        atomic(status,dict(status='failed',pid=os.getpid(),completed=len(entries),total=len(plan),error=traceback.format_exc(),seconds=time.perf_counter()-start))
        raise

if __name__=='__main__':main()
