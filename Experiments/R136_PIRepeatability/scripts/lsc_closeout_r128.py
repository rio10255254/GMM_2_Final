"""Close only the four-method extension; earlier deliveries remain immutable."""
from common import *
import re,zipfile
import numpy as np,pandas as pd,cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
OUT=ROOT/'results/lsc/four_model_analysis';T=OUT/'tables';FIG=ROOT/'reports/lsc_four_model_figures';REPORT=ROOT/'reports/R136_LSC_FOUR_MODEL_RESULTS.md'
MODELS=['Raw','R61','R129','R128'];COLORS={'Raw':'#565D67','R61':'#117C99','R129':'#C56B2A','R128':'#8054A5'}

def protected(plan):
    for r in plan['extension']['protected_prior_results']:assert sha(r['path'])==r['sha256'],r['path']

def prepare():
    plan=load(ROOT/'config/r128_extension.json');protected(plan);cfg=load(ROOT/'config/lsc_plan.json');audit=load(OUT/'verification.json');assert audit['complete'] and audit['independent_circle_fits']==33480
    assert sha(cfg['core_source']['path'])==cfg['core_source']['sha256'];assert sha(plan['models']['R128']['checkpoint']['path'])==plan['models']['R128']['checkpoint']['sha256']
    complete=load(ROOT/'results/R128/complete.json');assert complete['frames']==930 and len(complete['records'])==930
    for r in complete['records']:
        assert Path(r['values']['path']).is_file() and Path(r['image']['path']).is_file()
    centers=pd.read_csv(T/'all_circle_centers.csv');individual=pd.read_csv(T/'all_individual_circle_pairs.csv');main=pd.read_csv(T/'all_measurements.csv');main=main[main.view=='nominal_all30'];counts={}
    for m in MODELS:
        c=centers[centers.model==m];assert len(c)==8370 and len(c.drop_duplicates(['run','index','pillar_id']))==8370;assert c.groupby(['run','index']).size().eq(9).all();assert len(main[main.model==m])==1800
        assert load(ROOT/'results/lsc/centers'/m/'complete.json')['frames']==930
        counts[m]=dict(scans=30,frames=930,centers=8370,adjacent_pairs=900,start_pairs=900)
    # Same targets and initial search locations, without reusing another method's final centers.
    seeds=centers[centers.model=='Raw'][['run','index','pillar_id','seed_x_px','seed_y_px']]
    joined=centers[centers.model=='R128'].merge(seeds,on=['run','index','pillar_id'],suffixes=('','_raw'),validate='one_to_one');assert len(joined)==8370
    assert np.max(np.abs(joined[['seed_x_px','seed_y_px']].to_numpy()-joined[['seed_x_px_raw','seed_y_px_raw']].to_numpy()))<1e-8
    keys=['model','run','kind','i','j'];med=individual.groupby(keys)[['dx_px','dy_px']].median().reset_index();joined=main.merge(med,on=keys,suffixes=('','_from_centers'),validate='one_to_one');assert len(joined)==7200
    difference=float(np.max(np.abs(joined[['dx_px','dy_px']].to_numpy()-joined[['dx_px_from_centers','dy_px_from_centers']].to_numpy())));assert difference<1e-7
    frames={(f['run'],f['index']):f for f in plan['frames']};pi_diff=0.
    for r in main.itertuples(index=False):
        a,b=frames[(r.run,r.i)],frames[(r.run,r.j)];pi_diff=max(pi_diff,abs(r.pi_dy_um-(b['pi_y_um']-a['pi_y_um'])))
    assert pi_diff<1e-7
    old=pd.read_csv(ROOT/'results/lsc/analysis/tables/readable_lsc_summary.csv');new=pd.read_csv(T/'readable_lsc_summary.csv');sort=['view','kind','model']
    pd.testing.assert_frame_equal(old.sort_values(sort).reset_index(drop=True),new[new.model!='R128'][old.columns].sort_values(sort).reset_index(drop=True),check_exact=False,rtol=1e-9,atol=1e-9)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.16,'svg.fonttype':'none'})
    fig,axes=plt.subplots(2,4,figsize=(17,8),layout='constrained')
    for row,f in enumerate([plan['frames'][0],plan['frames'][-1]]):
        common=seeds[(seeds.run==f['run'])&(seeds['index']==f['index'])]
        for col,m in enumerate(MODELS):
            if m=='Raw':im=cv2.imread(f['source']['path'],0).astype(float)/255
            else:
                with np.load(ROOT/'results'/m/f['run']/f"{f['index']+1:02d}.npz") as z:im=z['output']
            c=centers[(centers.model==m)&(centers.run==f['run'])&(centers['index']==f['index'])].sort_values('pillar_id')
            with np.load(ROOT/'results/lsc/centers'/m/(f['run']+'.npz')) as z:pts=z['points'][f['index']]
            ax=axes[row,col];ax.imshow(im,cmap='gray',vmin=0,vmax=1);ax.grid(False)
            for (_,r),p in zip(c.iterrows(),pts):ax.plot(p[:,0],p[:,1],'.',ms=2,color='#F2BC4D');ax.plot(r.center_x_px,r.center_y_px,'+',color='#00CFFF');ax.add_patch(Circle((r.center_x_px,r.center_y_px),r.radius_px,fill=False,ec='#00CFFF',lw=.7))
            ax.set_xlim(common.seed_x_px.min()-18,common.seed_x_px.max()+18);ax.set_ylim(common.seed_y_px.max()+18,common.seed_y_px.min()-18);ax.set_title(m+' | '+('first capture, first frame' if row==0 else 'last capture, last frame'),fontsize=10);ax.set_xlabel('Image x (px)');ax.set_ylabel('Image y (px)')
    fig.suptitle('Same 9 LSC targets | yellow: measured boundary | cyan: fitted center and circle')
    fig.savefig(FIG/'01_circle_fit_check.png',dpi=220);fig.savefig(FIG/'01_circle_fit_check.svg');plt.close(fig)
    # Four legends need more headroom than the earlier three-method version.
    separate=pd.read_csv(T/'individual_circle_summary.csv');fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained');width=.18
    for ax,kind,label in zip(axes,['adjacent','start'],['Adjacent steps','Relative to scan start']):
        for n,m in enumerate(MODELS):
            g=separate[(separate.model==m)&(separate.kind==kind)].sort_values('pillar_id');ax.bar(g.pillar_id+(n-1.5)*width,g.mae_nm,width,label=m,color=COLORS[m])
        ax.set_xticks(range(1,10));ax.set(title=label,xlabel='Tracked circle ID',ylabel='Single-circle mean absolute error (nm)',ylim=(0,float(separate[separate.kind==kind].mae_nm.max())*1.5));ax.legend(frameon=False,loc='upper right')
    fig.suptitle('All 9 targets reported separately | complete 30-capture data');fig.savefig(FIG/'05_individual_circles.png',dpi=220);fig.savefig(FIG/'05_individual_circles.svg');plt.close(fig)
    p=pd.read_csv(T/'paired_comparisons.csv');q=pd.read_csv(T/'repeatability_comparisons.csv');sub=p[(p.view=='nominal_all30')&(p.candidate=='R128')&(p.metric=='mae_nm')];rq=q[(q.view=='nominal_all30')&(q.candidate=='R128')]
    lead='''## R128追加後的主要結論

四組都已完成全部30次、930張與8370笔圓心。R128相對原圖的短步平均誤差降低53.57%，重拍波動降低59.99%；相對起點誤差降低12.64%，波動降低28.57%。短步30次全改善，相對起點24次改善、6次退步。

R128和R129非常接近。R128短步平均誤差4.025nm，R129為4.092nm，只差0.067nm；兩者逐次比較各有15次較好，平均差的95%範圍包含零。R128長距離平均誤差與重拍波動數字略低於R129，但差異範圍同樣包含零，不能宣稱已證明R128全面勝過R129。短步的最大誤差反而是R129較低（16.104nm，R128為17.305nm）。

相對R61，R128短步平均誤差較小且波動較低；長距離平均誤差沒有明確優勢，R61的平均及最大誤差數字仍略低。R128的長距離重拍波動則較低。各指標需分開看，不自動更換正式模型。

以下差值皆為R128減比較對象，負值表示R128較小。

'''
    lines=[]
    for _,r in sub.iterrows():lines.append(f'- {r.reference}／{r["kind"]}平均誤差差：{r.candidate_minus_reference_mean_nm:.6f}nm；95%範圍[{r.ci95_low:.6f},{r.ci95_high:.6f}]，3次成組範圍[{r.block3_ci95_low:.6f},{r.block3_ci95_high:.6f}]；R128改善{int(r.improved_scans)}次、退步{int(r.worsened_scans)}次。')
    for _,r in rq.iterrows():lines.append(f'- {r.reference}／{r["kind"]}重拍波動差：{r.difference_nm:.6f}nm；95%範圍[{r.ci95_low:.6f},{r.ci95_high:.6f}]。')
    text=REPORT.read_text(encoding='utf-8');text=text.replace('# R136：LSC圓心定位的30次位移比較','# R136：原圖、R61、R129、R128的完整LSC位移比較',1);text=text.replace('## 完成範圍與主要數值',lead.replace('笔','筆')+'\n'.join(lines)+'\n\n## 完成範圍與主要數值',1);text=text.replace('實際圓心與取邊核對（原圖／R61代表案例）','實際圓心與取邊核對（四組首末代表案例）').replace('R61或R129結果不參與校正','任何模型的重建結果都不參與校正').replace('座標相减','座標相減')
    text+='\n## 版本與保存\n\n本份為2026-09-18新增R128後的四組結果。原三組報告、18頁PDF及既有ZIP均保留，不改寫為含R128。R128影像實體保存在H槽，D槽入口保持原樣。另一个訓練程序未停止或修改。\n';REPORT.write_text(text.replace('另一个','另一個'),encoding='utf-8')
    save(OUT/'closeout_checked.json',dict(counts=counts,aggregate_pairs=7200,max_median_difference_px=difference,max_PI_join_difference_um=pi_diff,previous_three_method_numbers_unchanged=True,protected_prior_results=plan['extension']['protected_prior_results'],checkpoint=plan['models']['R128']['checkpoint'],storage=plan['extension']['storage'],completed_utc=now()));print('Four-method closeout checks and actual R128 overlay complete')

