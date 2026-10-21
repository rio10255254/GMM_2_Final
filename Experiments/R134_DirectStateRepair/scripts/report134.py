"""Source-backed R134 status publication; changes only the R134 current-index entries."""
from pathlib import Path
import sys,time,re,shutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rt import *
import pandas as pd

LABELS={
 'waiting_full201':'短訓練與12對位移驗證通過；201張完整影像檢查中',
 'not_admitted':'完整影像未通過事先條件；未啟動長訓練',
 'building_separate_package':'完整影像通過；正在製作這一代的獨立訓練包',
 'verifying_actual_package':'正在實測獨立訓練包；尚未啟動長訓練',
 'testing_manual_training_controls':'正在實際測試開始、暫停與續訓',
 'long_training_running':'獨立訓練包已通過實測；長訓練進行中',
 'user_paused':'長訓練已安全暫停',
 'final_full_comparison':'長訓練與包內定期驗證完成；最終201張完整影像比較中',
 'A_C_execution_complete_B_D_pending_calibration':'A/C比較、合格代別獨立長訓練與最終實拍比較完成；B/D仍待獨立校準',
 'failed':'執行遇到錯誤，已保留記錄；未宣告完成'
}

def publish():
    state=load(ROOT/'results/continuation/status.json');phase=state['phase'];label=LABELS[phase]
    dev=pd.read_csv(ROOT/'results/development_summary.csv');screen=load(ROOT/'results/screening_decision.json');motion=load(ROOT/'results/motion_screen.json');audit=load(ROOT/'results/motion_audit.json')
    report=ROOT/'reports/R134_RESULTS.md';lines=['# R134 執行結果與目前狀態','',label+'。','',f"狀態記錄時間：{state['updated_utc']}。模型仍屬研究版本；COMBO、V42及原R129的角色和檔案保留。",'',
    '## 已完成的比較','',
    'A為原R129的影像輸出設計；C為直接學習輸出影像的新設計。兩組都保留四次共享修正、實測光學提示及抗混疊上採樣，使用相同資料、順序、噪聲及誤差要求。兩個全新起點各做512次更新，共2048次。兩組新初始化皆將最後輸出層設為零；這不是歷史R129權重的重播。',
    '', 'C的初始影像等於原始輸入；光學提示仍能影響學習後的輸出。變更涵蓋整個影像狀態與輸出安排，因此不能將改善只歸因於最後一條公式。這是同樣短訓練的匹配比較，尚未證明勝過已長訓練的R129。', '',
    '| 設計／起點 | 生成開發影像誤差（灰階） | 清楚影像平均改動 | 清楚影像最差個別改動 |', '|---|---:|---:|---:|']
    for r in dev.itertuples():lines.append(f'| {r.arm}／{r.seed} | {r.dev_mae_gray:.4f} | {r.clean_identity_mae_gray:.4f} | {r.clean_max_gray:.4f} |')
    lines += ['', '原始輸入的生成開發誤差為4.97965。C相較A的生成影像誤差較高、清楚影像改動也较大，並非全面獲勝。清楚影像的事先條件是平均不超過1灰階，不代表每個例子都低於1。', '',
    '| C起點 | 相較同起點A：尺寸誤差變化 | 相較A：輪廓形狀誤差變化 |', '|---|---:|---:|']
    for seed in [1342001,1342002]:
        rows={r['metric']:r for r in screen['checks'] if r['seed']==seed and 'metric' in r}
        lines.append(f"| {seed} | {100*rows['diameter_error_nm']['paired_relative_change_vsA']:.2f}% | {100*rows['centered_shape_nm']['paired_relative_change_vsA']:.2f}% |")
    lines += ['', '尺寸與形狀變化先在同一顆、同一曝光內相減，再按曝光及36顆取中位數；不是兩個總中位數相減。兩個起點均通過事先短測条件。即便如此，C的實拍直徑總誤差中位數仍約81–82nm，不能宣稱已還原真實材料尺寸。', '',
    '## 連續影像','', '| 起點 | 位移量誤差中位數 C / A / 原始（nm） | 九柱一致性 C / A / 原始（nm） | 垂直方向偏移 C / A / 原始（nm） |','|---|---|---|---|']
    for seed in [1342001,1342002]:
        rows={r['metric']:r for r in motion['checks'] if r['seed']==seed};cells=[' / '.join(f'{rows[k][a]:.3f}' for a in ['C','A','Raw']) for k in ['median_nominal','median_within','median_cross']]
        lines.append('| '+str(seed)+' | '+' | '.join(cells)+' |')
    lines += ['',f"12對由原始影像既有清單預先固定，未按C結果挑選。全96張模型輸出、864個中心均有效；位移方向錯誤均為0。獨立重算864個中心最大差距 {audit['maximum_center_refit_difference_px']:.3g} 像素，四個模型各一張完整影像重建也完全重現。",'',
    '後續起點1342001由生成開發誤差預先選出，沒有因另一個起點的SEM較好而改選。全部201張使用原先固定120對與同次拍攝194對分開檢查；3對重新定位另列，不混入。門檻在結果前固定，不因未通過而放寬。']
    admission=ROOT/'results/long_admission.json'
    if admission.exists():
        a=load(admission);lines += ['',f"完整影像長訓練資格：{'通過' if a['eligible'] else '未通過'}。{a['reason']}"]
        full=ROOT/'results/full_motion/complete.json'
        if full.exists():
            v=load(full);lines += [f"完成201張／1809個中心，獨立重算{v['independent_center_refits']}個；重用24張經核對的相同輸出。"]
            for c in v['checks']:
                if not c['passed']:lines.append('- 未通過：'+str(c))
    lines += ['', '## 獨立訓練包與未完成工作','',
    '每個值得長訓練的模型代別必須單獨一包，內含模型、資料、起始權重、校準、固定驗證、說明與手動開始／暫停／續訓入口。只有完成201張篩選才製作R134 C的包，並實跑搬移、重建及暫停續訓檢查後，接續8192次長訓練。這是同代512次後的延續，並非从零長訓練。任何失敗均停止後續推進。', '',
    'B/D的新成像資料仍缺獨立材料邊界與光學對應校準，目前未執行；25張既有光學校準照無法單獨補足這件事。已重算既有間距校準，結果一致，但不是材料邊界已認證。幾何要求的原型另有30種擾動及10個不變例子的檢查，尚未加入這次A/C訓練。初始原型失敗記錄保留。', '',
    '所有實拍／SEM均為既有開發資料，不是未看過的最終驗證；舊144場景不再作未知驗證。此輪不宣告取代論文模型，也不宣告已解決實體尺寸問題。', '',
    '實際進度：`results/continuation/status.json`；完整影像進度：`results/full_motion/status.json`。包建立後的位置與實測結果另見`results/package_built.json`及`results/continuation/`。']
    if state.get('package'):lines+=['', '目前獨立包位置：`'+state['package']+'`。']
    final=ROOT/'results/long_final_comparison/complete.json'
    if final.exists():
        summary=pd.read_csv(ROOT/'results/long_final_comparison/summary.csv');summary=summary[summary.scope=='all_four_sequences']
        lines+=['','## 長訓練後的完整影像比較','','| 方法 | 配對範圍 | 位移量平均誤差 | 九柱一致性中位數 | 垂直偏移中位數 |','|---|---|---:|---:|---:|']
        for r in summary.itertuples():lines.append(f'| {r.method} | {r.population} | {r.mean_nominal_abs_error_nm:.3f} | {r.median_within_grid_sd_nm:.3f} | {r.median_cross_axis_abs_nm:.3f} |')
        lines+=['','以上單位均為nm；全部結果及最差例子保留於long_final_comparison。長訓練完成不代表所有指標更好，也不自動採用模型。']
    if state.get('error'):lines+=['', '執行錯誤原文：','```',state['error'],'```']
    repo=ROOT.parent.parent;snapshot=ROOT/'results/index_history'/str(time.time_ns());snapshot.mkdir(parents=True)
    for p in [report,repo/'PROJECT_STATE.md',repo/'ESTIMATOR_POLICY.json',repo/'Experiments/INDEX.md']:
        if p.exists():shutil.copy2(p,snapshot/p.name)
    report.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    p=repo/'ESTIMATOR_POLICY.json';policy=load(p);item=next(x for x in policy['open_side_tracks'] if x.get('candidate_id')=='R134_direct_state');item.update(status=phase,report=report.relative_to(repo).as_posix(),completed_short_updates=2048,B_D_complete=False,model_promoted=False);atomic(p,policy)
    p=repo/'PROJECT_STATE.md';text=p.read_text(encoding='utf-8-sig');text=re.sub(r'(?m)^Last updated:.*$',f'Last updated: 2026-09-15（R134：{label}）',text,count=1)
    text=re.sub(r'\*\*R134執行中（2026-09-15）：\*\*.*?(?= \*\*R133)',f'**R134執行中（2026-09-15）：** {label}；[當前結果](Experiments/R134_DirectStateRepair/reports/R134_RESULTS.md)。A/C共2048短訓練更新完成，SEM與12對位移條件通過；B/D仍待獨立校準，原模型保留。',text,count=1)
    start=text.index('### R134 ');end=text.index('### R133 ',start)
    text=text[:start]+f'### R134 direct-state repair (2026-09-15)\n\n{label}。[Canonical results](Experiments/R134_DirectStateRepair/reports/R134_RESULTS.md). Two fresh matched seeds × A/C ×512updates complete; same source data, parameter initialization, input order/noise/loss. Both C seeds pass SEM and12pair motion screening,864independent motion center fits and4fullfield replays. Dev-selected Cseed1342001 proceeds to full201. A/C changed whole image-state/output semantics; C has higher synthetic dev error and clean-image disturbance than A. Real size error remains81–82nm. B/D independent material calibration unqualified and unexecuted; no historical holdout reuse or default promotion. Every admitted longtraininggeneration receives an isolated manual package and actual package/resume validation before continuation. Live state: Experiments/R134_DirectStateRepair/results/continuation/status.json.\n\n'+text[end:];p.write_text(text,encoding='utf-8')
    p=repo/'Experiments/INDEX.md';text=p.read_text(encoding='utf-8-sig');text=re.sub(r'(?m)^\| R134 .*$',f'| R134 直接影像狀態修正 | [當前結果](R134_DirectStateRepair/reports/R134_RESULTS.md) | {label}；B/D待校準；未升級 |',text);p.write_text(text,encoding='utf-8')

if __name__=='__main__':publish()
