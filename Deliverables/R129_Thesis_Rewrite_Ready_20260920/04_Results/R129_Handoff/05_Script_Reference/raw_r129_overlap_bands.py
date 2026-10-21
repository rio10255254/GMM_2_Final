"""Overlay the verified latest Raw/R129 means and repeat SD bands; no PDF."""
from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];O=R/'results/sem_corner9/Raw_R129_comparison';F=O/'figures'
p=pd.read_csv(O/'fixed_position_statistics_120.csv');d=pd.read_csv(O/'all_displacements_3600.csv');colors={'Raw':'#59616b','R129':'#2088aa'}
rows=[]
for (m,k,j),g in d.groupby(['model','kind','j']):
 r=p[(p.model==m)&(p.kind==k)&(p.position_index==j)].iloc[0];mean=g.error_nm.mean();sd=g.error_nm.std(ddof=1)
 assert len(g)==30 and abs(mean-r.bias_nm)<1e-7 and abs(sd-r.repeatability_sd_nm)<1e-7
 rows.append(dict(model=m,kind=k,position_index=j,n=30,mean_error_nm=mean,repeat_sd_nm=sd,lower_mean_minus_sd_nm=mean-sd,upper_mean_plus_sd_nm=mean+sd))
data=pd.DataFrame(rows);data.to_csv(O/'overlay_mean_sd_plot_data.csv',index=False,encoding='utf-8-sig')
plt.rcParams.update({'font.size':12,'axes.spines.top':False,'axes.spines.right':False,'axes.titlesize':15,'axes.labelsize':13,'legend.frameon':False,'svg.fonttype':'none'})
fig,axes=plt.subplots(1,2,figsize=(15,6))
for ax,kind,title in zip(axes,['adjacent','start'],['Adjacent steps (~1 um)','Relative to scan start (~1-30 um)']):
 for m in ['Raw','R129']:
  q=data[(data.model==m)&(data.kind==kind)].sort_values('position_index');x=q.position_index.to_numpy();mean=q.mean_error_nm.to_numpy();sd=q.repeat_sd_nm.to_numpy()
  ax.fill_between(x,mean-sd,mean+sd,color=colors[m],alpha=.17,linewidth=.9,edgecolor=colors[m],zorder=1)
  ax.plot(x,mean,color=colors[m],lw=2,label=m,zorder=3)
 ax.axhline(0,color='#888888',lw=.9,zorder=2);ax.set_title(title);ax.set_xlabel('Position index');ax.set_ylabel('LSC displacement minus PI (nm)');ax.set_xlim(.5,30.5);ax.set_xticks(np.arange(0,31,5));ax.grid(alpha=.14);ax.set_axisbelow(True);ax.legend(loc='upper left')
fig.suptitle('Raw vs R129 | mean error and +/-1 SD across 30 captures',fontsize=17,y=.985)
fig.text(.5,.012,'Latest cross-corner nine pillars | shaded bands = repeat standard deviation, not a confidence interval',ha='center',fontsize=10,color='#555555')
fig.tight_layout(rect=[0,.045,1,.95]);name='09_mean_error_sd_overlay';fig.savefig(F/(name+'.png'),dpi=240,facecolor='white');fig.savefig(F/(name+'.svg'),facecolor='white');plt.close(fig)
marker='<!-- MEAN_SD_OVERLAY -->';text='''
## 平均曲線與波動帶疊合圖

灰色Raw、藍色R129，兩組直接疊在同一座標。實線是每個固定位置30次的平均PI差值，半透明帶是平均±1個樣本標準差；帶越窄代表本次重拍越一致。它不是95%信賴區間，也不是最大誤差範圍。左圖相鄰約1μm短步，右圖相對起點約1～30μm。兩圖均使用最新十字中心九顆，不使用範例中的舊R129資料。

![Raw與R129平均曲線及重拍波動帶](figures/09_mean_error_sd_overlay.png)

PNG可直接閱讀；同名SVG可作向量圖排版。逐點畫圖資料在overlay_mean_sd_plot_data.csv，全部120組平均與標準差均重新由3600筆明細核對。
'''
for path,prefix in [(O/'README.md','figures/'),(R/'reports/R136_RAW_R129_CORNER9_RESULTS.md','../results/sem_corner9/Raw_R129_comparison/figures/')]:
 t=path.read_text(encoding='utf-8')
 if marker not in t:path.write_text(t+'\n'+marker+'\n'+text.replace('](figures/',']('+prefix),encoding='utf-8')
(O/'overlay_verification.json').write_text(json.dumps({'mean_sd_groups_independently_recomputed':120,'observations':3600,'band_definition':'mean +/- sample SD (ddof=1), n=30 each','source_sha256':hashlib.sha256((O/'all_displacements_3600.csv').read_bytes()).hexdigest(),'models':['Raw','R129'],'target_group':'latest cross-corner nine','outputs':[name+'.png',name+'.svg']},indent=2),encoding='utf-8')
print('120 mean/SD groups verified; PNG and SVG generated.')
