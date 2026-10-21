"""Paper-ready matched efficiency evidence; real metrology is reported separately."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from study import read,sha,save,MOSR_SOURCE
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    final='--final' in sys.argv
    completed_only='--completed-only' in sys.argv
    assert not(final and completed_only)
    methods=['RAW','Wiener','EDSR-x1','NAFNet','RDN-x1','RCAN-x1','MOSR'];rows=[];detail=[];identities=[]
    if final:methods=methods[:-1]+['Restormer','USRNet-x1','SwinIR','MOSR']
    if completed_only:
        config=read(ROOT/'config/COMPLETED_ONLY_SCOPE.json');methods=config['include_methods'];assert len(methods)==9 and 'SwinIR' not in methods
    scope='completed_efficiency' if completed_only else 'full_efficiency' if final else 'available_efficiency'
    directory=ROOT/'reports/data'/scope;directory.mkdir(parents=True,exist_ok=True)
    figs=ROOT/'reports/figures'/scope;figs.mkdir(parents=True,exist_ok=True)
    plan=read(MOSR_SOURCE/'evaluation/capture_plan.json')['frames'];selected=[plan[i] for i in [0,465,929]]
    for method in methods:
        p=ROOT/'results/runtime'/(method+'.json');record=read(p)
        assert record['state']=='complete' and record['gpu']=='NVIDIA RTX A6000' and record['precision']=='FP32' and record['batch']==1
        assert record['TF32'] is False and record['repetitions_per_frame']==5 and record['warmup_per_frame']==2
        values=[];allocated=[];reserved=[]
        for actual,source in zip(record['frames'],selected):
            assert actual['source_sha256']==source['source']['sha256'] and actual['run']==source['run'] and actual['index']==source['index']
            assert len(actual['samples'])==5
            for sample in actual['samples']:
                values.append(sample['forward_seconds']);allocated.append(sample['peak_allocated_bytes']);reserved.append(sample['peak_reserved_bytes'])
                detail.append({'method':method,'run':actual['run'],'index':actual['index'],**sample})
        if method not in ['RAW','Wiener','MOSR']:
            complete=read(ROOT/'runs'/method/'training_complete.json');assert record['checkpoint_sha256']==complete['checkpoint_sha256']
            parameters=complete['total_parameters']
        else:parameters=1207105 if method=='MOSR' else 0
        row={'method':method,'parameters':parameters,'seconds_mean':float(np.mean(values)),'seconds_sd':float(np.std(values,ddof=1)),
             'seconds_median':float(np.median(values)),'seconds_min':float(np.min(values)),'seconds_max':float(np.max(values)),
             'peak_allocated_GiB':max(allocated)/2**30,'peak_reserved_GiB':max(reserved)/2**30,'mode':record['mode']}
        rows.append(row);identities.append({'method':method,'receipt_sha256':sha(p),'checkpoint_sha256':record['checkpoint_sha256']})
    pd.DataFrame(rows).to_csv(directory/'summary.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(detail).to_csv(directory/f'all{len(detail)}_samples.csv',index=False,encoding='utf-8-sig')
    lines=['| 方法 | 參數數量 | 平均±樣本SD 秒 | 中位數 秒 | GPU配置峰值 GiB | GPU保留峰值 GiB | 推論策略 |',
           '| --- | ---: | ---: | ---: | ---: | ---: | --- |']
    for row in rows:
        m=row['method'];mode='原圖，不需重建' if m=='RAW' else '原有512核心／24邊緣分塊' if m=='MOSR' else '原生整張' if row['mode']=='native_full_frame' else '記憶體不足替代分塊'
        lines.append(f"| {m} | {row['parameters']} | {'—' if m=='RAW' else f'{row["seconds_mean"]:.6f} ± {row["seconds_sd"]:.6f}'} | {'—' if m=='RAW' else f'{row["seconds_median"]:.6f}'} | {row['peak_allocated_GiB']:.3f} | {row['peak_reserved_GiB']:.3f} | {mode} |")
    plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    plot=[r for r in rows if r['method']!='RAW'];fig,axs=plt.subplots(1,2,figsize=(8,3.4));x=np.arange(len(plot))
    for ax,key,label in [(axs[0],'seconds_mean','Mean reconstruction time (s)'),(axs[1],'peak_allocated_GiB','Peak allocated GPU memory (GiB)')]:
        ax.bar(x,[r[key] for r in plot],color=['0.15' if r['method']=='MOSR' else '0.75' for r in plot],edgecolor='0.15',linewidth=.6)
        ax.set_xticks(x,[r['method'] for r in plot],rotation=45,ha='right');ax.set_ylabel(label);ax.grid(axis='y',color='0.9',linewidth=.5);ax.set_axisbelow(True)
    fig.tight_layout()
    for ext in ['png','svg','pdf']:fig.savefig(figs/('time_memory.'+ext),dpi=300,bbox_inches='tight')
    plt.close(fig)
    text='''# 已完成模型的新重建效率比較

本份效率測試已完成，可以作為階段論文資料。外部模型的完整實拍位移、輪廓與SEM比較仍在執行，不以本表推定重建效果或量測排名。

## 測試條件

相同NVIDIA RTX A6000、PyTorch2.3.0+cu121、FP32、batch=1、TF32關閉。固定三張1544×2064實拍影像：第一趟起點、第16趟起點、最後一趟終點（固定影像索引0、465、929）。各張暖身兩次、正式前向五次，共每方法15次。每個方法使用獨立新程序，訓練已暫停並釋放GPU；測試時未並行執行其他本研究GPU工作。

時間僅計GPU同步前後的模型前向，不含權重載入、讀檔、輸入傳輸、存檔、輸出檢查與CPU量測。光學模組的首次FFT建立包含在暖身，不將首次建立成本混入穩態時間；此結果是暖身後的重建成本，不是開機至第一張結果的等待時間。

配置與保留峰值均取自該程序，包含模型、光學模組、输入／輸出及前向暫存；在輸出有限性檢查之前讀取峰值。CUDA環境及顯示程序的其他配置不在此程序統計內。峰值數字不是整台電腦RAM或GPU總占用。

## 結果

'''+ '\n'.join(lines)+'''

RAW没有重建；附件保留原圖identity操作的計時，但主表不把其微小呼叫成本當成重建時間。MOSR使用原有完整PSF／背景處理與512核心、24邊緣的階段分塊。其他完成方法在本GPU均使用原生整張；沒有因本測試選擇較有利的局部影像或調整權重。若未來方法原生整張記憶體不足，應另列固定替代分塊策略及其限制，不與整張等價混寫。

![灰階效率比較](figures/available_efficiency/time_memory.png)

圖說：相同三張實拍影像、相同GPU與FP32條件下，各方法暖身後的平均重建時間與GPU配置峰值。每方法15次前向；右圖取所有正式前向中最大配置峰值。兩張圖採灰階。重建速度與量測效果是不同評估面向。

## 可直接放入論文的敘述

在相同RTX A6000、FP32及單張輸入條件下，EDSR-x1與NAFNet的平均重建時間約0.53與0.51秒，MOSR約1.46秒；RDN-x1與RCAN-x1約9.87與6.73秒。MOSR的GPU配置峰值約2.78 GiB，EDSR-x1與NAFNet約3.06與3.12 GiB，RDN-x1約32.71 GiB。MOSR的GPU保留峰值則約5.56 GiB，高於EDSR-x1與NAFNet的3.10與4.34 GiB；因此配置峰值較低不能直接寫成所有記憶體占用都較低。MOSR重建時間未優於EDSR-x1與NAFNet；相對較慢的RDN-x1與RCAN-x1則有較低時間成本。這些結果不能直接推導位移或輪廓表現較佳，須與完整實拍量測分別判讀。

## 使用限制與完整紀錄

本次為三張固定影像的穩態效率測試，五次重複前向不是五張獨立影像；平均±SD描述本測試樣本的時間變動，不是跨樣品泛化區間。全部105次原始資料保存在data/available_efficiency/all105_samples.csv，摘要在summary.csv；每方法原始收據另保存GPU、框架、权重身分及策略。使用者指定較短訓練後，各模型實際輪數不同：EDSR-x1／NAFNet32輪、RDN-x1有14完整輪、RCAN-x1有8輪。不可將此表寫成各模型均已充分收斂或相同訓練時間。

原論文与MOSR權重未修改；不要把不同日期、精度、影像大小或分塊方式的舊效率數字混入本表。
'''
    for a,b in [('输入','輸入'),('没有','沒有'),('权重','權重'),('与MOSR','與MOSR')]:text=text.replace(a,b)
    if final:
        text=text.replace('data/available_efficiency/','data/full_efficiency/').replace('figures/available_efficiency/','figures/full_efficiency/').replace('all105_samples.csv','all150_samples.csv').replace('全部105次','全部150次')
        text=text.replace('本份效率測試已完成，可以作為階段論文資料。外部模型的完整實拍位移、輪廓與SEM比較仍在執行，不以本表推定重建效果或量測排名。','十種可執行方法的完整實拍驗證與效率測試均已完成，可連同完整結果用於論文；效率與位移、輪廓、SEM指標分別解讀。')
        text=text.replace('其他完成方法在本GPU均使用原生整張；','其他方法的實際策略見上表，原生整張記憶體不足時只採預定替代分塊；')
        if (ROOT/'config/USER_RESUME_20261006.json').exists():
            text+='\nRestormer／USRNet-x1／SwinIR同樣各8輪，使用相同GPU、FP32、batch=1與相同三張影像，在訓練結束釋放GPU後測量。已交付九方法的135次效率資料直接重用，本次只新增SwinIR的15次，共150次；不同日期的同硬體／版本／精度測試保留原始收據，不當作同一時刻測量。\n'
        else:
            text+='\n後續Restormer／USRNet-x1／SwinIR同樣各8輪，使用相同GPU、FP32、batch=1與相同三張影像，在訓練結束釋放GPU後測量。七方法既有105次資料直接重用，三個後續方法新增45次，共150次；不同日期的同硬體／版本／精度測試保留原始收據，不當作同一時刻測量。\n'
        by_method={row['method']:row for row in rows}
        text+='\nRestormer、USRNet-x1與SwinIR的平均前向時間分別為'+ '、'.join(f"{by_method[m]['seconds_mean']:.3f}" for m in ['Restormer','USRNet-x1','SwinIR'])+'秒。這些數字使用各方法記錄的原生策略，不能由速度推定量測表現，亦不能據此宣稱相同訓練時間或充分收斂。\n'
    if completed_only:
        text=text.replace('data/available_efficiency/','data/completed_efficiency/').replace('figures/available_efficiency/','figures/completed_efficiency/').replace('all105_samples.csv','all135_samples.csv').replace('全部105次','全部135次')
        text=text.replace('其他完成方法在本GPU均使用原生整張；','其他方法實際策略見上表，僅原生整張記憶體不足時採原先替代分塊；')
        text+='\n本次九方法資料：原七方法105次直接重用，Restormer及USRNet-x1新增30次，共135次。後兩模型同樣使用原8輪上限、相同GPU／FP32／batch=1與三張固定影像，測試時訓練已釋放GPU。SwinIR依使用者要求暫停，不列入結果，不自動續訓。不同日期的同條件測試保留原始收據，不宣稱同一時刻完成。\n'
    (ROOT/'reports'/('COMPLETED_MODELS_EFFICIENCY.md' if completed_only else 'FINAL_BENCHMARK_EFFICIENCY.md' if final else 'AVAILABLE_MODELS_EFFICIENCY.md')).write_text(text,encoding='utf-8')
    save(ROOT/'results/runtime'/('completed_efficiency_verified.json' if completed_only else 'full_efficiency_verified.json' if final else 'available_efficiency_verified.json'),{'state':'complete','methods':methods,'samples':len(detail),
        'same_gpu_precision_batch_and_frames':True,'receipt_identities':identities,'weight_and_source_hashes_verified':True,
        'full_real_metrology_complete':False})
    print('MATCHED EFFICIENCY REPORT COMPLETE',flush=True)


if __name__=='__main__':main()
