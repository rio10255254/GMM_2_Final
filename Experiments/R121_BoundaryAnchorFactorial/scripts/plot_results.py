"""Source-backed factorial comparison figures, with fixed image examples."""
from pathlib import Path
import json
import cv2,numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.io import loadmat
ROOT=Path(__file__).resolve().parents[1]
COLORS={'A':'#646B73','B':'#374F8A','C':'#B25B37','D':'#967CA2'}
LABELS={'A':'Control','B':'Data change','C':'Position loss','D':'Both changes'}

def main():
    decision=json.loads((ROOT/'results/assessment/decision.json').read_text())
    matrix=json.loads((ROOT/'results/matrix_finished_v2.json').read_text())['runs']
    gallery=ROOT/'results/gallery_v2';gallery.mkdir(exist_ok=False)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
    for i,seed in enumerate([1215001,1215002]):
        for j,reference in enumerate(['historical','pitch_matched']):
            ax=axes[i,j]
            rows=[r for r in decision['shape_effects'] if r['seed']==seed and r['reference']==reference]
            for k,r in enumerate(rows):
                value=r['median_pillar_paired_effect_vs_A'];low,high=r['bootstrap95_vs_A']
                ax.errorbar(k,value,yerr=[[max(0,value-low)],[max(0,high-value)]],fmt='o',color=COLORS[r['arm']],capsize=4,ms=7)
            ax.axhline(0,color='#333333',lw=1);ax.set_xticks(range(4),[LABELS[a] for a in 'ABCD'])
            ax.set_title(f"Initialization {i+1} | {'Historical SEM' if j==0 else 'Global pitch-matched SEM'}",loc='left')
            ax.set_ylabel('Paired contour change vs control\n(pitch percentage points; lower is better)');ax.grid(axis='y',alpha=.15)
    fig.suptitle('R121 four-arm, two-initialization short comparison',x=.035,ha='left',fontsize=15)
    fig.savefig(gallery/'paired_sem_effects.png',dpi=170);plt.close(fig)
    gates=pd.DataFrame(decision['gates']);fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for i,seed in enumerate([1215001,1215002]):
        g=gates[gates.seed==seed].set_index('arm').loc[list('ABCD')]
        axes[0].plot(range(4),g.textured_highpass_error_ratio_vs_A,marker=['o','s'][i],ls=['-','--'][i],label=f'Initialization {i+1}')
        axes[1].plot(range(4),g.maximum_motion_error_px-g.control_motion_error_px,marker=['o','s'][i],ls=['-','--'][i],label=f'Initialization {i+1}')
    axes[0].axhline(1.02,color='#333333',ls=':',label='Declared limit');axes[0].set_ylabel('Texture high-pass error / control');axes[0].set_title('Known-target texture guard',loc='left')
    axes[1].axhline(.01,color='#333333',ls=':',label='Declared limit');axes[1].set_ylabel('Worst controlled motion error increase (px)');axes[1].set_title('Controlled motion guard',loc='left')
    for ax in axes:ax.set_xticks(range(4),[LABELS[a] for a in 'ABCD']);ax.grid(axis='y',alpha=.15);ax.legend(fontsize=9)
    fig.savefig(gallery/'quality_guards.png',dpi=170);plt.close(fig)
    old=loadmat(ROOT.parent/'R119_SequenceGeometryValidation/results/formal_sem/results/masks/acm_primary_masks.mat',variable_names=['opt_centers','global_index'])
    pos=np.argwhere(old['global_index']==21)[0];center=old['opt_centers'][int(pos[0])*6+int(pos[1])]
    cx,cy=np.floor(center+.5).astype(int)-1
    names=['Raw']+[next(r['run_id'] for r in matrix if r['seed']==1215001 and r['arm']==a) for a in 'ABCD']
    fig,axes=plt.subplots(2,5,figsize=(12,5.5),layout='constrained')
    for i,exposure in enumerate([13,24]):
        raw=cv2.imread(str(ROOT.parent/f'R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack/{exposure}.bmp'),0)
        raw_crop=raw[cy-52:cy+52,cx-52:cx+52];lo,hi=np.percentile(raw_crop,[1,99])
        for j,name in enumerate(names):
            image=raw if name=='Raw' else cv2.imread(str(ROOT/f'results/sem/recon/{name}/{exposure}.png'),0)
            crop=image[cy-52:cy+52,cx-52:cx+52]
            axes[i,j].imshow(crop,cmap='gray',vmin=lo,vmax=hi,interpolation='nearest');axes[i,j].set_xticks([]);axes[i,j].set_yticks([])
            if i==0:axes[i,j].set_title('Raw' if j==0 else LABELS['ABCD'[j-1]])
            if j==0:axes[i,j].set_ylabel(f'Exposure {exposure}')
    fig.suptitle('Fixed pillar 21, initialization 1 | shared Raw-derived display limits',fontsize=13)
    fig.savefig(gallery/'fixed_real_examples.png',dpi=170);plt.close(fig)
    with (gallery/'manifest.json').open('x') as f:json.dump({'source_decision':'../assessment/decision.json','SEM_units':'pitch percentage points, paired by pillar across exposures','error_bars':'3000 pillar bootstrap resamples; same sample only','image_selection':'fixed pillar 21, exposures 13 and 24, seed 1215001, all four arms','not_an_unseen_holdout':True},f,indent=2)
    print('Three source-backed comparison figures generated')

if __name__=='__main__':main()
