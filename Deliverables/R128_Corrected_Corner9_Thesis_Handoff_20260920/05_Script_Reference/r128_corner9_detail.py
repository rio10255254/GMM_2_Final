"""Focused R128 tables/figures from the verified cross-corner nine; no inference."""
from pathlib import Path
import json,hashlib,zipfile
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];B=R/'results/sem_corner9';O=B/'R128_detail';O.mkdir(exist_ok=True);F=O/'figures';F.mkdir(exist_ok=True)
T=B/'analysis/tables';color='#9356ad'
d=pd.read_csv(T/'all_measurements.csv').query("model=='R128' and view=='nominal_all30'").sort_values(['kind','run_index','j']);assert len(d)==1800
p=pd.read_csv(T/'per_position.csv').query("model=='R128' and view=='nominal_all30'").sort_values(['kind','position_index']);assert len(p)==60 and (p.n==30).all()
c=pd.read_csv(B/'shape_size/per_contour.csv').query("model=='R128'").sort_values(['run_index','index','pillar_id']);assert len(c)==8370
shape=pd.read_csv(B/'shape_size/summary.csv').query("model=='R128'").iloc[0]
z=np.load(B/'shape_size/R128_radial_profiles.npz');rad=z['radius_nm'].astype(float);theta=z['angle_rad'];assert rad.shape==(30,31,9,720)
diam=c.diameter_nm.to_numpy().reshape(30,31,9);sh=rad-rad.mean(axis=-1,keepdims=True)
assert abs(np.sqrt(diam.var(axis=0,ddof=1).mean())-shape.diameter_repeat_sd_nm)<1e-8
assert abs(np.sqrt(sh.var(axis=0,ddof=1).mean())-shape.shape_repeat_sd_nm)<1e-4
details=[];ids=[22,23,24,28,29,30,34,35,36]
for j in range(9):
 details.append(dict(local_pillar=j+1,SEM_id_inferred=ids[j],mean_diameter_nm=diam[:,:,j].mean(),diameter_repeat_sd_nm=np.sqrt(diam[:,:,j].var(axis=0,ddof=1).mean()),diameter_max_deviation_nm=abs(diam[:,:,j]-diam[:,:,j].mean(axis=0)).max(),contour_repeat_sd_nm=np.sqrt(rad[:,:,j].var(axis=0,ddof=1).mean()),shape_repeat_sd_nm=np.sqrt(sh[:,:,j].var(axis=0,ddof=1).mean())))
pillars=pd.DataFrame(details);pillars.to_csv(O/'nine_pillars.csv',index=False)
d.to_csv(O/'displacement_all_1800.csv',index=False);p.to_csv(O/'displacement_by_position_60.csv',index=False);c.to_csv(O/'contours_all_8370.csv',index=False)
summary=[];worst=[]
for kind in ['adjacent','start']:
 q=d[d.kind==kind];positions=p[p.kind==kind]
 for j,g in q.groupby('j'):
  ref=positions[positions.position_index==j].iloc[0];assert abs(g.error_nm.std(ddof=1)-ref.repeatability_sd_nm)<1e-7
 for row in q.loc[q.error_nm.abs().nlargest(5).index].itertuples():worst.append(dict(kind=kind,run=row.run,run_index=row.run_index,from_index=row.i,to_index=row.j,error_nm=row.error_nm,pi_displacement_um=row.pi_dy_um))
 ci=pd.read_csv(T/'repeatability.csv').query("model=='R128' and view=='nominal_all30' and kind==@kind").iloc[0]
 summary.append(dict(kind=kind,observations=len(q),scans=30,positions=30,mean_abs_PI_difference_nm=q.error_nm.abs().mean(),mean_signed_PI_difference_nm=q.error_nm.mean(),repeat_sd_average_nm=positions.repeatability_sd_nm.mean(),repeat_sd_pooled_rms_nm=np.sqrt(np.mean(positions.repeatability_sd_nm**2)),repeat_sd_min_nm=positions.repeatability_sd_nm.min(),repeat_sd_max_nm=positions.repeatability_sd_nm.max(),repeat_sd_average_ci95_low_nm=ci.ci95_low,repeat_sd_average_ci95_high_nm=ci.ci95_high,max_abs_PI_difference_nm=q.error_nm.abs().max()))