def register():
    assert load(OUT/'visual_review.json')['passed'];plan=load(ROOT/'config/r128_extension.json');protected(plan);checked=load(OUT/'closeout_checked.json');key=load(OUT/'key_results.json');rel=REPORT.relative_to(REPO).as_posix()
    notice=f'**R136四組LSC完成（2026-09-18）：** 新增固定R128，全四組各930張／8370圓心。短步MAE原圖／R61／R129／R128=8.667／5.160／4.092／4.025nm；長距離17.738／15.267／15.712／15.496nm。R128與R129差距未明確，最差短步R129較低；不作全面升級。新影像放H槽，旧三組資料及PDF/ZIP保持不變。[四組報告]({rel})'.replace('旧','舊')
    p=REPO/'PROJECT_STATE.md';s=p.read_text(encoding='utf-8-sig');marker='<!-- R136_R128_COMPLETE -->'
    if marker not in s:s=s.replace('### Open Research / Side Tracks','### Open Research / Side Tracks\n'+marker+'\n'+notice,1)
    if '### R136 R128追加完成' not in s:s=s.replace('## Full Current State / 完整現況\n','## Full Current State / 完整現況\n\n### R136 R128追加完成\n\n'+notice+'\n',1)
    s=re.sub(r'(?m)^Last updated:.*$','Last updated: 2026-09-18（R136追加R128完成；四組LSC核對與圖表完成，舊成果保留）',s,count=1);p.write_text(s,encoding='utf-8')
    p=REPO/'ESTIMATOR_POLICY.json';policy=load(p);baseline=policy['formal_baseline'].copy();e=next(x for x in policy['open_side_tracks'] if x.get('candidate_id')=='r136_pi_repeatability')
    e.setdefault('previous_three_method_report',e.get('report'));e.setdefault('previous_three_method_results',{'main_results':e.get('main_results'),'comparisons':e.get('comparisons')});e.setdefault('r128_extension',{}).update(dict(status='complete_research_only',report=rel,models=MODELS,centers_each=8370,main_results=key['tables'],comparisons=key['comparisons'],r128_vs_r129_superiority_not_established=True,model_promoted=False));e.update(status='four_method_LSC_complete_research_only',latest_report=rel,report=rel,models_completed=MODELS,main_results=key['tables'],comparisons=key['comparisons']);assert policy['formal_baseline']==baseline;save(p,policy)
    p=REPO/'Experiments/INDEX.md';s=p.read_text(encoding='utf-8-sig');line=f'| R136 PI重拍比較 | [四組完整LSC](R136_PIRepeatability/reports/R136_LSC_FOUR_MODEL_RESULTS.md)／[原三組](R136_PIRepeatability/reports/R136_LSC_RESULTS.md) | 加入R128，各8370圓心；R128短步4.025nm、長距離15.496nm，與R129差距未明確；舊包保留 |';s=re.sub(r'(?m)^\| R136 PI重拍比較 \|.*$',line,s);p.write_text(s,encoding='utf-8')
    with (ROOT/'README.md').open('a',encoding='utf-8') as f:f.write('\n## 四組完整LSC（追加R128）\n\n[四組報告](reports/R136_LSC_FOUR_MODEL_RESULTS.md)及[四組結果包](output/R136_LSC_Four_Method_Results.zip)完成。原三組報告與PDF/ZIP保留，未改動另一個訓練程序。\n')
    for name in ['MANIFEST.md','HANDOFF.md']:
        with (ROOT/name).open('a',encoding='utf-8') as f:f.write('\n## R128 extension complete2026-09-18\n\nAllfour930frames/8370centers,33480independentcirclefits and7200median/PIpairs verified. Actualfour-modelfirst/last overlay and4comparisonplots reviewed. reports/R136_LSC_FOUR_MODEL_RESULTS.md currentextension; four_model_analysis/delivery_complete.json completion. Originalthree-methoddelivery/PDF/ZIP protected hashes unchanged; H reconstruction untouched. R128/R129differences inconclusive; no promotion. Othertrainingnotmodified. Automationr136 maynowpause.\n')
    p=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';reg=load(p);e=next(x for x in reg['entries'] if x.get('id')=='r136_r128_extension');e.update(state='complete_four_method_LSC_research_only',report=rel);reg['updated_at']=now();save(p,reg)
    pub=load(OUT/'published.json');pub['report']=record(REPORT);pub['figures']=[record(p) for p in sorted(FIG.glob('*.png'))];save(OUT/'published.json',pub)
    files=[REPORT,ROOT/'config/r128_extension.json',ROOT/'config/lsc_plan.json',*sorted(FIG.glob('*.png')),*sorted(FIG.glob('*.svg')),*sorted(T.glob('*')),OUT/'verification.json',OUT/'closeout_checked.json',OUT/'visual_review.json']
    for m in MODELS:files.extend(sorted((ROOT/'results/lsc/centers'/m).glob('*.npz')))
    manifest=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files];archive=ROOT/'output/R136_LSC_Four_Method_Results.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,p.relative_to(ROOT).as_posix())
        z.writestr('00_先讀我.txt','四組完整LSC結果：原圖、R61、R129、R128。\n先讀reports/R136_LSC_FOUR_MODEL_RESULTS.md；圖表在reports/lsc_four_model_figures；全部統計表在results/lsc/four_model_analysis/tables。\n四組各30次、930張、8370圓心；含定位邊界點與核對紀錄。\n不含全量影像或模型權重。本包不含新的PDF；舊PDF/ZIP仍為既有版本。\n'.encode('utf-8-sig'));z.writestr('PACKAGE_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for x in manifest:assert hashlib.sha256(z.read(x['path'])).hexdigest()==x['sha256']
    protected(plan);delivery=dict(status='complete',counts=checked['counts'],report=record(REPORT),figures=pub['figures'],archive=record(archive),verification=record(OUT/'verification.json'),visual_review=record(OUT/'visual_review.json'),previous_results_unchanged=True,completed_utc=now());save(OUT/'delivery_complete.json',delivery)
    save(ROOT/'runs/launcher_logs/r128_extension.json',dict(status='complete',model='R128',frames=930,centers=8370,report=rel,completed_utc=now()));save(ROOT/'results/lsc/r128_extension/status.json',dict(status='complete',stage='delivered',finished_scans=30,total_scans=30,updated_utc=now()));print('Four-method extension delivered;ZIP MiB',round(archive.stat().st_size/2**20,2))
if __name__=='__main__':
    if '--register' in sys.argv:register()
    else:prepare()
