"""Report the completed comparisons; no performance-selected model changes."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

def md_table(frame,columns,formats=None):
    formats=formats or {};lines=['| '+' | '.join(columns.values())+' |','| '+' | '.join(['---']*len(columns))+' |']
    for _,row in frame.iterrows():lines.append('| '+' | '.join(format(row[k],formats[k]) if k in formats else str(row[k]) for k in columns)+' |')
    return '\n'.join(lines)

def main():
    out=ROOT/'results/lsc_comparison';v=load(out/'verification.json');assert v['all7primary_methods_same120pairs']
    assessment=load(out/'assessment.json');summary=pd.read_csv(out/'combined_summary.csv');full=summary[summary.scope=='all_four_sequences'].set_index('method')
    methods=['Raw','Wiener','R61v16_PSFOFF','R109 E48','R119_B_E42','R128_P_s1285002'];labels=['原圖','傳統處理','R61','R109','R119','R128'];names=dict(zip(methods,labels));colors=['#949DA5','#BAC0C5','#6A8EA6','#366887','#8B9CA8','#D58236']
    metrics=['step_sd_nm','median_within_grid_sd_nm','mean_nominal_abs_error_nm','median_cross_axis_abs_nm']
    titles=['量到的步距波動','不同柱體量出的位移不一致','與設定步距的差距','橫向偏移']
    font_manager.fontManager.addfont('C:/Windows/Fonts/msjh.ttc');plt.rcParams['font.family']='Microsoft JhengHei'
    fig,axes=plt.subplots(2,2,figsize=(11.3,8.3))
    for ax,metric,title in zip(axes.flat,metrics,titles):
        values=full.loc[methods,metric].to_numpy();bars=ax.bar(labels,values,color=colors,width=.66)
        ax.set_ylim(0,values.max()*1.22);ax.set_title(title,fontsize=13);ax.set_ylabel('奈米；越小越好');ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True);ax.spines[['top','right']].set_visible(False)
        for bar,value in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,value+values.max()*.025,f'{value:.2f}',ha='center',fontsize=10)
    fig.suptitle('相同 120 對實拍影格：R128 與 R61、近期模型的位移比較',fontsize=17,y=.98)
    fig.text(.5,.035,'四組資料各 30 對、每次同樣 9 顆柱體；第一項先算各組波動再平均。\n設定步距不是獨立實際位置真值；本圖比較穩定性，不能直接當作物理準確度。',ha='center',fontsize=10,linespacing=1.5)
    fig.tight_layout(rect=[0,.10,1,.95],h_pad=2.3,w_pad=2.2)
    figure=ROOT/'reports/figures/R128_R61_LSC_comparison.png';assert not figure.exists();fig.savefig(figure,dpi=155);plt.close(fig)
    seqs=['50x_x_0p5um','50x_x_1um','20x_0p5um','20x_1um'];sl=['50×／0.5 微米','50×／1 微米','20×／0.5 微米','20×／1 微米']
    g=summary[summary.scope=='per_sequence'].pivot(index='sequence',columns='method',values='step_sd_nm').loc[seqs]
    fig,ax=plt.subplots(figsize=(11.3,5.7));x=np.arange(4);chosen=['Raw','R61v16_PSFOFF','R109 E48','R128_P_s1285002'];width=.19
    for i,method in enumerate(chosen):
        values=g[method].to_numpy();bars=ax.bar(x+(i-1.5)*width,values,width,label=names[method],color=colors[methods.index(method)],edgecolor='#444444',linewidth=.3)
        for bar,value in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,value+.22,f'{value:.2f}',ha='center',fontsize=9)
    ax.set_xticks(x,sl);ax.set_ylim(0,g[chosen].to_numpy().max()*1.24);ax.set_ylabel('量到的步距波動（奈米；越小越好）');ax.legend(ncol=4,frameon=False);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.spines[['top','right']].set_visible(False)
    ax.set_title('逐組比較：每組都是相同的 30 對影格',fontsize=16,pad=18);fig.tight_layout()
    seqfig=ROOT/'reports/figures/R128_R61_LSC_by_sequence.png';assert not seqfig.exists();fig.savefig(seqfig,dpi=155);plt.close(fig)
    lines=['# R128 與 R61、近期模型：完整同條件位移比較','',assessment['lead'],'',*assessment['findings'],'',
        '## 版本與比較範圍','',
        '正式專案基準仍是 COMBO。本次 R128 P_s1285002 step8192 是現有唯一研究試用候選；R61 是 2026-06-23 v16 的 best_tradeoff、既有 PSF-off 使用設定；R109 是 E48，R119 是 B E42。V42 E120 為歷史論文結果模型，與 R61 是不同權重。此次沒有新訓練或更換任何模型。','',
        '四組 20×/50× 真實位移序列，159 張不同影格構成原先固定的 120 對相鄰影格，每組 30 對、每次 9 顆相同柱體。沒有替模型重新挑影格；原先名單偏向原圖較穩定的影格，因此這不是所有拍攝條件的無條件成績。相鄰影格對會共用照片，不視為 120 次獨立實驗。','',
        'R128 新處理 150 張完整照片，另外 9 張使用同權重、來源一致且已核對的既有輸出。R61 使用 159 張既有重建，另以原本推理設定重新處理每組一張、共四張完整照片，皆逐像素重現當年結果。兩者都先處理整張照片，再使用相同位置取出相同柱體進行 LSC。','',
        '## 位移比較','',
        '全部越小越好。「步距波動」先計算各組 30 次步距的標準差，再平均四組；「柱體間不一致」是同一對照片中九顆柱體量出位移的分散程度，再彙整全部 120 對。設定步距是平台命令，並非另一台儀器記錄的實際位置真值。','']
    table=full.loc[methods].reset_index();table['method']=table.method.map(names)
    columns={'method':'方法','step_sd_nm':'步距波動（奈米）','mean_nominal_abs_error_nm':'與設定步距差距（奈米）','median_within_grid_sd_nm':'柱體間不一致（奈米）','median_cross_axis_abs_nm':'橫向偏移（奈米）'}
    lines += [md_table(table,columns,{k:'.3f' for k in columns if k!='method'}),'','![相同實拍位移比較](figures/R128_R61_LSC_comparison.png)','',
        f'V42 的歷史對應數字另保留：步距波動 {full.loc["V42 E120","step_sd_nm"]:.3f} 奈米，柱體間不一致 {full.loc["V42 E120","median_within_grid_sd_nm"]:.3f} 奈米。先前已查明其訓練資料包含這批評估照片的衍生資料與 SEM 半徑答案，不能當作未見資料上的公平勝出證據。此處不推斷動機，也不把該特定重疊結論擴大套到其他權重。R119 的後續因果審查修正仍優先於舊完成與因果宣稱，這次只保留其可重現的量測成績。','',
        '## 直接與 R61 比','']
    change=[]
    for metric,title in zip(metrics,titles):
        a=float(full.loc['R61v16_PSFOFF',metric]);b=float(full.loc['R128_P_s1285002',metric]);change.append(dict(metric=title,R61=a,R128=b,improvement_pct=100*(1-b/a)))
    lines += [md_table(pd.DataFrame(change),{'metric':'項目','R61':'R61（奈米）','R128':'R128（奈米）','improvement_pct':'R128 改善（%；負值為退步）'},{'R61':'.3f','R128':'.3f','improvement_pct':'.2f'}),'','### 各組步距波動','']
    rows=g[methods].reset_index();rows['sequence']=sl;cols={'sequence':'拍攝／設定步距',**{m:names[m] for m in methods}}
    lines += [md_table(rows,cols,{m:'.3f' for m in methods}),'','![每組位移比較](figures/R128_R61_LSC_by_sequence.png)','',
        '### 最差情況也保留','']
    cols={'method':'方法','p95_nominal_abs_error_nm':'95%位置的步距差距（奈米）','max_nominal_abs_error_nm':'最大步距差距（奈米）','max_cross_axis_abs_nm':'最大橫向偏移（奈米）'}
    lines += [md_table(table,cols,{k:'.3f' for k in cols if k!='method'}),'',
        '逐對勝負是重複影格的描述，不是獨立樣本的顯著性檢定。所有逐對及逐柱結果都保存，最不利案例沒有剔除。','',
        '## 完整外輪廓、面積、周長與圓度','',
        '這部分使用先前已核對的同一 SEM 配對試片，36 顆柱體、三張正常拍攝照片；與上述位移序列不是同一批實物對應，因此不能把該 SEM 當成位移影像中柱體的同顆真值。每顆先取三張照片的中間表現，再彙整 36 顆；數字是與 SEM 的差距，越小越好。','']
    shape=pd.read_csv(ROOT/'results/competitive_review/summary.csv');shape=shape[shape.scope=='all_36'];sr=[]
    for ref,label in [('historical','既有尺度'),('global_pitch_matched','依柱距統一尺度')]:
        q=shape[shape.reference==ref].set_index('method')
        for metric,label2 in [('mean_boundary_px','輪廓差距（像素）'),('area_error_pct','面積差距（%）'),('perimeter_error_pct','周長差距（%）'),('circularity_error','圓度差距')]:
            a=float(q.loc['R61v16',metric]);b=float(q.loc['R128_P_s1285002',metric]);sr.append(dict(reference=label,metric=label2,Raw=float(q.loc['Raw',metric]),R61=a,R128=b,improvement_pct=100*(1-b/a)))
    lines += [md_table(pd.DataFrame(sr),{'reference':'SEM 參考','metric':'項目','Raw':'原圖','R61':'R61','R128':'R128','improvement_pct':'相對 R61 改善（%）'},{'Raw':'.5f','R61':'.5f','R128':'.5f','improvement_pct':'.2f'}),'',
        'R128 相對 R61 的輪廓差距整體減少約 5–6%，面積差距減少約 7–13%，周長差距減少約 64–75%，圓度差距減少約 69–75%。這不是每顆都改善同樣百分比；外輪廓較好的柱體在兩種參考下分別為 26/36 與 25/36 顆。','',
        '雖然圓度比 R61 更接近 SEM，但按柱距統一尺度後，R128 的圓度仍不如原圖；不同參考會改變它是否勝過原圖的判斷。完整輪廓平均貼合也不能保證所有局部邊緣都更準。','',
        '![R61 與 R128 的 SEM 輪廓](figures/R61_R128_SEM_comparison.png)','',
        '## 影像邊緣保留原圖的影響','',
        'R128 原本的試用設定會在整幅照片邊緣保留原圖並逐漸過渡到重建。這次先依原圖決定的量測範圍核對：50× 兩組所有量測範圍均完全使用模型；20×、0.5 微米有 180/306 個柱體影格範圍完全使用模型、27 個完全保留原圖；20×、1 微米則為 333/360 與 3 個，其餘包含過渡區。主成績完整保留這個实际使用設定。','',
        '另外只移除最後的邊緣原圖保留，使用同一次推理已保存的模型直接輸出重算，作為原因檢查；這不是另一個訓練模型，也沒有直接改成使用這個版本。','']
    diag=pd.read_csv(out/'diagnostic_summary.csv');diag=diag[(diag.scope=='all_four_sequences') & diag.method.isin(['R128_P_s1285002','R128_no_FOV_guard_diagnostic'])]
    lines += [md_table(diag,columns,{k:'.3f' for k in columns if k!='method'}),'',*assessment['boundary_findings'],'',
        '依原圖範圍決定、兩張照片的九顆柱體都完全使用模型的共同子集為 95 對（四組分別 30、30、9、26 對），所有對手使用同一子集，僅作補充診斷；不拿這個較小子集替代完整 120 對的主結果。','',
        '## 已完成的核對與下一步','',
        '原圖 159 張、1,431 顆次的圓心及 120 對位移全部重現歷史結果。Raw、R61、R128、R128 邊緣診斷共 5,724 個圓心，以保存的完整邊緣點另行擬合，並獨立重算逐對位移與彙整；所有 159 張 R128 輸出的來源、灰階匯出和原圖保留計算也逐張核對。四組 R61 代表圖重建完全重現。','',
        '所有原始模型、來源照片、舊預期雜湊和既有報告都保留；沒有重訓，也没有讀取或重新命名舊封閉確認集。','',*assessment['next_actions'],'',
        '- [固定的照片、模型與比較方法](../results/lsc_comparison/plan.json)',
        '- [逐項核對結果](../results/lsc_comparison/verification.json)',
        '- [全部模型的逐對位移](../results/lsc_comparison/combined_pairs.csv)',
        '- [各組與整體數字](../results/lsc_comparison/combined_summary.csv)',
        '- [相對 R61 最不利的各對影格](../results/lsc_comparison/worst_pairs_vs_R61.csv)',
        '- [原圖位置決定的邊緣範圍檢查](../results/lsc_comparison/source_boundary_context.csv)',
        '- [完全使用模型範圍的共同子集](../results/lsc_comparison/fully_neural_subset_summary.csv)',
        '- [此前的完整輪廓比較與限制](R128_COMPETITIVE_REVIEW.md)','']
    report=ROOT/'reports/R128_LSC_R61_COMPARISON.md'
    with report.open('x',encoding='utf-8') as f:f.write('\n'.join(lines))
    save(out/'report_record.json',dict(created_utc=now(),report=record(report),overview_figure=record(figure),sequence_figure=record(seqfig),assessment=record(out/'assessment.json'),source=record(__file__)))
    print(report)

if __name__=='__main__':main()
