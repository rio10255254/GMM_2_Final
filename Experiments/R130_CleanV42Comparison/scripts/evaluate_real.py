"""Fixed real microscopy/SEM monitoring; metrics never update training weights."""
import os,subprocess,shutil,time
import numpy as np,pandas as pd,cv2,torch
from scipy.io import loadmat
from common import *
from output_guard import guard
from validation import reference_circle_core as core
from validation.readout_helpers import mask_center_radius,radial_signature,reset_curvature_cycle

def matlab_path():
    value=os.environ.get('MATLAB_EXE') or shutil.which('matlab')
    if value and Path(value).is_file():return value
    candidates=sorted(Path(os.environ.get('ProgramFiles','C:/Program Files')).glob('MATLAB/*/bin/matlab.exe'))
    if candidates:return str(candidates[-1])
    raise RuntimeError('MATLAB with Image Processing Toolbox is needed for the locked SEM contour measurement; set MATLAB_EXE')

def evaluate(model,out,step,device='cuda'):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if (out/'complete.json').exists():return load(out/'complete.json')
    panel=load(ROOT/'validation/panel.json');model.eval();centers=[];images=[]
    for item in panel['images']:
        source=ROOT/item['path']
        if sha(source)!=item['sha256']:raise RuntimeError('Real input changed')
        raw=cv2.imdecode(np.fromfile(source,np.uint8),0);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].to(device)
        with torch.no_grad():details=model.forward_details(x,trace=True);value=guard(x,details.output)[0,0].cpu().numpy()
        image=np.rint(value*255).clip(0,255).astype(np.uint8);path=out/(item['name']+'.png')
        if path.exists():
            if not np.array_equal(cv2.imread(str(path),0),image):raise RuntimeError('Existing evaluation output differs')
        else:
            ok,png=cv2.imencode('.png',image);assert ok
            with path.open('xb') as f:f.write(png.tobytes())
        images.append(dict(name=item['name'],image=record(path),quality=float(details.quality[0]),weak_effective_beta=float(model.network.weak_psf_block.last_beta)))
        if item['kind']=='motion':
            s=panel['sequences'][item['sequence']];gx,gy=item['global_origin']
            for pid,cx,cy in item['centers_local']:
                patch,c,origin=core.crop_around(image.astype(float)/255,(cx,cy),int(np.ceil(.46*s['pitch_px'])))
                reset_curvature_cycle();m=core.measure_inflection_lsc(patch,c,s['radius_px'],sample_count=64 if s['magnification']=='20x' else 96,acm_iterations=13 if s['magnification']=='20x' else 15,normal_half_width_px=2.4 if s['magnification']=='20x' else 4.,polarity='dark')
                centers.append(dict(sequence=item['sequence'],frame_index=item['frame_index'],pillar_id=int(pid),cx=m.lsc.cx+origin[0]+gx,cy=m.lsc.cy+origin[1]+gy))
    tables=pd.DataFrame(centers);tables.to_csv(out/'motion_centers.csv',index=False);pairs=[]
    for pair in panel['motion_pairs']:
        s=panel['sequences'][pair['sequence']];t=tables[tables.sequence==pair['sequence']]
        a=t[t.frame_index==pair['start']].set_index('pillar_id');b=t[t.frame_index==pair['end']].set_index('pillar_id')
        if len(a)!=9 or len(b)!=9:raise RuntimeError('Incomplete nine-pillar pair')
        v=(b[['cx','cy']]-a[['cx','cy']]).to_numpy()*s['object_um_per_px'];dx,dy=np.median(v,0)
        pairs.append(dict(sequence=pair['sequence'],nominal_error_nm=float(abs(abs(dx)-s['nominal_step_um'])*1000),within_grid_nm=float(np.std(v[:,0],ddof=1)*1000),cross_axis_nm=float(abs(dy)*1000)))
    motion=pd.DataFrame(pairs);motion.to_csv(out/'motion_pairs.csv',index=False)
    if not (out/'sem_masks.mat').exists():
        scriptdir=str(ROOT/'validation').replace('\\','/').replace("'","''");outputdir=str(out).replace('\\','/').replace("'","''")
        command=f"addpath('{scriptdir}'); extract_sem('{outputdir}');"
        with (out/'matlab.log').open('ab') as log:
            result=subprocess.run([matlab_path(),'-batch',command],stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode:raise RuntimeError('SEM extraction failed; inspect '+str(out/'matlab.log'))
    d=loadmat(out/'sem_masks.mat');ref=loadmat(ROOT/'validation/sem_reference.mat',variable_names=['truth_cells','truth_masks','opt_pitch'])
    if not d['valid'].all():raise RuntimeError('SEM extraction failures retained; no cases excluded')
    scale=5000/float(ref['opt_pitch'].item());truth={};points={};rows=[]
    for i in range(36):
        mask=ref['truth_masks'][:,:,i].astype(bool);c,r=mask_center_radius(mask)
        truth[i]=core.measure_boundary_and_circles(ref['truth_cells'][:,:,i],c,r,coarse_mask=mask,sample_count=180,normal_half_width_px=3.,polarity='auto')
        points[f'SEM_{i+1}']=truth[i].inflection_points_xy
    for k,exposure in enumerate([13,14,15]):
        for i in range(36):
            mask=d['masks'][:,:,i,k].astype(bool);c,r=mask_center_radius(mask)
            m=core.measure_boundary_and_circles(d['cells'][:,:,i,k],c,r,coarse_mask=mask,sample_count=144,normal_half_width_px=3.,polarity='auto');t=truth[i]
            a=radial_signature(m);b=radial_signature(t)
            rows.append(dict(exposure=exposure,pillar=i+1,radial_nm=float(np.mean(abs(a-b))*scale),correlation=float(np.corrcoef(a-a.mean(),b-b.mean())[0,1]),diameter_error_nm=float(2*abs(m.circles.lsc.radius-t.circles.lsc.radius)*scale),MZC_error_nm=float(abs(m.circles.mzc_zone_width-t.circles.mzc_zone_width)*scale),centered_shape_nm=float(np.mean(abs((a-a.mean())-(b-b.mean())))*scale)))
            points[f'{exposure}_{i+1}']=m.inflection_points_xy
    sem=pd.DataFrame(rows)
    if len(sem)!=108 or not np.isfinite(sem.select_dtypes('number')).all().all():raise RuntimeError('Invalid SEM population')
    sem.to_csv(out/'sem_measurements.csv',index=False);np.savez_compressed(out/'sem_points.npz',**points)
    metrics=['radial_nm','correlation','diameter_error_nm','MZC_error_nm','centered_shape_nm']
    summary=sem.groupby('pillar')[metrics].median().median().to_dict()
    result=dict(step=step,completed_utc=now(),SEM=summary,motion=motion.drop(columns='sequence').mean().to_dict(),SEM_measurements=108,SEM_pillars=36,motion_pairs=4,temporal_SD_not_available=True,images=images,scope='Reused fixed development panel, historical SEM correspondence; not unseen qualification')
    save(out/'complete.json',result);print('Real panel:',step,summary,flush=True);return result
