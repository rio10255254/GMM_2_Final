"""Identical deterministic LSC reader with new output locations and retained points."""
import os,sys,ast,importlib.util,argparse,time
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('MKL_NUM_THREADS','1')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,pandas as pd
from PIL import Image
import skimage.segmentation.morphsnakes as morphsnakes
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def reader(plan):
    base=ROOT.parent/'R80_InflectionReferenceCircleSEMValidation/scripts'
    path=base/'reference_circle_core.py'
    spec=importlib.util.spec_from_file_location('r128_locked_reference_core',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    scope=dict(np=np,pd=pd,Path=Path,Image=Image,SESSION_TABLE=Path(PROJECT_ROOT / plan['sessions']['path']),morphsnakes=morphsnakes)
    source=base/'run_displacement_lsc.py';wanted={'session_prediction','load_grayscale','summarize_pairs'}
    tree=ast.parse(source.read_text(encoding='utf-8-sig'))
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
    assert {n.name for n in nodes}==wanted
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),scope)
    reset=ROOT.parent/'R116_CoherentGeometryAnchorScratch/validation/run_lsc_e42.py'
    nodes=[n for n in ast.parse(reset.read_text(encoding='utf-8-sig')).body if isinstance(n,ast.FunctionDef) and n.name=='reset_curvature_cycle']
    assert len(nodes)==1
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(reset),'exec'),scope)
    return module,scope


def measure_frame(core,scope,sequence,index,specification,raw,image,method):
    centers=np.asarray(specification['centers'],float)
    predicted=scope['session_prediction'](sequence,index,centers,float(specification['expected_signed_dx_px']))
    pitch=float(specification['pitch_px']);radius=float(specification['radius_px']);scale=float(specification['object_um_per_px'])
    mag=specification['magnification'];margin=int(np.ceil(.55*pitch));half=int(np.ceil(.46*pitch))
    x0=max(0,int(np.floor(np.min(predicted[:,1])))-margin);x1=min(raw.shape[1],int(np.ceil(np.max(predicted[:,1])))+margin+1)
    y0=max(0,int(np.floor(np.min(predicted[:,2])))-margin);y1=min(raw.shape[0],int(np.ceil(np.max(predicted[:,2])))+margin+1)
    crop=image[y0:y1,x0:x1];rows=[];boundaries=[];coarse=[];strengths=[]
    for pid,px,py in predicted:
        patch,pc,origin=core.crop_around(crop,(float(px-x0),float(py-y0)),half)
        scope['reset_curvature_cycle']()
        result=core.measure_inflection_lsc(patch,pc,radius,sample_count=64 if mag=='20x' else 96,acm_iterations=13 if mag=='20x' else 15,normal_half_width_px=2.4 if mag=='20x' else 4.,polarity='dark')
        c=result.lsc;assert np.isfinite([c.cx,c.cy,c.radius]).all()
        pts=result.inflection_points_xy+np.array([origin[0]+x0,origin[1]+y0])
        rad=np.linalg.norm(result.inflection_points_xy-np.array([c.cx,c.cy]),axis=1)
        rows.append(dict(sequence=sequence,magnification=mag,frame_index=index,method=method,pillar_id=int(pid),predicted_x_px=float(px),predicted_y_px=float(py),lsc_center_x_px=c.cx+origin[0]+x0,lsc_center_y_px=c.cy+origin[1]+y0,lsc_radius_px=c.radius,gradient_strength_median=float(np.median(result.signed_gradient_strength)),object_um_per_px=scale,radial_residual_rms_px=float(np.sqrt(np.mean((rad-c.radius)**2))),radial_residual_max_abs_px=float(np.max(np.abs(rad-c.radius)))))
        boundaries.append(pts);coarse.append(result.coarse_contour_xy+np.array([origin[0]+x0,origin[1]+y0]));strengths.append(result.signed_gradient_strength)
    return pd.DataFrame(rows),dict(inflection_points=np.stack(boundaries),coarse_contours=np.stack(coarse),gradient_strength=np.stack(strengths),pillar_ids=predicted[:,0].astype(int),roi_bounds=np.array([x0,y0,x1,y1]))


def pair_table(centers,pairs,cfg,method):
    indexed=centers.set_index(['sequence','frame_index','pillar_id']);rows=[];pillar_rows=[]
    for item in pairs.itertuples(index=False):
        s=cfg['sequences'][item.sequence];scale=float(s['object_um_per_px']);nominal=float(s['nominal_step_um']);dx=[];dy=[]
        for pid,_,_ in s['centers']:
            a=indexed.loc[(item.sequence,item.start_frame_index,int(pid))];b=indexed.loc[(item.sequence,item.end_frame_index,int(pid))]
            vx=(float(b.lsc_center_x_px)-float(a.lsc_center_x_px))*scale;vy=(float(b.lsc_center_y_px)-float(a.lsc_center_y_px))*scale
            dx.append(vx);dy.append(vy)
            pillar_rows.append(dict(sequence=item.sequence,start_frame_index=item.start_frame_index,end_frame_index=item.end_frame_index,method=method,pillar_id=int(pid),dx_um=vx,dy_um=vy,radius_change_nm=float(b.lsc_radius_px-a.lsc_radius_px)*scale*1000))
        mx,my=float(np.median(dx)),float(np.median(dy))
        rows.append(dict(sequence=item.sequence,magnification=s['magnification'],pair_rank_raw_locked=item.pair_rank_raw_locked,start_frame_index=item.start_frame_index,end_frame_index=item.end_frame_index,method=method,nominal_step_um=nominal,aggregate_dx_um=mx,aggregate_dy_um=my,measured_step_um=abs(mx),nominal_abs_error_nm=abs(abs(mx)-nominal)*1000,within_grid_sd_nm=float(np.std(dx,ddof=1)*1000),cross_axis_abs_nm=abs(my)*1000))
    return pd.DataFrame(rows),pd.DataFrame(pillar_rows)


