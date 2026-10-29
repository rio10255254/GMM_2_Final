"""Independently verify complete-contour distances, then summarize all cases."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,pandas as pd
from scipy.io import loadmat
from scipy import ndimage
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager,patheffects
from matplotlib.lines import Line2D
from skimage.measure import find_contours
PROJECT_ROOT = Path(__file__).resolve().parents[4]

def shift_mask(mask,dx,dy):
    out=np.zeros_like(mask);h,w=mask.shape;x0=max(0,-dx);x1=min(w,w-dx);y0=max(0,-dy);y1=min(h,h-dy)
    out[y0+dy:y1+dy,x0+dx:x1+dx]=mask[y0:y1,x0:x1];return out

def metrics(a,b):
    ae=a&~ndimage.binary_erosion(a,np.ones((3,3)),border_value=0);be=b&~ndimage.binary_erosion(b,np.ones((3,3)),border_value=0)
    dist=np.r_[ndimage.distance_transform_edt(~ae)[be],ndimage.distance_transform_edt(~be)[ae]]
    return dict(mean_boundary_px=float(dist.mean()),hd95_px=float(np.percentile(dist,95,method='hazen')),iou=float(np.sum(a&b)/np.sum(a|b)),area_error_pct=float(100*abs(int(b.sum())-int(a.sum()))/a.sum()),maximum_boundary_px=float(dist.max()))

def main():
    out=ROOT/'results/full_contour';plan=load(out/'plan.json');extraction=load(out/'extraction_summary.json');assert extraction['Raw_primary_exact']
    for ref in plan['references']:assert sha(str(PROJECT_ROOT / ref['record']['path']))==ref['record']['sha256']
    assert sha(str(PROJECT_ROOT / plan['new_matlab_source']['path']))==plan['new_matlab_source']['sha256']
    d=loadmat(out/'masks.mat',variable_names=['masks','cells','truth_masks','sem_cells','shifts','raw_parity','opt_pitch','global_index','opt_centers'])
    table=pd.read_csv(out/'measurements.csv');table['valid']=table.valid.astype(str).str.lower().isin(['1','true'])
    assert len(table)==1944 and table.valid.all()
    masks=d['masks'].astype(bool);truth=d['truth_masks'].astype(bool)
    original=loadmat(str(PROJECT_ROOT / plan['references'][0]['record']['path']),variable_names=['raw_masks','truth_masks'])
    alternate=loadmat(str(PROJECT_ROOT / plan['references'][1]['record']['path']),variable_names=['truth_masks'])
    assert np.array_equal(truth[:,:,:,0],original['truth_masks'].astype(bool)) and np.array_equal(truth[:,:,:,1],alternate['truth_masks'].astype(bool))
    assert np.array_equal(masks[:,:,:,:,0,0],original['raw_masks'][:,:,:,:3].astype(bool))
    refs=['historical','global_pitch_matched'];presets=['primary','less_smooth','more_smooth'];methods=['Raw','R128_PNG','R128_float']
    errors={k:0. for k in ['mean_boundary_px','hd95_px','iou','area_error_pct']};independent=[];support=[];yy,xx=np.mgrid[1:105,1:105];ring=(xx-52.5)**2+(yy-52.5)**2>=44**2
    for _,row in table.iterrows():
        p=presets.index(row.preset);f=refs.index(row.reference);m=methods.index(row.method);e=int(row.exposure)-13;i=int(row.pillar)-1
        image=masks[:,:,i,e,m,p];target=truth[:,:,i,f];dx,dy=int(row.Raw_shift_x),int(row.Raw_shift_y)
        tc=np.array(ndimage.center_of_mass(target))[::-1];rc=np.array(ndimage.center_of_mass(original['raw_masks'][:,:,i,e]))[::-1]
        diff=tc-rc;expected=np.where(diff>=0,np.floor(diff+.5),np.ceil(diff-.5)).astype(int);assert np.array_equal(expected,[dx,dy])
        result=metrics(target,shift_mask(image,dx,dy))
        for k in errors:
            error=abs(result[k]-row[k]);errors[k]=max(errors[k],error);assert error<1e-5,(k,error)
        independent.append(dict(preset=row.preset,reference=row.reference,exposure=int(row.exposure),pillar=i+1,method=row.method,**result))
        support.append(int(np.sum(image&ring)))
    independent=pd.DataFrame(independent);independent.to_csv(out/'independent_metrics.csv',index=False)
    summaries=[]
    for (preset,reference,exp),group in table.groupby(['preset','reference','exposure']):
        raw=group[group.method=='Raw'].set_index('pillar')
        for method in ['R128_PNG','R128_float']:
            pred=group[group.method==method].set_index('pillar');result=dict(preset=preset,reference=reference,exposure=int(exp),candidate=method,objects=36)
            for metric in ['mean_boundary_px','hd95_px','iou','area_error_pct','perimeter_error_pct','circularity_error']:
                change=(pred[metric]-raw[metric])*(1 if metric=='iou' else -1)
                result[metric]=dict(Raw_median=float(raw[metric].median()),candidate_median=float(pred[metric].median()),paired_improvement_median=float(change.median()),improved=int((change>1e-6).sum()),worsened=int((change< -1e-6).sum()),tied=int((change.abs()<=1e-6).sum()))
            summaries.append(result)
    # Retain per-object paired differences including the unfavorable object.
    primary=table[table.preset=='primary'];pairs=[]
    for (reference,exp),group in primary.groupby(['reference','exposure']):
        a=group[group.method=='Raw'].set_index('pillar');b=group[group.method=='R128_PNG'].set_index('pillar')
        for i in a.index:pairs.append(dict(reference=reference,exposure=int(exp),pillar=int(i),Raw_boundary_px=float(a.loc[i,'mean_boundary_px']),candidate_boundary_px=float(b.loc[i,'mean_boundary_px']),boundary_improvement_px=float(a.loc[i,'mean_boundary_px']-b.loc[i,'mean_boundary_px']),Raw_iou=float(a.loc[i,'iou']),candidate_iou=float(b.loc[i,'iou']),hd95_change_px=float(b.loc[i,'hd95_px']-a.loc[i,'hd95_px']),perimeter_error_change_pct=float(b.loc[i,'perimeter_error_pct']-a.loc[i,'perimeter_error_pct'])))
    pd.DataFrame(pairs).to_csv(out/'paired_primary.csv',index=False)
    primary_summary=[x for x in summaries if x['preset']=='primary' and x['candidate']=='R128_PNG']
    save(out/'summary.json',dict(completed=True,primary=primary_summary,all_presets_and_export_types=summaries,source=record(__file__),one_physical_specimen=True,objects=36,repeated_exposures=3,no_unseen_confirmation=True))
    save(out/'verification.json',dict(passed=True,verified_utc=now(),all1944_rows_valid=True,all108_primary_Raw_masks_bitwise_equal=True,SEM_masks_identical_to_fixed_sources=True,common_Raw_alignment_independently_verified=True,independent_numeric_max_differences=errors,support_contact_rows=sum(x>0 for x in support),original_sources_unchanged=True,plan=record(out/'plan.json'),masks=record(out/'masks.mat'),measurements=record(out/'measurements.csv'),independent_source=record(__file__),fine_shape_properties_from_unchanged_MATLAB_regionprops=True))
    font_manager.fontManager.addfont('C:/Windows/Fonts/msjh.ttc');plt.rcParams['font.family']='Microsoft JhengHei';figdir=ROOT/'reports/figures'
    def outline(ax,mask,color,style='-',width=1.3,stroke=False):
        for contour in find_contours(mask.astype(float),.5):
            line,=ax.plot(contour[:,1],contour[:,0],color=color,linestyle=style,lw=width)
            if stroke:line.set_path_effects([patheffects.Stroke(linewidth=width+1.2,foreground='#222222'),patheffects.Normal()])
    # Fixed same pillar used in the preceding visual review plus the least
    # favorable primary global-reference case. All36are also shown separately.
    worst=min([x for x in pairs if x['reference']=='global_pitch_matched'],key=lambda x:x['boundary_improvement_px'])
    cases=[dict(reference='historical',exposure=13,pillar=16),dict(reference=worst['reference'],exposure=worst['exposure'],pillar=worst['pillar'])]
    fig,axes=plt.subplots(1,2,figsize=(10,5.6))
    for ax,case in zip(axes,cases):
        f=refs.index(case['reference']);i=case['pillar']-1;e=case['exposure']-13;target=truth[:,:,i,f]
        ax.imshow(d['sem_cells'][:,:,i,f],cmap='gray',vmin=0,vmax=255,interpolation='nearest')
        outline(ax,target,'white','-',1.4,True)
        for m,color,style in [(0,'#356DA8','-'),(1,'#D38638','--')]:
            dx,dy=d['shifts'][i,e,f,:].astype(int);outline(ax,shift_mask(masks[:,:,i,e,m,0],dx,dy),color,style,1.6)
        row=next(x for x in pairs if x['reference']==case['reference'] and x['exposure']==case['exposure'] and x['pillar']==case['pillar'])
        ax.set_xlim(6,97);ax.set_ylim(97,6);ax.set_xticks([]);ax.set_yticks([]);ax.set_title(f"柱{case['pillar']}，照片{case['exposure']}\n輪廓距離 {row['Raw_boundary_px']:.3f} → {row['candidate_boundary_px']:.3f} 像素",fontsize=12)
    fig.suptitle('對應 SEM 照片上的完整輪廓',fontsize=18)
    legend=[Line2D([0],[0],color='#333333',lw=1.5,label='SEM參考輪廓'),Line2D([0],[0],color='#356DA8',lw=1.5,label='原圖輪廓'),Line2D([0],[0],color='#D38638',lw=1.5,ls='--',label='重建輪廓')]
    fig.legend(handles=legend,loc='lower center',ncol=3,frameon=False,bbox_to_anchor=(.5,.055))
    fig.text(.5,.018,'左：先前放大的同一顆柱體；右：這次最不利的完整輪廓案例。背景為按固定對應尺度整理的SEM照片。',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.12,1,.90]);fig.savefig(figdir/'full_contour_SEM_overlay.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(6,6,figsize=(12,12))
    for gy in range(6):
        for gx in range(6):
            ax=axes[gy,gx];i=int(d['global_index'][gy,gx])-1;f=0;e=0;target=truth[:,:,i,f];ax.imshow(d['sem_cells'][:,:,i,f],cmap='gray',vmin=0,vmax=255)
            outline(ax,target,'white','-',.65,True)
            dx,dy=d['shifts'][i,e,f,:].astype(int)
            outline(ax,shift_mask(masks[:,:,i,e,0,0],dx,dy),'#356DA8','-',.7);outline(ax,shift_mask(masks[:,:,i,e,1,0],dx,dy),'#D38638','--',.7)
            ax.set_xlim(5,98);ax.set_ylim(98,5);ax.set_xticks([]);ax.set_yticks([]);ax.set_title(f'柱{i+1}',fontsize=9)
    fig.suptitle('照片13：全部36顆 pillar 與配對 SEM 的輪廓疊圖',fontsize=17);fig.legend(handles=legend,loc='lower center',ncol=3,frameon=False);fig.tight_layout(rect=[0,.035,1,.955]);fig.savefig(figdir/'full_contour_all36.png',dpi=140);plt.close(fig)
    print(json.dumps(dict(primary=primary_summary,independent_errors=errors,support_contact_rows=sum(x>0 for x in support),worst_case=worst)),flush=True)

if __name__=='__main__':main()
