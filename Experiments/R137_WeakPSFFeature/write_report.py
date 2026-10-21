import json,numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from utils import ROOT,load,save,now

def main():
 audit=load(ROOT/'results/final_audit.json');assert audit['updates']==8192 and audit['images_sha_verified']==930
 comp=ROOT/'results/comparison';assert load(comp/'complete.json')['independent_new_circle_refits']==8370
 names=['displacement_summary','shape_size_summary','SEM_comparison','paired_scan_intervals'];tables={n:pd.read_csv(comp/(n+'.csv')) for n in names}
 colors={'Raw':'#777777','R129':'#2774AE','R130-Clean':'#E47722','R137-WeakPSF':'#198754'}
 pos=pd.read_csv(comp/'position_statistics.csv');fig,axs=plt.subplots(1,2,figsize=(12,4),layout='constrained')
 for ax,kind in zip(axs,['adjacent','start']):
  for m,c in colors.items():
   v=pos[(pos.model==m)&(pos.kind==kind)];ax.plot(v.position,v.mean_error_nm,color=c,label=m);ax.fill_between(v.position,v.mean_error_nm-v.repeat_sd_nm,v.mean_error_nm+v.repeat_sd_nm,color=c,alpha=.08)
  ax.set(title=kind+' mean +/-1 SD',xlabel='Position',ylabel='PI-relative error nm');ax.legend()
 fig.savefig(ROOT/'reports/figures/displacement.png',dpi=180);plt.close(fig)
 run=ROOT/'runs/formal_8192';train=load(run/'training_complete.json');runtime=pd.read_csv(ROOT/'results/reconstruction_runtime.csv');activity=pd.read_csv(ROOT/'results/PSF_activity_real_examples.csv')
 text='# R137 弱 PSF 特徵測試結果\n\n完成日期：'+now()+'。固定舊25顆PSF正規化後平均，Wiener線索經局部轉換後以0.02強度融入特徵；沒有先改写Raw。這是使用者要求的弱輔助測試，不是新PSF校準或正式基準更換。\n\n'
 text+='## 實際設計與來源\n\n從零8192次更新，16循環，與R130相同512/128/128合成母場景、順序及噪聲種子。主幹初始參數逐位元相同，新增640個局部光學轉換參數。固定最後模型，未依真實效果挑選。\n\n全局FFT光學線索：鏡射50像素，按PSF強度質心定義原點，Wiener regularization=0.0565且DC增益1。訓練先對384影像求線索再取320，與128中央監督；實拍先對完整1544×2064求線索。分塊只裁同一份完整光學線索，不能宣稱整條光學路徑具有R130純網路的有限局部性。\n\n25顆沒有經確認的此次視野映射，故只使用固定平均，不猜空間分佈。PSF來源沿用R129，可能來自SEM校準，因此本輪不能稱完全獨立SEM確認。合成訓練沒有直接加入實拍/SEM/PI標籤。\n\n'
 text+=f"參數：{train['parameter_count']}；訓練時間：{train['elapsed_seconds']:.2f}秒；最終模型SHA256：{train['final_checkpoint']['sha256']}。\n\n"
 for n,df in tables.items():text+='## '+n+'\n\n'+df.to_markdown(index=False,floatfmt='.6f')+'\n\n'
 text+='位移差與輪廓/尺寸重拍分開解讀；SEM尺寸偏差與去尺寸形狀差分列。兩方向候選均保留。95%配對區間以完整趟次抽樣；沒有新的獨立實拍保留集。\n\n'
 text+='## PSF確實參與運算\n\n'+activity.to_markdown(index=False,floatfmt='.8f')+'\n\n同權重關閉與零線索比較是機制檢查，不是重新訓練的因果消融；四張實拍診斷不能當930張關閉PSF的效果統計。0.02限制的是特徵注入幅度，不保證最终影像差剛好小於0.02。\n\n'
 text+=f"## 時間\n\n本輪930張包含PSF及神經重建中位數{runtime.total_reconstruction_seconds.median():.4f}秒；含讀寫{runtime.end_to_end_load_infer_save_seconds.median():.4f}秒。不能把這個數字標為純神經時間。\n\n"
 text+='![位移](figures/displacement.png)\n\n![PSF開關](figures/PSF_on_off_example.png)\n\n'
 (ROOT/'reports/R137_RESULTS.md').write_text(text,encoding='utf-8')
 save(ROOT/'results/complete.json',dict(state='complete_research_test_not_promoted',updates=8192,images=930,circles=8370,model='R137-WeakPSF',baseline_changed=False,report='reports/R137_RESULTS.md',completed_utc=now()))
if __name__=='__main__':main()
