"""Publication-ready compact figure for the R150 real validation."""
from pathlib import Path
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];COMP=ROOT/'results/comparison';OUT=ROOT/'reports/figures';OUT.mkdir(parents=True,exist_ok=True)
def main():
 disp=pd.read_csv(COMP/'displacement_summary.csv');geo=pd.read_csv(COMP/'shape_size_summary.csv');sem=pd.read_csv(COMP/'SEM_corrected_size_summary.csv');scan=pd.read_csv(ROOT/'results/real_validation_analysis/scan_diameter_delta.csv');models=['Raw','R148v2-HybridContextNativePSF','R150-MatchedGeometryMeanPSF'];labels=['Raw','R148v2','R150'];colors=['#7f8c8d','#2f80ed','#f2994a'];metrics=[('Short-step MAE (nm)',[float(disp[(disp.model==m)&(disp.kind=='adjacent')].mae_nm.iloc[0]) for m in models]),('Long-distance MAE (nm)',[float(disp[(disp.model==m)&(disp.kind=='start')].mae_nm.iloc[0]) for m in models]),('Diameter repeatability (nm)',[float(geo[geo.model==m].diameter_repeat_sd_nm.iloc[0]) for m in models]),('Contour repeatability (nm)',[float(geo[geo.model==m].contour_repeat_sd_nm.iloc[0]) for m in models]),('Mean SEM diameter error (nm)',[float(sem[sem.model==m].mean_absolute_pillar_difference_nm.iloc[0]) for m in models])]
 fig,axes=plt.subplots(2,3,figsize=(13,7.5));axes=axes.ravel()
 for ax,(title,values) in zip(axes[:5],metrics):
  bars=ax.bar(labels,values,color=colors);ax.set_title(title,fontsize=11);ax.grid(axis='y',alpha=.22);ax.set_axisbelow(True);ax.bar_label(bars,fmt='%.2f',padding=2,fontsize=8);ax.set_ylim(0,max(values)*1.22)
 ax=axes[5];y=scan.R150_minus_R148v2_diameter_nm.to_numpy();ax.plot(np.arange(1,len(y)+1),y,'o-',color=colors[2],markersize=3,linewidth=1.3);ax.axhline(y.mean(),color='#333',linestyle='--',linewidth=1,label=f'Mean {y.mean():.2f} nm');ax.axhline(0,color='#888',linewidth=.8);ax.set(title='R150 − R148v2 mean diameter by scan',xlabel='Scan',ylabel='Diameter difference (nm)');ax.grid(alpha=.22);ax.legend(frameon=False,fontsize=8)
 fig.suptitle('R150 fixed 930-frame validation: localization gain, size trade-off',fontsize=15,fontweight='bold');fig.tight_layout(rect=(0,0,1,.95));path=OUT/'R150_real_validation_summary.png';fig.savefig(path,dpi=190);print(path)
if __name__=='__main__':main()
