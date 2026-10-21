from common133 import *
import subprocess,traceback

def main():
    out=ROOT/'results/real'
    while not (out/'cases.json').exists():
        if list((ROOT/'results').glob('failure_*.json')):raise RuntimeError('Inference failed')
        time.sleep(.5)
    verify();cmd=f"addpath('{(PKG/'validation').as_posix()}');"+''.join(f"extract_sem('{(out/arm).as_posix()}');" for arm in ARMS)
    with (out/'matlab.log').open('xb') as log:
        result=subprocess.run([r'C:\Program Files\MATLAB\R2025b\bin\matlab.exe','-batch',cmd],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode==0,'See MATLAB log'
    ref=loadmat(PKG/'validation/sem_reference.mat',variable_names=['truth_cells','truth_masks','opt_pitch']);scale=5000/ref['opt_pitch'].item();truth={};points={};rows=[]
    for i in range(36):
        mask=ref['truth_masks'][:,:,i].astype(bool);c,r=mask_center_radius(mask);truth[i+1]=core.measure_boundary_and_circles(ref['truth_cells'][:,:,i],c,r,coarse_mask=mask,sample_count=180,normal_half_width_px=3.,polarity='auto');points[f'SEM_{i+1}']=truth[i+1].inflection_points_xy
    for arm in ARMS:
        d=loadmat(out/arm/'sem_masks.mat')
        for k,e in enumerate([13,14,15]):
            for i in range(36):
                row=dict(arm=arm,exposure=e,pillar=i+1,valid=bool(d['valid'][i,k]))
                if row['valid']:
                    try:
                        mask=d['masks'][:,:,i,k].astype(bool);c,r=mask_center_radius(mask);m=core.measure_boundary_and_circles(d['cells'][:,:,i,k],c,r,coarse_mask=mask,sample_count=144,normal_half_width_px=3.,polarity='auto');t=truth[i+1];a,b=radial_signature(m),radial_signature(t)
                        row.update(radial_nm=float(abs(a-b).mean()*scale),correlation=float(np.corrcoef(a-a.mean(),b-b.mean())[0,1]),diameter_error_nm=float(2*abs(m.circles.lsc.radius-t.circles.lsc.radius)*scale),signed_diameter_nm=float(2*(m.circles.lsc.radius-t.circles.lsc.radius)*scale),centered_shape_nm=float(abs((a-a.mean())-(b-b.mean())).mean()*scale),MZC_error_nm=float(abs(m.circles.mzc_zone_width-t.circles.mzc_zone_width)*scale),cx=m.circles.lsc.cx,cy=m.circles.lsc.cy,radius=m.circles.lsc.radius)
                        points[f'{arm}_{e}_{i+1}']=m.inflection_points_xy
                    except Exception as ex:row.update(valid=False,failure=str(ex))
                rows.append(row)
        print('SEM',arm,flush=True)
    t=pd.DataFrame(rows);assert len(t)==972;t.to_csv(out/'measurements.csv',index=False);np.savez_compressed(out/'points.npz',**points)
    metrics=['radial_nm','correlation','diameter_error_nm','signed_diameter_nm','centered_shape_nm','MZC_error_nm'];by=t.groupby(['arm','pillar'])[metrics].median().reset_index();by.to_csv(out/'per_pillar.csv',index=False);s=by.groupby('arm')[metrics].median();s.to_csv(out/'summary.csv')
    ref=pd.read_csv(R132/'results/all_sem/summary.csv');ref=ref[(ref.width==16)&(ref.population=='all36')].iloc[0]
    for k in metrics:assert abs(s.loc['Final',k]-ref[k])<1e-5
    save(out/'complete.json',dict(rows=972,invalid_rows=int((~t.valid).sum()),scale_nm_per_px=scale,Final_reproduces_R132_W16=True,source=rec(__file__)));print(s.to_string(),flush=True)

if __name__=='__main__':
    try:main()
    except BaseException:
        save(ROOT/f'results/failure_sem_{time.time_ns()}.json',dict(error=traceback.format_exc(),utc=now()));raise
