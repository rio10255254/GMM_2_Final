from pathlib import Path
import json,zipfile,html
import numpy as np,pandas as pd
from scipy.optimize import least_squares
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];O=R/'results/sem_reference_followup';OLD=R.parent/'R135_UnifiedModelComparison'
models=['Raw','R61','R129','R128'];colors=['#777777','#df8636','#2088aa','#9356ad'];data={};maxerr=0
sc=json.loads((O/'R129_original80/complete.json').read_text())['scale_nm_per_px']
def centered(p):
 o=p.mean(0);z=p-o
 def f(c):
  d=np.linalg.norm(z-c,axis=1);return d-d.mean()
 c=least_squares(f,[0,0],xtol=1e-12,ftol=1e-12,gtol=1e-12).x
 return (z-c)*sc
tab=pd.read_csv(O/'historical_sem_per_pillar.csv')
for model in models:
 p=O/'R129_original80' if model=='R129' else OLD/f'results/{model}/sem';data[model]=np.load(p/'points.npz')
 for row in tab[tab.model==model].itertuples():
  a=centered(data[model][f'{row.exposure}_{row.pillar}']);b=centered(data[model][f'SEM_{row.pillar}'])
  err=abs(2*(np.linalg.norm(a,axis=1).mean()-np.linalg.norm(b,axis=1).mean())-row.signed_diameter_nm);maxerr=max(maxerr,err)
assert maxerr<1e-4
fig,axes=plt.subplots(3,4,figsize=(12,9))
for row,pid in enumerate([5,15,22]):
 for col,(model,color) in enumerate(zip(models,colors)):
  ax=axes[row,col]
  for exp in [13,14,15]:
   p=centered(data[model][f'{exp}_{pid}']);p=np.vstack([p,p[0]]);ax.plot(p[:,0],p[:,1],color=color,alpha=.5,lw=1.2)
  p=centered(data[model][f'SEM_{pid}']);p=np.vstack([p,p[0]]);ax.plot(p[:,0],p[:,1],color='black',lw=1.2)
  ax.set_title(f'{model} / SEM ID {pid}');ax.set_aspect('equal');ax.set_xlim(-1500,1500);ax.set_ylim(-1500,1500);ax.set_xlabel('x (nm)');ax.set_ylabel('y (nm)')
fig.suptitle('Black: SEM; color: 3 optical exposures (historical paired sample)');fig.tight_layout(rect=[0,0,1,.97]);fig.savefig(O/'sem_model_columns.png',dpi=180)
summary=pd.read_csv(O/'historical_sem_summary.csv');rng=np.random.default_rng(136);draw=rng.integers(0,36,(10000,36));ci=[]
for key in ['diameter_error_nm','centered_shape_nm','radial_nm']:
 a=tab[tab.model=='R128'].groupby('pillar')[key].median().sort_index().to_numpy();b=tab[tab.model=='R129'].groupby('pillar')[key].median().sort_index().to_numpy()
 bs=np.median(a[draw],axis=1)-np.median(b[draw],axis=1);lo,hi=np.quantile(bs,[.025,.975]);ci.append(dict(metric=key,difference=np.median(a)-np.median(b),low=lo,high=hi))
