from common133 import *
import re,copy

def main():
    verify();audit=load(ROOT/'results/audit_complete.json');pub=load(ROOT/'results/publication_final.json');assert audit['real_SEM_refits']==972 and audit['controlled_refits']==640 and audit['generated_metric_recomputations']==2304
    report=ROOT/'reports/R133_RESULTS.md';design=ROOT/'reports/R133_REPAIR_DESIGN.md';assert rec(report)==pub['report'] and rec(design)==pub['repair_design']
    for p in [report,design]:
        for target in re.findall(r'\]\(([^\n)]+)\)',p.read_text(encoding='utf-8')):
            if not target.startswith(('http:','https:')):assert (p.parent/target).resolve().exists(),target
    # Verify the reported within-exposure paired changes; do not substitute
    # differences of overall medians.
    rt=pd.read_csv(ROOT/'results/real/measurements.csv');pivot=rt.pivot(index=['pillar','exposure'],columns='arm',values='signed_diameter_nm');saved=pd.read_csv(ROOT/'results/real/paired_diameter_changes.csv')
    for row in saved.itertuples():
        delta=(pivot[row.candidate]-pivot[row.reference]).groupby('pillar').median();assert abs(delta.median()-row.paired_diameter_change_nm)<1e-8
        assert int((delta>1e-7).sum())==row.increased and int((delta< -1e-7).sum())==row.decreased
    for p in (ROOT/'scripts').glob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'))
    before=ROOT/'results/registration_before';before.mkdir(exist_ok=False);paths=[REPO/'PROJECT_STATE.md',REPO/'ESTIMATOR_POLICY.json',REPO/'Experiments/INDEX.md',REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json']
    for i,p in enumerate(paths):(before/f'{i}_{p.name}').write_bytes(p.read_bytes())
    rel=report.relative_to(REPO).as_posix();drel=design.relative_to(REPO).as_posix();p=paths[1];policy=load(p);old=copy.deepcopy(policy);assert not any(r.get('round')=='R133' for r in policy['open_side_tracks'])
    policy['open_side_tracks'].insert(0,dict(candidate_id='R133_size_mechanism_diagnosis',round='R133',experiment=ROOT.relative_to(REPO).as_posix(),status='frozen_diagnosis_and_repair_design_complete',mainline_status='no_replacement_model',report=rel,repair_design=drel,training_updates=0,known_geometry_controls=64,generated_test_parents=128,real_SEM_rows=972,controls_improved_vs_Raw=41,controls_worsened_vs_Raw=23,paired_actual_model_size_increment_nm=12.122171,findings='Ideal blur often underestimates size; learned outward correction can help controls but aggravates already-outward realSEM discrepancy. Dataset/reference mismatch supported, exact physical shares unresolved. Frozen head/optics changes do not repair realsize.',prototype='Neutral residual outputs and qualified coverage-gradient contracts tested; not a trained architecture. Frozen replacements worsen generated image fidelity.',model_promoted=False,original_defaults_unchanged=True))
    check=copy.deepcopy(policy);check['open_side_tracks'].pop(0);assert check==old;p.write_text(json.dumps(policy,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    p=paths[0];s=p.read_text(encoding='utf-8-sig');lines=s.splitlines();lines[2]='Last updated: 2026-09-14（R133完成尺寸機制診斷與底層修正方案；沒有新替代模型）';s='\n'.join(lines)+'\n'
    bullet=f'- **R133 尺寸機制診斷完成（2026-09-14）：** [實測與底層修正方案]({rel})。128生成父場景、64已知尺寸控制、972筆SEM與固定強度對照；理想模糊常偏小，R129可向外修回，但控制仍41改善／23退步。實拍相對Raw配對新增尺寸約12.122nm（36/36）；關光學或換最後公式未解決101–102nm總差距。中性接口及幾何梯度原型已測，直接套舊權重反而劣化合成影像。優先對齊成像／材料／讀法，再匹配短訓練；無升級。\n'
    s=s.replace('### Open Research / Side Tracks\n','### Open Research / Side Tracks\n'+bullet,1)
    detail=f'''### R133 size-mechanism diagnosis and repair design complete (2026-09-14)

Canonical results: [{rel}]({rel}); repair design: [{drel}]({drel}). FrozenR129long8192, ninearms:Raw,Optics,Neural,Final,NoOptics,ResidualHP,DirectResidual andtwoRMSmatchedFinalcontrols. All128generatedparents/256views,64area-renderedcircleconditions/640readouts,normal3SEMfields/972rows complete. FinalreproducesR132W16. ControlFinalabsdiametermedian.03952px vsRaw.05088;41improve23worsen,worst.70739. CleanTargetreaderitselfranges−.03217to+.04708;8vs16formationmaxdiameterdifference.000442. Idealbluroftenmakesmeasuredcircletoosmall andmodelmovesoutward, unlike already-large realSEMopticalreadout. This supports imaging/reference mismatch, not an identified allocation among material response, scale and reader definitions.

Realstage diameter medians:Raw88.204,Optics81.083,Neural101.492,Final102.232nm. Within-exposurepairedFinal-Raw median12.122nm all36increase;Neural-Optics18.905,Final-Neural.687nm. Head/opticsinterventionsremain101–102nm; nofrozenreplacementadopted. RMSmatchingbeforeFOV~.99857–1,actualafterFOV~.98896–1.01257:approximate, notexact; wordingcorrectionandinitialdraftretained. GeneratedFinalMAE1.831vsResidualHP2.682/DirectResidual4.377;Neural29.329,mean-aligned16.509. Internalimagescannotbeclaimedcleanphysicalreconstructionswithoutdirectsupervision; geometryinformationmaystillbeuseful.

Neutraloutputcontractandnonzero/finite-differencegradients verified; oldobjectivehascorrectradiusgradient, whileconsistent2pxdiameterbiasgiveszeropairloss. Qualifiedtwo-levelcoverageobjectiveisprototype-only,notvalidforunknownrealmaterialmapping. Initialneutralroundofffailureandtwoorchestrationwaitfailurespreserved; intendedstrictneutralcontractfixedbeforemainruns,originalweights/sourcesunchanged. Independent972SEM/640controlfitsand2304image metrics pass. No training, oldconfirmationaccess ordefaultchange. Proposednextwork: qualify reference/forward-data relationship, retainfoursharedupdates/AA/measuredopticalinformation whilemakingimage/outputsemanticsneutralanddirect, thenmatcheddata×interfaceprobes, followedbyseparatequalifiedgeometrylosscomparison. No new trainedreplacementexists.

'''
    s=s.replace('## Full Current State / 完整現況\n\n','## Full Current State / 完整現況\n\n'+detail,1)
    a,rest=s.split('<!-- QUICK_HANDOFF_START -->',1);q,b=rest.split('<!-- QUICK_HANDOFF_END -->',1)
    while len(q.splitlines())>60 and '\n\n' in q:q=q.replace('\n\n','\n',1)
    if len(q.splitlines())>60:q=q.replace('\n**Former baseline:**',' **Former baseline:**',1)
    if len(q.splitlines())>60:q=q.replace('\n**Canonical COMBO origin branch:**',' **Canonical COMBO origin branch:**',1)
    assert len(q.splitlines())<=60;p.write_text(a+'<!-- QUICK_HANDOFF_START -->'+q+'<!-- QUICK_HANDOFF_END -->'+b,encoding='utf-8')
    p=paths[2];s=p.read_text(encoding='utf-8-sig');needle='| Round | 目錄 | 狀態 |\n|-------|------|------|\n';assert needle in s;s=s.replace(needle,needle+'| R133 尺寸機制診斷 | [已知幾何、真實SEM與底層方案](R133_SizeMechanismDiagnosis/reports/R133_RESULTS.md) | 64控制、128生成父場景、972SEM與強度對照；無統一合成膨脹，實拍學習階段向外增加。簡單換公式失敗；中性及限定幾何要求原型通過，但未訓練替代模型，先對齊成像／材料／讀法 |\n',1);p.write_text(s,encoding='utf-8')
    p=paths[3];v=load(p);entry=next(r for r in v['entries'] if r.get('id')=='r133_size_mechanism');entry.update(state='diagnosis_and_repair_design_complete',report=rel,actual_gib=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())/1024**3);v['updated_at']=now();p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name in ['README.md','MANIFEST.md']:
        with (ROOT/name).open('a',encoding='utf-8') as f:f.write('\n完成：[診斷結果](reports/R133_RESULTS.md)；[底層修正設計](reports/R133_REPAIR_DESIGN.md)。沒有新訓練模型或原地公式替換；新接口僅是已測原型。\n')
    verify();save(ROOT/'results/registration.json',dict(utc=now(),report=rec(report),design=rec(design),updated=[rec(p) for p in paths],prior_policy_entries_unchanged=True,training=False,model_promoted=False,paired_size_arithmetic_reverified=True))
    status(ROOT/'runs/launcher_logs/active_formal_run.json',dict(status='complete_verified',training=False,generated_parents=128,controls=64,real_SEM_rows=972,output_contracts_tested=True,new_trained_model=False));print('R133 registered; prior entries preserved',flush=True)
if __name__=='__main__':main()
