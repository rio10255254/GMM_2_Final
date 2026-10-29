import numpy as np,pandas as pd,torch,cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from utils import ROOT,load,save,sha,now,verify_protected,verify_frozen
from infer_r130_clean import load_own_model
from dataset_r130_clean import Bank
from utils import config,setup

def table(df):return df.to_markdown(index=False,floatfmt='.3f')
def main():
 run=ROOT/'runs/formal_8192';train=load(run/'training_complete.json');comp=ROOT/'results/comparison';assert load(comp/'complete.json')['independent_new_circle_refits']==8370
 profile=load(ROOT/'results/profile.json');s=pd.read_csv(comp/'displacement_summary.csv');g=pd.read_csv(comp/'shape_size_summary.csv');sem=pd.read_csv(comp/'SEM_comparison.csv');pos=pd.read_csv(comp/'position_statistics.csv');figdir=ROOT/'reports/figures';figdir.mkdir(exist_ok=True)
 rows=[__import__('json').loads(x) for x in (run/'updates.jsonl').read_text().splitlines()];loss=np.array([x['loss'] for x in rows]);dev=[load(p) for p in sorted((run/'evaluations').glob('dev_*.json'))]
 fig,ax=plt.subplots(1,2,figsize=(10,3.5),layout='constrained');ax[0].plot(np.arange(128,8193,128),loss.reshape(-1,128).mean(1));ax[0].set(title='Scratch training objective',xlabel='Update',ylabel='128-update mean');ax[1].plot([x['step'] for x in dev],[x['means']['total'] for x in dev],marker='o',ms=3);ax[1].set(title='Fixed generated development',xlabel='Update',ylabel='Mean objective');fig.savefig(figdir/'training_curves.png',dpi=160);plt.close(fig)
 colors={'Raw':'#777777','R129':'#1e7898','R130-Clean':'#d16d20'}
 fig,axs=plt.subplots(1,2,figsize=(11,4),layout='constrained')
 for kind,ax in zip(['adjacent','start'],axs):
  for m in colors:
   p=pos[(pos.model==m)&(pos.kind==kind)].sort_values('position');x=p.position.to_numpy();y=p.mean_error_nm.to_numpy();sd=p.repeat_sd_nm.to_numpy();ax.plot(x,y,label=m,color=colors[m]);ax.fill_between(x,y-sd,y+sd,color=colors[m],alpha=.12)
  ax.set(title=kind+' mean error +/-1 SD',xlabel='Position index',ylabel='Image minus PI (nm)');ax.axhline(0,color='black',lw=.5);ax.legend()
 fig.savefig(figdir/'displacement.png',dpi=160);plt.close(fig)
 fig,axs=plt.subplots(1,3,figsize=(12,3.7),layout='constrained')
 for key,ax in zip(['diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm'],axs):
  order=['Raw','R129','R130-Clean'];values=[g[g.model==m][key].iloc[0] for m in order];ax.bar(order,values,color=[colors[m] for m in order]);ax.set(title=key.replace('_',' '),ylabel='nm');ax.tick_params(axis='x',labelsize=9)
 fig.savefig(figdir/'repeatability.png',dpi=160);plt.close(fig)
 # Fixed first full frame, image displays only; preserve measurement precision.
 plan=load(ROOT/'evaluation/capture_plan.json');f=plan['frames'][0];raw=cv2.imread(f['source']['path'],0).astype(float)/255
 from pathlib import Path
 r129path=ROOT.parents[1]/'Experiments/R136_PIRepeatability/results/R129'/f['run']/'01.npz'
 with np.load(r129path) as z:old=z['output']
 with np.load(ROOT/'results/reconstruction'/f['run']/'01.npz') as z:new=z['output']
 fig,axs=plt.subplots(1,3,figsize=(11,4),layout='constrained')
 for ax,image,m in zip(axs,[raw,old,new],['Raw','R129','R130-Clean']):ax.imshow(image[690:820,1555:1685],cmap='gray',vmin=0,vmax=1,interpolation='nearest');ax.set_title(m);ax.axis('off')
 fig.suptitle('Same native crop, common grey range; no visual outcome selection');fig.savefig(figdir/'native_nine_example.png',dpi=180);plt.close(fig)
 # Historical runtime is clearly separated from the fresh neural timing.
 oldseconds=[]
 for f in plan['frames']:
  p=ROOT.parents[1]/'Experiments/R136_PIRepeatability/results/R129'/f['run']/f"{f['index']+1:02d}.json"
  if p.exists():oldseconds.append(load(p)['seconds'])
 newtime=pd.read_csv(ROOT/'results/reconstruction_runtime.csv')
 timing=dict(R130_neural_median_seconds=float(newtime.total_neural_inference_seconds.median()),R130_load_infer_save_median_seconds=float(newtime.end_to_end_load_infer_save_seconds.median()),R129_historical_load_infer_save_median_seconds=float(np.median(oldseconds)) if oldseconds else None,R129_runtime_not_rerun=True)
 save(ROOT/'results/runtime_comparison_scope.json',timing)
 test=load(run/'evaluations/test_08192.json');clean_ids={e['index'] for e in load(ROOT/'data/manifest.json')['entries'] if e['split']=='test' and e['category']=='clean_identity'}
 clean=[x for x in test['rows'] if x['index'] in clean_ids];save(ROOT/'results/clean_control_summary.json',dict(count=len(clean),rows=clean,interpretation='Clean-control image error after training; exact identity is representable but not guaranteed to remain learned.'))
 positive=['all required execution outputs present'];limitations=[]
 row=s[(s.model=='R130-Clean')&(s.kind=='adjacent')].iloc[0];base=s[(s.model=='R129')&(s.kind=='adjacent')].iloc[0];raws=s[(s.model=='Raw')&(s.kind=='adjacent')].iloc[0]
 conclusion=f"R130-Clean短步平均PI差 {row.mae_nm:.3f} nm；R129 {base.mae_nm:.3f} nm，Raw {raws.mae_nm:.3f} nm。短步重拍 {row.repeatability_nm:.3f} nm。各項取捨如下表，不以單一分數選模型。"
 final_hash=train['final_checkpoint']['sha256']
 text=f'''# R130-Clean 完整結果

完成日期：{now()}。此輪只建立一個新模型，從零訓練8192次；未載入舊神經權重，PSF全程關閉，訓練只用既有合成配對。R129及原始結果保留，未自動更換正式基準。

## 主要結果

{conclusion}

{table(s)}

## 尺寸與輪廓重複性

{table(g)}

## SEM對照

{table(sem)}

九顆集合相同；逐顆方向仍沿用兩種候選，沒有為新模型重配方向或尺度。尺寸平均有號差、完整徑向差及去尺寸形狀差分開解讀。

## 速度與記憶體

參數量：{train['parameter_count']}。GPU：{profile['device']}，FP32、TF32關閉，完整1544×2064影像。

930張神經推論中位耗時：{timing['R130_neural_median_seconds']:.3f}秒；本輪讀取、推論、寫檔中位耗時：{timing['R130_load_infer_save_median_seconds']:.3f}秒。

R129歷史讀取、推論、寫檔中位耗時：{timing['R129_historical_load_infer_save_median_seconds']:.3f}秒。這是既有執行紀錄，不是本轮重新載入R129做匹配微基準；不得與R130純神經計時混成速度倍數。

{table(pd.DataFrame(profile['full_image_and_tile_records']))}

分段及ACM獨立耗時見results/profile.json；數值包含固定主幹、局部線索、四次修正、輸出、切塊複製及全流程範圍。

## 訓練與生成驗證

固定8192次更新，16個循環，每個循環512來源。開發檢查{train['dev_evaluations']}次。最終生成測試：{test['means']}。

清楚控制的訓練後結果見results/clean_control_summary.json；初始輸出精確等於Raw不代表訓練後所有清楚影像都完全不變。

![訓練曲線](figures/training_curves.png)
![固定三方法位移](figures/displacement.png)
![輪廓與尺寸波動](figures/repeatability.png)
![固定實拍例圖](figures/native_nine_example.png)

## 核對與範圍

同一930張、Raw追蹤、ACM最大梯度邊界、LSC、名義172.5nm/px及原PI算式。Raw與R129既有摘要重算符合；新8370圓另行獨立擬合核對。完整掃描配對區間另表保存，不把九顆或720方向當獨立樣品。

這是既有資料上的固定模型比較，不是新的未知holdout；未認證完整绝對量測不確定度。不得將更穩等同所有尺寸更準。PSF feature branch只有關閉介面，沒有正式實作，不能宣稱已具光學輔助能力。

最終權重SHA256：{final_hash}。來源及設定在runs/formal_8192/run_config.json；輸出930张位於results/reconstruction（H槽活動資料）。所有舊證據原樣保留。
'''
 (ROOT/'reports/R130_CLEAN_RESULTS.md').write_text(text,encoding='utf-8')
 (ROOT/'reports/TRAINING_PROVENANCE.md').write_text(f'''# R130-Clean 訓練來源

- 從零訓練：YES。正式run初始SHA256：{train['initial_parameter_sha256']}。
- 載入舊神經／optimizer／EMA／step strength：NO。
- PSF：OFF，無PSF參數或檔案讀取；資料準備只保留source/noiseless/target，不解壓存放的kernel4。
- SEM／PI／實拍訓練：NO。真實影像只在8192最終模型保存後進入驗證。
- synthetic data：YES，512／128／128；母場景ID及幾何雜湊跨組交集0。
- 正式更新：8192，最後模型預先固定；32次sanity使用獨立scratch實例並丟棄。
- 最終SHA256：{final_hash}。
- 原始規格及未指定數值的決斷保存於config； source_lock在正式啟動前建立，未用新雜湊覆蓋歷史收據。

執行核對不能單獨證明模型效果；請讀R130_CLEAN_RESULTS.md的完整位移、尺寸、輪廓與效率數字。
''',encoding='utf-8')
 verify_frozen(load(ROOT/'config/source_lock.json'));verify_protected()
 save(ROOT/'results/complete.json',dict(state='training_inference_measurement_profiling_report_complete',training_updates=8192,images=930,circles=8370,parameter_count=train['parameter_count'],final_checkpoint_sha256=final_hash,formal_baseline_changed=False,completed_utc=now()))
 save(ROOT/'runs/launcher_logs/active_formal_run.json',dict(state='complete',model='R130-Clean',completed_utc=now(),proof='results/complete.json'))
 print('R130-Clean pipeline complete.',flush=True)
if __name__=='__main__':main()
