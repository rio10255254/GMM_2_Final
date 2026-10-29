from common import *
import argparse,re,collections
import numpy as np,pandas as pd,cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUT=ROOT/'results/lsc/analysis';T=OUT/'tables';REPORT=ROOT/'reports/R136_LSC_RESULTS.md'

def prepare():
    plan=load(ROOT/'config/plan.json');cfg=load(ROOT/'config/lsc_plan.json');assert load(OUT/'verification.json')['complete']
    assert sha(str(PROJECT_ROOT / cfg['core_source']['path']))==cfg['core_source']['sha256']
    counts={};centers=pd.read_csv(T/'all_circle_centers.csv');pairs=pd.read_csv(T/'all_individual_circle_pairs.csv');readout=pd.read_csv(T/'all_measurements.csv')
    for model in ['Raw','R61','R129']:
        c=centers[centers.model==model];assert len(c)==8370 and len(c.drop_duplicates(['run','index','pillar_id']))==8370
        assert c.groupby(['run','index']).size().eq(9).all()
        assert load(ROOT/'results/lsc/centers'/model/'complete.json')['frames']==930
        if model!='Raw':
            complete=load(ROOT/'results'/model/'complete.json');assert len(complete['records'])==930
            assert sha(plan['models'][model]['checkpoint']['path'])==plan['models'][model]['checkpoint']['sha256']
            for r in complete['records']:
                assert Path(r['values']['path']).is_file() and Path(r['image']['path']).is_file()
        counts[model]=dict(frames=930,centers=8370,scans=30,adjacent=900,start_relative=900)
    keys=['model','run','kind','i','j'];aggregated=pairs.groupby(keys)[['dx_px','dy_px']].median().reset_index();main=readout[readout.view=='nominal_all30'];joined=main.merge(aggregated,on=keys,suffixes=('','_from_centers'),validate='one_to_one');assert len(joined)==5400
    diff=float(np.max(np.abs(joined[['dx_px','dy_px']].to_numpy()-joined[['dx_px_from_centers','dy_px_from_centers']].to_numpy())));assert diff<1e-7
    sources={(f['run'],f['index']):f for f in plan['frames']};pi_error=0.
    for r in main.itertuples(index=False):
        a,b=sources[(r.run,r.i)],sources[(r.run,r.j)]
        pi_error=max(pi_error,abs(r.pi_dy_um-(b['pi_y_um']-a['pi_y_um'])))
    assert pi_error<1e-7
    # Actual first/last R129 circles are displayed alongside the other two methods.
    fig,axes=plt.subplots(2,3,figsize=(14,8),layout='constrained')
    for ri,f in enumerate([plan['frames'][0],plan['frames'][-1]]):
        for ci,model in enumerate(['Raw','R61','R129']):
            if model=='Raw':image=cv2.imread(f['source']['path'],0).astype(float)/255
            else:
                with np.load(ROOT/'results'/model/f['run']/f"{f['index']+1:02d}.npz") as z:image=z['output']
            c=centers[(centers.model==model)&(centers.run==f['run'])&(centers['index']==f['index'])].sort_values('pillar_id')
            with np.load(ROOT/'results/lsc/centers'/model/(f['run']+'.npz')) as z:points=z['points'][f['index']]
            ax=axes[ri,ci];ax.imshow(image,cmap='gray',vmin=0,vmax=1)
            for (_,r),p in zip(c.iterrows(),points):
                ax.plot(p[:,0],p[:,1],'.',ms=2,color='#F2BC4D');ax.plot(r.center_x_px,r.center_y_px,'+',color='#00CFFF');ax.add_patch(Circle((r.center_x_px,r.center_y_px),r.radius_px,fill=False,edgecolor='#00CFFF',lw=.8))
            ax.set_xlim(c.seed_x_px.min()-18,c.seed_x_px.max()+18);ax.set_ylim(c.seed_y_px.max()+18,c.seed_y_px.min()-18);ax.set_title(model+' | '+('first capture / first frame' if ri==0 else 'last capture / last frame'));ax.set_xlabel('Image x (px)');ax.set_ylabel('Image y (px)')
    fig.suptitle('Same 9 LSC targets | yellow: measured edge | cyan: fitted circle and center');fig.savefig(ROOT/'reports/lsc_figures/01_circle_fit_check.png',dpi=200);fig.savefig(ROOT/'reports/lsc_figures/01_circle_fit_check.pdf');plt.close(fig)
    p=pd.read_csv(T/'paired_comparisons.csv');sub=p[(p.view=='nominal_all30')&(p.candidate=='R129')&(p.reference=='R61')&(p.metric=='mae_nm')]
    q=pd.read_csv(T/'repeatability_comparisons.csv');q=q[(q.view=='nominal_all30')&(q.candidate=='R129')&(q.reference=='R61')]
    lead='''## 三組完成後的主要結論

三組均已完成全部30次、930張與8370筆圓心定位。以本批20倍LSC流程來看，R129的短步平均誤差、重拍波動與最差誤差都低於R61；相對起點的長距離則沒有足夠證據判定R129優於R61。兩個模型各有較低的觀察數字，不應選一個稱為全面勝出。

R129相較R61，短步30次中24次改善、6次退步，平均絕對誤差少1.069nm；長距離只有5次改善、25次退步，平均誤差多0.444nm，但平均差的95%範圍仍包含零。長距離重拍波動雖然R129較小，兩模型的差異範圍也包含零。這些配對結果與模型相對原圖的改善是不同問題。

'''
    lines=[]
    for _,r in sub.iterrows():lines.append(f'- {r["kind"]}：R129減R61的平均誤差差距{r.candidate_minus_reference_mean_nm:.6f}nm，95%範圍[{r.ci95_low:.6f},{r.ci95_high:.6f}]nm；時間分組範圍[{r.block3_ci95_low:.6f},{r.block3_ci95_high:.6f}]nm。')
    for _,r in q.iterrows():lines.append(f'- {r["kind"]}重拍波動：R129減R61為{r.difference_nm:.6f}nm，95%範圍[{r.ci95_low:.6f},{r.ci95_high:.6f}]nm。')
    text=REPORT.read_text(encoding='utf-8');text=text.replace('## 完成範圍與主要數值',lead+'\n'.join(lines)+'\n\n## 完成範圍與主要數值',1);text=text.replace('實際圓心與取邊核對（原圖／R61代表案例）','實際圓心與取邊核對（三組首末代表案例）');text=text.replace('座標相减','座標相減')
    text+='\n## 完成與版本\n\n三組完整統計完成於2026-09-17。先前18頁PDF及R61閱讀壓縮包仍是原圖／R61版，保留不變，未聲稱包含R129。本份報告及results/lsc/analysis/tables才是三方法完整結果。\n'
    REPORT.write_text(text,encoding='utf-8')
    save(OUT/'closeout_checked.json',dict(counts=counts,aggregate_pairs=5400,max_median_difference_px=diff,max_PI_join_difference_um=pi_error,original_R61_package=load(ROOT/'output/package_delivery.json')['archive'],completed_utc=now()))
    print('Checked complete three-method LSC; report and overlay ready for visual review')

