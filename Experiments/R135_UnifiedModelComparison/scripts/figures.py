from r135_common import *
from publish import ORDER
import pandas as pd
from scipy.io import loadmat
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
LABELS=['Raw','Old V42*','Clean V42','R61','R128','R129 W16','R134 P1']
def render(out,require_all=True):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);done=[k for k in ORDER if (ROOT/f'results/{k}/complete.json').exists()]
    if require_all:assert len(done)==7
    fig,ax=plt.subplots(2,2,figsize=(13,8));data={k:load(ROOT/f'results/{k}/complete.json') for k in done}
    specifications=[('SEM shape difference (nm)','centered_shape_nm'),('SEM diameter difference (nm)','diameter_error_nm'),('194 pairs: between-pillar spread (nm)','median_within_grid_sd_nm'),('194 pairs: measured step variation (nm)','step_sd_nm')]
    for a,(label,key) in zip(ax.ravel(),specifications):
        values=[]
        for k in ORDER:
            if k not in done:values.append(np.nan);continue
            if key in data[k]['SEM']:v=data[k]['SEM'][key]
            else:
                t=pd.read_csv(ROOT/f'results/{k}/motion_summary.csv');v=float(t[(t.scope=='all_four_sequences')&(t.population=='within_session194')].iloc[0][key])
            values.append(v)
        bars=a.bar(np.arange(7),values,color=['#777777','#cb893f','#427a91','#427a91','#427a91','#427a91','#427a91']);bars[1].set_hatch('//');a.set_xticks(np.arange(7),LABELS,rotation=20,ha='right');a.set_ylabel(label);a.grid(axis='y',alpha=.2);a.set_axisbelow(True)
        for b,v in zip(bars,values):
            if np.isfinite(v):a.annotate(f'{v:.2f}',(b.get_x()+b.get_width()/2,v),xytext=(0,3),textcoords='offset points',ha='center',fontsize=8)
        a.set_ylim(0,max(v for v in values if np.isfinite(v))*1.18)
    fig.suptitle('Same images and precise readout; lower is better in these four panels'+(' — partial' if not require_all else ''),fontsize=12);fig.text(.5,.01,'* Old V42 has known evaluation-source overlap. Fixed deployment settings differ. No unseen-data winner is implied.',ha='center',fontsize=9);fig.tight_layout(rect=[0,.035,1,.96]);fig.savefig(out/'comparison.png',dpi=160);plt.close(fig)
    ref=loadmat(ROOT/'validation/sem_reference.mat');pillar=18;loc=np.argwhere(ref['global_index']==pillar);assert len(loc)==1;gy,gx=loc[0];cx,cy=ref['opt_centers'][gy*6+gx];ix,iy=int(np.floor(cx+.5)),int(np.floor(cy+.5));fig,axes=plt.subplots(2,4,figsize=(12,6.7));sem=ref['truth_cells'][:,:,pillar-1].astype(float)/255;axes[0,0].imshow(sem,cmap='gray',vmin=0,vmax=1);axes[0,0].set_title('Prepared SEM reference')
    verified=[]
    for a,k,label in zip(list(axes.ravel())[1:],ORDER,LABELS):
        a.set_title(label)
        if k not in done:a.text(.5,.5,'Pending',ha='center');a.set_axis_off();continue
        image=np.load(ROOT/f'results/{k}/sem/sem14_values.npz')['image'].astype(float);padded=np.pad(image,52,mode='symmetric');x,y=ix+51,iy+51;patch=padded[y-52:y+52,x-52:x+52];assert patch.shape==(104,104);expected=loadmat(ROOT/f'results/{k}/sem/sem_masks.mat')['cells'][:,:,pillar-1,1];normalized=(patch-patch.min())/(patch.max()-patch.min());assert np.allclose(normalized,expected,rtol=0,atol=1e-12),'Displayed patch differs from measured patch';a.imshow(patch,cmap='gray',vmin=0,vmax=1,interpolation='nearest');verified.append(k)
    for a in axes.ravel():a.set_xticks([]);a.set_yticks([])
    fig.suptitle('Same pillar18 / exposure14; identical display scale for optical images'+(' — partial' if not require_all else ''),fontsize=12);fig.text(.5,.01,'* Old V42: known data overlap. SEM is a prepared reference, not an unscaled native SEM photograph.',ha='center',fontsize=9);fig.tight_layout(rect=[0,.035,1,.96]);fig.savefig(out/'pillar18.png',dpi=160);plt.close(fig);save(out/'verified.json',dict(methods=verified,displayed_patches_match_measured_cells=True,partial=not require_all,source=record(__file__)))
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--partial',action='store_true');a=p.parse_args();render(ROOT/('results/figure_preview' if a.partial else 'reports/figures'),not a.partial)
