"""Publish the fixed endpoint and all scheduled real results without model promotion."""
import sys,json,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,pandas as pd
from scipy.io import loadmat
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Microsoft JhengHei','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False

def main():
    out=ROOT/'results/long_training_review_20260913_v2';v=load(out/'verification.json');assert v['final_public_inference_replay_exact']
    pkg=Path(v['package']);run=pkg/'results/training/r129_long_01';t=pd.read_csv(out/'trajectory.csv');dev=pd.read_csv(out/'development.csv')
    figures=ROOT/'reports/figures';fig,axes=plt.subplots(1,3,figsize=(13,4.2),layout='constrained')
    plots=[('centered_shape_nm','細部形狀誤差（奈米）','#367d78'),('diameter_error_nm','尺寸誤差（奈米）','#b66448')]
    for ax,(key,title,color) in zip(axes,plots):
        ax.plot(t.step,t[key],'o-',color=color);ax.set_title(title+'\n越低越好');ax.set_xlabel('訓練更新次數');ax.grid(alpha=.2)
        for x,y in zip(t.step,t[key]):ax.annotate(f'{y:.1f}',(x,y),xytext=(0,8),textcoords='offset points',ha='center',fontsize=9)
        ax.margins(y=.3)
    axes[2].plot(dev.step,dev.loss,'o-',color='#536b9a');axes[2].set_title('合成開發資料誤差\n越低越好');axes[2].set_xlabel('訓練更新次數');axes[2].grid(alpha=.2)
    fig.suptitle('R129 長訓練：细部形狀改善，但尺寸偏差增加\n相同36顆柱子 × 正常拍攝13–15；依原定時點全部呈現',fontsize=14)
    figure=figures/'R129_long_training_tradeoff.png';assert not figure.exists();fig.savefig(figure,dpi=160);plt.close(fig)
    # Fixed example index matches the preceding architecture review, not a newly selected success.
    baseline=loadmat(run/'evaluations/step00000/real/sem_masks.mat',variable_names=['cells'])['cells']
    final=loadmat(run/'evaluations/step08192/real/sem_masks.mat',variable_names=['cells'])['cells']
    reference=loadmat(pkg/'validation/sem_reference.mat',variable_names=['truth_cells'])['truth_cells']
    historical=REPO/'Experiments/R128_SourceOnlyFullTraining/results/thesis_v34_review_20260912/normal_sem_fine_v2'
    raw=loadmat(historical/'input_cells.mat',variable_names=['raw_cells'])['raw_cells']
    fig,axes=plt.subplots(1,4,figsize=(11,3.6),layout='constrained')
    for ax,name,image in zip(axes,['SEM參考','原始光學影像','R129長訓練前','R129長訓練後'],[reference[:,:,17],raw[:,:,17,1],baseline[:,:,17,1],final[:,:,17,1]]):
        ax.imshow(image,cmap='gray',vmin=0,vmax=255);ax.set_title(name);ax.axis('off')
    fig.suptitle('固定第18顆柱子、正常拍攝14｜每格依既有讀法調整對比\n視覺變平順不等於尺寸更準，判斷以全部柱子的數據為準',fontsize=12)
    imagepath=figures/'R129_long_training_pillar18.png';assert not imagepath.exists();fig.savefig(imagepath,dpi=170);plt.close(fig)
    first=t.iloc[0];last=t.iloc[-1];relative=lambda key:(last[key]/first[key]-1)*100
    table=t[['step','radial_nm','correlation','diameter_error_nm','MZC_error_nm','centered_shape_nm','nominal_error_nm','within_grid_nm','cross_axis_nm']].to_markdown(index=False,floatfmt='.4f')
    report=ROOT/'reports/R129_LONG_TRAINING_RESULTS.md'
    text=f'''# R129 長訓練結果與完成核對

核對日期：2026-09-13。訓練於 **2026-09-12 22:20（台灣時間）** 完成。

## 結論

預定8192次更新、16個資料循環及全部指定驗證均完成。細部形狀改善，但尺寸與輪廓半徑誤差變大，位移指標也有取捨。**保留R129架構與訓練成果，不直接採用最後模型，不覆寫套件起始模型。**

相同36顆柱子、正常曝光13–15，先逐顆跨曝光取中位數，再跨柱取中位數：

| 主要指標 | 訓練前 | 第8192次 | 判斷 |
|---|---:|---:|---|
| 去除平均尺寸後的細部形狀誤差 | 21.352nm | 16.397nm | 降低23.2%；36/36顆改善 |
| 細部形狀相關 | 0.6689 | 0.6919 | 29/36顆改善 |
| 非圓程度與SEM差距 | 86.605nm | 62.651nm | 降低27.7%；31/36顆改善 |
| 輪廓半徑誤差 | 41.579nm | 49.523nm | 增加19.1%；30/36顆變差 |
| 尺寸誤差 | 80.679nm | 96.380nm | 增加19.5%；31/36顆變差 |
| 同圖九柱位移分散（四對平均） | 8.828nm | 7.434nm | 降低15.8% |
| 與名義位移的差距（四對平均） | 6.746nm | 6.970nm | 增加3.3% |
| 橫向偏移（四對平均） | 6.933nm | 7.721nm | 增加11.4% |

非圓程度的目標是貼近SEM實際起伏，並非強迫柱子成為正圓。逐顆配對中位數不必等於兩個總體中位數相減，完整配對數量與數字均保留。

![固定時點的變化](figures/R129_long_training_tradeoff.png)

合成開發誤差由4.87358降到2.68142，降低約45.0%；所有17個指定開發驗證均保留。結尾既有合成測試誤差1.97272，因不是與開發資料同一批，不拿它和起始開發誤差計算改善率。合成誤差降低，並未同時守住真實尺寸。

## 全部指定真實時點

下表距離單位為奈米，correlation除外。step0是原R129 D短測24次之後的起始模型；8192是本輪新增更新數，不含原短測或套件試跑。

{table}

尺寸誤差在512次時就已增加，而非只在最後才變差。細形狀於4096次達16.285nm，最後16.397nm；但較早時點也已犧牲尺寸。這不支持單靠任選較早保存點便能解決問題，沒有事後將中間版本改稱預定最佳終點。

![固定實拍示例](figures/R129_long_training_pillar18.png)

示例沿用第18顆、曝光14，不按此次成績挑有利個案；每格使用歷史讀法的對比正規化，不能把灰階外觀當成材料邊界證明。

## 與既有結果的關係

沿用先前同一SEM讀法的歷史數字：Raw尺寸誤差88.204nm、R128為76.647nm；目前R129終點96.380nm，兩者都沒有超過。去尺寸細形狀誤差R128為16.119nm、V42為6.810nm，R129終點16.397nm，已接近R128但尚未勝過它。

這只是相同既有SEM配對场景的參照，不是同訓練成本的純架構對照，也不能替V42補回獨立未知資料證據。沒有把舊120對完整位移統計與本輪僅四對的結果混成同一張排名表。

## 完成與獨立驗證

- 8192條實際更新紀錄，步數1至8192完整、無重複；每循環512個訓練來源全部使用，順序、來源內容識別與雜訊種子逐條符合設定。
- 另從原始陣列重建64個實際輸入，涵蓋16個循環的固定位置，與記錄完全一致。這是64筆獨立重建，不宣稱8192筆全部重新生成。
- 最後權重及全部優化器步數均為8192；權重內容與自身保存的數值識別一致。完成紀錄中的24個資源、包內1603個靜態資源全部核對；無修改模型、資料或舊預期雜湊。
- 17次開發、5次真實、1次結尾合成測試均齊全；五次共有540筆SEM讀值、20筆方法／位移對結果。
- 540筆SEM点以另一種圓心擬合法重算四項指標，最大差異{v['SEM_refit_max_difference']:.8g}；非圓程度仍沿用共用的歷史方法，沒有宣稱獨立重寫。
- 20筆位移算術重新計算一致。最後模型以公開單圖入口重建正常曝光14，與結束時保存影像逐像素相同。
- 首次公開重建呼叫退出1且沒有返回診斷、未產出影像，第一版審查因此停止。保留該次未完成結果；在新目錄重跑成功，完整審查另存v2，沒有放寬比較標準或修改原模型。首次退出原因未確定。

## 如何解讀與下一步

這輪顯示目前訓練能改善細部形狀，但沒有同時控制平均尺寸偏差。它沒有單獨證明是哪個模組造成偏差，也沒有證明增加參數或繼續訓練就會改善。

下一步應保留R129主架構，針對原圖參照、放大層承接與現有訓練要求，先做固定權重或同條件的小範圍拆解，找出尺寸偏差來源，再決定修改。不能直接用這次終點替換論文／量測模型，也不立刻延長訓練。

真實證據仍只有三張正常拍攝、36顆既有柱子與四對固定區域。無法由每序列一對影像估計時間波動，名義位移也不是新增的獨立實际位置真值。光學／SEM物理邊界對應、跨樣品與儀器校準限制仍有效。未重新讀取舊144張封存確認集。

模型保存在包內 `results/training/r129_long_01/checkpoints/step08192.pth`，SHA256 `{v['final_checkpoint']['sha256']}`。套件預設重建仍使用原 `weights/initial_r129.pth`。本次不變更這個預設。

完整表與核對資料位於 `results/long_training_review_20260913_v2/`；原訓練資料與結果在獨立套件內，舊報告與起始模型保留。COMBO正式基準與R129研究身分不變。
'''
    with report.open('x',encoding='utf-8') as f:f.write(text)
    save(out/'published.json',dict(created_utc=now(),source=record(__file__),report=record(report),figures=[record(figure),record(imagepath)],verification=record(out/'verification.json'),conclusion='Completed study, mixed real results; no model adoption'))
    print('Published fixed-endpoint result report and two figures')
if __name__=='__main__':main()