def register():
    assert load(OUT/'visual_review.json')['passed'];checked=load(OUT/'closeout_checked.json');assert sha(checked['original_R61_package']['path'])==checked['original_R61_package']['sha256']
    rel=REPORT.relative_to(REPO).as_posix();key=load(OUT/'key_results.json')
    note=f'**R136 LSC完整結果（2026-09-17）：** 原圖／R61／R129各930張、8370圓心完成；短步平均絕對PI差距8.667／5.160／4.092nm，起點相對17.738／15.267／15.712nm。R129短步優於R61；長距離兩模型差距未明確，不能全面排名。全部25110圓心獨立重算、5400合併位移與PI對應核對。R61既有PDF包保留。無模型升級。[三組LSC結果]({rel})'
    p=REPO/'PROJECT_STATE.md';s=p.read_text(encoding='utf-8-sig');s=re.sub(r'(?m)^\*\*R136 LSC先行結果.*$',note,s);s=re.sub(r'(?m)^Last updated:.*$','Last updated: 2026-09-17（R136三組完整LSC與核對完成；R129短步較佳，長距離無全面勝出）',s,count=1);p.write_text(s,encoding='utf-8')
    p=REPO/'ESTIMATOR_POLICY.json';policy=load(p);baseline=policy['formal_baseline'].copy();e=next(x for x in policy['open_side_tracks'] if x.get('candidate_id')=='r136_pi_repeatability');e.update(status='three_method_LSC_complete_research_only',report=rel,models_completed=['Raw','R61','R129'],main_results=key['tables'],comparisons=key['comparisons'],notes='Complete30capture,common9circle thesisLSC. R129shortstepsimprovevsR61;longdistance differences inconclusive. Prior phase readout separate. PriorR61PDFpackagepreserved. No modelpromotion.',model_promoted=False);assert policy['formal_baseline']==baseline;save(p,policy)
    p=REPO/'Experiments/INDEX.md';s=p.read_text(encoding='utf-8-sig');s=re.sub(r'(?m)^\| R136 PI重拍比較 \|.*$',f'| R136 PI重拍比較 | [三組完整LSC](R136_PIRepeatability/reports/R136_LSC_RESULTS.md) | 各8370圓心完成；短步8.667／5.160／4.092nm，長距離17.738／15.267／15.712nm；R129短步較佳，無全面升級 |',s);p.write_text(s,encoding='utf-8')
    p=ROOT/'README.md';s=p.read_text(encoding='utf-8');s=s.replace('\n','\n\n**三組完整LSC已完成：[原圖／R61／R129比較](reports/R136_LSC_RESULTS.md)。以下先行結果與R61閱讀包保留為歷史版本。**\n',1);p.write_text(s,encoding='utf-8')
    for file in ['MANIFEST.md','HANDOFF.md']:
        with (ROOT/file).open('a',encoding='utf-8') as f:f.write('\n## Full LSC closeout2026-09-17\n\nAllRaw/R61/R129930framesand8370centers eachcomplete;25110independentcirclefits,5400aggregatepairs andPIjoins checked. reports/R136_LSC_RESULTS.md current. R129better shortsteps;longrangevsR61inconclusive. All5figuresvisuallyreviewed includingnew3-methodfirst/lastcircleoverlay. PriorR61PDF/ZIP unchanged. No training/promotion. Automation r136 can be paused.\n')
    p=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';reg=load(p);e=next(x for x in reg['entries'] if x.get('id')=='r136_pi_repeatability');e.update(state='complete_three_method_LSC_research_results',report=rel);reg['updated_at']=now();save(p,reg)
    pub=load(OUT/'published.json');pub['report']=record(REPORT);pub['figures']=[record(p) for p in sorted((ROOT/'reports/lsc_figures').glob('*.png'))];save(OUT/'published.json',pub)
    delivery=dict(status='complete',counts=checked['counts'],report=record(REPORT),figures=pub['figures'],verification=record(OUT/'verification.json'),additional_checks=record(OUT/'closeout_checked.json'),visual_review=record(OUT/'visual_review.json'),R61_package_unchanged=True,completed_utc=now())
    save(OUT/'delivery_complete.json',delivery);save(ROOT/'results/delivery_complete.json',delivery);save(ROOT/'runs/launcher_logs/active_formal_run.json',dict(status='complete',models=['Raw','R61','R129'],frames_each=930,centers_each=8370,method='thesis_LSC',training_updates=0,completed_utc=now()));save(ROOT/'results/lsc/delivery_status.json',dict(status='complete',stage='delivered',updated_utc=now()));print('Complete three-method LSC registered')
if __name__=='__main__':
    if '--register' in sys.argv:register()
    else:prepare()
