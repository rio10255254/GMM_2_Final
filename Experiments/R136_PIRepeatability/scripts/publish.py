from common import *
import numpy as np,pandas as pd

def main():
    t=ROOT/'results/tables';s=pd.read_csv(t/'summary.csv');r=pd.read_csv(t/'repeatability.csv');p=pd.read_csv(t/'paired_comparisons.csv');cal=load(t/'calibration.json');audit=load(ROOT/'results/verification.json');assert audit['complete']
    labels={'Raw':'原圖','R61':'R61 v16','R129':'R129'}
    def compact(view,kind):
        a=s[(s.view==view)&(s.kind==kind)].set_index('model');b=r[(r.view==view)&(r.kind==kind)].set_index('model');rows=[]
        for m in ['Raw','R61','R129']:
            v=a.loc[m];rows.append({'方法':labels[m],'掃描次數':int(v.scans),'平均有向誤差nm':v.bias_nm_mean,'平均絕對誤差nm':v.mae_nm_mean,'位置重複標準差均值nm':b.loc[m,'mean_position_sd_nm'],'最大絕對誤差nm':v.largest_error_nm})
        return pd.DataFrame(rows).to_markdown(index=False,floatfmt='.3f')
    texts=['# R136：30次重複位移的 PI 回授比較','',f'完成時間（UTC）：{now()}。全部930張原圖、R61與R129各930張重建及全部30次掃描均完成。沒有重新訓練或按分數挑選模型。','',
    '## 結論適用範圍','',
    '這是同一樣品、同次拍攝工作階段、20倍條件下的PI回授比較。原圖、R61 v16既有PSF-off設定與R129長訓練第8192次／原始80像素邊緣保留設定，使用相同影像座標與量法。R129四次更新及全圖光學／品質處理保留。此處誤差指影像讀值與PI回授之差，不把PI視為零不確定度的絕對真值。沒有據此更換正式模型。','',
    '## 全部30次：相鄰位移','',compact('nominal_all30','adjacent'),'',
    '## 全部30次：相對起點的位移','',compact('nominal_all30','start'),'',
    '以上使用名義0.1725μm/px。重複標準差先在每一相同位置的30次誤差間計算，再對30個位置取平均；不是單次掃描內30步的標準差。所有失敗／異常保留在明細；沒有挑較穩的30步。','',
    '## 前6次校正，後24次檢驗','',f'Basler acA2040-120um感光像素3.45μm，20倍名義尺度為0.1725μm/px。前6次原圖相對起點位移與PI Y回授共同估計得到{cal["estimated_um_per_px"]:.9f}μm/px，與名義值差{cal["nominal_relative_scale_difference_percent"]:.5f}%。同一尺度與方向用於三組後24次資料，模型結果沒有参与校正。這是以PI為參照的操作校正，並非獨立校正證書。','',
    '### 後24次相鄰位移','',compact('calibrated_late24','adjacent'),'',
    '### 後24次相對起點位移','',compact('calibrated_late24','start'),'',
    '## 改善是否一致','',
    '下表為後24次的逐掃描配對比較，負值表示前者平均絕對誤差較小。95%區間以完整掃描為重抽單位，10000次；另用連續3次掃描成組的方式檢查時間相關性。區間以固定校正參數計算，不能当作完整量測不確定度。', '']
    for kind in ['adjacent','start']:
        g=p[(p.view=='calibrated_late24')&(p.kind==kind)&(p.metric=='mae_nm')][['candidate','reference','candidate_minus_reference_mean_nm','ci95_low','ci95_high','block3_ci95_low','block3_ci95_high','improved_scans','worsened_scans']].copy()
        g.columns=['方法','比較對象','平均差nm','95%下限','95%上限','時間分組下限','時間分組上限','改善次數','退步次數'];texts += [('相鄰位移' if kind=='adjacent' else '相對起點位移'),'',g.to_markdown(index=False,floatfmt='.3f'),'']
    texts+=['## 量測與檢查','',
    '- 每個方法的900段相鄰位移及900筆非零起點相對位移全部計算。跨掃描回到起點不併入正常位移。',
    '- 整張2064×1544影像重建；浮點結果為正式量測來源，16位灰階PNG供檢視。另量化為8位的結果只作存圖敏感度比較。',
    '- 量測區域在模型結果出來之前依原圖固定。先由影像決定整數位移，再於共同重疊範圍估計細位移；讀取過程不使用PI位置作搜尋中心或校正影像。',
    '- 已知影像位移測試最大差0.001px；實拍正反方向一致。這是數值測試，並非奈米物理準確度認證。',
    '- 另有內縮區域、交界區域、原亮度讀法、8位存圖與逐步加總／直接起點位移比較。少量代表及最差案例以亮度配準的另一套計算核對，差異保留於independent_reader_checks.csv。',
    '- 前6次每掃描約20.5秒，後24次約26.4秒，中間約11分鐘空檔。兩段與隨時間變化均另報，不解讀為同一固定節奏。',
    '- 本資料主要沿PI Y方向移動。側向數值是影像中垂直於主移動方向的變化；沒有足夠獨立X方向行程來認證完整二維尺度／正負方向，不能把側向數字直接稱為已校正的PI X誤差。',
    '- R61歷史訓練包含其他SEM尺寸監督，本輪只比較此批PI位移表現，不借此宣稱完整訓練祖譜無重疊。','',
    '## 不確定度能說到哪裡','',
    '本輪提供重複拍攝的實測散布、平均表現與配對改善的可信範圍。PI校正證書、有效光學尺度的獨立不確定度及殘餘拍攝／回授時間差未提供，因此沒有捏造總合或擴展不確定度。位置誤差包含PI參考的波動，之後合併誤差來源時需避免重複計入。也不以30次平均後的較小不確定度冒充單次讀值表現。','',
    '## 圖表','']
    for name,caption in [('01_error_by_position','各位置的平均誤差及重拍散布'),('02_capture_comparison','30次逐次比較與後24次檢驗'),('03_paired_improvement','改善量及95%範圍'),('04_repeatability','相同位置的重複表現'),('05_sensitivity','量測區域、讀法與存圖的影響'),('06_measurement_regions','三組共同量測區域'),('07_reconstruction_examples','相同顯示條件下的重建範例')]:texts += [f'![{caption}](figures/{name}.png)','']
    texts+=['## 成果與重做入口','',
    '- results/tables/summary.csv：主要數值與平均值95%範圍。',
    '- results/tables/per_scan.csv：每次掃描表現；per_position.csv：每個位置的重拍散布；repeatability.csv：跨掃描重複程度。',
    '- results/tables/paired_comparisons.csv、repeatability_comparisons.csv：逐掃描配對改善及重複程度差異。',
    '- results/tables/all_measurements.csv：逐段明細，包含像素位移、PI回授差、換算與誤差。',
    '- results/tables/time_blocks.csv、time_drift.csv、sensitivity.csv、path_closure.csv、largest_errors.csv：時段、區域、存圖、累積一致性與最差情況。',
    '- config/plan.json：來源、兩個模型與全部影像對應。results/R61、results/R129：完整重建。',
    '- scripts/reconstruct.py、measure_all.py、analyze.py、figures.py、verify_results.py：可重新執行的流程。',
    '- results/verification.json：完整性與重算核對；原圖和兩個模型的內容未更動。','',
    '## 參考','',
    '- [Basler相機規格](https://www.baslerweb.com/en/shop/aca2040-120um/)',
    '- [NIST：重複觀測與平均值的不確定度](https://physics.nist.gov/cuu/Uncertainty/typea.html)',
    '- [NIST：其他不確定度來源](https://physics.nist.gov/cuu/Uncertainty/typeb.html)',
    '- [NIST：合併不確定度](https://physics.nist.gov/cuu/Uncertainty/combination.html)','']
    report=ROOT/'reports/R136_RESULTS.md';report.write_text('\n'.join(texts),encoding='utf-8')
    (ROOT/'README.md').write_text('# R136：30次位移重拍比較\n\n原圖、R61與R129全批重建與PI回授比較已完成。\n\n[完整結果與論文圖表](reports/R136_RESULTS.md)\n\n- 30組，每組31張；兩模型各930張重建。\n- 全30次名義尺度，以及前6次校正／後24次檢驗分開呈現。\n- 逐次、逐位置、最差情況與可信範圍皆保留。\n- 共享來源型，原照片及模型不搬動、不修改。未進行訓練或模型升級。\n- 分支codex/r136-pi-repeatability。\n',encoding='utf-8')
    save(ROOT/'results/published.json',dict(report=record(report),published_utc=now()))
    print(str(report),flush=True)
if __name__=='__main__':main()
