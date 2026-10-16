"""R139 report is generated only after all required evidence exists."""
import json,numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from utils import ROOT,load,save,now,verify_protected

def table(df):return df.to_markdown(index=False,floatfmt='.6f')

def main():
 audit=load(ROOT/'results/final_audit.json');assert audit['updates']==8192 and audit['output_sha256_verified']==930 and audit['new_circle_refits']==8370
 run=ROOT/'runs/formal_8192';train=load(run/'training_complete.json');comp=ROOT/'results/comparison';figure=ROOT/'reports/figures';figure.mkdir(exist_ok=True)
 s=pd.read_csv(comp/'displacement_summary.csv');g=pd.read_csv(comp/'shape_size_summary.csv');sem=pd.read_csv(comp/'SEM_comparison.csv');paired=pd.read_csv(comp/'paired_scan_intervals.csv');pos=pd.read_csv(comp/'position_statistics.csv');timing=pd.read_csv(ROOT/'results/reconstruction_runtime.csv')
 rows=[json.loads(v) for v in (run/'updates.jsonl').read_text().splitlines()];loss=np.array([v['loss'] for v in rows]);dev=[load(p) for p in sorted((run/'evaluations').glob('dev_*.json'))]
 fig,ax=plt.subplots(1,2,figsize=(11,3.5),layout='constrained');ax[0].plot(np.arange(128,8193,128),loss.reshape(-1,128).mean(1));ax[0].set(xlabel='Update',ylabel='128-update loss mean',title='Scratch training')
 ax[1].plot([v['step'] for v in dev],[v['means']['total'] for v in dev],marker='o',ms=3);ax[1].set(xlabel='Update',ylabel='Fixed generated dev loss',title='Fixed synthetic development');fig.savefig(figure/'training.png',dpi=170);plt.close(fig)
 colors={'Raw':'#777777','R129':'#287bb8','R130-Clean':'#e47722','R137-WeakPSF':'#218b58','R138-V42PSF8':'#9c45ad','R139-UNetRecurrent':'#d43f52'}
 fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
 for ax,kind in zip(axes,['adjacent','start']):
  for model,color in colors.items():
   p=pos[(pos.model==model)&(pos.kind==kind)];ax.plot(p.position,p.mean_error_nm,label=model,color=color);ax.fill_between(p.position,p.mean_error_nm-p.repeat_sd_nm,p.mean_error_nm+p.repeat_sd_nm,color=color,alpha=.07)
  ax.set(xlabel='Position',ylabel='Image minus PI (nm)',title=kind+' mean +/-1 repeat SD');ax.legend(fontsize=7)
 fig.savefig(figure/'displacement.png',dpi=170);plt.close(fig)
 fig,axes=plt.subplots(1,3,figsize=(12,4),layout='constrained')
 for ax,key in zip(axes,['diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm']):
  vals=[g[g.model==name].iloc[0][key] for name in colors];ax.bar(list(colors),vals,color=list(colors.values()));ax.set(ylabel='nm',title=key.replace('_',' '));ax.tick_params(axis='x',rotation=30,labelsize=7)
 fig.savefig(figure/'repeatability.png',dpi=170);plt.close(fig)
 side=s[s.model=='R139-UNetRecurrent'];baseline=s[s.model=='R137-WeakPSF'];gnew=g[g.model=='R139-UNetRecurrent'].iloc[0];gold=g[g.model=='R137-WeakPSF'].iloc[0]
 conclusion=f"R139短步平均PI差{side[side.kind=='adjacent'].mae_nm.iloc[0]:.3f}nm，R137為{baseline[baseline.kind=='adjacent'].mae_nm.iloc[0]:.3f}nm；R139直徑重拍{gnew.diameter_repeat_sd_nm:.3f}nm、輪廓重拍{gnew.contour_repeat_sd_nm:.3f}nm，R137分別{gold.diameter_repeat_sd_nm:.3f}與{gold.contour_repeat_sd_nm:.3f}nm。各指標分開解讀，未自動替換論文或正式模型。"
 text=f'''# R139 U-Net 反覆修正模型完整結果

完成時間：{now()}。真正三層U-Net加四次共享修正，使用同一批合成資料從零8192次訓練；V42八候選PSF放半尺寸解碼層，在末次修正啟用。訓練前固定最後checkpoint及共同真實驗證方法。

## 主要判讀

{conclusion}

模型參數：{train['parameter_count']}；最終checkpoint SHA256：{train['final_checkpoint']['sha256']}。實際光學參與：{audit['PSF_activity_observed']}；原始beta={audit['PSF_beta_raw']:.6f}、scale={audit['PSF_beta_scale']:.6f}、有效beta={audit['PSF_beta_effective']:.6f}。若光學無作用應如實說明，不把可關閉介面當成PSF有效性。

## 位移

{table(s)}

## 尺寸與輪廓重複性

{table(g)}

## SEM 對照 兩方向候選

{table(sem)}

## 整趟配對區間

{table(paired)}

每趟是配對重抽樣單位；九顆與720插值方向不是九或720個獨立樣本。新模型僅使用既有30趟、930影像，非未見保留集。相對起點直接算位置j減0，不累加逐段中位數。

## 訓練與來源

完成{train['unique_updates']}次；開發評估{train['dev_evaluations']}次；最終既有生成測試{train['test_summary']}。同R138的資料母場景、順序、噪聲和主要學習率逐筆核對。新架構及PSF訓練政策是本輪刻意改變，不能歸因為U-Net單一元件效果。

## 速度與範圍

本輪930張GPU完整重建中位{timing.total_reconstruction_seconds.median():.3f}秒；含讀寫中位{timing.end_to_end_load_infer_save_seconds.median():.3f}秒。沒有同時控制其他程序的跨模型速度測試，因此不做固有效率排名。

獨立檢查核對930張輸出SHA、8370次新模型圓重擬合、10800筆六方法位移重新計算及歷史來源不變。PSF開關機制只在4張固定實拍與32組既有生成資料上額外檢查，不是重訓消融。SEM舊核來源未證明與同一資料完全獨立；沒有完整量測不確定度合成。

![訓練](figures/training.png)
![位移](figures/displacement.png)
![尺寸與輪廓重拍](figures/repeatability.png)
'''
 (ROOT/'reports/R139_RESULTS.md').write_text(text,encoding='utf-8');verify_protected();save(ROOT/'results/complete.json',dict(state='complete_research_not_promoted',updates=8192,images=930,circles=8370,PSF_activity_observed=audit['PSF_activity_observed'],baseline_changed=False,report='reports/R139_RESULTS.md',completed_utc=now()));print('REPORT_COMPLETE',conclusion,flush=True)
if __name__=='__main__':main()