summary=pd.DataFrame(summary);summary.to_csv(O/'displacement_summary.csv',index=False);pd.DataFrame(worst).to_csv(O/'worst_displacements.csv',index=False)
endpoint=p.query("kind=='start' and position_index==30");endpoint.to_csv(O/'endpoint_30um.csv',index=False)
fig,axs=plt.subplots(2,2,figsize=(12,8))
for col,kind in enumerate(['adjacent','start']):
 q=d[d.kind==kind];stats=p[p.kind==kind];ax=axs[0,col]
 for run,g in q.groupby('run_index'):ax.plot(g.j,g.error_nm,color=color,alpha=.17,lw=.8)
 ax.plot(stats.position_index,stats.bias_nm,color=color,lw=2,label='Mean of 30 repeats');ax.axhline(0,color='black',lw=.7);ax.set_title('Adjacent ~1 um steps' if kind=='adjacent' else 'Displacement from start');ax.set_ylabel('Image minus PI (nm)');ax.set_xlabel('Step / position index');ax.legend(fontsize=8)
 ax=axs[1,col];ax.fill_between(stats.position_index,stats.observed_min_nm,stats.observed_max_nm,color=color,alpha=.13,label='Observed min to max');ax.plot(stats.position_index,stats.bias_nm,color=color,lw=1.8,label='Mean');ax.errorbar(stats.position_index,stats.bias_nm,yerr=stats.repeatability_sd_nm,fmt='none',ecolor=color,alpha=.7,label='Mean +/- 1 sample SD');ax.axhline(0,color='black',lw=.7);ax.set_ylabel('Image minus PI (nm)');ax.set_xlabel('Step / position index');ax.legend(fontsize=8)
fig.suptitle('R128 / cross-corner nine: 30 complete scans, nominal 0.1725 um/px');fig.tight_layout(rect=[0,0,1,.96]);fig.savefig(F/'01_displacement_30_repeats.png',dpi=180);plt.close(fig)
fig,axs=plt.subplots(3,3,figsize=(10,10))
for j,ax in enumerate(axs.flat):
 for trace in rad[:,0,j]:ax.plot(trace*np.cos(theta),trace*np.sin(theta),color=color,alpha=.17,lw=.8)
 mean=rad[:,0,j].mean(axis=0);ax.plot(mean*np.cos(theta),mean*np.sin(theta),color=color,lw=1.8);ax.set_title(f'Local pillar {j+1} (inferred SEM {ids[j]})',fontsize=9);ax.set_aspect('equal');ax.set_xlim(-1650,1650);ax.set_ylim(-1650,1650);ax.set_xlabel('x (nm)');ax.set_ylabel('y (nm)');ax.tick_params(labelsize=8)
fig.suptitle('R128: all nine pillars / 30 repeats at the first position\nCentered contours; equal scale; no size normalization',fontsize=12);fig.tight_layout(rect=[0,0,1,.95]);fig.savefig(F/'02_all_nine_contours.png',dpi=180);plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(12,4))
for j in range(9):
 axs[0].plot(np.arange(31),diam[:,:,j].mean(axis=0),label=str(j+1))
 axs[1].plot(np.arange(31),diam[:,:,j].std(axis=0,ddof=1),label=str(j+1))
axs[0].set_title('Mean diameter over 30 repeats');axs[1].set_title('Diameter repeat SD at each fixed position')
for ax in axs:ax.set_xlabel('Position index (0 = start)');ax.set_ylabel('nm');ax.legend(title='Local pillar',ncol=3,fontsize=7)
fig.tight_layout();fig.savefig(F/'03_diameter_by_position.png',dpi=180);plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(12,4))
for j in range(9):
 axs[0].plot(np.degrees(theta),np.sqrt(rad[:,:,j].var(axis=0,ddof=1).mean(axis=0)),label=str(j+1))
 axs[1].plot(np.degrees(theta),np.sqrt(sh[:,:,j].var(axis=0,ddof=1).mean(axis=0)),label=str(j+1))