pd.DataFrame(ci).to_csv(O/'historical_paired_intervals.csv',index=False)
report='''# R136 SEM資料找回、逐顆對照與四組比較

2026-09-19。使用者確認九月重拍與舊SEM為同一片樣品；同一顆位置仍需核對。

## 已找回與核對

- 原始SEM：H:/From_2TB_D_disk/13_thesis/SEM_data；專案副本：Thesis_MOSR_Evidence/20260618_100MG/SEM_data。
- P-01～09 與 V-01～09 共18張，與舊MATLAB的SEM資料夾三方逐檔雜湊完全一致。
- ordering_result_20260729/SEM_center36_file_mapping.csv 提供36顆的P/V影像、四角與6×6位置。P/V是兩種實體結構，不可將V孔輪廓當P柱輪廓的真值。本次四模型量化使用P柱，V的影像與位置對照已核實但未宣稱完成V模型評分。
- 原始對位程式 SEM2img_v2.m 將P對應曝光13～24、V對應1～11。此次採已有完整浮點重建的P曝光13、14、15，共36顆×3曝光×4方法=432次對照。
- image_cropped/13.bmp 在原始 image_B2D/13.bmp 的左上座標(1581,1088)，逐像素影像相關為1.0，找回原裁切位置。

## 舊樣品有紀錄的逐顆比較

單位nm，越小代表與SEM差距越小。每顆先取3曝光中位數，再取36顆中位數；不是九月30次重拍的統計。

| 方法 | 直徑差距 | 去除平均尺寸後的形狀差距 | 包含尺寸的輪廓差距 |
|---|---:|---:|---:|
'''
for x in summary.itertuples():report+=f'| {x.model} | {x.diameter_error_nm:.2f} | {x.centered_shape_nm:.2f} | {x.radial_nm:.2f} |\n'
report+='''
R128的直徑及包含尺寸的輪廓差距最小；R61的去尺寸形狀差距最小。R128、R129形狀中位數很接近，不以細微差值宣布普遍優勝。配對範圍見historical_paired_intervals.csv，以36顆為重抽單位，不將三個曝光當108個独立物體。

R61曾用本批SEM尺寸答案訓練；上述分數可作已有樣品表現，不能作未見答案的獨立驗證。完整來源審查見R135_R61_TRAINING_AUDIT.md。所有方法結果均保留，不挑除SEM ID17與28等輪廓局部不規則點；這些位置可能包含邊界讀取異常，圖中完整呈現，不能直接認定為真實缺陷。

## R129設定與檢查

使用與R136相同固定8192權重及80/16邊界政策。由舊R135保存的W16浮點輸出恢復80/16：80像素內取原圖、80～96混合、96以上保留既有模型值。這些區域在W16內已是完全模型輸出；恢復僅有既有浮點捨入限制，沒有新推論。重新執行同一MATLAB邊界分割與SEM讀取，108次直徑獨立重擬合通過。原圖、R61、R128沿用相同固定權重既有邊界，再獨立重擬合全部432次直徑驗證，最大差異小於0.0001nm。

因此本表R129不是先前R135的W16數值，不能與W16的8.46nm形狀差距混稱同一輸出政策。尺度沿用舊SEM對位資料每5μm節距的換算，沒有在這次重新認證實物尺度。圖中僅去除各自圓心平移，不逐顆縮放或旋轉去除誤差。

## 九月九顆的位置檢查：尚未建立逐顆對應

完整視野比對的兩個主要候選為水平鏡像(相關0.963)、90度旋轉(0.936)。兩者都把舊SEM区域放在柱陣列與線條交界附近，均未覆蓋先前選的九顆。初步證據顯示它們是同片不同區域，不能把舊36顆隨意配成九月九顆。

規則陣列與線條容易產生高相關；另試特徵點配對得到不合理倍率，已拒絕接受為身份證據。尚未鎖定鏡像／旋轉及逐顆編號，field_match_provisional.png僅為候選位置示意，不是已驗證的SEM標註。

後續若要使用九月30次照片作逐顆SEM準確度，應先用可追溯方向或獨特標記確定上述SEM區域，再從已保存四組重建中追加量測那一區；不用重建930張，也不需更動另一項訓練。先前九顆仍可保留作重拍穩定性證據。

## 圖表

沿用已認可的簡潔輪廓風格：同尺度、各模型固定配色、重複觀測淡線；SEM另用黑線。sem_model_columns.png按方法分欄，historical_sem_36_overlays.png保留全部36顆。結果與原始P/V編號圖均置於results/sem_reference_followup。
'''
rp=R/'reports/R136_SEM_REFERENCE_RESULTS.md';rp.write_text(report,encoding='utf-8')
body='<h1>SEM逐顆對照</h1><p>以下為有歷史配對紀錄的36顆，非九月30次的九顆。</p>'+summary.round(3).to_html(index=False)
for name in ['sem_model_columns.png','historical_sem_36_overlays.png','SEM_P_V_pairing_map.png','field_match_provisional.png']:body+=f'<img src="{name}">'
body+='<pre>'+html.escape(report)+'</pre>'
(O/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>SEM comparison</title><style>body{max-width:1300px;margin:30px auto;padding:20px;font:17px/1.7 sans-serif}img{width:100%}pre{white-space:pre-wrap;font:inherit}td,th{padding:10px}</style>'+body,encoding='utf-8')
verification={'sem_files_verified':18,'copies_each':3,'physical_sample_same':'user confirmed','current_nine_to_sem_ids':'not established','feature_registration':'rejected: implausible scale','historical_pillar_comparisons':432,'independent_diameter_max_difference_nm':maxerr,'r129_policy':'original80/16 restored from stored float, no inference','via_model_scoring':'not performed; file identity and mapping only'}
(O/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
package=R/'output/R136_SEM_Reference_Comparison.zip'
with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
 for p in O.rglob('*'):
  if p.is_file() and not p.name.startswith('landmarks_flip'):z.write(p,p.relative_to(O))
 z.write(rp,rp.name)
with zipfile.ZipFile(package) as z:assert z.testzip() is None
print(pd.DataFrame(ci).to_string(index=False));print('432 refits passed; ZIP verified.')
