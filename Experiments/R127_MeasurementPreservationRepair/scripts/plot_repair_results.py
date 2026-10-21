import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from common import *

def main():
    font_manager.fontManager.addfont('C:/Windows/Fonts/msjh.ttc');plt.rcParams['font.family']='Microsoft JhengHei';plt.rcParams['axes.unicode_minus']=False;out=ROOT/'reports/figures';out.mkdir(exist_ok=True)
    context=json.loads((ROOT/'results/real_motion_v4/verification.json').read_text());full=json.loads((ROOT/'results/fullfield_motion/verification.json').read_text())
    fig,ax=plt.subplots(figsize=(8,5));counts=[context['local128_valid'],context['accepted_context_pairs'],full['accepted_pairs']+context['valid_full_field_Raw']];bars=ax.bar(['128像素小區塊','原先保存的較大區塊','完整視野'],counts,color=['#bc826c','#cca650','#4e8c9d']);ax.bar_label(bars,labels=[f'{v}/30' for v in counts],padding=5,fontsize=13);ax.set_ylim(0,35);ax.set_ylabel('可判定的影像配對數');ax.set_title('增加真實影像線索，處理小區塊的配對歧義\n原圖與四模型 × 六組影像；不是30個獨立樣品');ax.spines[['top','right']].set_visible(False);fig.text(.5,.01,'較大視野量到的是該視野的主要位移，不能把小區塊的未知結果改稱有效。',ha='center',fontsize=10);fig.tight_layout(rect=(0,.05,1,1));fig.savefig(out/'motion_information_scope.png',dpi=160);plt.close(fig)
    table=pd.read_csv(ROOT/'results/readout_definition_probe/summary.csv');fig,ax=plt.subplots(figsize=(8,5))
    for definition,label,style in [('central_3_to15','柱子中央亮度作內側參考','o-'),('inner_24_to28','較靠近邊緣的亮度作內側參考','s--')]:
        r=table[(table.exposure==24)&(table.method=='Q_s1265002')&(table.definition==definition)].sort_values('level');ax.plot(r.level*100,r.mean_radius_change_vs_Raw,style,label=label)
    ax.axhline(0,c='.4',lw=1);ax.set_xticks([30,50,70],['過渡30%位置','過渡50%位置','過渡70%位置']);ax.set_ylabel('相對原圖的位置變化（像素）\n正值向外、負值向內');ax.set_title('同一模型、同一批暗影像，取邊位置不同會得到不同方向\n這是亮暗過渡形狀改變，不能直接等同材料尺寸改變');ax.grid(alpha=.2);ax.legend(fontsize=9);fig.tight_layout();fig.savefig(out/'edge_definition_sensitivity.png',dpi=160);plt.close(fig)

if __name__=='__main__':main()
