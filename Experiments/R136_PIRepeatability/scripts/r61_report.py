from common import *
import pandas as pd,numpy as np

def main():
    out=ROOT/'results/r61_analysis';t=out/'tables';summary=pd.read_csv(t/'summary.csv');repeat=pd.read_csv(t/'repeatability.csv');paired=pd.read_csv(t/'paired_comparisons.csv');rp=pd.read_csv(t/'repeatability_comparisons.csv');sense=pd.read_csv(t/'sensitivity.csv');blocks=pd.read_csv(t/'time_blocks.csv');checks=pd.read_csv(t/'independent_reader_checks.csv');cal=load(t/'calibration.json');verification=load(out/'verification.json');assert verification['complete']
    rows=[]
    for view in ['nominal_all30','calibrated_late24']:
        for kind in ['adjacent','start']:
            a=summary[(summary.view==view)&(summary.kind==kind)].set_index('model');b=repeat[(repeat.view==view)&(repeat.kind==kind)].set_index('model');c=paired[(paired.view==view)&(paired.kind==kind)&(paired.metric=='mae_nm')].iloc[0];rc=rp[(rp.view==view)&(rp.kind==kind)].iloc[0]
            rows.append(dict(view=view,kind=kind,scans=int(a.loc['R61','scans']),raw_mae_nm=float(a.loc['Raw','mae_nm_mean']),r61_mae_nm=float(a.loc['R61','mae_nm_mean']),mae_change_percent=float((a.loc['R61','mae_nm_mean']/a.loc['Raw','mae_nm_mean']-1)*100),raw_repeatability_nm=float(b.loc['Raw','mean_position_sd_nm']),r61_repeatability_nm=float(b.loc['R61','mean_position_sd_nm']),raw_max_nm=float(a.loc['Raw','largest_error_nm']),r61_max_nm=float(a.loc['R61','largest_error_nm']),improved_scans=int(c.improved_scans),worsened_scans=int(c.worsened_scans),mae_delta_ci=[float(c.ci95_low),float(c.ci95_high)],mae_delta_block_ci=[float(c.block3_ci95_low),float(c.block3_ci95_high)],repeatability_delta_ci=[float(rc.ci95_low),float(rc.ci95_high)]))
    reader_pairs=pd.read_csv(t/'reader_sensitivity_paired.csv');reverse=reader_pairs[(reader_pairs.kind=='adjacent')&(reader_pairs.roi=='primary')&(reader_pairs.reader=='intensity')].iloc[0]
    save(out/'key_results.json',dict(completed_utc=now(),comparisons=rows,intensity_reader=dict(raw_mae_nm=float(reverse.reference_mae_nm),r61_mae_nm=float(reverse.candidate_mae_nm),r61_improved_scans=int(reverse.improved),r61_worsened_scans=int(reverse.worsened),difference_ci95=[float(reverse.ci95_low),float(reverse.ci95_high)]),independent_reader_max_difference_nm=float(checks.independent_along_difference_nm.abs().max()),coverage=dict(raw_frames=930,r61_frames=930,scans_each=30,adjacent_pairs_each=900,start_pairs_each=900)))
    def table(view):
        v=[r for r in rows if r['view']==view];data=[]
        for r in v:
            for model in ['raw','r61']:data.append({'位移讀法':'每一步' if r['kind']=='adjacent' else '相對起點','方法':'原圖' if model=='raw' else 'R61','平均絕對誤差nm':r[model+'_mae_nm'],'重拍散布nm':r[model+'_repeatability_nm'],'最大誤差nm':r[model+'_max_nm']})
        return pd.DataFrame(data).to_markdown(index=False,floatfmt='.3f')
    intensity=sense[(sense.view=='nominal_all30')&(sense.kind=='adjacent')&(sense.roi=='primary')&(sense.reader=='intensity')&(sense.precision=='full')].set_index('model')
    text=['# R136：R61與原圖的30次重拍統計','',
    '**本次結論：R61在原定的細節讀法下，改善相鄰短步位移，但相對起點的長距離誤差與重複程度沒有明確提升。換成直接亮度讀法後，原圖反而較準；改善與量法有關，不能寫成重建全面提高位移準確度。**','',
    f'直接亮度讀法的每步平均絕對誤差為原圖{intensity.loc["Raw","mae_nm"]:.3f}nm、R61 {intensity.loc["R61","mae_nm"]:.3f}nm，{int(reverse.worsened)}次R61皆較差。完整逐次核對見reader_sensitivity_paired.csv。這個反向結果與主結果同等保留。','',
    '本份先交付完整原圖／R61比較。R129仍另行執行，不把它尚未完成的結果混入排名。以下「誤差」均指與PI回授的差距，適用於本次100MF樣品、Basler acA2040-120um、20倍拍攝與指定影像讀法。','',
    '## 主要結果','',table('nominal_all30'),'',
    '共30次掃描、每次31張；原圖930張及R61重建930張。每種方法各有900段相鄰位移及900筆相對起點位移，全部納入。表中重拍散布是在每個相同位置計算30次誤差的標準差，再對30個位置取平均；不是一個掃描內不同步距的標準差。','']
    for r in rows[:2]:
        label='每一步位移' if r['kind']=='adjacent' else '相對起點位移';lo,hi=r['mae_delta_ci'];blo,bhi=r['mae_delta_block_ci'];direction='降低' if r['mae_change_percent']<0 else '增加'
        strength='兩種區間都低於零，支持本批資料中平均誤差較小。' if hi<0 and bhi<0 else ('兩種區間都高於零，顯示本批資料中平均誤差較大。' if lo>0 and blo>0 else '區間包含零或對時間分組敏感，不能把平均差距說成穩定改善。')
        text += [f'- **{label}**：平均絕對誤差{direction}{abs(r["mae_change_percent"]):.2f}%；30次中{r["improved_scans"]}次改善、{r["worsened_scans"]}次退步。R61減原圖的平均誤差差距95%區間為[{lo:.3f}, {hi:.3f}]nm；連續3次成組重抽為[{blo:.3f}, {bhi:.3f}]nm。{strength}']
    text += ['', '## 後24次的分開檢驗','',
    f'相機感光像素3.45μm，20倍名義尺度為0.1725μm/px。只用前6次原圖與PI估計方向及尺度，得到{cal["estimated_um_per_px"]:.9f}μm/px，再固定給兩種方法的後24次使用。模型結果不參與校正。', '',table('calibrated_late24'),'',
    '全30次名義尺度與後24次校正尺度是兩個不同範圍，不能混用其樣本數或把校正用的6次也算成獨立檢驗。此校正使用同一PI參考，並非獨立尺度校正證書。','',
    '## 所有主要指標的範圍','',
    '平均值的95%範圍與跨次波動都保留在summary.csv；逐次數值在per_scan.csv；各位置的30次平均、標準差、觀察到的最小／最大值在per_position.csv。平均表現的範圍不是下一次量測的保證範圍。完整掃描是重抽樣單位，不把900段相鄰位移當成900個獨立實驗。位置的重拍散布包含此次時間漂移，不等同純隨機雜訊。','',
    '下表呈現全30次主要指標（nm）。「單次內誤差波動」是掃描內30個位置誤差的標準差；與上表跨次重拍散布不同。','']
    statsrows=[]
    names={'bias_nm':'有向偏差','mae_nm':'平均絕對誤差','rmse_nm':'較重視大誤差的綜合值','error_sd_nm':'單次內誤差波動'}
    for _,r in summary[summary.view=='nominal_all30'].iterrows():
        for metric,name in names.items():statsrows.append({'位移':'每一步' if r.kind=='adjacent' else '相對起點','方法':r.model,'指標':name,'30次平均':r[metric+'_mean'],'次間標準差':r[metric+'_sd_between_scans'],'平均值95%下限':r[metric+'_ci95_low'],'平均值95%上限':r[metric+'_ci95_high']})
    compact=pd.DataFrame(statsrows);compact.to_csv(t/'readable_statistics.csv',index=False,encoding='utf-8-sig');text += [compact.to_markdown(index=False,floatfmt='.3f'),'','## 區域、讀法、時間及存圖的影響','']
    sens=[]
    for (kind,roi,reader,precision),g in sense[sense.view=='nominal_all30'].groupby(['kind','roi','reader','precision']):
        a=g.set_index('model');raw=a.loc['Raw','mae_nm'] if 'Raw' in a.index else sense[(sense.view=='nominal_all30')&(sense.kind==kind)&(sense.roi==roi)&(sense.reader==reader)&(sense.model=='Raw')&(sense.precision=='full')].iloc[0].mae_nm;r61=a.loc['R61','mae_nm']
        sens.append({'位移':kind,'區域':roi,'讀法':reader,'精度':precision,'原圖MAE_nm':raw,'R61_MAE_nm':r61,'差值nm':r61-raw})
    text += [pd.DataFrame(sens).to_markdown(index=False,floatfmt='.3f'),'',
    '8位列只表示把R61結果另存成一般灰階圖之後的讀值；原圖本來就是8位。正式量測保留R61完整計算精度。不同區域和讀法全部保留，不挑最有利者當主結果。','',
    f'另以不同的亮度配準方式核對代表及最差案例，與主讀法最大差{checks.independent_along_difference_nm.abs().max():.3f}nm。它使用不同空間權重與亮度模型，顯示讀法本身會影響數值；本報告的模型比較必須連同固定讀法解讀，不能把全部差異歸因於網路。逐案數值見independent_reader_checks.csv。','',
    '前6次每掃描約20.5秒，後24次約26.4秒，中間有約11分鐘空檔。各時段與順序趨勢保留在time_blocks.csv及time_drift.csv；直接起點位移與逐步加總的差別保留在path_closure.csv。','',
    blocks[(blocks.view=='nominal_all30')][['model','kind','time_block','mae_nm','error_sd_nm']].to_markdown(index=False,floatfmt='.3f'),'','## 實際做過的核對與限制','',
    '- R61全部930張完整精度結果均已讀回、確認尺寸和有效數值；代表性16位圖片存取一致。原圖、模型權重保持不變。',
    '- 從保存的像素位移重新換算誤差，再核對平均數；代表與最差案例重跑主讀法。',
    '- 初版細搜尋誤跳到重複格點的結果保存在readouts_v1。修正為影像粗對齊後的局部細搜尋，所有方法統一重算；未利用PI答案定位、未選擇性刪除壞結果。已知移動的數值測試最大差0.001像素，不代表物理準確度已達0.001像素。',
    '- 此資料主要沿PI Y移動，側向只報影像中垂直於主移動方向的變化，沒有獨立認證PI X的正負方向與尺度。',
    '- PI校正證書、有效光學尺度的獨立不確定度及殘餘拍攝時間差尚缺，因此不聲稱已得到完整量測不確定度。',
    '- 這是同一樣品與同次拍攝的表現；不代表不同樣品、不同天或不同倍率也必然改善。R61歷史資料來源的其他限制不因這次新比較而消失。','',
    '## 圖表','']
    for file,label in [('01_error_by_position','各位置平均誤差與30次散布'),('02_capture_comparison','逐次誤差比較'),('03_paired_improvement','改善量與95%範圍'),('04_repeatability','重複拍攝的波動'),('05_sensitivity','讀法與存圖敏感度'),('06_measurement_regions','共同量測範圍'),('07_reconstruction_examples','原圖與重建範例')]:text += [f'![{label}](r61_figures/{file}.png)','']
    text += ['## 成果入口','',
    '- [容易閱讀的主要統計表](../results/r61_analysis/tables/readable_statistics.csv)',
    '- [全部平均值與範圍](../results/r61_analysis/tables/summary.csv)',
    '- [30次逐次結果](../results/r61_analysis/tables/per_scan.csv)',
    '- [每個位置的重拍散布](../results/r61_analysis/tables/per_position.csv)',
    '- [逐段位移及PI對照](../results/r61_analysis/tables/all_measurements.csv)',
    '- [配對改善與時間分組範圍](../results/r61_analysis/tables/paired_comparisons.csv)',
    '- [改換讀法時的完整配對比較](../results/r61_analysis/tables/reader_sensitivity_paired.csv)',
    '- [核對紀錄](../results/r61_analysis/verification.json)','',
    '[相機規格](https://www.baslerweb.com/en/shop/aca2040-120um/)；[重複觀測的不確定度說明](https://physics.nist.gov/cuu/Uncertainty/typea.html)；[其他不確定度來源](https://physics.nist.gov/cuu/Uncertainty/typeb.html)。','']
    report=ROOT/'reports/R136_R61_RESULTS.md';report.write_text('\n'.join(text),encoding='utf-8');save(out/'published.json',dict(report=record(report),completed_utc=now()))
    print(json.dumps(rows,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