def main(method,stream=False):
    out=ROOT/'results/lsc_comparison';plan=load(out/'plan.json');cfg=load(str(PROJECT_ROOT / plan['configuration']['path']));pairs=pd.read_csv(out/'locked_pairs.csv')
    assert method in ['Raw','R61v16_PSFOFF','R128_P_s1285002']
    for source in plan['sources']:assert sha(str(PROJECT_ROOT / source['path']))==source['sha256'],str(PROJECT_ROOT / source['path'])
    if method=='R61v16_PSFOFF':assert load(out/'R61_reproduction.json')['all_exact']
    folder=out/'measurements'/method;folder.mkdir(parents=True,exist_ok=False)
    core,scope=reader(plan)
    save(folder/'started.json',dict(started_utc=now(),source=record(__file__),plan=record(out/'plan.json'),method=method,pid=os.getpid()))
    tables=[];records=[];repeat_errors=[];start=time.perf_counter()
    for n,frame in enumerate(plan['frames'],1):
        seq=frame['sequence'];idx=frame['frame_index'];source=frame['source'];assert sha(str(PROJECT_ROOT / source['path']))==source['sha256']
        if method=='Raw':image_source=source
        elif method=='R61v16_PSFOFF':image_source=frame['R61']
        else:
            rec=out/'R128_images'/seq/f'frame_{idx:04d}'/'record.json'
            while not rec.is_file():
                if not stream:raise FileNotFoundError(rec)
                time.sleep(1)
            image_source=load(rec)['image']
        assert sha(image_source['path'])==image_source['sha256']
        raw=scope['load_grayscale'](Path(PROJECT_ROOT / source['path']));image=scope['load_grayscale'](Path(image_source['path']));assert raw.shape==image.shape
        measured,points=measure_frame(core,scope,seq,idx,cfg['sequences'][seq],raw,image,method)
        if not any(x['sequence']==seq for x in repeat_errors):
            repeated,_=measure_frame(core,scope,seq,idx,cfg['sequences'][seq],raw,image,method)
            diff=float(np.max(np.abs(measured[['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']].to_numpy()-repeated[['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']].to_numpy())))
            assert diff==0;repeat_errors.append(dict(sequence=seq,max_repeat_difference_px=diff))
        frameout=folder/seq/f'frame_{idx:04d}';frameout.mkdir(parents=True,exist_ok=False)
        measured.to_csv(frameout/'centers.csv',index=False);np.savez_compressed(frameout/'boundaries.npz',**points)
        record_item=dict(sequence=seq,frame_index=idx,source=source,image=image_source,centers=record(frameout/'centers.csv'),boundaries=record(frameout/'boundaries.npz'))
        save(frameout/'record.json',record_item);records.append(record_item);tables.append(measured)
        if n%10==0 or n==len(plan['frames']):print(json.dumps(dict(method=method,frames=n,total=len(plan['frames']),seconds=round(time.perf_counter()-start,1))),flush=True)
    centers=pd.concat(tables,ignore_index=True);assert len(centers)==len(plan['frames'])*9
    per_pair,pillar_pairs=pair_table(centers,pairs,cfg,method);assert len(per_pair)==120 and len(pillar_pairs)==1080
    summary=scope['summarize_pairs'](per_pair)
    centers.to_csv(folder/'centers.csv',index=False);per_pair.to_csv(folder/'per_pair.csv',index=False);pillar_pairs.to_csv(folder/'per_pillar_pair.csv',index=False);summary.to_csv(folder/'summary.csv',index=False)
    parity={}
    if method=='Raw':
        oldpath=next(str(PROJECT_ROOT / x['path']) for x in plan['sources'] if str(PROJECT_ROOT / x['path']).endswith('four_method_lsc_centers_current_top30.csv'))
        old=pd.read_csv(oldpath);old=old[old.method=='Raw'];matched=centers.merge(old,on=['sequence','frame_index','method','pillar_id'],suffixes=('','_old'),validate='one_to_one');assert len(matched)==len(centers)==len(old)
        for key in ['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']:
            parity[key]=float((matched[key]-matched[key+'_old']).abs().max());assert parity[key]<1e-7,(key,parity[key])
        joined=per_pair.merge(pairs,on=['sequence','start_frame_index','end_frame_index','method'],suffixes=('','_old'),validate='one_to_one')
        for key in ['measured_step_um','within_grid_sd_nm','nominal_abs_error_nm','cross_axis_abs_nm']:
            parity[key]=float((joined[key]-joined[key+'_old']).abs().max());assert parity[key]<1e-7,(key,parity[key])
    save(folder/'complete.json',dict(completed_utc=now(),method=method,frames=len(records),center_rows=len(centers),pair_rows=len(per_pair),pillar_pair_rows=len(pillar_pairs),repeat_checks=repeat_errors,Raw_historical_parity_max=parity,records=records,summary=record(folder/'summary.csv'),centers=record(folder/'centers.csv'),pairs=record(folder/'per_pair.csv'),source=record(__file__),seconds=time.perf_counter()-start))
    print(summary.to_string(index=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--method',required=True);parser.add_argument('--stream',action='store_true');args=parser.parse_args();main(args.method,args.stream)
