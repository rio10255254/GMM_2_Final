"""Label the fixed reference scale on each retained SEM overlay example."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
from scipy.io import loadmat
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager,patheffects
from matplotlib.lines import Line2D
from skimage.measure import find_contours
from analyze import shift_mask

def main():
    out=ROOT/'results/full_contour';d=loadmat(out/'masks.mat',variable_names=['masks','truth_masks','sem_cells','shifts']);pairs=pd.read_csv(out/'paired_primary.csv')
    font_manager.fontManager.addfont('C:/Windows/Fonts/msjh.ttc');plt.rcParams['font.family']='Microsoft JhengHei'
    cases=[dict(reference='historical',exposure=13,pillar=16,label='既有固定比例'),dict(reference='global_pitch_matched',exposure=14,pillar=12,label='柱距修正比例')]
    fig,axes=plt.subplots(1,2,figsize=(10,5.8))
    def line(ax,mask,color,style,lw,outline=False):
        for c in find_contours(mask.astype(float),.5):
            obj,=ax.plot(c[:,1],c[:,0],color=color,ls=style,lw=lw)
            if outline:obj.set_path_effects([patheffects.Stroke(linewidth=lw+1.2,foreground='#222222'),patheffects.Normal()])
    for ax,case in zip(axes,cases):
        i=case['pillar']-1;e=case['exposure']-13;f=0 if case['reference']=='historical' else 1
        ax.imshow(d['sem_cells'][:,:,i,f],cmap='gray',vmin=0,vmax=255,interpolation='nearest')
        line(ax,d['truth_masks'][:,:,i,f].astype(bool),'white','-',1.3,True);dx,dy=d['shifts'][i,e,f,:].astype(int)
        line(ax,shift_mask(d['masks'][:,:,i,e,0,0].astype(bool),dx,dy),'#356DA8','-',1.6)
        line(ax,shift_mask(d['masks'][:,:,i,e,1,0].astype(bool),dx,dy),'#D38638','--',1.6)
        row=pairs[(pairs.reference==case['reference'])&(pairs.exposure==case['exposure'])&(pairs.pillar==case['pillar'])].iloc[0]
        ax.set_title(f"柱{case['pillar']}，照片{case['exposure']}（{case['label']}）\n輪廓距離 {row.Raw_boundary_px:.3f} → {row.candidate_boundary_px:.3f} 像素",fontsize=12)
        ax.set_xlim(6,97);ax.set_ylim(97,6);ax.set_xticks([]);ax.set_yticks([])
    fig.suptitle('配對 SEM 照片上的完整輪廓比較',fontsize=17)
    sem=Line2D([0],[0],color='white',lw=1.5,label='SEM參考輪廓');sem.set_path_effects([patheffects.Stroke(linewidth=2.8,foreground='#222222'),patheffects.Normal()])
    fig.legend(handles=[sem,Line2D([0],[0],color='#356DA8',label='原圖輪廓'),Line2D([0],[0],color='#D38638',ls='--',label='重建輪廓')],loc='lower center',ncol=3,bbox_to_anchor=(.5,.065),frameon=False)
    fig.text(.5,.017,'左為先前放大的同一顆，右為不利案例；每張內原圖與模型共用對齊。兩套固定參考均完整統計，未挑有利者。',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.13,1,.9]);p=ROOT/'reports/figures/full_contour_SEM_overlay_labeled.png';fig.savefig(p,dpi=160);plt.close(fig)
    save(out/'overlay_record.json',dict(cases=cases,reference_labels_explicit=True,figure=record(p),source=record(__file__),prior_figure_retained=True))

if __name__=='__main__':main()
