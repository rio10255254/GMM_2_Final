"""Common real SEM and LSC measurement for each boundary policy."""
from common132 import *
import argparse,subprocess,traceback
from validation import reference_circle_core as coreSEM
from validation.readout_helpers import mask_center_radius,radial_signature

def motion(width):
    verify();tag=f'W{width}';out=ROOT/'results/measurements'/tag;out.mkdir(parents=True,exist_ok=False)
    cfg=load(PLAN['configuration']['path']);core,scope=base.reader(PLAN);tables=[];repeats=[];start=time.perf_counter()
    for j,f in enumerate(PLAN['frames']):
        case=f"{f['sequence']}/frame_{f['frame_index']:04d}";p=ROOT/'results/records'/(case+'.json');wait(p);r=next(x for x in load(p)['outputs'] if x['width']==width);assert sha(r['path'])==r['sha256']
        raw=scope['load_grayscale'](Path(f['source']['path']));image=scope['load_grayscale'](Path(r['path']))
        t,points=scope['measure_frame'](core,scope,f['sequence'],f['frame_index'],cfg['sequences'][f['sequence']],raw,image,tag)
        if f['sequence'] not in repeats:
            repeat,_=scope['measure_frame'](core,scope,f['sequence'],f['frame_index'],cfg['sequences'][f['sequence']],raw,image,tag)
            assert np.array_equal(t[['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']],repeat[['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']]);repeats.append(f['sequence'])
        dest=out/case;dest.mkdir(parents=True);t.to_csv(dest/'centers.csv',index=False);np.savez_compressed(dest/'boundaries.npz',**points);tables.append(t)
        status(out/'status.json',dict(status='running',frames=j+1,total=201))
        if j%50==0:print(tag,j+1,'/201',round(time.perf_counter()-start,1),flush=True)
    centers=pd.concat(tables,ignore_index=True);assert len(centers)==1809;centers.to_csv(out/'centers.csv',index=False)
    adj=pd.read_csv(PLAN['adjacent_pairs']['path'])
    for pop,p in [('locked120',pd.read_csv(PLAN['locked_pairs']['path'])),('within_session194',adj[~adj.is_repositioning]),('repositioning3',adj[adj.is_repositioning])]:
        per,pp=scope['pair_table'](centers,p,cfg,tag);per.to_csv(out/(pop+'_pairs.csv'),index=False);pp.to_csv(out/(pop+'_pillar_pairs.csv'),index=False);scope['summarize_pairs'](per).to_csv(out/(pop+'_summary.csv'),index=False)
    if width==80:
        old=pd.read_csv(R131/'results/measurements/N4/centers.csv');join=centers.merge(old,on=['sequence','frame_index','pillar_id'],suffixes=('','_old'),validate='one_to_one');assert len(join)==1809
        for key in ['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']:assert abs(join[key]-join[key+'_old']).max()<1e-7
    save(out/'complete.json',dict(frames=201,centers=1809,width=width,repeats=repeats,utc=now(),source=rec(__file__)));status(out/'status.json',dict(status='complete',frames=201));print(tag,'complete',flush=True)

