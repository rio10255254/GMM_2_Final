from pathlib import Path
import argparse,json,sys,os,runpy
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
a=argparse.ArgumentParser();a.add_argument('--stage',required=True);a.add_argument('--device',required=True);a.add_argument('--threads',type=int,required=True);args=a.parse_args()
if args.device=='cpu':os.environ['CUDA_VISIBLE_DEVICES']='-1'
else:os.environ.pop('CUDA_VISIBLE_DEVICES',None)
os.environ['PYTHONWARNINGS']='ignore::FutureWarning';sys.path.insert(0,str(ROOT))
import utils
original=utils.config;cfg=original();cfg.update(device=args.device,cpu_threads=args.threads);utils.config=lambda:cfg
import infer_r138_psf
oldload=infer_r138_psf.load_own_model
infer_r138_psf.load_own_model=lambda path,device=args.device:oldload(path,device)
# Runtime device history supersedes the originalCPU plan; original reports remain immutable.
runpy.run_path(str(ROOT/args.stage),run_name='__main__')

if args.stage=='write_report.py':
 p=ROOT/'reports/R138_RESULTS.md';s=p.read_text(encoding='utf-8');s=s.replace('本輪依使用者要求全程CPU','本輪裝置依保存進度切換記錄，實際使用見device_history.jsonl');s+='\n## 中途續訓及計時範圍\n\n本輪加上獨立版本的裝置與執行緒續訓層，原始執行程式雜湊保留不變。模型、優化器、步数、隨機狀態保存後再切換；全部段落見runs/formal_8192/device_history.jsonl。訓練時間為各更新時間總和，不含開發檢查與停頓，不與前輪总時間直接比較。CPU與GPU浮點差異可使訓練軌跡略不同，混合裝置不能宣稱逐位元等同單裝置訓練。\n';p.write_text(s,encoding='utf-8')
