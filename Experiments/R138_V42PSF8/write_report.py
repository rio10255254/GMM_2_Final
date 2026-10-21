import json,numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from utils import ROOT,load,save,now,verify_protected

def main():
 audit=load(ROOT/'results/final_audit.json');assert audit['updates']==8192 and audit['output_hashes_verified']==930
 comp=ROOT/'results/comparison';assert load(comp/'complete.json')['independent_new_circle_refits']==8370
 colors={'Raw':'#777777','R129':'#2774AE','R130-Clean':'#E47722','R137-WeakPSF':'#198754','R138-V42PSF8':'#9b3ca8'}
 pos=pd.read_csv(comp/'position_statistics.csv');fig,axes=plt.subplots(1,2,figsize=(12,4),layout='constrained')
 for ax,kind in zip(axes,['adjacent','start']):
  for m,c in colors.items():
   v=pos[(pos.model==m)&(pos.kind==kind)];ax.plot(v.position,v.mean_error_nm,label=m,color=c);ax.fill_between(v.position,v.mean_error_nm-v.repeat_sd_nm,v.mean_error_nm+v.repeat_sd_nm,alpha=.07,color=c)
  ax.set(title=kind+' mean +/-1 SD',xlabel='Position',ylabel='PI-relative nm');ax.legend(fontsize=8)
 fig.savefig(ROOT/'reports/figures/displacement.png',dpi=180);plt.close(fig)
 run=ROOT/'runs/formal_8192';train=load(run/'training_complete.json');rt=pd.read_csv(ROOT/'results/reconstruction_runtime.csv')
 text='# R138 V42八候選PSF完整結果\n\n完成日期：'+now()+'。本輪依使用者要求，把原R137的平均PSF特徵改成V42 WeakPSFDeconvBlock，從零完整8192次訓練，再重建930張真實影像及量測8370輪廓。既有模型及正式基準不改。\n\n'
 text+='## 實際模型與公平範圍\n\n使用既有25顆PSF，未假設視野網格，自動等間距取索引0,3,7,10,14,17,21,24；網路依64通道輸入特徵給八顆混合權重。模組類別與V42原始程式相同，接在R137主幹stem、SiLU前，每個迭代回合使用一次，共四次。不是整個網路變成V42。\n\n原V42正則值30、頻率遮罩比例0.25、softmax溫度1.5、clamp處理與FFT原點規則沿用；beta從0.02可學、限制0至0.1；beta_scale_max設1保留初始有效0.02。新增gating末層從零開始，初始八顆等權。全網scratch，沒有V42或R137神經權重匯入。\n\n共享同512/128/128合成資料、噪聲、順序、學習率和三項損失；主幹起點一致，8192更新並固定最後模型。V42模組使用全圖池化與FFT，沒有沿用R130有限依賴半徑、裁切上下文等價或分塊等價的宣稱。訓練320區塊中央128監督，實拍完整1544×2064；訓練/完整視野的全局上下文不同為此設計限制。\n\n'
 text+=f"参数{train['parameter_count']}，訓練經過{train['elapsed_seconds']:.2f}秒；最後模型SHA256 {train['final_checkpoint']['sha256']}。實際beta={audit['learned_beta']:.8f}，有效beta={audit['effective_beta']:.8f}。\n\n"
 for name in ['displacement_summary','shape_size_summary','SEM_comparison','paired_scan_intervals','endpoint_30um']:
  text+='## '+name+'\n\n'+pd.read_csv(comp/(name+'.csv')).to_markdown(index=False,floatfmt='.6f')+'\n\n'
 text+='## PSF參與及查核\n\n'+pd.read_csv(ROOT/'results/PSF_activity_real_examples.csv').to_markdown(index=False,floatfmt='.8f')+'\n\n全部930張×4回合權重另存PSF_all930_iteration_weights.csv；四張實拍與32生成資料做同權重PSF开关檢查，不是完整關閉版930影像或重新訓練消融。若beta退到0或權重近乎一致，應如實解讀為模型未依賴此分支，不能修改門檻或結果硬稱有效。\n\n'
 text+=f"已核對8192次與R137輸入/噪聲/順序相同、930輸出識別、8370獨立圓重擬合，另從五方法圓心重算9000位移，最大差{audit['displacement_max_difference_nm']:.3g}nm。\n\n"
 text+=f"## 耗時範圍\n\n本次930張重建中位{rt.total_reconstruction_seconds.median():.4f}秒，含讀寫{rt.end_to_end_load_infer_save_seconds.median():.4f}秒。本輪依使用者要求全程CPU，未作受控跨裝置效率比較，不據此聲稱PSF固有速度代價。\n\n"
 text+='## 限制\n\n同一已用過的真實資料集、同一樣本工作階段；PSF有歷史SEM校準來源限制，兩SEM方向候選都保留。重拍穩定與尺寸準確分開，未合成完整系統不確定度，不主張全套XAI或多種樣本泛化。\n\n![位移](figures/displacement.png)\n\n![影像與PSF開關](figures/real_example.png)\n'
 (ROOT/'reports/R138_RESULTS.md').write_text(text,encoding='utf-8');verify_protected()
 save(ROOT/'results/complete.json',dict(state='complete_research_not_promoted',updates=8192,images=930,circles=8370,PSF_effect_observed=audit['PSF_effect_observed'],baseline_changed=False,completed_utc=now()))
if __name__=='__main__':main()
