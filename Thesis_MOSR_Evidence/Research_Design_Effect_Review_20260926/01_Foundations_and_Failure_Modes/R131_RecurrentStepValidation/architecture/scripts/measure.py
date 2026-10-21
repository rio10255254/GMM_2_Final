"""Same external readers at every prefix; all saved points retained."""
from study import *
import argparse,subprocess,traceback
from scipy.io import loadmat
from validation import reference_circle_core as semcore
from validation.readout_helpers import mask_center_radius,radial_signature

def wait_image(p):
    while not p.exists():
        if list((ROOT/'results').glob('failure_infer_*.json')):raise RuntimeError('Inference failed; retain partial measurements')
        time.sleep(1)

def motion(n):
    verify_sources();tag=f'N{n}';out=ROOT/'results/measurements'/tag;out.mkdir(parents=True,exist_ok=False)
    cfg=load(PLAN['configuration']['path']);core,scope=reader(PLAN);tables=[];repeated=[];start=time.perf_counter()
    save(out/'started.json',dict(utc=now(),pid=os.getpid(),source=rec(__file__)))
    for j,frame in enumerate(PLAN['frames']):
        imagepath=ROOT/'results/images'/tag/frame['sequence']/f"frame_{frame['frame_index']:04d}.png"
        recordpath=ROOT/'results/records'/frame['sequence']/f"frame_{frame['frame_index']:04d}.json"
        wait_image(recordpath);record=next(r for r in load(recordpath)['images'] if r['step']==n)
        assert sha(imagepath)==record['sha256'];assert sha(frame['source']['path'])==frame['source']['sha256']
        raw=scope['load_grayscale'](Path(frame['source']['path']));image=scope['load_grayscale'](imagepath)
        table,points=scope['measure_frame'](core,scope,frame['sequence'],frame['frame_index'],cfg['sequences'][frame['sequence']],raw,image,tag)
        if frame['sequence'] not in repeated:
            again,_=scope['measure_frame'](core,scope,frame['sequence'],frame['frame_index'],cfg['sequences'][frame['sequence']],raw,image,tag)
            assert np.array_equal(table[['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']],again[['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']]);repeated.append(frame['sequence'])
        folder=out/frame['sequence']/f"frame_{frame['frame_index']:04d}";folder.mkdir(parents=True)
        table.to_csv(folder/'centers.csv',index=False);np.savez_compressed(folder/'boundaries.npz',**points);tables.append(table)
        status(out/'status.json',dict(status='running',frames=j+1,total=201,seconds=time.perf_counter()-start))
        if j%25==0:print(tag,'LSC',j+1,'/201',round(time.perf_counter()-start,1),flush=True)
    centers=pd.concat(tables,ignore_index=True);assert len(centers)==1809;centers.to_csv(out/'centers.csv',index=False)
    fixed=pd.read_csv(PLAN['locked_pairs']['path']);adj=pd.read_csv(PLAN['adjacent_pairs']['path'])
    for label,pairs in [('locked120',fixed),('within_session194',adj[~adj.is_repositioning]),('repositioning3',adj[adj.is_repositioning])]:
        per,pillars=scope['pair_table'](centers,pairs,cfg,tag)
        per.to_csv(out/(label+'_pairs.csv'),index=False);pillars.to_csv(out/(label+'_pillar_pairs.csv'),index=False)
        scope['summarize_pairs'](per).to_csv(out/(label+'_summary.csv'),index=False)
    parity={}
    if n==4:
        old=pd.read_csv(OLD/'measurements/R129/centers.csv');joint=centers.merge(old,on=['sequence','frame_index','pillar_id'],validate='one_to_one',suffixes=('','_old'));assert len(joint)==1809
        for key in ['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']:
            parity[key]=float(abs(joint[key]-joint[key+'_old']).max());assert parity[key]<1e-7
    save(out/'complete.json',dict(utc=now(),frames=201,centers=1809,repeat_sequences=repeated,old_four_step_parity=parity,seconds=time.perf_counter()-start))
    status(out/'status.json',dict(status='complete',frames=201,total=201));print(tag,'LSC complete',flush=True)

