"""Record completed diagnostics without changing any baseline or R129 entry."""
from study import *
import copy,re

def main():
    audit=load(ROOT/'results/analysis_verified.json');timed=load(ROOT/'results/runtime_verified.json');published=load(ROOT/'results/published.json');verify_sources()
    assert audit['motion_refits']==9045 and audit['pair_arithmetic_checks']==1585
    assert len(timed['parity'])==10
    report=ROOT/'reports/R131_RESULTS.md';assert published['report']==rec(report)
    for target in re.findall(r'\]\(([^\n)]+)\)',report.read_text(encoding='utf-8')):
        if not target.startswith(('http:','https:')):assert (report.parent/target).resolve().exists(),target
    before=ROOT/'results/registration_before';before.mkdir(exist_ok=False)
    paths=[REPO/'PROJECT_STATE.md',REPO/'ESTIMATOR_POLICY.json',REPO/'Experiments/INDEX.md',REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json']
    for i,p in enumerate(paths):(before/f'{i}_{p.name}').write_bytes(p.read_bytes())
    relative=report.relative_to(REPO).as_posix();p=REPO/'ESTIMATOR_POLICY.json';policy=load(p);old=copy.deepcopy(policy)
    assert not any(x.get('round')=='R131' for x in policy['open_side_tracks'])
    policy['open_side_tracks'].insert(0,dict(candidate_id='R131_R129_frozen_prefixes',round='R131',experiment=ROOT.relative_to(REPO).as_posix(),status='frozen_zero_to_four_steps_real_validation_complete',mainline_status='diagnostic_not_promoted',report=relative,training_updates=0,checkpoint=PLAN['checkpoint'],recurrent_prefixes=[0,1,2,3,4],real_frames_per_prefix=201,normal_SEM_rows=540,LSC_centers=9045,original_R129_preserved=True,model_promoted=False,claim='Existing four-step-trained model truncation, not separately trained architecture optimum. See all paired geometry/motion/cost tradeoffs.'))
    check=copy.deepcopy(policy);check['open_side_tracks'].pop(0);assert check==old
    p.write_text(json.dumps(policy,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    p=REPO/'PROJECT_STATE.md';s=p.read_text(encoding='utf-8-sig')
    lines=s.splitlines();lines[2]='Last updated: 2026-09-14（R131完成R129零至四次修復的完整實拍驗證；原模型與正式基準不變）';s='\n'.join(lines)+'\n'
    bullet=f'- **R131 R129 iteration diagnostic complete (2026-09-14):** [Frozen0–4step real validation]({relative}). Same trainedR129,0newupdates,all201nativeframes perprefix,540SEMrows/9045LSCcenters. Fourthstep improves centeredshape33/36anddiameter30/36 versus3, butMZCpaired20/36worse; complete120/194motion andtrueearly-exit timing separatelyreported. Allfour-stepPNGs andcentersreproduceR129; independentrefits andsourcecheckspass. No defaultchange/promotion. Truncationdoesnotcertifyretrainedarchitectureoptimality.\n'
    s=s.replace('### Open Research / Side Tracks\n','### Open Research / Side Tracks\n'+bullet,1)
    detail=f'''### R131 frozen recurrent-step validation complete (2026-09-14)

Canonical report: [{relative}]({relative}). User requested checking four repeated refinements. The frozen R129 long-training8192 checkpoint is evaluated at0–4learned updates, always retaining the same global optical conditioning, final original-image anchor and80/16FOV guard. Zero is not Raw; intermediate final outputs never feed the next iteration. All201nativeframes plus3normalSEM fields at5prefixes yield1020PNGs,540SEM rows and9045LSC centers. Existingfour-stepoutputreproducedonall201frames, oldLSCcenters reproduced. Fourthversusthird: centeredshape33/36better,diameter30/36better, butMZC20/36worse despite loweroverallmedian. Fullsame120pair and194within-session results,3recordedrepositionings andworstcases remain separate. Standaloneprefix timing excludes intermediate exports and matches savedPNGs onSEM/full-fieldcases.

Independent540SEMmetric recomputations and9045circle refits,1585pair-arithmetic checks andaggregate recomputations complete. Initial random-inputpreflight mistakenly askedbitidentityacrossdifferentconvolutionshapes; failedsource/logpreserved, actual1.19e-7difference iswithinoriginal1e-6protocol. No historicalexpectedhashreset. Allreadsource/protectedbindings preserved. This isfrozencheckpointusagediagnostic,notfromscratcharchitecturecomparisonorproofthatfourisoptimal. No training,default replacement,promotionoroldconfirmationaccess. See canonical tables for model,shape,motion andruntime tradeoffs.

'''
    s=s.replace('## Full Current State / 完整現況\n\n','## Full Current State / 完整現況\n\n'+detail,1)
    a,rest=s.split('<!-- QUICK_HANDOFF_START -->',1);q,b=rest.split('<!-- QUICK_HANDOFF_END -->',1)
    while len(q.splitlines())>60 and '\n\n' in q:q=q.replace('\n\n','\n',1)
    s=a+'<!-- QUICK_HANDOFF_START -->'+q+'<!-- QUICK_HANDOFF_END -->'+b
    p.write_text(s,encoding='utf-8')
    p=REPO/'Experiments/INDEX.md';s=p.read_text(encoding='utf-8-sig');needle='| Round | 目錄 | 狀態 |\n|-------|------|------|\n';assert needle in s
    s=s.replace(needle,needle+'| R131 R129反覆修復驗證 | [零至四次的實拍得失](R131_RecurrentStepValidation/reports/R131_RESULTS.md) | 相同權重、完整201張與正常SEM；第四次仍有細形狀收益，尺寸／位移／速度各自報告。1020張輸出、9045個圓心獨立核對；零訓練、未採用新版本，不宣稱四次架構已最佳 |\n',1);p.write_text(s,encoding='utf-8')
    p=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';registry=load(p);entry=next(x for x in registry['entries'] if x.get('id')=='r131_recurrent_steps');entry.update(state='frozen_prefix_validation_complete',report=relative,actual_gib=sum(x.stat().st_size for x in ROOT.rglob('*') if x.is_file())/1024**3);registry['updated_at']=now();p.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name in ['README.md','MANIFEST.md']:
        with (ROOT/name).open('a',encoding='utf-8') as f:f.write('\n完整201張與SEM／位移／速度核對已完成，見 [正式結果報告](reports/R131_RESULTS.md)。沒有重新訓練或採用較少次數版本。\n')
    verify_sources();save(ROOT/'results/registration.json',dict(utc=now(),report=rec(report),updated=[rec(p) for p in paths],all_prior_policy_entries_unchanged=True,model_promoted=False))
    status(ROOT/'runs/launcher_logs/active_formal_run.json',dict(status='complete_verified',training=False,frames=201,prefixes=5,SEM_rows=540,LSC_centers=9045,model_changed=False,report=relative))
    print('R131 registered; prior baseline and R129 entries unchanged',flush=True)
if __name__=='__main__':main()
