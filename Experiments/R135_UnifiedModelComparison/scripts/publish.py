from r135_common import *
import pandas as pd,re,shutil
LABEL={'Raw':'原圖','V42_old':'舊V42（資料重疊）','V42_clean':'乾淨重訓V42','R61':'R61','R128':'R128','R129_W16':'R129（邊緣16）','R134_P1':'R134 P1長訓練'}
ORDER=['Raw','V42_old','V42_clean','R61','R128','R129_W16','R134_P1']
def publish():
    state=load(ROOT/'results/status.json');done=[k for k in ORDER if (ROOT/f'results/{k}/complete.json').exists()];lines=['# R135：包含舊V42的統一比較','',f"目前：{state['phase']}，完成{len(done)}/7組。記錄時間{state['utc']}。",'',
    '比較舊V42 E120、乾淨重訓V42固定32epoch、R61 v16 PSF-off、R128 P_s1285002 step8192、R129長訓練／邊緣16、R134 P1長訓練，並列原圖。沒有新訓練、另挑最佳權重或模型升級。', '',
    '所有版本使用同一批201張完整相機影像、原先固定120對與全部194對同次拍攝配對；3次重新定位另列。正常SEM照片13/14/15、36顆，使用同一參考與保存精度。輪廓讀法與每柱的狀態重設相同；不直接搬用舊論文的分數。每模型保留已選定的原始推論／邊緣設定，所以這是實際系統比較，不是排除全部前後處理差異的純架構比較。', '',
    '**舊V42的分數完整保留，但已確認訓練資料有評估來源及尺寸答案重用。它可以顯示在這批影像上的能力，不能以此單獨證明未知影像的優勢，也不據此推斷動機。其餘模型同樣是在已用過的開發影像上比較，不是新確認集。**', '',
    '## 同一精度的SEM比較','', '| 模型 | 細形狀差距nm | 尺寸差距nm | 形狀相關↑ | 與SEM非圓起伏差距nm | 重建秒數 |','|---|---:|---:|---:|---:|---:|']
    for k in done:
        v=load(ROOT/f'results/{k}/complete.json');s=v['SEM'];sec=v['median_inference_seconds'];lines.append(f"| {LABEL[k]} | {s['centered_shape_nm']:.3f} | {s['diameter_error_nm']:.3f} | {s['correlation']:.4f} | {s['MZC_error_nm']:.3f} | {sec:.3f} |" if sec is not None else f"| {LABEL[k]} | {s['centered_shape_nm']:.3f} | {s['diameter_error_nm']:.3f} | {s['correlation']:.4f} | {s['MZC_error_nm']:.3f} | — |")
    for pop,label in [('locked120','固定120對'),('within_session194','完整194對')]:
        lines+=['','## '+label,'','| 模型 | 步距波動nm | 與設定步距平均差距nm | 九柱不一致nm | 側向偏移nm |','|---|---:|---:|---:|---:|']
        for k in done:
            t=pd.read_csv(ROOT/f'results/{k}/motion_summary.csv');r=t[(t.scope=='all_four_sequences')&(t.population==pop)].iloc[0];lines.append(f"| {LABEL[k]} | {r.step_sd_nm:.3f} | {r.mean_nominal_abs_error_nm:.3f} | {r.median_within_grid_sd_nm:.3f} | {r.median_cross_axis_abs_nm:.3f} |")
    lines+=['','數字均為這批重複觀察的摘要，未以單一加權總分選冠軍。設定步距不是独立實際位置真值，側向偏移亦不等於已知真誤差。尺寸與SEM有材料邊界對應限制；非圓程度是與樣本比較，不要求變成正圓。速度使用同一張完整影像、相同FP32設定、一次暖身三次計時，包含各模型必要的前後處理，不含存檔與量測。', '',
    '每張保存未取整的數值與看圖副本；量測使用前者。歷史浮點結果只在來源及雜湊吻合、代表整張重新推論相同時重用。全部中心另做獨立擬合與配對算式核對，失敗不刪除。原模型、旧完成記錄及144場景均不改動。']
    if state.get('error'):lines+=['','執行錯誤：','```',state['error'],'```']
    path=ROOT/'reports/R135_RESULTS.md';history=ROOT/'results/report_history'/str(time.time_ns());history.mkdir(parents=True)
    if path.exists():shutil.copy2(path,history/path.name)
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    text=f"R135：六個固定模型加原圖的同精度比較，完成{len(done)}/7組；舊V42含資料重疊標記，無訓練或升級。"
    p=REPO/'PROJECT_STATE.md';s=p.read_text(encoding='utf-8-sig');shutil.copy2(p,history/p.name);note='**R135：** '+text+' [結果](Experiments/R135_UnifiedModelComparison/reports/R135_RESULTS.md)'
    if '**R135：**' in s:s=re.sub(r'(?m)^\*\*R135：\*\*.*$',note,s,count=1)
    else:s=s.replace('### Open Research / Side Tracks','### Open Research / Side Tracks\n'+note,1)
    if '<!-- R135_START -->' in s:s=re.sub(r'<!-- R135_START -->.*?<!-- R135_END -->','<!-- R135_START -->\n'+note+'\n<!-- R135_END -->',s,flags=re.S)
    else:s=s.replace('## Full Current State / 完整現況','## Full Current State / 完整現況\n\n<!-- R135_START -->\n'+note+'\n<!-- R135_END -->',1)
    s=re.sub(r'(?m)^Last updated:.*$','Last updated: 2026-09-16（'+text+'）',s,count=1);p.write_text(s,encoding='utf-8')
    p=REPO/'Experiments/INDEX.md';s=p.read_text(encoding='utf-8-sig');entry=f'| R135 統一模型比較 | [結果](R135_UnifiedModelComparison/reports/R135_RESULTS.md) | {text} |'
    if '| R135 ' in s:s=re.sub(r'(?m)^\| R135 .*$',entry,s)
    else:s=s.replace('| R134 ',entry+'\n| R134 ',1)
    p.write_text(s,encoding='utf-8');p=REPO/'ESTIMATOR_POLICY.json';v=load(p);items=v['open_side_tracks'];x=next((x for x in items if x.get('candidate_id')=='r135_comparison'),None)
    if x is None:x=dict(candidate_id='r135_comparison',round='R135');items.insert(0,x)
    x.update(status=state['phase'],completed_methods=done,report='Experiments/R135_UnifiedModelComparison/reports/R135_RESULTS.md',training_updates=0,model_promoted=False,oldV42_overlap_disclosed=True);atomic(p,v)
if __name__=='__main__':publish()
