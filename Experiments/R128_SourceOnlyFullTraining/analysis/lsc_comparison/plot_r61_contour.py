"""Display the fixed pillar and least favorable R128-vs-R61 historical-reference case."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,pandas as pd
from scipy.io import loadmat
from skimage.measure import find_contours
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager,patheffects
from matplotlib.lines import Line2D

def shift(mask,dx,dy):
    h,w=mask.shape;v=np.zeros_like(mask);x0=max(0,-dx);x1=min(w,w-dx);y0=max(0,-dy);y1=min(h,h-dy)
    v[y0+dy:y1+dy,x0+dx:x1+dx]=mask[y0:y1,x0:x1];return v

def main():
    comp=ROOT/'results/competitive_review';out=ROOT/'results/lsc_comparison';p=load(comp/'preparation.json');assert sha(p['inputs']['path'])==p['inputs']['sha256']
    t=pd.read_csv(comp/'measurements.csv');t=t[t.reference=='historical']
    paired=t[t.method=='R128_P_s1285002'].merge(t[t.method=='R61v16'],on=['exposure','pillar'],suffixes=('','_R61'),validate='one_to_one')
    worst=paired.iloc[np.argmax((paired.mean_boundary_px-paired.mean_boundary_px_R61).to_numpy())]
    cases=[dict(exposure=13,pillar=16,role='先前展示的同一顆柱體'),dict(exposure=int(worst.exposure),pillar=int(worst.pillar),role='本次 R128 相對 R61 最不利的案例')]
    d=loadmat(comp/'inputs.mat');bg=loadmat(ROOT/'results/full_contour/masks.mat',variable_names=['sem_cells'])['sem_cells']
    font_manager.fontManager.addfont('C:/Windows/Fonts/msjh.ttc');plt.rcParams['font.family']='Microsoft JhengHei'
    fig,axes=plt.subplots(1,2,figsize=(11,6.1))
    for ax,case in zip(axes,cases):
        i=case['pillar']-1;e=case['exposure']-13;dx,dy=d['shifts'][i,e,0,:].astype(int)
        ax.imshow(bg[:,:,i,0],cmap='gray',vmin=0,vmax=255,interpolation='nearest')
        items=[(d['truth_masks'][:,:,i,0], 'white','-',1.4), (shift(d['masks'][:,:,i,e,1],dx,dy),'#44779B','-',1.8), (shift(d['masks'][:,:,i,e,4],dx,dy),'#D58236','--',1.8)]
        for mask,color,style,width in items:
            for path in find_contours(mask.astype(float),.5):
                line,=ax.plot(path[:,1],path[:,0],color=color,ls=style,lw=width)
                if color=='white':line.set_path_effects([patheffects.Stroke(linewidth=2.8,foreground='#222222'),patheffects.Normal()])
        row=paired[(paired.pillar==case['pillar']) & (paired.exposure==case['exposure'])].iloc[0]
        case['R61_boundary_px']=float(row.mean_boundary_px_R61);case['R128_boundary_px']=float(row.mean_boundary_px)
        ax.set_title(f"{case['role']}\n柱 {case['pillar']}／照片 {case['exposure']}\n輪廓差距：R61 {row.mean_boundary_px_R61:.3f} → R128 {row.mean_boundary_px:.3f} 像素",fontsize=11)
        ax.set_xlim(5,98);ax.set_ylim(98,5);ax.set_xticks([]);ax.set_yticks([])
    fig.suptitle('R61 與 R128 的實拍外輪廓，疊在同顆柱體的 SEM 上',fontsize=16,y=.98)
    legend=[Line2D([0],[0],color='#333333',lw=1.5,label='SEM 參考輪廓'),Line2D([0],[0],color='#44779B',lw=1.8,label='R61'),Line2D([0],[0],color='#D58236',lw=1.8,ls='--',label='R128')]
    fig.legend(handles=legend,loc='lower center',ncol=3,frameon=False,bbox_to_anchor=(.5,.055))
    fig.text(.5,.018,'兩張均使用相同的既有尺度參考；同一個由原圖決定的對齊。右圖保留不利結果，沒有排除。',ha='center',fontsize=10)
    fig.tight_layout(rect=[0,.12,1,.93]);target=ROOT/'reports/figures/R61_R128_SEM_comparison.png';assert not target.exists();fig.savefig(target,dpi=155);plt.close(fig)
    save(out/'R61_contour_figure.json',dict(created_utc=now(),cases=cases,reference='historical',scope='same36pillars x3normalimages; select worst by candidate-minus-R61meanboundary, no exclusions',figure=record(target),source=record(__file__),measurements=record(comp/'measurements.csv')))
    print(cases)

if __name__=='__main__':main()
