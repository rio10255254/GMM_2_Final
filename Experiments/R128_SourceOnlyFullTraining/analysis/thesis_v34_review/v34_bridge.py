"""Replay the thesis's fixed population/reader in a separate supplemental study."""
import os,sys,json,time,argparse,hashlib,importlib.util
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/thesis_v34_review_20260912/v34_bridge';sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT))
from common import load,save,record,sha,now
import numpy as np,pandas as pd,cv2
PROJECT_ROOT = Path(__file__).resolve().parents[4]
THESIS=Path('C:/Users/Rio/OneDrive/學業/碩班/論文');ASSETS=THESIS/'可用/_thesis_assets_v34/lsc_mzc_comparison'
MODEL='R128_P_s1285002'

def prepare():
    OUT.mkdir(parents=True,exist_ok=False);old=load(ROOT/'results/lsc_comparison/plan.json');cfg=load(str(PROJECT_ROOT / old['configuration']['path']))
    pairs=pd.read_csv(ASSETS/'per_pair_lsc_mzc.csv');pairs=pairs[(pairs.method=='Raw')&(pairs.center=='LSC')];assert len(pairs)==120
    cache={x['source']['sha256']:dict(image=x['image'],output_float=x['output_float']) for x in load(ROOT/'results/lsc_comparison/inference_complete.json')['outputs']}
    sp=load(ROOT/'results/structure_check/plan.json');sr={x['key']:x for x in sp['sources']}
    for x in load(ROOT/'results/structure_check/inference.json')['outputs']:cache.setdefault(sr[x['key']]['source']['sha256'],dict(image=None,output_float=x['output']))
    frames=[]
    for seq,spec in cfg['sequences'].items():
        group=pairs[pairs.sequence==seq]
        for i in sorted(set(group.start_frame_index)|set(group.end_frame_index)):
            source=record(Path(spec['raw_dir'])/f'frame_{i:04d}.bmp');v42=record(Path(spec['v42_dir'])/f'frame_{i:04d}.bmp')
            reused=cache.get(source['sha256'])
            if reused:
                for r in reused.values():
                    if r:assert sha(str(PROJECT_ROOT / r['path']))==r['sha256']
            frames.append(dict(sequence=seq,frame_index=int(i),source=source,V42=v42,reuse=reused))
    assert len(frames)==166
    sources=[record(ASSETS/name) for name in ['analysis_manifest.json','centers_lsc_mzc.csv','per_pair_lsc_mzc.csv','combined_summary_lsc_mzc.csv']]
    for key in ['srcnn','unet','vdsr','edsr','rdn','nafnet','pft']:sources.append(record(ROOT.parent/f'R81_MultiArchitectureReferenceCircleBenchmark/results/evaluation/{key}/displacement_per_pair.csv'))
    sources += [record(THESIS/'analyze_v34_lsc_mzc.py'),record(ROOT.parent/'R81_MultiArchitectureReferenceCircleBenchmark/scripts/evaluate_model.py'),record(ROOT.parent/'R80_InflectionReferenceCircleSEMValidation/scripts/reference_circle_core.py'),record(ROOT/'analysis/lsc_comparison/measure.py')]
    plan=dict(created_utc=now(),purpose='Assess replacing v34thesisV42with fixedR128 using its actual120pairs; no rewriting priorrecords.',source=record(__file__),configuration=old['configuration'],sessions=old['sessions'],checkpoint=old['checkpoint_R128'],frames=frames,sources=sources,
        population='166frames/120pairs/9pillars; same v34Raw-onlyselection; all cases retained.',
        reader='Exact v34loop order by sequence/frame/pillar and unchanged R80core, initialskimagecurvaturecycle reset once per method, notperpillar. RawandV42must reproduce v34centers before accepting modelcomparison. Preserve the difference from recentper-pillar-resetreader.',
        candidate='Same validated R128fullFOV output andRawguard, same8bitrounding. Reuse only verified same-source/same-weightoutputs.',
        limitations=['Same system and reused development, not new unseen confirmation.','Seven old baselines have different training/inference policies; comparison of fixed outputs, not pure architecture.','This bridge does not establish thesisSEMmaxgradient/MZC or inference-speed claims.'],new_training_updates=0,no_confirmation_access=True)
    save(OUT/'plan.json',plan);pairs.to_csv(OUT/'locked_pairs.csv',index=False)
    print(json.dumps(dict(frames=len(frames),new_inference=sum(x['reuse'] is None for x in frames),reused=sum(x['reuse'] is not None for x in frames))),flush=True)

