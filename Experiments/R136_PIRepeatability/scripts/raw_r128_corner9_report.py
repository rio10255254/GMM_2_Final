"""Matched Raw/R128 report on the same nine cross-corner pillars, without inference."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import json,hashlib,zipfile,shutil
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
R=Path(__file__).resolve().parents[1];B=R/'results/sem_corner9';T=B/'analysis/tables';S=B/'shape_size';O=B/'Raw_R128_comparison';O.mkdir(exist_ok=True);F=O/'figures';F.mkdir(exist_ok=True)
MODELS=['Raw','R128'];COL={'Raw':'#777777','R128':'#9356ad'};IDS=[22,23,24,28,29,30,34,35,36]
def read(name):return pd.read_csv(T/name)
def filt(df):
 if 'model' in df:df=df[df.model.isin(MODELS)]
 if 'view' in df:df=df[df.view=='nominal_all30']
 return df.copy()
def write(df,name):df.to_csv(O/name,index=False,encoding='utf-8-sig')
def save(fig,name):fig.tight_layout();fig.savefig(F/name,dpi=180);plt.close(fig)
def improvement(a,b):return 100*(1-b/a)
def main():
 d=filt(read('all_measurements.csv')).sort_values(['model','kind','run_index','j']);p=filt(read('per_position.csv'));c=pd.read_csv(S/'per_contour.csv');c=c[c.model.isin(MODELS)].sort_values(['model','run_index','index','pillar_id'])
 assert len(d)==3600 and len(c)==16740 and len(p)==120
 for model in MODELS:
  q=d[d.model==model];assert q.run.nunique()==30 and not q.duplicated(['kind','run_index','j']).any()
 a=d[d.model=='Raw'].set_index(['kind','run_index','j']);b=d[d.model=='R128'].set_index(['kind','run_index','j']);assert a.index.equals(b.index);assert np.array_equal(a.pi_dy_um,b.pi_dy_um)
 for (m,k,j),g in d.groupby(['model','kind','j']):
  ref=p[(p.model==m)&(p.kind==k)&(p.position_index==j)].iloc[0];assert len(g)==30 and abs(g.error_nm.std(ddof=1)-ref.repeatability_sd_nm)<1e-7
 write(d,'all_displacements_3600.csv');write(p,'fixed_position_statistics_120.csv');write(c,'all_contours_16740.csv')
 write(filt(read('all_individual_circle_pairs.csv')),'individual_circle_displacements_32400.csv');individual=filt(read('individual_circle_summary.csv'));write(individual,'individual_circle_displacement_summary.csv')
 paired=read('paired_comparisons.csv').query("view=='nominal_all30' and candidate=='R128' and reference=='Raw'");write(paired,'paired_displacement_evidence.csv');write(read('repeatability_comparisons.csv').query("view=='nominal_all30' and candidate=='R128' and reference=='Raw'"),'paired_repeatability_evidence.csv');write(pd.read_csv(S/'paired_scan_intervals.csv').query("comparison=='R128 - Raw'"),'paired_shape_size_evidence.csv')
 write(filt(read('per_scan.csv')),'per_scan_displacement.csv');write(filt(read('time_blocks.csv')),'time_block_displacement.csv')
 ds=pd.read_csv(B/'displacement_summary.csv');ds=ds[ds.model.isin(MODELS)];rows=[]
 for kind in ['adjacent','start']:
  z=ds[ds.kind==kind].set_index('model')
  for key in ['mae_nm','repeatability_nm','maximum_error_nm']:
   x,y=z.loc['Raw',key],z.loc['R128',key];rows.append(dict(scope=kind,metric=key,Raw_nm=x,R128_nm=y,R128_minus_Raw_nm=y-x,reduction_percent=improvement(x,y)))
 ss=pd.read_csv(S/'summary.csv').set_index('model')
 for key in ['diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm','diameter_repeat_absmax_nm']:
  x,y=ss.loc['Raw',key],ss.loc['R128',key];rows.append(dict(scope='contour',metric=key,Raw_nm=x,R128_nm=y,R128_minus_Raw_nm=y-x,reduction_percent=improvement(x,y)))
 comparison=pd.DataFrame(rows);write(comparison,'main_comparison.csv')
 endpoint=p[(p.kind=='start')&(p.position_index==30)];write(endpoint,'endpoint_30um.csv')
 # The worst cases are paired against the other method at exactly the same scan/step.
 worst=[]
 for m in MODELS:
  for k in ['adjacent','start']:
   q=d[(d.model==m)&(d.kind==k)]
   for ix in q.error_nm.abs().nlargest(5).index:
    r=q.loc[ix];other=d[(d.model!=m)&(d.kind==k)&(d.run_index==r.run_index)&(d.j==r.j)].iloc[0];worst.append(dict(selected_worst_of=m,kind=k,run=r.run,run_index=r.run_index,step=r.j,selected_error_nm=r.error_nm,other_model=other.model,other_error_same_observation_nm=other.error_nm))
 write(pd.DataFrame(worst),'paired_worst_cases.csv')
 radial={};diam={};shape={};perpillar=[];angles=[];bypos=[]
 for m in MODELS:
  z=np.load(S/f'{m}_radial_profiles.npz');radial[m]=z['radius_nm'].astype(float);theta=z['angle_rad'];diam[m]=c[c.model==m].diameter_nm.to_numpy().reshape(30,31,9);shape[m]=radial[m]-radial[m].mean(axis=-1,keepdims=True)
  assert abs(np.sqrt(diam[m].var(axis=0,ddof=1).mean())-ss.loc[m,'diameter_repeat_sd_nm'])<1e-8
  assert abs(np.sqrt(shape[m].var(axis=0,ddof=1).mean())-ss.loc[m,'shape_repeat_sd_nm'])<1e-4
  for j in range(9):
   perpillar.append(dict(model=m,local_pillar=j+1,SEM_id_inferred=IDS[j],diameter_mean_nm=diam[m][:,:,j].mean(),diameter_repeat_sd_nm=np.sqrt(diam[m][:,:,j].var(axis=0,ddof=1).mean()),contour_repeat_sd_nm=np.sqrt(radial[m][:,:,j].var(axis=0,ddof=1).mean()),shape_repeat_sd_nm=np.sqrt(shape[m][:,:,j].var(axis=0,ddof=1).mean()),diameter_max_deviation_nm=np.abs(diam[m][:,:,j]-diam[m][:,:,j].mean(axis=0)).max()))
  ar=np.sqrt(radial[m].var(axis=0,ddof=1).mean(axis=(0,1)));ash=np.sqrt(shape[m].var(axis=0,ddof=1).mean(axis=(0,1)))
  for i in range(720):angles.append(dict(model=m,angle_deg=i/2,contour_repeat_sd_nm=ar[i],shape_repeat_sd_nm=ash[i]))
  for j in range(31):bypos.append(dict(model=m,position=j,mean_nine_diameter_nm=diam[m][:,j].mean(),pooled_nine_diameter_repeat_sd_nm=np.sqrt(diam[m][:,j].var(axis=0,ddof=1).mean())))
 perpillar=pd.DataFrame(perpillar);write(perpillar,'nine_pillar_size_shape_comparison.csv');angles=pd.DataFrame(angles);write(angles,'angular_repeatability_1440.csv');bypos=pd.DataFrame(bypos);write(bypos,'diameter_by_position_62.csv')
 sem=pd.read_csv(B/'sem_group_size_comparison.csv');sem=sem[sem.model.isin(MODELS)];write(sem,'SEM_group_mean_size.csv');sens=pd.read_csv(B/'sem_mapping_sensitivity_summary.csv');sens=sens[sens.model.isin(MODELS)];write(sens,'SEM_direction_sensitivity.csv')
 fig,axs=plt.subplots(2,2,figsize=(12,8),sharex=True)
 for col,k in enumerate(['adjacent','start']):
  population=d[d.kind==k].error_nm;lim=(population.min()-3,population.max()+3)
  for row,m in enumerate(MODELS):
   ax=axs[row,col];q=d[(d.kind==k)&(d.model==m)];stats=p[(p.kind==k)&(p.model==m)].sort_values('position_index')
   for _,g in q.groupby('run_index'):ax.plot(g.j,g.error_nm,color=COL[m],alpha=.18,lw=.7)
   ax.plot(stats.position_index,stats.bias_nm,color=COL[m],lw=2);ax.axhline(0,color='black',lw=.7);ax.set_ylim(lim);ax.set_title(f'{m}: '+('adjacent ~1 um' if k=='adjacent' else 'from start ~1-30 um'));ax.set_xlabel('Step / position index');ax.set_ylabel('Image minus PI (nm)')
 fig.suptitle('Same nine pillars / 30 scans; faint = each scan, thick = mean; matched y-scales');fig.tight_layout(rect=[0,0,1,.96]);fig.savefig(F/'01_displacement_traces.png',dpi=180);plt.close(fig)
 fig,axs=plt.subplots(1,2,figsize=(12,4))
 for ax,k in zip(axs,['adjacent','start']):
  for m in MODELS:
   q=p[(p.model==m)&(p.kind==k)].sort_values('position_index');ax.plot(q.position_index,q.repeatability_sd_nm,color=COL[m],lw=1.8,label=m)
  ax.set_title('Adjacent steps' if k=='adjacent' else 'From start');ax.set_xlabel('Step / position index');ax.set_ylabel('Repeat sample SD (nm)');ax.set_ylim(bottom=0);ax.legend()
 save(fig,'02_displacement_repeatability.png')
 for pos in [0,30]:
  fig,axs=plt.subplots(3,3,figsize=(10,10))
  for j,ax in enumerate(axs.flat):
   for m in MODELS:
    for sig in radial[m][:,pos,j]:ax.plot(sig*np.cos(theta),sig*np.sin(theta),color=COL[m],alpha=.12,lw=.65)
    mean=radial[m][:,pos,j].mean(axis=0);ax.plot(mean*np.cos(theta),mean*np.sin(theta),color=COL[m],lw=1.5)
   ax.set_aspect('equal');ax.set_xlim(-1650,1650);ax.set_ylim(-1650,1650);ax.set_title(f'Local {j+1} / inferred SEM {IDS[j]}',fontsize=9);ax.set_xlabel('x (nm)');ax.set_ylabel('y (nm)');ax.tick_params(labelsize=8)
  fig.legend([Line2D([0],[0],color=COL[m]) for m in MODELS],MODELS,loc='upper center',ncol=2);fig.suptitle(f'All nine / 30 repeats at position {pos}; centers aligned, no size normalization',y=.965,fontsize=11);fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(F/f'03_contours_position{pos:02d}.png',dpi=180);plt.close(fig)
 fig,axs=plt.subplots(1,2,figsize=(12,4))
 for m in MODELS:
  q=bypos[bypos.model==m];axs[0].plot(q.position,q.mean_nine_diameter_nm,color=COL[m],label=m);axs[1].plot(q.position,q.pooled_nine_diameter_repeat_sd_nm,color=COL[m],label=m)
 axs[0].axhline(sem.SEM_group_mean_diameter_nm.iloc[0],color='black',ls='--',label='SEM nine mean');axs[0].set_title('Mean diameter (all nine, 30 scans)');axs[1].set_title('Diameter repeat SD at each position')
 for ax in axs:ax.set_xlabel('Position index (0 = start)');ax.set_ylabel('nm');ax.legend()
 axs[1].set_ylim(bottom=0);save(fig,'04_diameter_and_SEM.png')
 fig,axs=plt.subplots(1,2,figsize=(12,4))
 for ax,key,title in zip(axs,['contour_repeat_sd_nm','shape_repeat_sd_nm'],['Contour: size changes retained','Shape: mean radius removed']):
  for m in MODELS:
   q=angles[angles.model==m];ax.plot(q.angle_deg,q[key],color=COL[m],label=m)
  ax.set_title(title);ax.set_xlabel('Angle (degrees)');ax.set_ylabel('Pooled repeat SD (nm)');ax.set_ylim(bottom=0);ax.legend()
 save(fig,'05_angular_repeatability.png')
 fig,axs=plt.subplots(1,3,figsize=(14,4))
 for ax,key,title in zip(axs,['diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm'],['Diameter repeatability','Contour repeatability','Shape repeatability']):
  for m in MODELS:
   q=perpillar[perpillar.model==m];ax.plot(q.local_pillar,q[key],marker='o',color=COL[m],label=m)
  ax.set_title(title);ax.set_xlabel('Local pillar');ax.set_ylabel('Repeat SD (nm)');ax.set_xticks(range(1,10));ax.set_ylim(bottom=0);ax.legend()
 save(fig,'06_each_pillar_repeatability.png')
 # Include all individually tracked displacement results, rather than only the nine-circle aggregate.
 fig,axs=plt.subplots(1,2,figsize=(12,4))
 for ax,k in zip(axs,['adjacent','start']):
  for m in MODELS:
   q=individual[(individual.model==m)&(individual.kind==k)].sort_values('pillar_id');ax.plot(q.pillar_id,q.mae_nm,marker='o',color=COL[m],label=m)
  ax.set_title('Individual-circle '+k+' PI difference');ax.set_xlabel('Local pillar');ax.set_ylabel('Mean absolute difference (nm)');ax.set_xticks(range(1,10));ax.set_ylim(bottom=0);ax.legend()
 save(fig,'07_individual_circle_displacement.png')
 from scipy.optimize import least_squares
 ref=np.load(B/'sem_nine_original_reference_points.npz');scale=json.loads((R.parent/'R135_UnifiedModelComparison/results/Raw/sem/complete.json').read_text())['scale_nm_per_px']
 fig,axs=plt.subplots(3,3,figsize=(10,10))
 for j,ax in enumerate(axs.flat):
  for m in MODELS:
   for sig in radial[m][:,0,j]:ax.plot(sig*np.cos(theta),sig*np.sin(theta),color=COL[m],alpha=.12,lw=.7)
  q=ref[f'SEM_{IDS[j]}'];q=q-q.mean(axis=0)
  def fun(center):
   rr=np.linalg.norm(q-center,axis=1);return rr-rr.mean()
  center=least_squares(fun,[0,0],xtol=1e-12,ftol=1e-12,gtol=1e-12).x;q=(q-center)*scale;q[:,0]*=-1;q=np.vstack([q,q[0]])
  ax.plot(q[:,0],q[:,1],color='black',lw=1.1);ax.set_title(f'Local {j+1} / inferred SEM {IDS[j]}',fontsize=9);ax.set_aspect('equal');ax.set_xlim(-1650,1650);ax.set_ylim(-1650,1650);ax.set_xlabel('x (nm)');ax.set_ylabel('y (nm)');ax.tick_params(labelsize=8)
 fig.legend([Line2D([0],[0],color=x) for x in ['#777777','#9356ad','black']],['Raw','R128','SEM'],loc='upper center',ncol=3);fig.suptitle('Position 0 / 30 repeats; SEM uses inferred horizontal mirror (not uniquely verified)',y=.965,fontsize=10);fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(F/'08_SEM_inferred_comparison.png',dpi=180);plt.close(fig)
 def md(x):return x.round(3).to_markdown(index=False)
 text='''# Raw與R128：最新十字中心九顆的完整比較

相同九顆、相同30次掃描、每次31位置；每組930影像／8370輪廓。所有主要指標重新核對Raw/R128的掃描、位置和PI配對。沿用相同論文LSC邊界與圓心量法，名義172.5nm/px；無新推論、無训练、無剔除最差觀測。

結論：R128明顯降低短步位移與尺寸／輪廓的重拍波動。但九顆平均直徑相對SEM的偏大差距增加，不能把更穩定寫成尺寸更準。長距離位移的平均差距是否改善，另看配對範圍，不能只看平均值的名次。

## 主要比較

下表reduction_percent正值為相對Raw降低百分比；maximum是本次觀察到的最差值，不是未來保證界限。adjacent為相鄰約1μm，start為相對起點約1～30μm。

'''+md(comparison)+'''

位移repeatability是30個固定步／位置的跨30次標準差之平均。尺寸／輪廓repeatability是固定位置、顆粒與方向的樣本變異數平均後開根號。尺寸是直徑波動；輪廓與形狀是半徑方向波動，不應將其數值直接視為同一量。

## 完整掃描配對的差距範圍

R128減Raw，負值表示變小。以完整掃描為抽樣單位，不把900筆或九顆当独立掃描。保留普通重抽與連續三次掃描成組的範圍，包含零代表本批不足以確認方向。

'''+md(paired[paired.metric=='mae_nm'][['kind','candidate_minus_reference_mean_nm','ci95_low','ci95_high','block3_ci95_low','block3_ci95_high','improved_scans','worsened_scans']])+'''

## 約30μm終點（與全路徑平均分開）

'''+md(endpoint[['model','pi_displacement_um','bias_nm','repeatability_sd_nm','observed_min_nm','observed_max_nm']])+'''

## 各顆尺寸與輪廓

'''+md(perpillar)+'''

局部1～9為固定追蹤身份；SEM編號採左右鏡像工作推定，未宣稱已唯一確認方向。起點與終點各提供全部九顆的30次輪廓疊圖，Raw灰色、R128紫色；只對齊圓心，不縮放或旋轉消除差異。

## 尺寸與SEM

'''+md(sem)+'''

R128比Raw的平均直徑大36.858nm；SEM九顆平均相同，因此整組平均尺寸偏大差距也增加36.858nm（約19.90%）。這項集合平均不受九顆編號排列影響。SEM逐顆方向仍有兩種候選；下表完整保留兩種的輪廓差距，不以較好分數挑方向，也不把去尺寸後的形狀改善當成完整輪廓或尺寸改善。candidate1為目前推定的左右鏡像、candidate2為保留的90度旋轉。radial_mae保留尺寸差；shape_mae扣除平均半徑差，均為nm。兩種方向下，R128形狀差距較小，但含尺寸的完整輪廓差距較大。

'''+md(sens)+'''

## 圖表

'''
 for path,caption in [('01_displacement_traces.png','兩組30次位移；每欄使用相同縱軸'),('02_displacement_repeatability.png','每個固定位置的重拍波動'),('03_contours_position00.png','起始位置全部九顆輪廓'),('03_contours_position30.png','約30μm終點全部九顆輪廓'),('04_diameter_and_SEM.png','沿移動位置的平均尺寸、SEM及重拍波動'),('05_angular_repeatability.png','各方向輪廓與形狀重拍波動'),('06_each_pillar_repeatability.png','逐顆尺寸、輪廓、形狀波動'),('07_individual_circle_displacement.png','每一顆獨立位移差距；與九顆合併的主結果分開'),('08_SEM_inferred_comparison.png','Raw／R128／SEM全部九顆；SEM方向標示為推定')]:text+=f'![{caption}](figures/{path})\n\n'
 text+='''## 明細、範圍與核對

共有3600筆九顆合併位移、32400筆單顆位移、16740輪廓、120個固定步／位置統計；另有每次掃描、前6／後24時段、同一觀測的兩模型最差案例對照、逐顆與逐角度表。最大直徑偏離是相對同位置同顆30次平均，不是對SEM的誤差。

結果來自已核對的四模型33480個獨立圓擬合。本次另重新核對所有120個位置標準差、兩模型全部尺寸／形狀彙總、掃描鍵及PI完全一致。輪廓插值720方向來自原64邊界點，不增加實際解析度；來源雜湊與驗證紀錄另存。

所有波動只代表本次拍攝工作階段；沒有把PI校正、實際倍率、SEM尺度和邊界判讀未知分量設成零。完整總不確定度尚未建立。更穩定不等同絕對尺寸更準。
'''
 (O/'README.md').write_text(text,encoding='utf-8');(R/'reports/R136_RAW_R128_CORNER9_RESULTS.md').write_text(text.replace('](figures/','](../results/sem_corner9/Raw_R128_comparison/figures/'),encoding='utf-8')
 sources=[T/'all_measurements.csv',T/'per_position.csv',T/'all_individual_circle_pairs.csv',S/'per_contour.csv',S/'Raw_radial_profiles.npz',S/'R128_radial_profiles.npz']
 (O/'verification.json').write_text(json.dumps({'verified':True,'matched_aggregate_displacements':1800,'positions_recomputed':120,'contours':16740,'sources':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in sources},'target_group':'latest cross-corner nine','SEM_direction':'working horizontal mirror inference; alternative retained','no_model_inference':True},indent=2),encoding='utf-8')
 print(comparison.to_string(index=False));print(paired[paired.metric=='mae_nm'].to_string(index=False));print(endpoint.to_string(index=False))
if __name__=='__main__':main()