def sem():
    verify_sources();out=ROOT/'results/sem';start=time.perf_counter()
    for n in range(5):wait_image(out/f'N{n}/sem15.png')
    cmds="addpath('"+str(PKG/'validation').replace('\\','/')+"');"
    for n in range(5):cmds+="extract_sem('"+str(out/f'N{n}').replace('\\','/')+"');"
    with (out/'matlab.log').open('xb') as f:
        proc=subprocess.run([r'C:\Program Files\MATLAB\R2025b\bin\matlab.exe','-batch',cmds],stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    assert proc.returncode==0,'SEM extraction failure; retain MATLAB log'
    ref=loadmat(PKG/'validation/sem_reference.mat');scale=5000/float(ref['opt_pitch'].item());truth={};points={};rows=[]
    for i in range(36):
        mask=ref['truth_masks'][:,:,i].astype(bool);c,r=mask_center_radius(mask)
        truth[i]=semcore.measure_boundary_and_circles(ref['truth_cells'][:,:,i],c,r,coarse_mask=mask,sample_count=180,normal_half_width_px=3.,polarity='auto')
        points[f'SEM_{i+1}']=truth[i].inflection_points_xy
    for n in range(5):
        d=loadmat(out/f'N{n}/sem_masks.mat');assert d['valid'].all()
        for k,e in enumerate([13,14,15]):
            for i in range(36):
                mask=d['masks'][:,:,i,k].astype(bool);c,r=mask_center_radius(mask)
                m=semcore.measure_boundary_and_circles(d['cells'][:,:,i,k],c,r,coarse_mask=mask,sample_count=144,normal_half_width_px=3.,polarity='auto');t=truth[i]
                a,b=radial_signature(m),radial_signature(t)
                rows.append(dict(step=n,exposure=e,pillar=i+1,radial_nm=float(abs(a-b).mean()*scale),correlation=float(np.corrcoef(a-a.mean(),b-b.mean())[0,1]),diameter_error_nm=float(2*abs(m.circles.lsc.radius-t.circles.lsc.radius)*scale),signed_diameter_nm=float(2*(m.circles.lsc.radius-t.circles.lsc.radius)*scale),MZC_error_nm=float(abs(m.circles.mzc_zone_width-t.circles.mzc_zone_width)*scale),centered_shape_nm=float(abs((a-a.mean())-(b-b.mean())).mean()*scale),cx=m.circles.lsc.cx,cy=m.circles.lsc.cy,radius=m.circles.lsc.radius))
                points[f'N{n}_{e}_{i+1}']=m.inflection_points_xy
            print('SEM',n,e,flush=True)
        pd.DataFrame(rows).to_csv(out/'progress_measurements.csv',index=False)
    table=pd.DataFrame(rows);assert len(table)==540 and np.isfinite(table.select_dtypes('number')).all().all()
    table.to_csv(out/'measurements.csv',index=False);np.savez_compressed(out/'points.npz',**points)
    metrics=['radial_nm','correlation','diameter_error_nm','signed_diameter_nm','MZC_error_nm','centered_shape_nm']
    by=table.groupby(['step','pillar'])[metrics].median().reset_index();by.to_csv(out/'per_pillar.csv',index=False)
    summ=by.groupby('step')[metrics].median();summ.to_csv(out/'summary.csv')
    reference=pd.read_csv(ROOT.parent/'R130_CleanV42Comparison/results/comparison.csv').iloc[0]
    for key in [k for k in metrics if k!='signed_diameter_nm']:assert abs(summ.loc[4,key]-float(reference[key]))<1e-5,(key,summ.loc[4,key],reference[key])
    save(out/'complete.json',dict(utc=now(),rows=540,pillars=36,steps=5,scale_nm_per_px=scale,old_four_step_metrics_match=True,seconds=time.perf_counter()-start))
    print(summ.to_string(),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['sem','motion']);p.add_argument('--step',type=int,choices=range(5));a=p.parse_args()
    try:sem() if a.mode=='sem' else motion(a.step)
    except BaseException:
        save(ROOT/f'results/failure_{a.mode}_{a.step}_{time.time_ns()}.json',dict(error=traceback.format_exc(),utc=now()));raise