axs[0].set_title('Contour repeat SD (size changes included)');axs[1].set_title('Shape repeat SD (mean radius removed)')
for ax in axs:ax.set_xlabel('Angle (degrees)');ax.set_ylabel('Pooled repeat SD (nm)');ax.legend(title='Local pillar',ncol=3,fontsize=7)
fig.tight_layout();fig.savefig(F/'04_contour_repeat_by_angle.png',dpi=180);plt.close(fig)
metadata={'model':'R128 fixed P_s1285002 step8192','checkpoint_sha256':'9fbdffa3bebe0a37e3f7c2b09239e2e00de6b0522feb101571fcfb7a42699abf','target_group':'cross-corner nine, NOT previous center nine','scans':30,'positions_per_scan':31,'images':930,'contours':8370,'boundary_points_per_contour':64,'radial_interpolation_angles':720,'nominal_nm_per_px':172.5,'direction':'working horizontal-mirror inference; SEM individual orientation not uniquely proved','statistics':'position matched across scans; sample SD ddof1; scan-level paired bootstrap already saved; no outlier removal','SEM':'group mean diameter comparison only is independent of nine-ID permutation; do not call repeat SD SEM error','full_system_uncertainty':'not established; scale, PI and SEM reference components incomplete','sources':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [T/'all_measurements.csv',T/'per_position.csv',B/'shape_size/per_contour.csv',B/'shape_size/R128_radial_profiles.npz']}}
(O/'method_and_sources.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
def tab(x):return x.round(4).to_markdown(index=False)
text='''# R128：十字中心附近九顆 pillar 的重複度詳表

本文件只使用最新選定的十字交界九顆。固定R128模型，30次完整掃描、每次31個位置，共930張／8370輪廓。沒有混入之前畫面中央九顆，也沒有重新訓練或改重建。

## 位移

每張以論文LSC找九顆圓心，逐顆相减后取九顆位移向量的分量中位數，再比較同時記錄的PI回授。adjacent為相鄰約1μm步距；start為相對起點約1～30μm。每類900筆。正值為影像量到的位移較PI大。

'''+tab(summary)+'''

repeat_sd_average是30個固定步／位置各自跨30次的樣本標準差之平均，表示平均重拍波動。另列變異數平均後開根號，避免兩種彙整方式混稱。範圍列出各位置最小／最大波動；它們不是誤差上下界。ci95是以完整掃描重抽所得平均波動的95%範圍，不是未來單次量測的保證範圍。圖中的淡色區為本次實際最小至最大，線上誤差棒為±1標準差，並非95%區間。

### 約30μm終點

'''+tab(endpoint[['pi_displacement_um','bias_nm','repeatability_sd_nm','observed_min_nm','observed_max_nm','mae_nm']])+'''

終點和全路徑平均必須分開：可有很小重拍波動，同時存在每次都相似的固定偏差。

## 輪廓、尺寸、形狀

'''+tab(pd.DataFrame([shape])[['diameter_mean_nm','diameter_repeat_sd_nm','diameter_repeat_sd_nm_ci_low','diameter_repeat_sd_nm_ci_high','contour_repeat_sd_nm','shape_repeat_sd_nm','shape_repeat_sd_nm_ci_low','shape_repeat_sd_nm_ci_high','diameter_repeat_absmax_nm','diameter_within_scan_sd_nm']])+'''

尺寸重拍波動：固定位置與固定顆粒，計算30次直徑變異數，再將31×9組變異數平均後開根號。輪廓重拍波動：去除圓心平移後，固定方向的邊界半徑跨30次波動，保留尺寸改變。形狀重拍波動：再扣除每條輪廓平均半徑，單看形狀改變。每個方向等權，沒有旋轉或縮放配合形狀。

最大尺寸偏離是所有8370次相對各自固定位置／顆粒30次平均的最大絕對直徑差，不是對SEM的最差誤差。diameter_within_scan_sd是一次掃描移動31個位置的尺寸波動，與重拍波動不同。

### 逐顆結果

'''+tab(pillars)+'''

SEM編號採左右鏡像工作推定；局部顆粒1～9的追蹤身份固定且不依賴SEM方向。這些統計不因兩個SEM排列候選切換而變化。

## 與SEM尺寸分開解讀

新九顆R128平均直徑2836.478nm；SEM九顆平均2614.439nm，平均偏大222.040nm。這是尺寸差距，不能因尺寸重拍波動僅9.527nm而忽略。單次量測穩定和尺寸接近實物是不同問題。

上述結果採名義172.5nm/px與現有SEM邊界。PI回授、實際倍率、SEM尺度與邊界判讀的不確定度尚未全部合入，不將重拍標準差或其兩倍宣稱為完整總不確定度。這是同一拍攝工作階段的結果，不直接外推其他日期或樣品。

## 圖表

![30次位移及各位置波動](figures/01_displacement_30_repeats.png)

![九顆各自的30次輪廓](figures/02_all_nine_contours.png)

![沿移動位置的尺寸與波動](figures/03_diameter_by_position.png)

![各方向的輪廓與形狀波動](figures/04_contour_repeat_by_angle.png)

## 明細與核對

displacement_all_1800.csv完整位移；displacement_by_position_60.csv固定位置統計；endpoint_30um.csv終點；worst_displacements.csv最差實際案例；contours_all_8370.csv每個輪廓的圓心、直徑與形狀；nine_pillars.csv逐顆摘要。method_and_sources.json記錄固定模型、量法與來源雜湊。資料來自已核對的33480個四模型獨立圓擬合；本次再次按位置重算R128全部60個標準差、尺寸與形狀彙總，結果一致。
'''
(O/'README.md').write_text(text,encoding='utf-8')
canonical=text.replace('](figures/','](../results/sem_corner9/R128_detail/figures/')
(R/'reports/R136_R128_CORNER9_DETAIL.md').write_text(canonical,encoding='utf-8')
print(summary.to_string(index=False));print(endpoint.to_string(index=False));print(pillars.to_string(index=False));print(pd.DataFrame(worst).head(1).to_string(index=False))
print('All focused numeric checks passed.')
