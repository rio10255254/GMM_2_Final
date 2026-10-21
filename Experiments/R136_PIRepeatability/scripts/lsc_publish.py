from common import *
import argparse,shutil
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
COLORS={'Raw':'#565D67','R61':'#117C99','R129':'#C56B2A','R128':'#8056A3'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.16,'savefig.dpi':200})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--models',nargs='+',default=['Raw','R61','R129']);ap.add_argument('--output',default='results/lsc/analysis');ap.add_argument('--report',default='reports/R136_LSC_RESULTS.md');ap.add_argument('--figures',default='reports/lsc_figures');args=ap.parse_args()
    out=ROOT/args.output;t=out/'tables';figdir=ROOT/args.figures;figdir.mkdir(parents=True,exist_ok=True);report=ROOT/args.report
    audit=load(out/'verification.json');assert audit['complete'];cfg=load(ROOT/'config/lsc_plan.json');cal=load(t/'calibration.json')
    s=pd.read_csv(t/'summary.csv');r=pd.read_csv(t/'repeatability.csv');p=pd.read_csv(t/'paired_comparisons.csv');rp=pd.read_csv(t/'repeatability_comparisons.csv');positions=pd.read_csv(t/'per_position.csv');scans=pd.read_csv(t/'per_scan.csv');individual=pd.read_csv(t/'individual_circle_summary.csv');within=pd.read_csv(t/'within_grid_variation.csv')
    comparisons=[];table_rows=[]
    for view in ['nominal_all30','calibrated_late24']:
        for kind in ['adjacent','start']:
            ss=s[(s.view==view)&(s.kind==kind)].set_index('model');rr=r[(r.view==view)&(r.kind==kind)].set_index('model')
            for model in args.models:
                row=ss.loc[model];table_rows.append(dict(view=view,kind=kind,model=model,scans=int(row.scans),mae_nm=float(row.mae_nm_mean),bias_nm=float(row.bias_nm_mean),repeatability_nm=float(rr.loc[model,'mean_position_sd_nm']),maximum_error_nm=float(row.largest_error_nm)))
            for model in args.models:
                if model=='Raw':continue
                pair=p[(p.view==view)&(p.kind==kind)&(p.metric=='mae_nm')&(p.candidate==model)&(p.reference=='Raw')].iloc[0]
                delta=rp[(rp.view==view)&(rp.kind==kind)&(rp.candidate==model)&(rp.reference=='Raw')].iloc[0]
                comparisons.append(dict(view=view,kind=kind,model=model,mae_reduction_percent=float((1-ss.loc[model,'mae_nm_mean']/ss.loc['Raw','mae_nm_mean'])*100),repeatability_reduction_percent=float((1-rr.loc[model,'mean_position_sd_nm']/rr.loc['Raw','mean_position_sd_nm'])*100),improved_scans=int(pair.improved_scans),worsened_scans=int(pair.worsened_scans),mae_improvement_ci95=[float(-pair.ci95_high),float(-pair.ci95_low)],mae_improvement_block_ci95=[float(-pair.block3_ci95_high),float(-pair.block3_ci95_low)],repeatability_improvement_ci95=[float(-delta.ci95_high),float(-delta.ci95_low)]))
    summary=pd.DataFrame(table_rows);summary.to_csv(t/'readable_lsc_summary.csv',index=False,encoding='utf-8-sig');save(out/'key_results.json',dict(method='LSC_center9_median',tables=table_rows,comparisons=comparisons,centers_per_model=8370,scans=30,frames_per_model=930))
    def finish(fig,name):
        fig.savefig(figdir/(name+'.png'),bbox_inches='tight');fig.savefig(figdir/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
    shutil.copy2(ROOT/'results/lsc/lsc_probe.png',figdir/'01_circle_fit_check.png')
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
    for ax,kind,label in zip(axes,['adjacent','start'],['Adjacent steps','Relative to scan start']):
        for model in args.models:
            g=positions[(positions.view=='nominal_all30')&(positions.kind==kind)&(positions.model==model)].sort_values('position_index');x=g.position_index.to_numpy();mean=g.bias_nm.to_numpy();sd=g.repeatability_sd_nm.to_numpy();ax.plot(x,mean,label=model,color=COLORS[model]);ax.fill_between(x,mean-sd,mean+sd,color=COLORS[model],alpha=.14)
        ax.axhline(0,color='#888',lw=.8);ax.set(title=label,xlabel='Position index',ylabel='LSC displacement minus PI (nm)');ax.legend(frameon=False)
    fig.suptitle('Same 9-circle LSC readout | 30 captures | band: +/- 1 SD across captures');finish(fig,'02_position_error')
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
    for ax,kind,label in zip(axes,['adjacent','start'],['Adjacent steps','Relative to scan start']):
        for model in args.models:
            g=scans[(scans.view=='nominal_all30')&(scans.kind==kind)&(scans.model==model)].sort_values('run_index');ax.plot(g.run_index,g.mae_nm,'o-',ms=3,color=COLORS[model],label=model)
        ax.axvline(6.5,ls='--',lw=.9,color='#999');ax.set(title=label,xlabel='Capture number',ylabel='Mean absolute PI-referenced error (nm)',ylim=(0,None));ax.legend(frameon=False)
    fig.suptitle('LSC: each point is one complete capture');finish(fig,'03_capture_comparison')
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
    for ax,kind,label in zip(axes,['adjacent','start'],['Adjacent steps','Relative to scan start']):
        for model in args.models:
            g=positions[(positions.view=='nominal_all30')&(positions.kind==kind)&(positions.model==model)].sort_values('position_index');ax.plot(g.position_index,g.repeatability_sd_nm,color=COLORS[model],label=model)
        ax.set(title=label,xlabel='Position index',ylabel='SD across 30 repeated captures (nm)',ylim=(0,None));ax.legend(frameon=False)
    fig.suptitle('LSC repeatability | same position across 30 captures');finish(fig,'04_repeatability')
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained');width=.75/len(args.models)
    for ax,kind,label in zip(axes,['adjacent','start'],['Adjacent steps','Relative to scan start']):
        for n,model in enumerate(args.models):
            g=individual[(individual.kind==kind)&(individual.model==model)].sort_values('pillar_id');x=g.pillar_id.to_numpy();ax.bar(x+(n-(len(args.models)-1)/2)*width,g.mae_nm,width=width,color=COLORS[model],label=model)
        ax.set_xticks(range(1,10));ax.set(title=label,xlabel='Tracked circle ID',ylabel='Single-circle mean absolute error (nm)',ylim=(0,float(individual[individual.kind==kind].mae_nm.max())*1.25));ax.legend(frameon=False)
    fig.suptitle('All 9 targets reported individually | not 9 independent experiments');finish(fig,'05_individual_circles')
    def table(view):
        a=summary[summary.view==view].copy();a.kind=a.kind.map({'adjacent':'每一步','start':'相對起點'});a.model=a.model.replace({'Raw':'原圖'});a=a[['kind','model','mae_nm','repeatability_nm','maximum_error_nm']];a.columns=['位移','方法','平均絕對誤差nm','重拍波動nm','最大誤差nm'];return a.to_markdown(index=False,floatfmt='.3f')
    text=['# R136：LSC圓心定位的30次位移比較','',
    '**這份才是LSC主結果。**直接沿用論文的取邊與最小平方圓心定位程式，對同一組9顆圓逐張量測，再將前後圓心座標相減。前面的影像區域比對報告另外保留為方法比較，不能當作LSC結果。','',
    '## 完成範圍與主要數值','',
    '每個方法均完成30次掃描、930張影像、8370筆圓心定位。每一步900段、相對起點900筆；以下是9顆圓位移合併後的結果。合併沿用論文：分別取9顆圓X與Y位移的中位數。不能把這些數字說成單顆圓的定位能力。','',table('nominal_all30'),'']
    for c in [x for x in comparisons if x['view']=='nominal_all30']:
        label='每一步' if c['kind']=='adjacent' else '相對起點';lo,hi=c['mae_improvement_ci95'];blo,bhi=c['mae_improvement_block_ci95']
        text.append(f'- {c["model"]} {label}：平均絕對誤差改善{c["mae_reduction_percent"]:.2f}%，重拍波動改善{c["repeatability_reduction_percent"]:.2f}%；30次中{c["improved_scans"]}次改善、{c["worsened_scans"]}次退步。平均改善量95%範圍[{lo:.3f}, {hi:.3f}]nm；連續3次成組重抽為[{blo:.3f}, {bhi:.3f}]nm。負改善代表退步。')
    text += ['', '重拍波動：在每個相同位置，計算30次誤差的標準差，再取30個位置的平均。不是把同一掃描的30步混算，也不是除以√30後的平均值不確定度。95%範圍以完整掃描重抽10000次；9顆圓不當作9個獨立實驗。','',
    '## 個別9顆圓與同張影像的一致性','']
    per=individual.pivot(index=['kind','pillar_id'],columns='model',values='mae_nm').reset_index();per.kind=per.kind.map({'adjacent':'每一步','start':'相對起點'});text += ['下表為每顆圓各自的平均絕對誤差（nm），未先合併9顆圓。', '',per.to_markdown(index=False,floatfmt='.3f'),'']
    for model in args.models:
        if model=='Raw':continue
        for kind in ['adjacent','start']:
            a=individual[individual.kind==kind].pivot(index='pillar_id',columns='model',values='mae_nm');text.append(f'- {model}（{kind}）：9顆圓中{int((a[model]<a.Raw).sum())}顆平均誤差改善。')
    text += ['', '每一段的9顆圓位移不一致程度保存在within_grid_variation.csv。它反映同張影像內的分散，不能直接等同與PI的真實誤差。','',
    '## 尺度與分開檢驗','',f'相機Basler acA2040-120um、20倍，名義尺度0.1725μm/px。只用前6次原圖LSC位移估計方向與尺度，得到{cal["estimated_um_per_px"]:.9f}μm/px，固定給所有方法後24次使用；R61或R129結果不參與校正。','',table('calibrated_late24'),'','## 定位方式與驗證','',
    '- 原圖影像中的黑色連通區只用來辨識同一顆圓所在範圍，不作最終位移值。未利用PI答案決定圓心，未把原圖圓心複製給重建圖。',
    '- 每張影像對每顆圓獨立取邊，再作幾何最小平方圓擬合。20倍沿用64個等弧長輪廓點、13次粗輪廓演化、法線兩側2.4像素搜索，並重設輪廓演化順序以保證重算一致。',
    '- 樣品不同於舊論文拍攝，初始圓的位置與約8.33像素半徑由本批原圖取得。共用同一組9顆圓及相同設定，沒有依哪個模型分數較好另選目標。',
    f'- 全部{audit["independent_circle_fits"]}組保存邊界點用另一個幾何圓心求解重算，最大圓心差{audit["max_independent_center_difference_px"]:.3g}像素；逐顆座標相减、代表影像重跑、PI換算均已核對。',
    '- 圓心及每顆圓的完整取邊點皆保存，可直接畫回影像核對；未剔除不利影格或圓。','',
    '## 結論的範圍','',
    '這是同一樣品、同次20倍拍攝、指定9顆圓及LSC流程的PI參照結果。改善不能直接外推到其他形狀、倍率、不同天，也不等於已認證圓的真實直徑或形狀。影像中的側向只作補充，沒有獨立X方向行程來認證完整二維尺度。', '',
    'PI校正證書、獨立有效倍率不確定度與殘餘拍攝／回授時間差未提供，因此本報告呈現重拍散布及PI差距，不捏造完整量測不確定度。前6次與後24次拍攝節奏不同，時間分段與趨勢也保留在表格中。','',
    '## 圖表','']
    for file,label in [('01_circle_fit_check','實際圓心與取邊核對（原圖／R61代表案例）'),('02_position_error','各位置平均誤差與30次波動'),('03_capture_comparison','30次逐次比較'),('04_repeatability','同一位置重拍的波動'),('05_individual_circles','每顆圓的完整比較')]:text += [f'![{label}]({figdir.name}/{file}.png)','']
    prefix=Path(os.path.relpath(t,report.parent)).as_posix();text += ['## 表格與資料','',f'- [主要結果總表]({prefix}/readable_lsc_summary.csv)',f'- [每次掃描及指標]({prefix}/per_scan.csv)',f'- [各位置30次的變動範圍]({prefix}/per_position.csv)',f'- [配對改善與95%範圍]({prefix}/paired_comparisons.csv)',f'- [所有圓心座標]({prefix}/all_circle_centers.csv)',f'- [每顆圓逐段位移與PI對照]({prefix}/all_individual_circle_pairs.csv)',f'- [每顆圓的統計]({prefix}/individual_circle_summary.csv)','',
    '舊影像區域比對報告不改數字，但必須與本份LSC報告分開引用。', '']
    if 'R129' not in args.models:text += ['R129重建及LSC定位仍在背景接續，本份僅交付已完整完成的原圖／R61比較。','']
    report.write_text('\n'.join(text),encoding='utf-8');save(out/'published.json',dict(report=record(report),figures=[record(p) for p in sorted(figdir.glob('*.png'))],completed_utc=now()))
    print(summary.to_string(index=False),flush=True)
if __name__=='__main__':main()