def sem():
    wait(ROOT/'results/sem_cases.json');meta=load(ROOT/'results/sem_cases.json');cases=meta['cases'];out=ROOT/'results/all_sem';out.mkdir(exist_ok=False)
    script=PKG/'validation/extract_sem.m';helpers=script.read_text(encoding='utf-8-sig').split('function centers = sort_grid_centers',1)[1]
    # Retain old extraction functions verbatim; only case iteration and origin differ.
    wrapper='''function extract_cases()
root='ROOT_PLACEHOLDER'; ref=load('REF_PLACEHOLDER'); meta=jsondecode(fileread(fullfile(root,'results','sem_cases.json'))); cases=meta.cases;
masks=false(104,104,615); cells=zeros(104,104,615,'uint8'); valid=false(615,1); case_index=zeros(615,1); pillar=zeros(615,1); failure=strings(615,1); count=0;
for k=1:numel(cases)
 im=imread(cases(k).image.path);
 for id=reshape(cases(k).pillars,1,[])
  count=count+1; [gy,gx]=find(ref.global_index==id); center=ref.opt_centers((gy-1)*6+gx,:)-[cases(k).origin_x,cases(k).origin_y];
  cellim=extract_padded_cell(im,center,52);cells(:,:,count)=im2uint8(mat2gray(cellim));case_index(count)=k;pillar(count)=id;
  try, masks(:,:,count)=segment_acm(cellim,40,200,1.0,45);valid(count)=true;catch ME,failure(count)=string(ME.message);end
 end
end
assert(count==615);save(fullfile(root,'results','all_sem','masks.mat'),'cells','masks','valid','case_index','pillar','failure','-v7');fprintf('Valid %d/%d\\n',nnz(valid),count);
end

function centers = sort_grid_centers'''+helpers
    wrapper=wrapper.replace('ROOT_PLACEHOLDER',ROOT.as_posix()).replace('REF_PLACEHOLDER',(PKG/'validation/sem_reference.mat').as_posix())
    (ROOT/'scripts/extract_cases.m').write_text(wrapper,encoding='utf-8')
    save(out/'extraction_source.json',dict(original=rec(script),helpers_verbatim=True,wrapper=rec(ROOT/'scripts/extract_cases.m')))
    with (out/'matlab.log').open('xb') as log:
        proc=subprocess.run([r'C:\Program Files\MATLAB\R2025b\bin\matlab.exe','-batch',f"addpath('{(ROOT/'scripts').as_posix()}');extract_cases();"],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    assert proc.returncode==0,'See preserved MATLAB failure'
    d=loadmat(out/'masks.mat');ref=loadmat(PKG/'validation/sem_reference.mat',variable_names=['truth_cells','truth_masks','opt_pitch','global_index']);scale=5000/float(ref['opt_pitch'].item());truth={};points={};rows=[]
    inner=set(int(x) for x in ref['global_index'][1:5,1:5].ravel())
    for i in range(36):
        mask=ref['truth_masks'][:,:,i].astype(bool);c,r=mask_center_radius(mask);truth[i+1]=coreSEM.measure_boundary_and_circles(ref['truth_cells'][:,:,i],c,r,coarse_mask=mask,sample_count=180,normal_half_width_px=3.,polarity='auto');points[f'SEM_{i+1}']=truth[i+1].inflection_points_xy
    for j,(k,pid,valid) in enumerate(zip(d['case_index'].ravel(),d['pillar'].ravel(),d['valid'].ravel())):
        case=cases[int(k)-1];pid=int(pid);row=dict(case=case['name'],scope=case['scope'],exposure=case['exposure'],width=case['width'],margin=case['margin'],pillar=pid,region='inner16' if pid in inner else 'outer20',valid=bool(valid))
        if valid:
            try:
                mask=d['masks'][:,:,j].astype(bool);c,r=mask_center_radius(mask);m=coreSEM.measure_boundary_and_circles(d['cells'][:,:,j],c,r,coarse_mask=mask,sample_count=144,normal_half_width_px=3.,polarity='auto');t=truth[pid];a,b=radial_signature(m),radial_signature(t)
                row.update(radial_nm=float(abs(a-b).mean()*scale),correlation=float(np.corrcoef(a-a.mean(),b-b.mean())[0,1]),diameter_error_nm=float(2*abs(m.circles.lsc.radius-t.circles.lsc.radius)*scale),signed_diameter_nm=float(2*(m.circles.lsc.radius-t.circles.lsc.radius)*scale),centered_shape_nm=float(abs((a-a.mean())-(b-b.mean())).mean()*scale),MZC_error_nm=float(abs(m.circles.mzc_zone_width-t.circles.mzc_zone_width)*scale),cx=m.circles.lsc.cx,cy=m.circles.lsc.cy,radius=m.circles.lsc.radius)
                points[f'{case["name"]}_{pid}']=m.inflection_points_xy
            except Exception as ex:row.update(valid=False,failure=str(ex))
        rows.append(row)
    table=pd.DataFrame(rows);assert len(table)==615;table.to_csv(out/'measurements.csv',index=False);np.savez_compressed(out/'points.npz',**points)
    metrics=['radial_nm','correlation','diameter_error_nm','signed_diameter_nm','centered_shape_nm','MZC_error_nm']
    main=table[table.scope=='full'];assert len(main)==540
    by=main.groupby(['width','pillar','region'])[metrics].median().reset_index();by.to_csv(out/'per_pillar.csv',index=False)
    summaries=[]
    for group,subset in [('all36',by),('inner16',by[by.region=='inner16']),('outer20',by[by.region=='outer20'])]:
        s=subset.groupby('width')[metrics].median().reset_index();s['population']=group;summaries.append(s)
    pd.concat(summaries).to_csv(out/'summary.csv',index=False)
    table[table.scope=='crop'].to_csv(out/'context_measurements.csv',index=False)
    old=pd.read_csv(R131/'results/sem/per_pillar.csv');a=by[by.width==80].set_index('pillar');b=old[old.step==4].set_index('pillar')
    assert np.max(abs(a[metrics].to_numpy()-b[metrics].to_numpy()))<1e-5
    save(out/'complete.json',dict(rows=615,full_rows=540,crop_rows=75,invalid=int((~table.valid).sum()),scale_nm_per_px=scale,old80_summary_reproduced=True,source=rec(__file__)));print(pd.concat(summaries).to_string(index=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['motion','sem']);p.add_argument('--width',type=int,choices=WIDTHS);a=p.parse_args()
    try:motion(a.width) if a.mode=='motion' else sem()
    except BaseException:
        save(ROOT/f'results/failure_{a.mode}_{a.width}_{time.time_ns()}.json',dict(error=traceback.format_exc(),utc=now()));raise
