"""Visible read-only progress display for R140v2. Ctrl+C stops this display only."""
from pathlib import Path
import json,time,datetime
ROOT=Path(__file__).resolve().parents[1]
def load(path):
 try:return json.loads(path.read_text(encoding='utf-8-sig'))
 except (FileNotFoundError,json.JSONDecodeError,PermissionError):return None
print('R140v2 前景監控：此視窗只顯示狀態；關閉它不會停止背景訓練。',flush=True)
last=None
while True:
 pipeline=load(ROOT/'runs/pipeline_status.json') or {}
 status=load(ROOT/'runs/formal_8192/status.json') or {}
 reconstruction=load(ROOT/'results/reconstruction_status.json') or {}
 fail=load(ROOT/'runs/pipeline_failure.json')
 stamp=datetime.datetime.now().strftime('%H:%M:%S')
 if fail:
  message=f'{stamp} 失敗：{str(fail.get("error",""))[-600:]}'
 elif pipeline.get('state')=='complete':
  message=f'{stamp} 全流程完成：8192次訓練、930張重建與量測。結果在 reports/R140v2_RESULTS.md'
 elif status.get('state')=='training':
  step=status['step'];elapsed=max(status.get('elapsed_seconds',0),1);speed=step/elapsed if step>0 else 0
  eta=(8192-step)/speed/3600 if speed>0 else float('nan')
  message=f'{stamp} GPU訓練 {step}/8192 ({step/8192:.1%})  損失 {status.get("latest_loss",0):.4f}  PSF beta {status.get("beta_raw",0):.4f}  PSF比例 {status.get("beta_scale",0):.3f}  訓練剩餘約 {eta:.1f}小時'
 elif status.get('state')=='generated_evaluation':
  message=f'{stamp} 生成資料檢查 {status.get("completed_parents",0)}/{status.get("total_parents",128)}，目前訓練步數 {status.get("step",0)}'
 elif pipeline.get('phase')=='evaluate_real_measurement.py':
  message=f'{stamp} 真實影像重建 {reconstruction.get("completed",0)}/930；完成後接續輪廓與位移量測'
 else:
  message=f'{stamp} 階段：{pipeline.get("phase","準備中")}  {pipeline.get("state","等待")}'
 if message!=last:print(message,flush=True);last=message
 if fail or pipeline.get('state')=='complete':break
 time.sleep(5)
