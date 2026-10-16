"""Independent arithmetic, saved-point refits and diagnostic figures for the observed failure."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rt import *
import pandas as pd,cv2
from scipy.optimize import least_squares
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    base=ROOT/'results/cross_axis_diagnosis';prec=ROOT/'results/cross_axis_precision_v2';out=ROOT/'results/cross_axis_analysis';out.mkdir(exist_ok=False)
    assert load(base/'forward_complete.json')['exact_original_fullfield_replays']==[16,17]
    assert load(prec/'complete.json')['exact_original_png_replays']==6
    t=pd.read_csv(base/'centers.csv');p=pd.read_csv(prec/'centers.csv');scale=172.5;sequence='20x_0p5um'
    def displacement(table,method,start,end):
        g=table[table.method==method];a=g[g.frame_index==start].set_index('pillar_id').sort_index();b=g[g.frame_index==end].set_index('pillar_id').sort_index();assert len(a)==len(b)==9 and a.index.equals(b.index)
        delta=(b[['lsc_center_x_px','lsc_center_y_px']]-a[['lsc_center_x_px','lsc_center_y_px']])*scale
        return delta,dict(method=method,start=start,end=end,dx_nm=float(delta.iloc[:,0].median()),dy_nm=float(delta.iloc[:,1].median()),cross_nm=float(abs(delta.iloc[:,1].median())))
    methods=[]
    for method,g in t.groupby('method'):
        if set(g.frame_index)=={16,17}:methods.append(displacement(t,method,16,17)[1])
    pd.DataFrame(methods).to_csv(out/'mechanism_comparison.csv',index=False)
    bits=[displacement(p,k,16,17)[1] for k in ['Raw_exact','C_q8','C_q10','C_q12','C_q16','C_float']];pd.DataFrame(bits).to_csv(out/'precision_comparison.csv',index=False)
    neighbors=[displacement(p,k,i,i+1)[1] for i in range(15,20) for k in ['Raw_exact','C_float','C_export8']];pd.DataFrame(neighbors).to_csv(out/'neighbor_pairs.csv',index=False)
    pillar={k:displacement(p,k,16,17)[0] for k in ['Raw_exact','C_float','C_export8']};bars=pd.DataFrame({k:v.iloc[:,1] for k,v in pillar.items()});bars['learned_change_nm']=bars.C_float-bars.Raw_exact;bars['export_change_nm']=bars.C_export8-bars.C_float;bars.to_csv(out/'nine_pillar_decomposition.csv')
    raw=next(x['cross_nm'] for x in bits if x['method']=='Raw_exact');fp=next(x['cross_nm'] for x in bits if x['method']=='C_float');q8=next(x['cross_nm'] for x in bits if x['method']=='C_q8')
    decomposition=dict(Raw_cross_nm=raw,C_float_cross_nm=fp,C_export8_cross_nm=q8,total_extra_nm=q8-raw,remaining_float_extra_nm=fp-raw,export_contribution_nm=q8-fp,export_share_of_this_case=(q8-fp)/(q8-raw),extra_displacement_pixels=(q8-raw)/scale,scope='Sequential intervention decomposition of this aggregate pair, not a universal causal percentage')
    # Original complete population, with no exclusion or replacement of cases.
    cohort=[]
    for pop in ['locked120','within_session194']:
        a=pd.read_csv(ROOT/f'results/full_motion/{pop}_pairs.csv');b=pd.read_csv(ROOT/f'results/full_motion/{pop}_Raw_pairs.csv');keys=['sequence','start_frame_index','end_frame_index'];v=a.merge(b,on=keys,suffixes=('_C','_Raw'),validate='one_to_one');v['extra_cross_nm']=v.cross_axis_abs_nm_C-v.cross_axis_abs_nm_Raw;v.to_csv(out/f'{pop}_original_comparison.csv',index=False)
        for seq,g in [('all',v),*list(v.groupby('sequence'))]:cohort.append(dict(population=pop,sequence=seq,n=len(g),smaller=int((g.extra_cross_nm<0).sum()),larger=int((g.extra_cross_nm>0).sum()),median_paired_change_nm=float(g.extra_cross_nm.median()),mean_paired_change_nm=float(g.extra_cross_nm.mean()),maximum_increase_nm=float(g.extra_cross_nm.max())))
    pd.DataFrame(cohort).to_csv(out/'original_cohort_context.csv',index=False)
    # Independent refits for all702 saved diagnostic centers.
    errors=[]
    for parent in [base,prec]:
        for file in (parent/'measurements').glob('*/frame_*/centers.csv'):
            table=pd.read_csv(file);points=np.load(file.parent/'points.npz')['inflection_points'];assert len(points)==len(table)
            for xy,row in zip(points,table.itertuples()):
                origin=xy.mean(0);z=xy-origin
                def objective(c):r=np.linalg.norm(z-c,axis=1);return r-r.mean()
                c=least_squares(objective,np.zeros(2),xtol=1e-12,ftol=1e-12,gtol=1e-12).x+origin;e=max(abs(c[0]-row.lsc_center_x_px),abs(c[1]-row.lsc_center_y_px));assert e<1e-4;errors.append(float(e))
    # Same-input known horizontal image shifts, preserving interpretation limits.
    virtual=[]
    for method,g in t[t.method.str.startswith('virtual')].groupby('method'):
        baseline='Raw' if '_Raw_' in method else 'C_s1342001_float';a=t[(t.method==baseline)&(t.frame_index==16)].sort_values('pillar_id');b=g.sort_values('pillar_id');dy=(b.lsc_center_y_px.values-a.lsc_center_y_px.values)*scale;virtual.append(dict(method=method,side_response_nm=float(np.median(dy))))
    pd.DataFrame(virtual).to_csv(out/'known_horizontal_image_shifts.csv',index=False)
    # Independent image registration is context only: real Y motion is not known.
    panel=load(ROOT/'config/motion_panel.json');plan=load(panel['source_plan']['path']);raws={};recons={};bounds=[]
    for i in [16,17]:
        f=next(f for f in plan['frames'] if f['sequence']==sequence and f['frame_index']==i);raws[i]=cv2.imread(f['source']['path'],0).astype(np.float32)/255;recons[i]=np.load(base/f'images/C_s1342001/{i:04d}.npz')['image'];bounds.append(np.load(ROOT/f'results/full_motion/{sequence}/frame_{i:04d}/points.npz')['roi_bounds'])
    bounds=np.stack(bounds);x0,y0=bounds[:,:2].min(0);x1,y1=bounds[:,2:].max(0);x0,y0,x1,y1=map(int,[x0,y0,x1,y1]);registration=[]
    for name,images in [('Raw',raws),('C_float',recons)]:
        a=images[16][y0:y1,x0:x1].astype(np.float32);b=images[17][y0:y1,x0:x1].astype(np.float32);warp=np.float32([[1,0,-2.9],[0,1,-.25]])
        try:
            cc,w=cv2.findTransformECC(a,b,warp,cv2.MOTION_TRANSLATION,(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,300,1e-8),None,3);registration.append(dict(method=name,success=True,correlation=float(cc),dx_nm=float(w[0,2]*scale),dy_nm=float(w[1,2]*scale)))
        except cv2.error as e:registration.append(dict(method=name,success=False,error=str(e)))
    save(out/'independent_image_registration.json',dict(rows=registration,scope='Rigid image registration sensitivity check, not ground-truth Y displacement'))
    # Verify whole measurement regions are beyond the Raw retention/transition band.
    margin=[]
    for i in [16,17]:
        points=np.load(ROOT/f'results/full_motion/{sequence}/frame_{i:04d}/points.npz')['inflection_points'].reshape(-1,2);h,w=raws[i].shape;margin.append(float(np.min(np.concatenate([points[:,0],points[:,1],w-1-points[:,0],h-1-points[:,1]]))))
    assert min(margin)>32
    # Inspect actual training metadata instead of assuming absence of small shapes.
    data=Path(load(ROOT/'config/study.json')['data_root']);entries=load(data/'manifest.json')['entries'];meta=[load(data/e['metadata_path']) for e in entries if e['split']=='train'];dense=[m['shape'] for m in meta if m['category']=='dense_close_structures'];radius=[m['shape']['radius'] for m in meta if 'radius' in m['shape']]
    coverage=dict(training_parents=len(meta),irregular_radius_minmax=[min(radius),max(radius)],dense_disks=sum(s['motif']=='disks' for s in dense),dense_pitch_minmax=[min(s['pitch'] for s in dense),max(s['pitch'] for s in dense)],training_x_shift_minmax=[min(m['shift_xy'][0] for m in meta),max(m['shift_xy'][0] for m in meta)],real_nominal_x_shift_px=-.5/.1725,scope='Coverage mismatch is a follow-up design concern, not the proven cause of this pair; small disks do exist in training')
    save(out/'data_coverage_context.json',coverage)
    fig,ax=plt.subplots(2,2,figsize=(12,8.5));ax[0,0].imshow(raws[16][y0:y1,x0:x1],cmap='gray',vmin=0,vmax=1,interpolation='nearest');ct=p[(p.method=='Raw_exact')&(p.frame_index==16)]
    for z in ct.itertuples():ax[0,0].text(z.lsc_center_x_px-x0,z.lsc_center_y_px-y0-9,str(z.pillar_id),ha='center',color='#ffa500',fontsize=8)
    ax[0,0].set_title('Captured image, frame 16: nine measured pillars');ax[0,0].set_xlabel('Native camera pixels');ax[0,0].set_ylabel('Native camera pixels')
    xpos=np.arange(9)
    for offset,name,color in [(-.25,'Raw_exact','#6c7785'),(0,'C_float','#238878'),(.25,'C_export8','#cf6737')]:ax[0,1].bar(xpos+offset,bars[name],width=.25,label={'Raw_exact':'Raw','C_float':'Model precision','C_export8':'8-bit export'}[name],color=color)
    ax[0,1].set_xticks(xpos,bars.index);ax[0,1].set_xlabel('Pillar');ax[0,1].set_ylabel('Signed Y step (nm)');ax[0,1].set_title('Same image pair, same nine pillars');ax[0,1].legend(fontsize=8);ax[0,1].axhline(0,color='black',lw=.6)
    values=[next(r['cross_nm'] for r in bits if r['method']==m) for m in ['C_q8','C_q10','C_q12','C_q16','C_float']];ax[1,0].plot(range(5),values,'o-',color='#238878');ax[1,0].axhline(raw,color='#6c7785',ls='--',label='Raw');ax[1,0].set_xticks(range(5),['8-bit','10-bit','12-bit','16-bit','Float']);ax[1,0].set_ylabel('Median side-step magnitude (nm)');ax[1,0].set_title('Only output precision changes');ax[1,0].legend()
    for name,color in [('Raw_exact','#6c7785'),('C_float','#238878'),('C_export8','#cf6737')]:ax[1,1].plot(range(5),[r['cross_nm'] for r in neighbors if r['method']==name],marker='o',label={'Raw_exact':'Raw','C_float':'Model precision','C_export8':'8-bit export'}[name],color=color)
    ax[1,1].set_xticks(range(5),[f'{i} to {i+1}' for i in range(15,20)]);ax[1,1].set_ylabel('Median side-step magnitude (nm)');ax[1,1].set_title('Neighboring frames: both improvements and regressions');ax[1,1].legend(fontsize=8)
    fig.suptitle('R134 diagnostic: reconstruction precision and measured side motion',fontsize=14);fig.tight_layout();fig.savefig(out/'diagnosis.png',dpi=160);plt.close(fig)
    verify();assert sha(ROOT/'results/long_admission.json')==load(prec/'plan.json')['original_admission']['sha256'];save(out/'complete.json',dict(decomposition=decomposition,independent_center_refits=len(errors),maximum_refit_error_px=max(errors),minimum_contour_to_image_edge_px=min(margin),guard_cannot_explain_this_case=True,fullfield_replay_frames=6,precision_file_roundtrip=True,original_negative_admission_unchanged=True,source=record(__file__)))
    print(json.dumps(decomposition,indent=2));print(pd.DataFrame(neighbors).to_string(index=False));print(pd.DataFrame(registration).to_string(index=False))
if __name__=='__main__':main()
