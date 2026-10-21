"""Four-method matched repeatability; no truth/accuracy claim without same-sample reference."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ[k]='1'
from pathlib import Path
import json, hashlib, zipfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/sem_corner9/shape_size'; OUT.mkdir(exist_ok=True)
FIG=OUT/'figures'; FIG.mkdir(exist_ok=True)
MODELS=['Raw','R61','R129','R128']; NM=172.5
TH=np.linspace(0,2*np.pi,720,endpoint=False)
COL=['#777777','#df8636','#2088aa','#9356ad']

def signature(p,c):
    d=p-c; a=np.mod(np.arctan2(d[:,1],d[:,0]),2*np.pi); r=np.linalg.norm(d,axis=1)
    ix=np.argsort(a); a,r=a[ix],r[ix]
    return np.interp(TH,np.r_[a[-1]-2*np.pi,a,a[0]+2*np.pi],np.r_[r[-1],r,r[0]])

def metrics(p,c,r):
    q=p-c; area=abs(np.sum(q[:,0]*np.roll(q[:,1],-1)-q[:,1]*np.roll(q[:,0],-1)))/2
    per=np.linalg.norm(q-np.roll(q,-1,axis=0),axis=1).sum()
    s=signature(p,c); z=s-s.mean(); f=np.fft.rfft(z)/len(z)
    return [2*r*NM,2*np.sqrt(area/np.pi)*NM,np.sqrt(np.mean((np.linalg.norm(q,axis=1)-r)**2))*NM,
            (s.max()-s.min())*NM,4*np.pi*area/per**2,2*abs(f[2])*NM,2*abs(f[4])*NM],s*NM

NAMES=['diameter_nm','area_diameter_nm','radial_rms_nm','radial_range_nm','circularity','harmonic2_nm','harmonic4_nm']
def boot_sd(x,w):
    x=x.reshape(30,-1); x=x-x.mean(axis=0); gram=x@x.T/x.shape[1]
    return np.sqrt(np.maximum(0,(w@np.diag(gram)-np.einsum('bi,ij,bj->b',w,gram,w))*30/29))

def main():
    # Check geometry and translation invariance before processing real observations.
    a=np.linspace(0,2*np.pi,64,endpoint=False); circle=8*np.c_[np.cos(a),np.sin(a)]
    m,s=metrics(circle,np.zeros(2),8)
    assert abs(m[0]-2760)<1e-9 and m[2]<1e-9 and np.ptp(s)<1e-9
    assert np.max(abs(signature(circle+[230,170],[230,170])-8))<1e-12
    ellipse=np.c_[9*np.cos(a),7*np.sin(a)]
    assert metrics(ellipse,np.zeros(2),8)[0][5]>100
    summaries=[]; tables=[]; sigs={}; vals={}; sources=[]; maxfit=0
    runs=sorted((ROOT/'results/sem_corner9/centers/Raw').glob('*.npz')); assert len(runs)==30
    for model in MODELS:
        arr=[]; profiles=[]
        for rp in runs:
            base=ROOT/'results/sem_corner9/centers'/model/rp.stem
            pts=np.load(base.with_suffix('.npz'))['points']; assert pts.shape==(31,9,64,2)
            df=pd.read_csv(base.with_suffix('.csv')).sort_values(['index','pillar_id'])
            assert len(df)==279 and not df.duplicated(['index','pillar_id']).any()
            out=[]; ss=[]
            for p,row in zip(pts.reshape(-1,64,2),df.itertuples()):
                c=np.array([row.center_x_px,row.center_y_px]); r=row.radius_px
                mm,sp=metrics(p,c,r); out.append(mm); ss.append(sp)
                maxfit=max(maxfit,abs(mm[2]/NM-row.radial_rms_px))
            arr.append(np.array(out).reshape(31,9,-1)); profiles.append(np.array(ss).reshape(31,9,720))
            for j,k in enumerate(NAMES): df[k]=np.array(out)[:,j]
            tables.append(df)
            for ext in ('.npz','.csv'):
                p=base.with_suffix(ext);sources.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        v=np.array(arr); p=np.array(profiles); vals[model]=v; sigs[model]=p
        centered=p-p.mean(axis=-1,keepdims=True)
        summaries.append(dict(model=model,contours=8370,diameter_mean_nm=v[:,:,:,0].mean(),
          diameter_repeat_sd_nm=np.sqrt(np.mean(np.var(v[:,:,:,0],axis=0,ddof=1))),
          diameter_repeat_absmax_nm=np.max(abs(v[:,:,:,0]-v[:,:,:,0].mean(axis=0))),
          diameter_within_scan_sd_nm=np.sqrt(np.mean(np.var(v[:,:,:,0],axis=1,ddof=1))),
          contour_repeat_sd_nm=np.sqrt(np.mean(np.var(p,axis=0,ddof=1))),
          shape_repeat_sd_nm=np.sqrt(np.mean(np.var(centered,axis=0,ddof=1))),
          radial_rms_mean_nm=v[:,:,:,2].mean(),circularity_mean=v[:,:,:,4].mean(),
          harmonic2_mean_nm=v[:,:,:,5].mean(),harmonic4_mean_nm=v[:,:,:,6].mean()))
    assert maxfit<1e-10
    allrows=pd.concat(tables,ignore_index=True);allrows.to_csv(OUT/'per_contour.csv',index=False)
    summary=pd.DataFrame(summaries)
    rng=np.random.default_rng(136); w=rng.multinomial(30,np.ones(30)/30,size=2000)/30
    bs={};pairs=[]
    for model in MODELS:
        p=sigs[model];z=p-p.mean(axis=-1,keepdims=True)
        bs[model]={}
        for key,x in [('diameter_repeat_sd_nm',vals[model][:,:,:,0]),('shape_repeat_sd_nm',z)]:
            b=boot_sd(x,w);bs[model][key]=b
            lo,hi=np.quantile(b,[.025,.975]); summary.loc[summary.model==model,key+'_ci_low']=lo;summary.loc[summary.model==model,key+'_ci_high']=hi
        delta=p-sigs['Raw']; shap=delta-delta.mean(axis=-1,keepdims=True)
        summary.loc[summary.model==model,'diameter_shift_vs_raw_nm']=(vals[model][:,:,:,0]-vals['Raw'][:,:,:,0]).mean()
        summary.loc[summary.model==model,'shape_difference_vs_raw_rms_nm']=np.sqrt(np.mean(shap**2))
        np.savez_compressed(OUT/f'{model}_radial_profiles.npz',radius_nm=p.astype('float32'),angle_rad=TH,runs=np.array([x.stem for x in runs]))
    for model in ['Raw','R61','R129']:
        for key in bs[model]:
            b=bs['R128'][key]-bs[model][key];lo,hi=np.quantile(b,[.025,.975])
            pairs.append(dict(comparison='R128 - '+model,metric=key,difference_nm=float(summary.loc[summary.model=='R128',key].iloc[0]-summary.loc[summary.model==model,key].iloc[0]),ci_low_nm=lo,ci_high_nm=hi))
    summary.to_csv(OUT/'summary.csv',index=False);pd.DataFrame(pairs).to_csv(OUT/'paired_scan_intervals.csv',index=False)
    allrows.groupby(['model','run'])[NAMES].mean().to_csv(OUT/'per_scan.csv')
    allrows.groupby(['model','index','pillar_id'])[NAMES].agg(['mean','std','min','max']).to_csv(OUT/'matched_target_statistics.csv')
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for ax,key,title in zip(axes,['diameter_repeat_sd_nm','shape_repeat_sd_nm','diameter_shift_vs_raw_nm'],['Diameter repeatability (lower is steadier)','Shape repeatability (lower is steadier)','Mean diameter change versus Raw']):
        ax.bar(MODELS,summary[key],color=COL);ax.set_title(title,fontsize=10);ax.set_ylabel('nm');ax.axhline(0,color='black',lw=.6)
    fig.tight_layout();fig.savefig(FIG/'repeatability.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for model,color in zip(MODELS,COL):
        p=sigs[model].mean(axis=(0,1,2));axes[0].plot(np.degrees(TH),p,label=model,color=color)
        axes[1].plot(np.degrees(TH),p-p.mean(),label=model,color=color)
    for ax in axes: ax.set_xlabel('Angle (degrees)');ax.set_ylabel('Radius (nm)');ax.legend()
    axes[0].set_title('Mean size and contour');axes[1].set_title('Mean shape after subtracting mean radius')
    fig.tight_layout();fig.savefig(FIG/'mean_contours.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(2,4,figsize=(12,6))
    for col,(model,color) in enumerate(zip(MODELS,COL)):
        for row,(fi,pi) in enumerate([(0,4),(30,4)]):
            ax=axes[row,col]
            for p in sigs[model][:,fi,pi,:]: ax.plot(p*np.cos(TH),p*np.sin(TH),color=color,alpha=.15,lw=.7)
            ax.set_aspect('equal');ax.set_xlim(-1700,1700);ax.set_ylim(-1700,1700);ax.set_title(f'{model}, position {fi+1}, circle 5');ax.set_xlabel('x (nm)');ax.set_ylabel('y (nm)')
    fig.tight_layout();fig.savefig(FIG/'thirty_repeat_contours.png',dpi=180);plt.close(fig)
    verification={'status':'repeatability_complete_reference_pending','contours':len(allrows),'models':MODELS,'runs_per_model':30,'frames_per_run':31,'circles_per_frame':9,'source_points':64,'interpolation_angles':720,'nominal_nm_per_pixel':NM,'max_existing_radial_rms_difference_px':maxfit,'bootstrap_unit':'complete scan; same sampled scan indices across methods; 2000 draws','truth_reference':'User confirms same-sample reference exists; path pending. No absolute accuracy claim.'}
    (OUT/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
    (OUT/'source_manifest.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
    print(summary.to_string(index=False));print(pd.DataFrame(pairs).to_string(index=False))

if __name__=='__main__':main()
