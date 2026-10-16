"""Presentation-only two-method figures from the verified LSC tables."""
from common import *
import shutil,zipfile
import pandas as pd,numpy as np,cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
OUT=ROOT/'output/R129_vs_Raw_LSC_Charts';T=ROOT/'results/lsc/analysis/tables'
MODELS=['Raw','R129'];COLORS={'Raw':'#565D67','R129':'#C56B2A'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.16,'pdf.fonttype':42,'svg.fonttype':'none','savefig.dpi':300})

def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'chart_data').mkdir(exist_ok=True);audit=load(ROOT/'results/lsc/analysis/verification.json');assert audit['complete']
    data={}
    for name in ['readable_lsc_summary','per_position','per_scan','individual_circle_summary']:
        d=pd.read_csv(T/(name+'.csv'));d=d[d.model.isin(MODELS)].copy()
        if 'view' in d:d=d[d.view=='nominal_all30']
        assert set(d.model)==set(MODELS);data[name]=d;d.to_csv(OUT/'chart_data'/(name+'.csv'),index=False,encoding='utf-8-sig')
    summary=data['readable_lsc_summary'];pos=data['per_position'];runs=data['per_scan'];individual=data['individual_circle_summary'];assert len(runs)==120 and len(pos)==120 and len(individual)==36
    paired=pd.read_csv(T/'paired_comparisons.csv');paired=paired[(paired.view=='nominal_all30')&(paired.candidate=='R129')&(paired.reference=='Raw')];paired.to_csv(OUT/'chart_data/paired_comparisons.csv',index=False,encoding='utf-8-sig')
    repeated=pd.read_csv(T/'repeatability_comparisons.csv');repeated=repeated[(repeated.view=='nominal_all30')&(repeated.candidate=='R129')&(repeated.reference=='Raw')];repeated.to_csv(OUT/'chart_data/repeatability_comparisons.csv',index=False,encoding='utf-8-sig')
    captions=[]
    def finish(fig,name,caption):
        fig.savefig(OUT/(name+'.png'),dpi=300,bbox_inches='tight');fig.savefig(OUT/(name+'.svg'),bbox_inches='tight');plt.close(fig);captions.append((name,caption))
    fig,axes=plt.subplots(1,3,figsize=(13,4.7),layout='constrained')
    for ax,metric,title in zip(axes,['mae_nm','repeatability_nm','maximum_error_nm'],['Mean absolute error','Repeatability','Largest observed error']):
        for mi,m in enumerate(MODELS):
            vals=[summary[(summary.model==m)&(summary.kind==k)].iloc[0][metric] for k in ['adjacent','start']];bars=ax.bar(np.arange(2)+(mi-.5)*.32,vals,width=.32,color=COLORS[m],label=m);ax.bar_label(bars,fmt='%.2f',padding=3,fontsize=10)
        ax.set_xticks([0,1],['Adjacent steps','From scan start']);ax.set(title=title,ylabel='nm',ylim=(0,float(summary[metric].max())*1.28));ax.legend(frameon=False)
    fig.suptitle('Raw vs R129 | LSC, median of the same 9 circles | all 30 captures')
    finish(fig,'01_summary','主要結果：平均誤差、同一位置重拍的波動及本批最大誤差。柱狀圖從零開始，數字單位為奈米。')
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    for ax,k,title in zip(axes,['adjacent','start'],['Adjacent steps','Relative to scan start']):
        for m in MODELS:
            g=pos[(pos.kind==k)&(pos.model==m)].sort_values('position_index');x=g.position_index.to_numpy();mean=g.bias_nm.to_numpy();sd=g.repeatability_sd_nm.to_numpy();ax.plot(x,mean,label=m,color=COLORS[m]);ax.fill_between(x,mean-sd,mean+sd,color=COLORS[m],alpha=.15)
        ax.axhline(0,color='#999',lw=.8);ax.set(title=title,xlabel='Position index',ylabel='LSC displacement minus PI (nm)');ax.legend(frameon=False)
    fig.suptitle('Raw vs R129 | mean error and +/-1 SD across 30 captures')
    finish(fig,'02_position_error','各位置的平均有向誤差；陰影為同一位置30次重拍的正負1個標準差，不是平均值95%範圍。')
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    for ax,k,title in zip(axes,['adjacent','start'],['Adjacent steps','Relative to scan start']):
        for m in MODELS:
            g=pos[(pos.kind==k)&(pos.model==m)].sort_values('position_index');ax.plot(g.position_index,g.repeatability_sd_nm,label=m,color=COLORS[m])
        ax.set(title=title,xlabel='Position index',ylabel='SD across 30 repeated captures (nm)',ylim=(0,None));ax.legend(frameon=False)
    fig.suptitle('Raw vs R129 | repeatability at each matched position')
    finish(fig,'03_repeatability','同一位置重拍30次的波動。數值越小，這批重複拍攝的讀值越一致。')
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    for ax,k,title in zip(axes,['adjacent','start'],['Adjacent steps','Relative to scan start']):
        for m in MODELS:
            g=runs[(runs.kind==k)&(runs.model==m)].sort_values('run_index');ax.plot(g.run_index,g.mae_nm,'o-',ms=3.5,label=m,color=COLORS[m])
        ax.axvline(6.5,color='#999',ls='--',lw=.9);ax.set(title=title,xlabel='Capture number',ylabel='Mean absolute PI-referenced error (nm)',ylim=(0,None));ax.legend(frameon=False)
    fig.suptitle('Raw vs R129 | each point is one complete capture')
    finish(fig,'04_capture_comparison','30次掃描逐次比较。虛線區隔前6次與後24次拍攝；每個點代表一次完整掃描。')
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    for ax,k,title in zip(axes,['adjacent','start'],['Adjacent steps','Relative to scan start']):
        for mi,m in enumerate(MODELS):
            g=individual[(individual.kind==k)&(individual.model==m)].sort_values('pillar_id');ax.bar(g.pillar_id+(mi-.5)*.36,g.mae_nm,.36,label=m,color=COLORS[m])
        ax.set_xticks(range(1,10));ax.set(title=title,xlabel='Tracked circle ID',ylabel='Single-circle mean absolute error (nm)',ylim=(0,float(individual[individual.kind==k].mae_nm.max())*1.24));ax.legend(frameon=False)
    fig.suptitle('Raw vs R129 | all 9 circles reported separately')
    finish(fig,'05_individual_circles','各顆圓各自量測的平均絕對誤差，尚未合併成9圓讀值。9顆圓共享拍攝條件，不算9個獨立實驗。')
    fig,axes=plt.subplots(1,2,figsize=(12,3.8),layout='constrained')
    for ax,metric,title in zip(axes,['mae','repeatability'],['Improvement in mean absolute error','Improvement in repeatability']):
        for i,k in enumerate(['adjacent','start']):
            q=(paired[(paired.kind==k)&(paired.metric=='mae_nm')].iloc[0] if metric=='mae' else repeated[repeated.kind==k].iloc[0]);mean=-float(q['candidate_minus_reference_mean_nm'] if metric=='mae' else q['difference_nm']);lo=-float(q.ci95_high);hi=-float(q.ci95_low)
            ax.errorbar(mean,i,xerr=np.array([[mean-lo],[hi-mean]]),fmt='o',capsize=5,color=COLORS['R129'],lw=2);ax.annotate(f'{mean:.2f} [{lo:.2f}, {hi:.2f}]',xy=(mean,i),xytext=(0,12),textcoords='offset points',ha='center',fontsize=10)
        ax.set_yticks([0,1],['Adjacent steps','From scan start']);ax.axvline(0,color='#888',ls='--');ax.set_ylim(-.45,1.5);ax.set_xlim(left=min(0,ax.get_xlim()[0]));ax.set(title=title,xlabel='Raw minus R129 (nm): positive favors R129')
    fig.suptitle('Paired 95% intervals | complete capture is the resampling unit')
    finish(fig,'06_improvement_intervals','平均改善量與95%範圍，以完整掃描重抽樣；正值表示R129較小。範圍不代表完整量測不確定度。')
    centers=pd.read_csv(T/'all_circle_centers.csv');centers=centers[centers.model.isin(MODELS)];plan=load(ROOT/'config/plan.json')
    fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
    for ri,f in enumerate([plan['frames'][0],plan['frames'][-1]]):
        seeds=centers[(centers.model=='Raw')&(centers.run==f['run'])&(centers['index']==f['index'])]
        for ci,m in enumerate(MODELS):
            if m=='Raw':im=cv2.imread(f['source']['path'],0).astype(float)/255
            else:
                with np.load(ROOT/'results'/m/f['run']/f"{f['index']+1:02d}.npz") as z:im=z['output']
            g=centers[(centers.model==m)&(centers.run==f['run'])&(centers['index']==f['index'])].sort_values('pillar_id')
            with np.load(ROOT/'results/lsc/centers'/m/(f['run']+'.npz')) as z:points=z['points'][f['index']]
            ax=axes[ri,ci];ax.imshow(im,cmap='gray',vmin=0,vmax=1)
            for (_,r),pts in zip(g.iterrows(),points):ax.plot(pts[:,0],pts[:,1],'.',ms=2,color='#F2BC4D');ax.plot(r.center_x_px,r.center_y_px,'+',color='#00CFFF');ax.add_patch(Circle((r.center_x_px,r.center_y_px),r.radius_px,fill=False,ec='#00CFFF',lw=.7))
            ax.set_xlim(seeds.seed_x_px.min()-18,seeds.seed_x_px.max()+18);ax.set_ylim(seeds.seed_y_px.max()+18,seeds.seed_y_px.min()-18);ax.set_title(m+' | '+('first capture, first frame' if ri==0 else 'last capture, last frame'));ax.set_xlabel('Image x (px)');ax.set_ylabel('Image y (px)');ax.grid(False)
    fig.suptitle('Same 9 LSC targets | yellow: boundary samples | cyan: fitted center and circle')
    finish(fig,'07_circle_localization','實際LSC定位。兩方法使用相同9顆圓、相同顯示亮度與共同座標範圍；展示首末拍攝案例。')
    readme=['# Raw與R129：LSC比較圖表','','本圖集只含Raw與R129，使用已完成核對的全30次LSC資料。每方法930張、8370圓心；主要位移為9顆圓位移的中位數，名義尺度0.1725μm/px。','', 'PNG為300dpi圖片，SVG可放大編輯。主結果僅限本批20倍樣品及LSC量法。','']
    for name,caption in captions:readme.extend([f'## {name}',caption,f'![{caption}]({name}.png)',''])
    (OUT/'README.md').write_text('\n'.join(readme),encoding='utf-8');save(OUT/'source_manifest.json',dict(models=MODELS,view='nominal_all30',method='thesis_LSC_center9_median',figures=len(captions),source_tables=[record(T/(n+'.csv')) for n in data],verification=record(ROOT/'results/lsc/analysis/verification.json'),created_utc=now()))
    print('Created7two-methodfigures,PNG/SVG:',str(OUT),flush=True)
if __name__=='__main__':main()
