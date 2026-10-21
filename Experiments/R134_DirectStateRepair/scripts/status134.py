"""Read-only human status for the active execution and any admitted package."""
from pathlib import Path
import json,sys
import psutil
ROOT=Path(__file__).resolve().parents[1]
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def main():
    precise=ROOT/'precision_revision/status.py'
    if precise.exists() and (ROOT/'precision_revision/results/status.json').exists():
        import runpy
        runpy.run_path(str(precise),run_name='__main__');return
    sys.stdout.reconfigure(encoding='utf-8')
    s=read(ROOT/'results/continuation/status.json')
    labels={'waiting_full201':'短訓練及初步實拍比較通過，完整影像檢查中','not_admitted':'完整檢查未通過；沒有開始長訓練','building_separate_package':'正在製作本代獨立訓練包','verifying_actual_package':'正在實測獨立訓練包','testing_manual_training_controls':'正在測試開始、暫停及續訓','long_training_running':'長訓練中','user_paused':'已安全暫停','final_full_comparison':'長訓練完成，正在做最終完整影像比較','A_C_execution_complete_B_D_pending_calibration':'本次可執行的訓練與實拍比較已完成；新校準資料部分尚未完成','failed':'執行失敗，詳見下列記錄'}
    print('R134：'+labels[s['phase']])
    p=ROOT/'results/full_motion/status.json'
    if p.exists():v=read(p);print(f"長訓練前完整影像：{v['frames']} / {v['total']} 張")
    p=ROOT/'results/package_built.json'
    if p.exists():
        pkg=Path(read(p)['path']);print('本代獨立包：'+str(pkg));t=pkg/'results/training/r134_long_01/status.json'
        if t.exists():v=read(t);print(f"長訓練：{v['completed_updates']} / {v['planned_updates']} 次，狀態 {v['status']}")
    else:print('獨立訓練包尚未建立；需先通過完整影像條件。')
    if not psutil.pid_exists(s['pid']) and s['phase'] not in ['failed','not_admitted','user_paused','A_C_execution_complete_B_D_pending_calibration']:print('注意：後續執行程序已停止，目前不能視為仍在自動推進。')
    if s.get('error'):print(s['error'])
    print('新成像資料仍待獨立配對校準；目前未執行該部分。')
    print('詳細結果：'+str(ROOT/'reports/R134_RESULTS.md'))
if __name__=='__main__':main()
