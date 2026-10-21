from pathlib import Path
import json,html,zipfile
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];B=R/'results/sem_corner9';T=B/'analysis/tables';models=['Raw','R61','R129','R128'];colors=['#777777','#df8636','#2088aa','#9356ad']
summary=pd.read_csv(T/'summary.csv');repeat=pd.read_csv(T/'repeatability.csv');rows=[]
for kind in ['adjacent','start']:
 for model in models:
  x=summary[(summary.view=='nominal_all30')&(summary.kind==kind)&(summary.model==model)].iloc[0];q=repeat[(repeat.view=='nominal_all30')&(repeat.kind==kind)&(repeat.model==model)].iloc[0]
  rows.append(dict(model=model,kind=kind,mae_nm=x.mae_nm_mean,bias_nm=x.bias_nm_mean,repeatability_nm=q.mean_position_sd_nm,maximum_error_nm=x.largest_error_nm))
d=pd.DataFrame(rows);d.to_csv(B/'displacement_summary.csv',index=False)
old=pd.read_csv(R/'results/lsc/four_model_analysis/tables/readable_lsc_summary.csv').query("view=='nominal_all30'");pd.merge(d,old[['model','kind','mae_nm','repeatability_nm','maximum_error_nm']],on=['model','kind'],suffixes=('_corner9','_previous9')).to_csv(B/'old_vs_new_targets.csv',index=False)
fig,axes=plt.subplots(1,2,figsize=(11,4))
for ax,kind,title in zip(axes,['adjacent','start'],['Short-step PI difference','Start-relative PI difference']):
 g=d[d.kind==kind].set_index('model').loc[models];ax.bar(models,g.mae_nm,color=colors);ax.set_title(title);ax.set_ylabel('Mean absolute difference (nm)')
fig.tight_layout();fig.savefig(B/'displacement_comparison.png',dpi=180)
shape=pd.read_csv(B/'shape_size/summary.csv');sem=pd.read_csv(B/'sem_group_size_comparison.csv');v=json.loads((B/'analysis/verification.json').read_text());assert v['independent_circle_fits']==33480
def md(df):return df.round(3).to_markdown(index=False)
report='''# R136 十字中心附近、SEM涵蓋九顆：四組重算

2026-09-19。原圖／R61／R129／R128，全部30次、930張、每張9顆已完成。使用既有浮點重建，不重新訓練、不重新推論，未干涉另一項訓練。新結果獨立保存，原結果不覆寫。

## 回答先前的資料問題

先前這批30次的位移、重拍穩定性與R129不確定度評估，均使用畫面內另一組九顆。它們有完整照片與同步PI回授，但沒有完成對應SEM的逐顆真值確認。因此其重拍波動及相對PI的位移比較有資料依據；不能當成同九顆的尺寸／形狀準確度證據。舊36顆SEM實驗本身有歷史配對，與此問題不同。

若要把位移、尺寸、輪廓與SEM串在同九顆上，應先完成SEM位置核對；之前未先做好這一步。本次固定改選靠近十字交界的3×3九顆後，再計算結果，未按模型成績挑顆粒。

## 新九顆位置與對應範圍

原图第一張座標約x1592／1621／1650，y726／755／784；是柱陣列最接近右下十字交界的完整3×3。930張、8370個Raw種子追蹤完整，局部重定位相對原Raw全域位移預測最大偏差小於0.636像素；四方法共用同一追蹤，不以PI或重建結果選顆粒。

舊SEM對應集合為22、23、24、28、29、30、34、35、36。兩個主要整圖方向候選皆得到同一集合，最近圓心最大位置差1.285像素；但鏡像／90度方向尚未完全定案。集合平均尺寸不受九顆排列影響；逐顆尺寸與方向輪廓另列兩種配對敏感度，不以較好分數決定配法。

## 位移重算

單位nm。adjacent為相鄰短步，start為相對起點。mae為相對PI平均絕對差，repeatability為固定步位置跨30次的平均樣本標準差，maximum_error為觀察到的最大絕對PI差。

'''+md(d)+'''

名義0.1725 μm/px，位移方向只由前六次Raw與PI決定；另保存後24次的名義尺度及PI校準尺度結果。PI回授是位移參考，不等同已認證無誤差真值。原／新九顆同算法對照表為old_vs_new_targets.csv。

## 尺寸與形狀重拍

直徑以LSC半徑兩倍計；固定位置固定顆粒的30次樣本變異數先平均再開根號。形狀先移除圓心與每條輪廓平均半徑，再固定720角度比較；來源64個邊界點，插值不增加物理解析度。重拍波動越小代表越一致，不能單獨代表越接近實物。

'''+md(shape[['model','diameter_mean_nm','diameter_repeat_sd_nm','shape_repeat_sd_nm','diameter_repeat_absmax_nm']])+'''

## 使用SEM九顆的尺寸比較

以下為九顆集合平均直徑的有號差，正值代表光學量到的平均尺寸較SEM大；不是逐顆平均絕對誤差。SEM参考用既有P柱边界，沒有拿V孔代替。SEM ID28局部邊界有不規則，完整保留，尚未認證為實物缺陷。像素尺度與SEM判邊不確定度尚未合入，不能宣稱完整絕對準確度認證。

'''+md(sem)+'''

sem_mapping_sensitivity_summary.csv保留兩個方向下的逐顆直徑差、含尺寸輪廓差、去平均尺寸的形狀差；两張SEM輪廓圖均清楚標示方向候選。它們不作已確定身份的主結論。

## R129不確定度重新計算

r129_uncertainty/r129_uncertainty_by_position.csv已重算60個固定步／位置的30次觀察波動、含時間變化的平均值分量與範圍。沿用原分析中考慮時間相關的方法；尺度、PI校正與跨日條件的未知分量保留未知，不把它們設為零。這些是本次拍攝的分量，並非完整總不確定度。

## 核對與圖表

四組各8370圓心，共33480獨立圓擬合、逐顆位移、PI算式和影像重播通過原有核對。追蹤930張全數成功、沒有剔除最差結果。輪廓圖沿用固定配色、同尺度、30次淡線；SEM參考黑線，方向未定明示。

selected_nine.png位置圖；shape_size/figures/thirty_repeat_contours.png重拍輪廓；displacement_comparison.png位移比較；sem_contours_candidate1.png及candidate2.png為兩個候選SEM對照。詳細資料、來源與核對表均位於results/sem_corner9。
'''
rp=R/'reports/R136_SEM_CORNER9_RESULTS.md';rp.write_text(report,encoding='utf-8')
body='<h1>十字交界九顆：四組完整重算</h1><p>30次重拍；九顆集合與SEM區域對應。逐顆影像方向仍列兩種候選。</p>'+d.round(3).to_html(index=False)
for p in ['selected_nine.png','displacement_comparison.png','shape_size/figures/thirty_repeat_contours.png','shape_size/figures/repeatability.png','sem_contours_candidate1.png','sem_contours_candidate2.png']:body+=f'<img src="{p}">'
body+='<pre>'+html.escape(report)+'</pre>'
(B/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Corner nine results</title><style>body{max-width:1250px;margin:30px auto;font:17px/1.7 sans-serif;padding:20px}img{width:100%}pre{white-space:pre-wrap;font:inherit}td,th{padding:8px;border:1px solid #bbb}</style>'+body,encoding='utf-8')
print(d.to_string(index=False));print(shape[['model','diameter_repeat_sd_nm','shape_repeat_sd_nm']].to_string(index=False));print(sem.to_string(index=False))
