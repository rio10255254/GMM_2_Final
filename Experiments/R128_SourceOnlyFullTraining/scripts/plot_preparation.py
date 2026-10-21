"""Representative training-only images and actual engineering learning trace."""
import sys
from common import *
sys.path.insert(0,str(ROOT))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from data.generator import parameters

def main():
    cfg=load(ROOT/'config/study.json')
    font_manager.fontManager.addfont('C:/Windows/Fonts/msjh.ttc')
    plt.rcParams['font.family']='Microsoft JhengHei'
    titles=['彎曲輪廓','轉角與交會','密集結構','紋理與邊緣','清楚原圖','清楚但有雜訊','平坦區域']
    fig,axes=plt.subplots(2,7,figsize=(16,5.5),facecolor='#f8fafc')
    entries=[]
    for col,category in enumerate(cfg['categories']):
        index=next(i for i in range(512) if parameters('train',i)[0]['category']==category)
        p=ROOT/'data/package/train'/f'{index:04d}.npz'
        with np.load(p) as a:
            source=a['source'][0,128:256,128:256]/255;target=a['target'][0,128:256,128:256]
        for row,value in enumerate([source,target]):
            axes[row,col].imshow(value,cmap='gray',vmin=0,vmax=1);axes[row,col].set_xticks([]);axes[row,col].set_yticks([])
        axes[0,col].set_title(titles[col],fontsize=13,pad=10)
        entries.append(dict(category=category,parent=f'r128_train_{index:04d}',source=record(p)))
    axes[0,0].set_ylabel('模型看到的照片',fontsize=12);axes[1,0].set_ylabel('生成時已知的清楚影像',fontsize=12)
    fig.suptitle('R128 訓練資料：照片與學習目標分開，真實顯微與 SEM 留作檢查',fontsize=17,y=.98)
    fig.text(.5,.03,'每類依編號取第一個訓練場景；亮度採同一顯示範圍。這些都是程式生成的影像。',ha='center',fontsize=11,color='#334155')
    fig.tight_layout(rect=[0,.06,1,.93])
    out=ROOT/'reports/figures';out.mkdir(parents=True,exist_ok=True);fig.savefig(out/'training_examples.png',dpi=150);plt.close(fig)
    save(out/'training_examples_sources.json',entries)

if __name__=='__main__':main()
