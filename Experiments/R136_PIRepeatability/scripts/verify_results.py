import os
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='1'
from common import *
import argparse
from reader import measure
import numpy as np,pandas as pd,cv2
from scipy import ndimage,optimize

def independent_fit(a,b,initial,roi):
    x,y,w,h=roi;dx,dy=initial
    # Fixed interior samples remain inside both images throughout a local +/-0.4px fit.
    xx=np.arange(x+max(3,int(np.ceil(-dx))+3),x+w-max(3,int(np.ceil(dx))+3),3)
    yy=np.arange(y+max(3,int(np.ceil(-dy))+3),y+h-max(3,int(np.ceil(dy))+3),3)
    gy,gx=np.meshgrid(yy,xx,indexing='ij');target=a[gy,gx].ravel();gx=gx.ravel();gy=gy.ravel();spline=ndimage.spline_filter(b,order=3)
    def residual(p):
        moved=ndimage.map_coordinates(spline,[gy+p[1],gx+p[0]],order=3,prefilter=False)
        return moved-p[2]*target-p[3]
    result=optimize.least_squares(residual,[dx,dy,1,0],bounds=([dx-.4,dy-.4,.5,-.3],[dx+.4,dy+.4,1.5,.3]),diff_step=1e-4,ftol=1e-9,xtol=1e-8,gtol=1e-8,max_nfev=30)
    return dict(dx_px=float(result.x[0]),dy_px=float(result.x[1]),gain=float(result.x[2]),offset=float(result.x[3]),success=bool(result.success),at_shift_bound=bool(np.any(np.abs(result.x[:2]-[dx,dy])>.395)),residual_rms=float(np.sqrt(np.mean(result.fun**2))))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--models',nargs='+',default=['Raw','R61','R129']);ap.add_argument('--tables',default='results/tables');args=ap.parse_args()
    plan=load(ROOT/'config/plan.json');tables=ROOT/args.tables;summary=pd.read_csv(tables/'summary.csv');scans=pd.read_csv(tables/'per_scan.csv');allrows=pd.read_csv(tables/'all_measurements.csv')
    for model in args.models:assert len(list((ROOT/'results/readouts'/model).glob('*.csv')))==30
    checked=0;sampled_exports=0
    for model in [m for m in args.models if m!='Raw']:
        complete=load(ROOT/'results'/model/'complete.json');assert len(complete['records'])==930
        for k,r in enumerate(complete['records']):
            assert sha(r['values']['path'])==r['values']['sha256']
            with np.load(r['values']['path']) as z:v=z['output'];assert v.shape==(1544,2064) and np.isfinite(v).all()
            assert Path(r['image']['path']).exists();checked+=1
            if k in [0,15,30,465,899,929]:
                png=cv2.imread(r['image']['path'],cv2.IMREAD_UNCHANGED);assert png.dtype==np.uint16 and np.array_equal(png,np.rint(v*65535).astype(np.uint16));sampled_exports+=1
    for f in plan['frames']:assert sha(f['source']['path'])==f['source']['sha256']
    for info in plan['models'].values():assert sha(info['checkpoint']['path'])==info['checkpoint']['sha256']
    # Independently recompute physical error from the stored pixel displacement, not stored derived columns.
    cal=load(tables/'calibration.json');u=np.array(cal['axis_unit_vector']);maxdiff=0.
    for view,g in allrows.groupby('view'):
        scale=cal['estimated_um_per_px'] if view=='calibrated_late24' else .1725
        error=(np.einsum('ij,j->i',g[['dx_px','dy_px']].to_numpy(),u)*scale-g.pi_dy_um.to_numpy())*1000
        maxdiff=max(maxdiff,float(np.max(np.abs(error-g.error_nm.to_numpy()))))
    assert maxdiff<.0001
    for _,r in summary.iterrows():
        g=scans[(scans.view==r['view'])&(scans.model==r['model'])&(scans.kind==r['kind'])];assert abs(g.mae_nm.mean()-r['mae_nm_mean'])<1e-6
    frames={(f['run'],f['index']):f for f in plan['frames']}
    def image(model,run,index):
        if model=='Raw':return cv2.imread(frames[(run,index)]['source']['path'],0).astype(np.float64)/255
        with np.load(ROOT/'results'/model/run/f'{index+1:02d}.npz') as z:return z['output'].astype(np.float64)
    rows=[]
    primary=allrows[(allrows.view=='nominal_all30')&(allrows.roi=='primary')&(allrows.reader=='highpass')&(allrows.precision=='full')]
    for model in args.models:
        m=primary[primary.model==model]
        samples=pd.concat([m[(m.run_index==1)&(m.kind=='adjacent')&(m.j==1)],m[(m.run_index==30)&(m.kind=='start')&(m.j==30)],m.loc[[m.error_nm.abs().idxmax()]]]).drop_duplicates(['run','kind','i','j'])
        for _,r in samples.iterrows():
            a=image(model,r.run,int(r.i));b=image(model,r.run,int(r.j));replay=measure(a,b,plan['rois']['primary']);difference=float(np.hypot(replay['dx_px']-r.dx_px,replay['dy_px']-r.dy_px));assert difference<.002
            fit=independent_fit(a,b,[r.dx_px,r.dy_px],plan['rois']['primary']);rows.append(dict(model=model,run=r.run,i=int(r.i),j=int(r.j),reader_replay_error_px=difference,independent_dx_px=fit['dx_px'],independent_dy_px=fit['dy_px'],independent_along_difference_nm=float((np.array([fit['dx_px']-r.dx_px,fit['dy_px']-r.dy_px])@u)*.1725*1000),**{k:v for k,v in fit.items() if k not in ['dx_px','dy_px']}))
    pd.DataFrame(rows).to_csv(tables/'independent_reader_checks.csv',index=False,encoding='utf-8-sig')
    save(tables.parent/'verification.json',dict(complete=True,models=args.models,reconstruction_arrays_checked=checked,export_images_sampled=sampled_exports,source_images_unchanged=930,model_weights_unchanged=True,arithmetic_max_difference_nm=maxdiff,replayed_pairs=len(rows),independent_method_scope='representative and worst samples,photometric least-squares;different spatial weighting,reported differences not discarded',completed_utc=now()))
    print('Verified',checked,'reconstructions,930sources; arithmetic max',maxdiff,flush=True)
if __name__=='__main__':main()
