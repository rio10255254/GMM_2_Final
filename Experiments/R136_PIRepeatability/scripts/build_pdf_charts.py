from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];TMP=ROOT/'tmp/package_build';T=ROOT/'results/lsc/r61_analysis/tables'
positions=pd.read_csv(T/'per_position.csv');scans=pd.read_csv(T/'per_scan.csv')
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.17})
for mode in ['position','repeatability','captures']:
    fig,axes=plt.subplots(2,1,figsize=(6.5,7.0),layout='constrained')
    for ax,kind,label in zip(axes,['adjacent','start'],['Adjacent steps','Relative to scan start']):
        for model,color in [('Raw','#565D67'),('R61','#117C99')]:
            if mode=='captures':g=scans[(scans.view=='nominal_all30')&(scans.kind==kind)&(scans.model==model)].sort_values('run_index');x=g.run_index;y=g.mae_nm
            else:g=positions[(positions.view=='nominal_all30')&(positions.kind==kind)&(positions.model==model)].sort_values('position_index');x=g.position_index;y=g.bias_nm if mode=='position' else g.repeatability_sd_nm
            ax.plot(x,y,'o-' if mode=='captures' else '-',ms=3,color=color,label=model)
            if mode=='position':ax.fill_between(x,y-g.repeatability_sd_nm,y+g.repeatability_sd_nm,color=color,alpha=.14)
        if mode=='position':ax.axhline(0,color='#999',lw=.8)
        else:ax.set_ylim(bottom=0)
        if mode=='captures':ax.axvline(6.5,color='#999',ls='--',lw=.8)
        ax.set(title=label,xlabel='Capture number' if mode=='captures' else 'Position index',ylabel={'position':'LSC minus PI displacement (nm)','repeatability':'SD across 30 captures (nm)','captures':'Mean absolute error (nm)'}[mode]);ax.legend(frameon=False)
    fig.savefig(TMP/f'pdf_chart_{mode}.png',dpi=200);plt.close(fig)
print('Prepared vertical PDF charts')
