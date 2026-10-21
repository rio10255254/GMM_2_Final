"""Read-only status for the precision revision."""
from pathlib import Path
import json,sys,psutil
P=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
    sys.stdout.reconfigure(encoding='utf-8');s=load(P/'results/status.json');labels={'qualifying':'保留精度的完整驗證中','not_admitted':'新精度流程未通過條件，未長訓練','building_package':'驗證通過，正在製作獨立包','package_preflight':'獨立包實測中','manual_control_test':'正在實測開始、暫停及續訓','long_training':'長訓練中','paused':'長訓練已暫停','final_comparison':'長訓練完成，最後完整影像比較中','complete':'長訓練及最後比較完成，尚未自動採用','failed':'執行遇到錯誤，請查看記錄'};print('R134 P1：'+labels[s['phase']])
    q=P/'results/motion/status.json'
    if q.exists():v=load(q);print(f"目前組別：{v['tag']}，{v['frames']} / {v['total']} 張；所有對照合計 {v['total_completed']} / {v['total_planned']} 張")
    q=P/'results/sem/complete.json'
    if q.exists():v=load(q);print('相同精度的SEM比較：'+('通過' if v['passed'] else '未通過'))
    q=P/'results/package_built.json'
    if q.exists():
        package=Path(load(q)['path']);print('獨立訓練包：'+str(package));r=package/'results/training/r134p_long_01/status.json'
        if r.exists():v=load(r);print(f"長訓練 {v['completed_updates']} / {v['planned_updates']} 次；{v['status']}")
    else:print('尚未建立長訓練包；需通過整套比較後才會建立並實測。')
    if s.get('error'):print(s['error'])
    if not psutil.pid_exists(s['pid']) and s['phase'] not in ['complete','failed','paused','not_admitted']:print('注意：後續執行程序已停止，目前不能視為仍在自動推進。')
    print('原256階未通過判定保留；本頁顯示另存的新精度驗證。')
    print('說明：'+str(P.parent/'reports/R134_PRECISION_REVALIDATION.md'))
if __name__=='__main__':main()
