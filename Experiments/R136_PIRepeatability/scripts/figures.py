from common import *
import argparse
import numpy as np,pandas as pd,cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':220,'axes.grid':True,'grid.alpha':.17})
COLORS={'Raw':'#555B65','R61':'#117C99','R129':'#C56B2A'}
OUT=ROOT/'reports/figures';OUT.mkdir(parents=True,exist_ok=True)
def finish(fig,name):
    fig.savefig(OUT/(name+'.png'),bbox_inches='tight');fig.savefig(OUT/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
def main():
    global OUT,COLORS
    ap=argparse.ArgumentParser();ap.add_argument('--models',nargs='+',default=list(COLORS));ap.add_argument('--tables',default='results/tables');ap.add_argument('--output',default='reports/figures');args=ap.parse_args()
    COLORS={k:v for k,v in COLORS.items() if k in args.models};OUT=ROOT/args.output;OUT.mkdir(parents=True,exist_ok=True)
    tables=ROOT/args.tables;scans=pd.read_csv(tables/'per_scan.csv');positions=pd.read_csv(tables/'per_position.csv');paired=pd.read_csv(tables/'paired_comparisons.csv');sensitivity=pd.read_csv(tables/'sensitivity.csv');rep=pd.read_csv(tables/'repeatability.csv')
    fig,axes=plt.subplots(1,2,figsize=(13,4.8),layout='constrained')
    for ax,kind,title in zip(axes,['adjacent','start'],['Adjacent displacement error','Displacement error relative to scan start']):
        for model,color in COLORS.items():
            g=positions[(positions.view=='nominal_all30')&(positions.kind==kind)&(positions.model==model)].sort_values('position_index');x=g.position_index.to_numpy();mean=g.bias_nm.to_numpy();sd=g.repeatability_sd_nm.to_numpy();ax.plot(x,mean,color=color,label=model);ax.fill_between(x,mean-sd,mean+sd,color=color,alpha=.13)
        ax.axhline(0,color='#888',lw=.7);ax.set(title=title,xlabel='Position index (1 to 30)',ylabel='Image minus PI displacement (nm)');ax.legend(frameon=False)
    fig.suptitle('All 30 captures | nominal scale | band = +/- 1 SD across captures',fontsize=13);finish(fig,'01_error_by_position')
    fig,axes=plt.subplots(2,2,figsize=(13,8.2),layout='constrained')
    for row,view in enumerate(['nominal_all30','calibrated_late24']):
        for col,kind in enumerate(['adjacent','start']):
            ax=axes[row,col]
            for model,color in COLORS.items():
                g=scans[(scans.view==view)&(scans.kind==kind)&(scans.model==model)].sort_values('run_index');ax.plot(g.run_index,g.mae_nm,'o-',ms=3,color=color,label=model)
            if row==0:ax.axvline(6.5,ls='--',color='#777',lw=1)
            ax.set(title=('All 30, nominal scale' if row==0 else 'Later 24, earlier 6 used for calibration')+' | '+kind,xlabel='Capture number',ylabel='Mean absolute PI-referenced error (nm)');ax.legend(frameon=False)
    finish(fig,'02_capture_comparison')
    fig,axes=plt.subplots(1,2,figsize=(12,3.0 if len(COLORS)==2 else 4.6),layout='constrained')
    for ax,kind in zip(axes,['adjacent','start']):
        g=paired[(paired.view=='calibrated_late24')&(paired.kind==kind)&(paired.metric=='mae_nm')].reset_index(drop=True)
        for i,r in g.iterrows():
            mean=r.candidate_minus_reference_mean_nm;ax.plot([r.block3_ci95_low,r.block3_ci95_high],[i+.08,i+.08],color='#888',lw=1.2);ax.plot([r.ci95_low,r.ci95_high],[i,i],color=COLORS[r.candidate],lw=3);ax.plot(mean,i,'o',color=COLORS[r.candidate])
        ax.set_yticks(range(len(g)),[r.candidate+' - '+r.reference for _,r in g.iterrows()]);ax.set_ylim(-.35,len(g)-.65);ax.axvline(0,color='#444',ls='--');ax.set(title=kind.capitalize()+' | later 24 captures',xlabel='Difference in mean absolute error (nm)\nNegative favors first method')
    fig.suptitle('Paired 95% bootstrap intervals | grey: 3-capture block sensitivity',fontsize=12);finish(fig,'03_paired_improvement')
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    for ax,kind in zip(axes,['adjacent','start']):
        for model,color in COLORS.items():
            g=positions[(positions.view=='nominal_all30')&(positions.kind==kind)&(positions.model==model)].sort_values('position_index');ax.plot(g.position_index,g.repeatability_sd_nm,label=model,color=color)
        ax.set(title=kind.capitalize(),xlabel='Position index',ylabel='SD across 30 captures at each position (nm)',ylim=(0,None));ax.legend(frameon=False)
    fig.suptitle('Repeatability of PI-referenced errors | nominal scale');finish(fig,'04_repeatability')
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    combos=[('primary','highpass','full','Primary'),('inner','highpass','full','Inner region'),('junction','highpass','full','Junction'),('primary','intensity','full','Intensity reader'),('primary','highpass','8bit','8-bit export')]
    for ax,kind in zip(axes,['adjacent','start']):
        for model,color in COLORS.items():
            ys=[]
            for roi,reader,precision,label in combos:
                g=sensitivity[(sensitivity.view=='nominal_all30')&(sensitivity.kind==kind)&(sensitivity.model==model)&(sensitivity.roi==roi)&(sensitivity.reader==reader)&(sensitivity.precision==precision)];ys.append(float(g.iloc[0].mae_nm) if len(g) else np.nan)
            ax.plot(range(5),ys,'o-',label=model,color=color)
        ax.set_xticks(range(5),[c[-1] for c in combos],rotation=25,ha='right');ax.set(title=kind.capitalize(),ylabel='Mean absolute error (nm)',ylim=(0,None));ax.legend(frameon=False)
    fig.suptitle('Sensitivity checks | all 30 captures, same nominal scale');finish(fig,'05_sensitivity')
    plan=load(ROOT/'config/plan.json');f=plan['frames'][0];raw=cv2.imread(f['source']['path'],0)
    fig,ax=plt.subplots(figsize=(11,8));ax.imshow(raw,cmap='gray',vmin=0,vmax=255)
    for (name,(x,y,w,h)),color in zip(plan['rois'].items(),['#117C99','#D39D22','#D05058']):ax.add_patch(Rectangle((x,y),w,h,fill=False,edgecolor=color,lw=2));ax.text(x+10,y+30,name,color=color,bbox=dict(facecolor='white',alpha=.85,edgecolor='none'))
    ax.set(title='Common measurement regions | chosen from Raw before model results',xlabel='Image x (pixels)',ylabel='Image y (pixels)');ax.grid(False);finish(fig,'06_measurement_regions')
    fig,axes=plt.subplots(2,len(COLORS),figsize=(13,8),layout='constrained')
    for row,f in enumerate([plan['frames'][0],plan['frames'][-1]]):
        for ax,(model,color) in zip(axes[row],COLORS.items()):
            if model=='Raw':im=cv2.imread(f['source']['path'],0)/255
            else:
                with np.load(ROOT/'results'/model/f['run']/f"{f['index']+1:02d}.npz") as z:im=z['output']
            ax.imshow(im[620:940,1230:1650],cmap='gray',vmin=0,vmax=1);ax.set_title(model+' | '+('first capture, first image' if row==0 else 'last capture, last image'));ax.axis('off')
    fig.suptitle('Identical display range and image-coordinate crops');finish(fig,'07_reconstruction_examples')
    save(tables.parent/'figures_complete.json',dict(figures=[str(p) for p in OUT.glob('*.png')],completed_utc=now()))
if __name__=='__main__':main()
