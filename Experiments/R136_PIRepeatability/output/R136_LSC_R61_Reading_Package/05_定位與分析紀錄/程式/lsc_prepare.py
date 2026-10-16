from lsc_core import *
import time,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

def main():
    plan=load(ROOT/'config/plan.json');first=plan['frames'][0];raw=cv2.imread(first['source']['path'],0);centers,radii=candidates(raw)
    anchor=centers[np.argmin(np.linalg.norm(centers-[1032,450],axis=1))]
    pair=np.linalg.norm(centers[:,None]-centers[None,:],axis=2);pair[pair==0]=np.inf;pitch=float(np.median(pair.min(1)))
    desired=np.array([anchor+[col*pitch,row*pitch] for row in [-1,0,1] for col in [-1,0,1]])
    base,ids=match(desired,centers,3)
    cfg=dict(created_utc=now(),core_source=record(CORE_PATH),thesis_reader_source=record(REPO/'Experiments/R128_SourceOnlyFullTraining/analysis/lsc_comparison/measure.py'),base_centers=base.tolist(),pitch_px=pitch,radius_px=float(np.median(radii[ids])),patch_half=int(np.ceil(.46*pitch)),sample_count=64,acm_iterations=13,normal_half_width_px=2.4,profile_step_px=.1,profile_sigma_px=.65,object_um_per_px=.1725,pillars=9,polarity='dark',tracking='Raw threshold components; nearest unique consecutive image correspondence;no PI or reconstructed-image selection',aggregation='componentwise median of9circle-center differences,matching existing thesis pipeline',complete_scans=30,frames_per_model=930)
    assert cfg['patch_half']==14
    save(ROOT/'config/lsc_plan.json',cfg);out=ROOT/'results/lsc';out.mkdir(parents=True,exist_ok=True)
    tracking=[];t=time.perf_counter()
    for run in plan['runs']:
        prev=base.copy()
        for f in [x for x in plan['frames'] if x['run']==run['run']]:
            raw=cv2.imread(f['source']['path'],0);cs,rs=candidates(raw);selected,_=match(prev,cs,pitch*.45)
            for pid,(x,y) in enumerate(selected,1):tracking.append(dict(run=f['run'],run_index=f['run_index'],index=f['index'],pillar_id=pid,seed_x_px=float(x),seed_y_px=float(y)))
            prev=selected
    df=pd.DataFrame(tracking);df.to_csv(out/'tracking.csv',index=False,encoding='utf-8-sig');assert len(df)==8370
    probe=[];fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for ri,f in enumerate([plan['frames'][0],plan['frames'][-1]]):
        cs=df[(df.run==f['run'])&(df['index']==f['index'])][['seed_x_px','seed_y_px']].to_numpy()
        for ci,model in enumerate(['Raw','R61']):
            if model=='Raw':image=cv2.imread(f['source']['path'],0).astype(float)/255
            else:
                with np.load(ROOT/'results/R61'/f['run']/f"{f['index']+1:02d}.npz") as z:image=z['output'].astype(float)
            rows,pts=measure_image(image,cs,cfg);second,_=measure_image(image,cs,cfg);assert rows==second
            probe.append(dict(model=model,run=f['run'],index=f['index'],centers=rows))
            for row,point in zip(rows,pts['points']):
                fit=core.fit_lsc(point);assert abs(fit.cx-row['center_x_px'])<1e-5 and abs(fit.cy-row['center_y_px'])<1e-5
            ax=axes[ri,ci];ax.imshow(image,cmap='gray',vmin=0,vmax=1)
            for row,point in zip(rows,pts['points']):
                ax.plot(point[:,0],point[:,1],'.',ms=2,color='#F2BC4D');ax.plot(row['center_x_px'],row['center_y_px'],'+',color='#00CFFF');ax.add_patch(Circle((row['center_x_px'],row['center_y_px']),row['radius_px'],fill=False,edgecolor='#00CFFF',lw=.7));ax.text(row['center_x_px']-3,row['center_y_px']-12,str(row['pillar_id']),color='#D94179',fontsize=9)
            ax.set_xlim(cs[:,0].min()-18,cs[:,0].max()+18);ax.set_ylim(cs[:,1].max()+18,cs[:,1].min()-18);ax.set_title(model+' | '+('first capture / first frame' if ri==0 else 'last capture / last frame'));ax.set_xlabel('Image x (px)');ax.set_ylabel('Image y (px)')
    fig.suptitle('Thesis LSC: same 9 targets | yellow: sampled edge | cyan: fitted circle and center');fig.savefig(out/'lsc_probe.png',dpi=180,bbox_inches='tight');plt.close(fig)
    save(out/'probe.json',dict(cases=probe,repeat_exact=True,all_tracking_rows=8370,tracking_seconds=time.perf_counter()-t));print('LSC tracking8370 and36probe circles verified; pitch',pitch,'radius',cfg['radius_px'],flush=True)
    with (ROOT/'HANDOFF.md').open('a',encoding='utf-8') as file:file.write('\n## Latest user correction: LSC is primary\n\nUser explicitly requested thesis LSC circle centers. New config/lsc_plan.json and scripts/lsc_*.py own the primary result; previous phase-correlation reports are supplementary and NOT LSC. The old phase measure_all and finish_when_ready processes were stopped after preserving outputs; R129 reconstruction PID19332 continues unchanged. Main LSC uses exact thesis core measure_inflection_lsc,20x settings64contourpoints/13ACMiterations/2.4pxnormalwindow,9central targets shared by allmodels,Raw-image-only coarse tracking. Results in results/lsc; forthcoming status/finish scripts there supersede old phase status flags. Completion notification must report LSC results.\n')
if __name__=='__main__':main()
