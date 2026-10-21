from pathlib import Path
import json,sys,psutil
R=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
    sys.stdout.reconfigure(encoding='utf-8');s=load(R/'results/status.json');tags=['Raw','V42_old','V42_clean','R61','R128','R129_W16','R134_P1'];done=[t for t in tags if (R/f'results/{t}/complete.json').exists()];print(f'六模型加原圖比較：{len(done)}/7組完成');print('已完成：'+', '.join(done))
    if s.get('current'):
        t=s['current'];p=R/f'results/{t}/status.json';print('目前：'+t)
        if p.exists():v=load(p);print(f"{v['phase']}，{v['frames']}/{v['total']}張")
    if s['phase']=='failed':print('已停止，錯誤：'+s.get('error',''))
    elif s['phase']=='complete':print('量測比較已完成；完整圖表交付：'+('完成' if (R/'results/delivery_complete.json').exists() else '整理中'))
    elif not psutil.pid_exists(s['pid']):print('執行程序已停止，不能視為仍在推進。')
    print('舊V42保留資料重疊標記；沒有訓練、改模型或自動採用。');print('結果：'+str(R/'reports/R135_RESULTS.md'))
if __name__=='__main__':main()
