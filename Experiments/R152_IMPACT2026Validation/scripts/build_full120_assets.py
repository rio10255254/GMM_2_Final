"""Publication assets using native 20x and original calibrated 50x optical information."""
from pathlib import Path
import json,sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sources'))
import run_displacement_lsc as backend
DATA=ROOT/'results/full120';OUT=ROOT/'poster_assets/full120';OUT.mkdir(parents=True,exist_ok=True)
METHODS=['Raw','Wiener','R152'];COLORS=['#7d8792','#ce8430','#18799a']
SEQS=['50x_x_0p5um','50x_x_1um','20x_0p5um','20x_1um']
LABELS=['50x / 0.5 um','50x / 1.0 um','20x / 0.5 um','20x / 1.0 um']
METRICS=[('step_sd_nm','Step SD'),('nominal_mae_nm','Nominal MAE'),('median_within_grid_sd_nm','Median within-grid SD')]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none'})
def savefig(fig,name):
    for ext in ['png','svg']:fig.savefig(OUT/f'{name}.{ext}',dpi=260,facecolor=fig.get_facecolor())
    plt.close(fig)
def main():
    done=json.loads((DATA/'complete.json').read_text());assert done['state']=='complete_objective_calibrated_full120'
    agg=pd.read_csv(DATA/'aggregate_summary.csv');cond=pd.read_csv(DATA/'condition_summary.csv')
    g=agg[agg.scope=='all120'].set_index('method')
    fig,axs=plt.subplots(1,3,figsize=(14,5))
    for ax,(field,title) in zip(axs,METRICS):
        vals=g.loc[METHODS,field].to_numpy();bars=ax.bar(METHODS,vals,color=COLORS,width=.62)
        ax.set_title(title,weight='bold',pad=15);ax.set_ylabel('nm');ax.set_ylim(0,max(vals)*1.25);ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
        for bar,val in zip(bars,vals):ax.text(bar.get_x()+bar.get_width()/2,val+max(vals)*.035,f'{val:.2f}',ha='center',weight='bold',fontsize=12)
    fig.suptitle('120 locked pairs | 20x and 50x',fontsize=21,weight='bold',y=.97)
    fig.text(.5,.025,'R152: same learned weights; native 20x bank / calibrated 50x single PSF. Original measurement backend.',ha='center',fontsize=10.5)
    fig.subplots_adjust(left=.055,right=.98,top=.77,bottom=.16,wspace=.30);savefig(fig,'01_aggregate_results')
    fig,axs=plt.subplots(3,1,figsize=(12,10),sharex=True)
    for ax,(field,title) in zip(axs,METRICS):
        for i,method in enumerate(METHODS):
            vals=cond[cond.method==method].set_index('sequence').loc[SEQS,field].to_numpy()
            bars=ax.bar(np.arange(4)+(i-1)*.24,vals,.24,color=COLORS[i],label=method)
            for bar,val in zip(bars,vals):ax.text(bar.get_x()+bar.get_width()/2,val,f'{val:.2f}',ha='center',va='bottom',fontsize=9)
        ax.set_ylabel(title+' (nm)');ax.set_ylim(0,ax.get_ylim()[1]*1.14);ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    axs[-1].set_xticks(range(4),LABELS);axs[0].legend(ncol=3,loc='upper right',frameon=False)
    fig.suptitle('All four original conditions | 30 pairs each',fontsize=20,weight='bold',y=.985)
    fig.text(.5,.015,'Same locked pairs and measurement backend; magnification-specific R152 optical input.',ha='center',fontsize=10.5)
    fig.subplots_adjust(left=.15,right=.98,top=.92,bottom=.07,hspace=.16);savefig(fig,'02_condition_results')
    backend.SESSION_TABLE=ROOT/'sources/session_anchors.csv'
    conf=json.loads((ROOT/'sources/sequence_config.json').read_text(encoding='utf-8-sig'));selection=pd.read_csv(ROOT/'sources/original_locked_pairs.csv')
    fig,axes=plt.subplots(4,3,figsize=(11,14));chosen=[]
    for ri,seq in enumerate(SEQS):
        spec=conf['sequences'][seq];fi=int(selection[selection.sequence==seq].iloc[0].start_frame_index);mag=spec['magnification'];sub='20x' if mag=='20x' else '50x_calibrated'
        chosen.append(dict(sequence=seq,frame_index=fi,rule='first locked pair start frame, no image-quality selection'))
        raw=backend.load_grayscale(Path(spec['raw_dir'])/f'frame_{fi:04d}.bmp');recon=np.load(ROOT/f'results/{sub}/reconstruction/{seq}/frame_{fi:04d}.npz')['output']
        pred=backend.session_prediction(seq,fi,np.array(spec['centers'],float),float(spec['expected_signed_dx_px']));pitch=spec['pitch_px'];margin=int(np.ceil(.55*pitch))
        x0=max(0,int(np.floor(pred[:,1].min()))-margin);x1=min(raw.shape[1],int(np.ceil(pred[:,1].max()))+margin+1)
        y0=max(0,int(np.floor(pred[:,2].min()))-margin);y1=min(raw.shape[0],int(np.ceil(pred[:,2].max()))+margin+1)
        roi=raw[y0:y1,x0:x1];psf=backend.loadmat(backend.SWEEP_ROOT/f'{mag}_deconvolution_sweep.mat')['psf']
        imgs=[roi,backend.wiener_contrast_restore(roi,psf,backend.NSR,pitch_px=pitch),recon[y0:y1,x0:x1]]
        for ci,(method,im) in enumerate(zip(METHODS,imgs)):
            ax=axes[ri,ci];ax.imshow(im,cmap='gray',vmin=0,vmax=1,interpolation='nearest');ax.axis('off');ax.set_title(f'{method} | {LABELS[ri]}',fontsize=11)
            h,w=im.shape;length=2/spec['object_um_per_px'];pad=w*.08;y=h-pad;x=w-pad-length
            ax.plot([x,x+length],[y,y],color='white',lw=3);ax.text(x+length/2,y-h*.045,'2 um',ha='center',color='white',fontsize=9)
    fig.suptitle('Representative outputs | identical display range',fontsize=20,weight='bold',y=.989)
    fig.text(.5,.01,'First locked pair in each condition. Display range: 0-1. Measurements use original numeric outputs.',ha='center',fontsize=10)
    fig.subplots_adjust(left=.02,right=.98,top=.95,bottom=.035,wspace=.08,hspace=.18);savefig(fig,'03_representative_outputs')
    (DATA/'figure_selection.json').write_text(json.dumps(chosen,indent=2)+'\n')
    fig,ax=plt.subplots(figsize=(14,7));fig.patch.set_facecolor('#f5f7fb');ax.set(xlim=(0,14),ylim=(0,7));ax.axis('off')
    ax.text(.45,6.55,'R152 with objective-specific optical input',fontsize=24,weight='bold',color='#17334e')
    ax.text(.45,6.05,'120 original pairs | same learned weights | calibrated optical input | no retraining',fontsize=12,color='#36576e')
    def box(x,y,w,h,title,detail,color):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.08,rounding_size=0.12',fc=color,ec='#a9bac8'))
        ax.text(x+.18,y+h-.30,title,weight='bold',fontsize=13,va='top',color='#17334e');ax.text(x+.18,y+h-.78,detail,fontsize=11.5,va='top',linespacing=1.6,color='#273c4f')
    box(.45,3.45,3.65,2.12,'FIXED DATA','20x / 50x; 0.5 / 1.0 um\n30 adjacent pairs per condition\n166 different frames\nSame nine pillar identities','#dce9f4')
    box(4.98,3.45,3.8,2.12,'IMAGE METHODS','Raw / fixed Wiener / R152\nR152 at 20x: native 25 PSFs\nR152 at 50x: calibrated 1 PSF\nSame learned weights','#e2eee8')
    box(9.64,3.45,3.9,2.12,'COMMON MEASUREMENT','Coarse contour\nMaximum-gradient boundary\nLeast-squares circle centers\nMedian horizontal pillar shift','#dce9f4')
    for a,b in [(4.2,4.86),(8.88,9.5)]:ax.annotate('',xy=(b,4.5),xytext=(a,4.5),arrowprops={'arrowstyle':'->','lw':2,'color':'#385d7c'})
    box(.45,1.14,13.1,1.6,'THREE SEPARATE OUTCOMES','Step SD: mean of four condition-level sample standard deviations\nNominal MAE: mean of four condition-level nominal-step absolute errors\nMedian within-grid SD: median of 120 nine-pillar sample standard deviations','#e2eee8')
    ax.text(.45,.54,'50x uses one measured PSF with weight 1; no multi-PSF selection is claimed at 50x.',fontsize=11,color='#88490e')
    fig.subplots_adjust(left=0,right=1,bottom=0,top=1);savefig(fig,'04_measurement_protocol')
    print('Created four PNG/SVG figure pairs in',OUT)
if __name__=='__main__':main()
