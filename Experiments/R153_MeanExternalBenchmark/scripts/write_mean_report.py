"""Produce paper-ready mean/median findings using only public method names."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from study import *
import numpy as np
import pandas as pd


def table(columns,rows):
    def fmt(v):
        if isinstance(v,(float,np.floating)):return f'{v:.6f}'
        return str(v)
    return '| '+' | '.join(columns)+' |\n| '+' | '.join(['---']*len(columns))+' |\n'+'\n'.join('| '+' | '.join(fmt(v) for v in row)+' |' for row in rows)+'\n'


def main():
    result=read(ROOT/'results/analysis/mean_median_complete.json')
    assert result['status']=='passed'
    rows=result['summary'];lookup={(r['method'],r['aggregation'],r['kind']):r for r in rows}
    intervals=pd.read_csv(PUBLIC/'data/mean_median_paired_intervals.csv')
    paired=pd.read_csv(PUBLIC/'data/paired_30_scan_comparison.csv')
    influence=pd.read_csv(PUBLIC/'data/pillar_influence_diagnostics.csv')
    perstep=pd.read_csv(PUBLIC/'data/nine_pillar_dispersion.csv')
    comparison={r['aggregation']:r for r in result['comparison']}
    mean_raw=lookup['RAW','mean','adjacent'];mean_mosr=lookup['MOSR','mean','adjacent']
    sd_gain=100*(1-mean_mosr['pooled_within_scan_sd_nm']/mean_raw['pooled_within_scan_sd_nm'])
    mae_gain=100*(1-mean_mosr['mae_nm']/mean_raw['mae_nm'])
    text=f'''# 九顆柱體平均位移與中位數位移比較

本報告回應口試委員對九顆柱體位移彙整方式的建議。主要分析改為九個二維位移向量的算術平均，再投影至固定移動方向；既有中位數結果作敏感度比較。

平均數版本的RAW與MOSR掃描內步距合併標準差分別為 **{mean_raw['pooled_within_scan_sd_nm']:.6f} nm** 與 **{mean_mosr['pooled_within_scan_sd_nm']:.6f} nm**，降低 **{sd_gain:.3f}%**。MOSR仍在 **{comparison['mean']['improved_scans']}/30** 次掃描中改善，逐次改善範圍為 **{comparison['mean']['minimum_scan_improvement_percent']:.3f}%–{comparison['mean']['maximum_scan_improvement_percent']:.3f}%**。相鄰位移的PI平均絕對差為 **{mean_raw['mae_nm']:.6f} nm** 與 **{mean_mosr['mae_nm']:.6f} nm**，降低 **{mae_gain:.3f}%**。

因此，主要結論維持，但論文應使用新數字；不得沿用中位數版本的52.3%步距改善與51.0%相鄰PI平均絕對差改善。

## 固定資料與舊結果重現

使用正式30次掃描、每次31張、固定九顆的保存LSC圓心，共每方法8370筆圓心。逐筆讀取的圓心與既有完整紀錄相同；原始PI回授檔、圓心、輪廓與固定設定共154個檔案核對通過。沒有重新擬合光學LSC、改動輪廓、重新推論MOSR或調整資料。

尺度為0.1725 μm/pixel，固定移動方向為u=(−0.9998766245119538, 0.015707824629190823)。PI使用同一影格對的Y方向回授差。原中位數相鄰與相對起點共3600筆位移均重現，最大差為{result['published_median_max_difference_um']:.3g} μm，屬浮點讀寫尾位。

## 計算定義

令r為掃描、j為位置、k為柱體；c為保存圓心。相鄰步距的九顆位移向量為Δc(r,j,k)=c(r,j,k)−c(r,j−1,k)。

新方法：m_mean(r,j)=(1/9)Σ_k Δc(r,j,k)，d_mean(r,j)=172.5 uᵀm_mean(r,j)，單位nm。

舊方法：m_median(r,j)=[median_k Δc_x, median_k Δc_y]，d_median(r,j)=172.5 uᵀm_median(r,j)。此處是分量中位數，並非九個投影值的中位數。

每次掃描的主要值為s_r=√[Σ_j(d(r,j)−d̄_r)²/29]，30次合併值為s_pooled=√mean_r(s_r²)。不以900步直接混算，不除以√30。30個s_r的算術平均與其樣本標準差另列。

相對起點使用c(r,j,k)−c(r,0,k)直接計算。平均與投影都是線性運算，因此平均版本的逐步累加與直接相對起點在本資料內相差小於2×10⁻¹¹ nm；主要輸出仍保存直接相對起點結果。這個等價關係不適用於分量中位數。

## 相鄰步距全部摘要

'''
    fields=['pooled_within_scan_sd_nm','mean_scan_sd_nm','sd_of_scan_sds_nm','mae_nm','rmse_nm','signed_bias_nm','maximum_absolute_error_nm']
    text+=table(['方法','九顆彙整','合併SD nm','30個SD平均 nm','30個SD之SD nm','PI MAE nm','PI RMSE nm','PI有號偏差 nm','PI最大絕對差 nm'],
                [[m,a,*[lookup[m,a,'adjacent'][f] for f in fields]] for a in ('mean','median') for m in ('RAW','MOSR')])
    text+='\n![平均向量版本之逐次掃描步距標準差](figures/mean_within_scan_sd.png)\n\n每點為一次掃描30步的樣本SD；水平灰帶是30個s_r的算術平均±這30個數值的樣本SD，並非每點的估計區間。\n'
    text+='\n## 全部30次掃描\n\n'
    fields=['RAW_mean_SD_nm','MOSR_mean_SD_nm','RAW_median_SD_nm','MOSR_median_SD_nm','mean_SD_improvement_percent']
    text+=table(['掃描','RAW平均版SD','MOSR平均版SD','RAW中位版SD','MOSR中位版SD','平均版MOSR降低%'],[[int(r['scan']),*[r[f] for f in fields]] for r in paired.to_dict('records')])
    text+='\n## 相對起點與终點\n\n'
    fields=['mae_nm','rmse_nm','signed_bias_nm','maximum_absolute_error_nm']
    text+=table(['方法','九顆彙整','相對起點MAE nm','RMSE nm','有號偏差 nm','最大絕對差 nm'],[[m,a,*[lookup[m,a,'start'][f] for f in fields]] for a in ('mean','median') for m in ('RAW','MOSR')])
    text+='\n'
    text+=table(['方法','九顆彙整','終點PI MAE nm','終點RMSE nm','終點有號偏差 nm','終點最大絕對差 nm','終點誤差跨掃描SD nm'],
                [[r['method'],r['aggregation'],r['mae_nm'],r['rmse_nm'],r['signed_bias_nm'],r['maximum_absolute_error_nm'],r['error_sd_nm']] for r in result['endpoints']])
    text+='\n平均版本的終點平均有號差為RAW +41.726 nm、MOSR +42.678 nm。短步改善不能延伸解讀為終點偏差同步改善。\n'
    text+='\n## 完整掃描配對區間\n\n抽樣單位是整趟掃描，兩方法使用相同30個掃描抽樣名單；20000次，固定種子20261002。九顆、900步及輪廓方向不作獨立重複實驗。差值為MOSR減RAW。\n\n'
    focus=intervals[(intervals.comparison=='MOSR minus RAW')&(intervals.aggregation=='mean')&intervals.metric.isin(['pooled_within_scan_sd_nm','adjacent_mae','start_mae','endpoint_bias'])]
    labels={'pooled_within_scan_sd_nm':'掃描內合併SD','adjacent_mae':'相鄰PI MAE','start_mae':'起點相對PI MAE','endpoint_bias':'終點有號PI差'}
    text+=table(['指標','MOSR−RAW nm','95%下界 nm','95%上界 nm'],[[labels[r.metric],r.difference,r.paired_CI95_low,r.paired_CI95_high] for r in focus.itertuples()])
    text+='\n## 平均與中位數差異來自哪裡\n\n![逐次掃描的平均／中位數敏感度](figures/mean_median_sensitivity.png)\n\n'
    for method in ('RAW','MOSR'):
        delta=paired[f'{method}_mean_minus_median_SD_nm']
        text+=f'{method}改用平均後，{int((delta<0).sum())}/30次掃描的SD降低；{int((delta>0).sum())}/30次增加。以下列出SD改變幅度最大的五次掃描，不因此排除任何資料。\n\n'
        selected=paired.iloc[np.argsort(-np.abs(delta.to_numpy()))[:5]]
        text+=table(['掃描','RAW檔案中的趟次ID','中位數SD nm','平均數SD nm','平均−中位數SD nm'],[[int(r['scan']),r['run'],r[f'{method}_median_SD_nm'],r[f'{method}_mean_SD_nm'],r[f'{method}_mean_minus_median_SD_nm']] for r in selected.to_dict('records')])
        text+='\n'
    text+='每一步中，第k顆對「平均位移−分量中位位移」的貢獻定義為(d_k−d_median)/9；九顆貢獻加總恰等於兩種彙整結果之差。另計算暫時不納入一顆時平均值的變化，只作影響分析，正式結果仍用全部九顆。\n\n'
    text+=table(['方法','柱體','平均絕對貢獻 nm','平均有號貢獻 nm','暫不納入該顆時的平均絕對變化 nm'],
                [[r.method,int(r.pillar),r.mean_abs_contribution_to_mean_median_nm,r.mean_signed_contribution_nm,r.mean_abs_leave_one_out_change_nm] for r in influence.itertuples()])
    text+='\nRAW九顆的平均絕對貢獻約1.85–1.98 nm，MOSR約0.67–0.74 nm，沒有單一柱體獨占差異。RAW的最大平均貢獻來自第3顆，MOSR來自第5顆；這些名次只是本批影響大小，不能據此斷定物體有污染、缺陷或量測錯誤。\n\n'
    large=perstep.iloc[np.argsort(-np.abs(perstep.mean_minus_component_median_nm.to_numpy()))[:12]]
    text+=table(['方法','掃描','步','平均−中位數 nm','九顆沿方向SD nm','九顆範圍 nm'],[[r.method,int(r.scan),int(r.step),r.mean_minus_component_median_nm,r.along_sample_sd_nm,r.along_range_nm] for r in large.itertuples()])
    text+='\n## 同一步九顆的離散與分布診斷\n\n沿方向与垂直方向分別計算九顆位移的樣本SD；二維離散量為√[Σ_k‖Δc_k−平均Δc‖²/(9−1)]×172.5。合併先對900個步驟的變異數取平均，再開根號。這些值描述同一步九顆的分散，不是主要的單次掃描30步SD。\n\n'
    text+=table(['方法','沿方向離散 nm','垂直方向離散 nm','二維離散 nm','含診斷旗標步數/900','旗標觀測數/8100','|偏態|中位數','|偏態|>1的步數'],
                [[d['method'],d['pooled_along_pillar_dispersion_nm'],d['pooled_transverse_pillar_dispersion_nm'],d['pooled_vector_pillar_scatter_nm'],d['steps_with_any_MAD_flag'],d['MAD_flagged_pillar_observations'],d['median_absolute_step_skewness'],d['steps_abs_skewness_over_1']] for d in result['diagnostics']])
    text+='''
診斷旗標為同一步九顆的|d_k−median(d)|/[1.4826 MAD(d)]>3.5。每一步只有九顆，這個旗標與樣本偏態都不等於已證明的壞點或常態性檢定；它們亦不是互相獨立的8100次實驗。全部旗標點都保留。

資料並非完全沒有偏態或較遠的讀值，因此不宜以「完全無離群」作為使用平均數的理由。較直接的依據是：研究欲估計固定九顆的共同平移，算術平均保留全部位移向量資訊；在同一保存資料上，平均版本的主要SD及PI MAE均較低，而且MOSR相對RAW的30/30改善不依賴彙整選擇。中位數作為對較大偏離值較不敏感的補充，兩者均完整報告。

平均數版本也不意味尺寸或完整輪廓變得更準確。此次未改圓心、半徑或邊界點，輪廓重複性、直徑重複性及SEM尺寸／輪廓比較維持原數值，後續外部模型以相同規則比較。

## 可用於論文的敘述

為依一致的向量定義估計固定九顆柱體之共同平移，本研究先逐顆計算指定影格對的LSC圓心差，再對九個二維位移向量取算術平均，最後投影至預先固定的移動方向。全部柱體與步距均納入分析，並以分量中位數作敏感度比較。平均彙整下，RAW與MOSR之掃描內步距合併標準差分別為8.781 nm與4.273 nm，降低51.3%，且30次掃描均改善；各次改善為34.6%至67.2%。相鄰位移相對PI回授的平均絕對差由6.969 nm降至3.598 nm，降低48.4%。兩種彙整方式均支持MOSR改善本批資料的短步量測表現，惟改善百分比與絕對數值應依平均版本更新。

## 可重算資料

data/提供全部30次掃描、7200筆彙整位移（兩方法×兩彙整×兩位移定義×900）、16200筆逐顆相鄰位移、逐步九顆離散、逐顆影響、終點摘要與完整掃描配對區間。任何旗標或暫不納入單顆的結果均只屬診斷；主分析使用全30次、全九顆、全30步。
'''
    text=text.replace('终點','終點').replace('方向与','方向與')
    assert not __import__('re').search(r'\bR(?:140|148|150|152|153)\b',text)
    (PUBLIC/'MEAN_MEDIAN_RESULTS.md').write_text(text,encoding='utf-8')
    print('Mean/median report complete. New primary SD improvement:',sd_gain,'%; PI MAE improvement:',mae_gain,flush=True)


if __name__=='__main__':main()
