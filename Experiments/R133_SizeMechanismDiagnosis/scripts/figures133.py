from common133 import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':'Microsoft JhengHei','axes.unicode_minus':False,'font.size':10})

def main():
    out=ROOT/'reports/figures';out.mkdir(exist_ok=True)
    real=pd.read_csv(ROOT/'results/real/summary.csv').set_index('arm');arms=['Raw','Optics','Neural','Final','NoOptics','ResidualHP','DirectResidual'];labels=['原圖','僅光學','網路輸出','目前最終','關閉光學','改細節差量','改完整差量']
    fig,axes=plt.subplots(1,2,figsize=(12,4),constrained_layout=True)
    for ax,key,title in zip(axes,['diameter_error_nm','centered_shape_nm'],['真實SEM尺寸差距','扣除平均大小的細形狀差距']):
        values=real.loc[arms,key];ax.bar(range(len(arms)),values,color=['#9a9a9a','#d6ac62','#7ea6a0','#2a718e','#ac8db1','#73a29a','#73a29a']);ax.set_xticks(range(len(arms)),labels,rotation=25,ha='right');ax.set(ylabel='奈米',title=title+'（越低越好）');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.margins(y=.18)
        for i,v in enumerate(values):ax.text(i,v+.5,f'{v:.2f}',ha='center',fontsize=8)
    fig.suptitle('固定R129與相同16像素保護；這些是拆解，不是重新訓練的新模型',fontsize=11);fig.savefig(out/'real_stage_diagnosis.png',dpi=170);plt.close(fig)
    t=pd.read_csv(ROOT/'results/controls/measurements.csv');fig,axes=plt.subplots(1,2,figsize=(10,4),constrained_layout=True)
    for arm,label,color in [('Raw','模糊輸入','#999999'),('Final','R129輸出','#27788d')]:
        g=t[t.arm==arm].groupby('sigma').diameter_bias_px
        med=g.median();lo=g.quantile(.1);hi=g.quantile(.9)
        axes[0].plot(med.index,med.values,'o-',label=label,color=color);axes[0].fill_between(med.index,lo.values,hi.values,color=color,alpha=.12)
    axes[0].axhline(0,color='black',lw=1);axes[0].set(xlabel='已知模糊程度',ylabel='量到的直徑－真直徑（像素）',title='理想控制：偏小輸入常被往外修回');axes[0].legend();axes[0].grid(alpha=.2)
    axes[1].scatter(t[t.arm=='Raw'].diameter_bias_px,t[t.arm=='Final'].diameter_bias_px,color='#27788d');axes[1].axhline(0,color='black',lw=.8);axes[1].axvline(0,color='black',lw=.8);axes[1].set(xlabel='輸入的直徑偏差（像素）',ylabel='R129的直徑偏差（像素）',title='64個條件：仍有失敗，並非全部修好');axes[1].grid(alpha=.2)
    fig.suptitle('陰影為條件間第10–90百分位，並非信賴區間；無SEM樣品進入生成',fontsize=10);fig.savefig(out/'controlled_size_direction.png',dpi=170);plt.close(fig)
    gen=pd.read_csv(ROOT/'results/generated/summary.csv').set_index('arm');fig,ax=plt.subplots(figsize=(8,4),constrained_layout=True);a=['Raw','Final','ResidualHP','DirectResidual'];labels=['原圖','目前完整模型','直接換成細節差量','直接換成完整差量'];v=gen.loc[a,'mae_gray'];ax.bar(labels,v,color=['#999999','#27788d','#be935e','#be935e']);ax.set(ylabel='影像平均誤差（灰階）',title='128個既有生成測試：新公式直接套舊權重反而較差');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    for i,n in enumerate(v):ax.text(i,n+.04,f'{n:.3f}',ha='center')
    fig.savefig(out/'frozen_swap_not_repair.png',dpi=160);plt.close(fig);print('R133 figures generated',flush=True)
if __name__=='__main__':main()