def infer():
    import torch
    from model.network import Model
    from training.engine import setup
    from evaluation.real import read_image,predict
    from train import verify_binding
    p=load(OUT/'plan.json');verify_binding(load(ROOT/'config/frozen_training.json'));assert sha(p['checkpoint']['path'])==p['checkpoint']['sha256']
    setup(1285002);payload=torch.load(p['checkpoint']['path'],map_location='cpu');m=Model(payload['model_config']).to('cuda');m.load_state_dict(payload['model']);m.eval();records=[];start=time.perf_counter()
    for n,f in enumerate(p['frames'],1):
        dest=OUT/'images'/f['sequence']/f"frame_{f['frame_index']:04d}";dest.mkdir(parents=True,exist_ok=False)
        if f['reuse']:
            r=f['reuse'];float_record=r['output_float'];assert sha(float_record['path'])==float_record['sha256']
            if r['image']:image_record=r['image'];assert sha(image_record['path'])==image_record['sha256']
            else:
                with np.load(float_record['path']) as z:out=z['output']
                assert cv2.imwrite(str(dest/'reconstruction.png'),np.rint(out*255).clip(0,255).astype(np.uint8));image_record=record(dest/'reconstruction.png')
        else:
            out,neural,w=predict(m,read_image(f['source']));np.savez_compressed(dest/'output_float.npz',output=out,neural_output=neural)
            assert cv2.imwrite(str(dest/'reconstruction.png'),np.rint(out*255).clip(0,255).astype(np.uint8));image_record=record(dest/'reconstruction.png');float_record=record(dest/'output_float.npz')
            print(json.dumps(dict(sequence=f['sequence'],frame=f['frame_index'],processed=n,total=len(p['frames']),elapsed_seconds=round(time.perf_counter()-start,1))),flush=True)
        r=dict(sequence=f['sequence'],frame_index=f['frame_index'],source=f['source'],image=image_record,output_float=float_record,reused=f['reuse'] is not None);save(dest/'record.json',r);records.append(r)
    verify_binding(load(ROOT/'config/frozen_training.json'));save(OUT/'inference_complete.json',dict(completed_utc=now(),records=records,source=record(__file__),seconds=time.perf_counter()-start))
    print('All166R128outputsavailable',flush=True)

def measure():
    sys.path.insert(0,str(ROOT/'analysis/lsc_comparison'));from measure import reader,pair_table
    p=load(OUT/'plan.json');cfg=load(p['configuration']['path']);core,scope=reader(p);locked=pd.read_csv(OUT/'locked_pairs.csv');oldcenters=pd.read_csv(ASSETS/'centers_lsc_mzc.csv');results=[];parity=[]
    for method in ['Raw','MOSR',MODEL]:
        folder=OUT/'measurements'/method;folder.mkdir(parents=True,exist_ok=False);scope['reset_curvature_cycle']();rows=[]
        for n,f in enumerate(p['frames'],1):
            source=f['source'] if method=='Raw' else f['V42'] if method=='MOSR' else None
            if source is None:
                rec=OUT/'images'/f['sequence']/f"frame_{f['frame_index']:04d}"/'record.json'
                while not rec.is_file():time.sleep(1)
                source=load(rec)['image']
            assert sha(source['path'])==source['sha256'];image=scope['load_grayscale'](Path(source['path']));s=cfg['sequences'][f['sequence']];base=np.asarray(s['centers'],float);mag=s['magnification'];half=int(np.ceil(.46*s['pitch_px']))
            predicted=scope['session_prediction'](f['sequence'],f['frame_index'],base,s['expected_signed_dx_px'])
            for pid,x,y in predicted:
                patch,pc,origin=core.crop_around(image,(float(x),float(y)),half)
                # Deliberately retain the thesis's processing-order state; do not silently substitute the newer reader.
                m=core.measure_inflection_lsc(patch,pc,s['radius_px'],sample_count=64 if mag=='20x' else 96,acm_iterations=13 if mag=='20x' else 15,normal_half_width_px=2.4 if mag=='20x' else 4.,polarity='dark')
                rows.append(dict(sequence=f['sequence'],frame_index=f['frame_index'],method=method,pillar_id=int(pid),lsc_center_x_px=m.lsc.cx+origin[0],lsc_center_y_px=m.lsc.cy+origin[1],lsc_radius_px=m.lsc.radius,magnification=mag,object_um_per_px=s['object_um_per_px']))
            if n%40==0:print(json.dumps(dict(method=method,frames=n,total=166)),flush=True)
        table=pd.DataFrame(rows);assert len(table)==1494;table.to_csv(folder/'centers.csv',index=False)
        if method!='Raw' and method!='MOSR':assert len(parity)==2 and all(x['passed'] for x in parity)
        else:
            other=oldcenters[oldcenters.method==method];joined=table.merge(other,on=['sequence','frame_index','method','pillar_id'],suffixes=('','_old'),validate='one_to_one');assert len(joined)==1494
            error={k:float((joined[k]-joined[k+'_old']).abs().max()) for k in ['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']}
            entry=dict(method=method,errors=error,passed=max(error.values())<1e-7);parity.append(entry);save(folder/'parity.json',entry);assert entry['passed'],entry
        pairs,pp=pair_table(table,locked,cfg,method);pairs.to_csv(folder/'per_pair.csv',index=False);pp.to_csv(folder/'per_pillar_pair.csv',index=False);summary=scope['summarize_pairs'](pairs);summary.to_csv(folder/'summary.csv',index=False);results.append(pairs)
        print(summary[summary.scope=='all_four_sequences'].to_string(index=False),flush=True)
    combined=pd.concat(results,ignore_index=True);combined.to_csv(OUT/'three_method_pairs.csv',index=False)
    scope['summarize_pairs'](combined).to_csv(OUT/'three_method_summary.csv',index=False)
    save(OUT/'measurement_complete.json',dict(completed_utc=now(),per_method1494centers=True,all120pairs=True,baseline_reader_parity=parity,source=record(__file__),plan=record(OUT/'plan.json'),new_training_updates=0))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('action',choices=['prepare','infer','measure']);args=a.parse_args();globals()[args.action]()
