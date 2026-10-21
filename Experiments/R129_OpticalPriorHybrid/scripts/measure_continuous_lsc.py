"""Apply the locked LSC reader to every source frame or completed R129 reconstruction."""
import os,sys,time,argparse,traceback
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('MKL_NUM_THREADS','1')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from continuous_common import *
def main(method):
    plan=load(OUT/'plan.json');cfg=load(plan['configuration']['path']);core,scope=reader(plan)
    for item in plan['protected_sources']:assert sha(item['path'])==item['sha256']
    out=OUT/'measurements'/method;out.mkdir(parents=True,exist_ok=False);tables=[];records=[];repeats=[];start=time.perf_counter()
    save(out/'started.json',dict(utc=now(),method=method,plan=record(OUT/'plan.json'),source=record(__file__)))
    try:
        for n,frame in enumerate(plan['frames'],1):
            if method=='Raw':image_source=frame['source']
            else:
                rec=OUT/'images'/frame['sequence']/f"frame_{frame['frame_index']:04d}"/'record.json'
                while not rec.exists():
                    status=OUT/'inference_status.json'
                    if status.exists() and load(status)['status']=='failed':raise RuntimeError('Reconstruction failed; retain all measurements')
                    time.sleep(2)
                image_source=load(rec)['image']
            assert sha(image_source['path'])==image_source['sha256']
            raw=scope['load_grayscale'](Path(frame['source']['path']));image=scope['load_grayscale'](Path(image_source['path']));assert raw.shape==image.shape
            table,points=scope['measure_frame'](core,scope,frame['sequence'],frame['frame_index'],cfg['sequences'][frame['sequence']],raw,image,method)
            if frame['sequence'] not in repeats:
                second,_=scope['measure_frame'](core,scope,frame['sequence'],frame['frame_index'],cfg['sequences'][frame['sequence']],raw,image,method)
                assert np.array_equal(table[['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']],second[['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']]);repeats.append(frame['sequence'])
            folder=out/frame['sequence']/f"frame_{frame['frame_index']:04d}";folder.mkdir(parents=True)
            table.to_csv(folder/'centers.csv',index=False);np.savez_compressed(folder/'boundaries.npz',**points)
            records.append(dict(sequence=frame['sequence'],frame_index=frame['frame_index'],image=image_source,centers=record(folder/'centers.csv'),boundaries=record(folder/'boundaries.npz')));tables.append(table)
            atomic(out/'status.json',dict(status='measuring',frames=n,total=201,updated_utc=now()))
            if n%20==0:print(method,n,'/201',round(time.perf_counter()-start,1),'seconds',flush=True)
        centers=pd.concat(tables,ignore_index=True);assert len(centers)==1809;centers.to_csv(out/'centers.csv',index=False)
        fixed=pd.read_csv(plan['locked_pairs']['path']);allpairs=pd.read_csv(plan['adjacent_pairs']['path'])
        for name,pairs in [('locked120',fixed),('within_session194',allpairs[~allpairs.is_repositioning]),('repositioning3',allpairs[allpairs.is_repositioning])]:
            per,pillars=scope['pair_table'](centers,pairs,cfg,method);summary=scope['summarize_pairs'](per)
            per.to_csv(out/(name+'_pairs.csv'),index=False);pillars.to_csv(out/(name+'_pillar_pairs.csv'),index=False);summary.to_csv(out/(name+'_summary.csv'),index=False)
        parity={}
        if method=='Raw':
            old=pd.read_csv(REPO/'Experiments/R128_SourceOnlyFullTraining/results/lsc_comparison/measurements/Raw/centers.csv')
            joined=centers.merge(old,on=['sequence','frame_index','pillar_id'],suffixes=('','_old'),validate='one_to_one');assert len(joined)==1431
            for key in ['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']:
                parity[key]=float(abs(joined[key]-joined[key+'_old']).max());assert parity[key]<1e-7
        save(out/'complete.json',dict(completed_utc=now(),source=record(__file__),method=method,frames=201,center_rows=1809,repeat_sequences=repeats,raw_old_parity=parity,records=records,locked_summary=record(out/'locked120_summary.csv'),seconds=time.perf_counter()-start))
        atomic(out/'status.json',dict(status='complete',frames=201,updated_utc=now()));print(method,'complete',flush=True)
    except BaseException:
        save(out/'failure.json',dict(utc=now(),error=traceback.format_exc()));raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--method',choices=['Raw','R129'],required=True);a=p.parse_args();main(a.method)
