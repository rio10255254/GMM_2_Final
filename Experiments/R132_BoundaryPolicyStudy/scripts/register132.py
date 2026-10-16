from common132 import *
import copy,re

def main():
    verify();a=load(ROOT/'results/audit_complete.json');assert a['independent_SEM_refits']==615 and a['independent_LSC_refits']==9045 and a['invalid_sem_rows']==0
    report=ROOT/'reports/R132_RESULTS.md';assert rec(report)==load(ROOT/'results/published.json')['report']
    ref=loadmat(PKG/'validation/sem_reference.mat',variable_names=['global_index','opt_centers']);gy,gx=np.argwhere(ref['global_index']==16)[0];c=ref['opt_centers'][int(gy)*6+int(gx)];cx,cy=[int(np.floor(v+.5))-1 for v in c]
    checks=[]
    for e in [13,14,15]:
        full=np.load(R131/f'results/edge_diagnostic/exposure{e}.npz')['raw'];expected=full[cy-52:cy+52,cx-52:cx+52]
        for margin in [0,16,32,64,96]:
            d=np.load(ROOT/f'results/context/e{e}_m{margin}.npz');actual=d['raw'][cy-52:cy+52,margin:margin+104];assert np.array_equal(expected,actual);checks.append(dict(exposure=e,margin=margin,same_raw_window=True))
    save(ROOT/'results/context/raw_window_verification.json',dict(cases=checks))
    x=np.full((223,217),.25,np.float32);p=np.full_like(x,.75)
    for width in WIDTHS:
        y=blend(x,p,width)
        for yy,xx in [(0,110),(16,110),(32,110),(80,110),(96,110),(111,108)]:
            distance=min(yy,xx,222-yy,216-xx);weight=1 if width==0 else max(0,min(1,(distance-width)/16));assert y[yy,xx]==.25+.5*weight
    paths=[REPO/'PROJECT_STATE.md',REPO/'ESTIMATOR_POLICY.json',REPO/'Experiments/INDEX.md',REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json'];before=ROOT/'results/registration_before';before.mkdir(exist_ok=False)
    for i,p in enumerate(paths):(before/f'{i}_{p.name}').write_bytes(p.read_bytes())
    rel=report.relative_to(REPO).as_posix();p=paths[1];policy=load(p);old=copy.deepcopy(policy);assert not any(r.get('round')=='R132' for r in policy['open_side_tracks'])
    policy['open_side_tracks'].insert(0,dict(candidate_id='R132_R129_boundary16_trial',round='R132',experiment=ROOT.relative_to(REPO).as_posix(),status='fixed_guard_and_real_context_study_complete',mainline_status='research_trial_not_promoted',report=rel,widths=WIDTHS,selected_research_width=16,transition=16,checkpoint=PLAN['checkpoint'],training_updates=0,frames_per_width=201,SEM_rows=615,LSC_centers=9045,findings='Broad80Raw blending degrades outer shape;16trial restores shape but increases size discrepancy. Full194cross-axis and some worst cases still worsen. Independent current/crop/source replay passed.',scope='Existing normal microscopy; no unseen qualification; cropped optical contour still>=14.5pixels inside edge',original_package_default_unchanged=True,model_promoted=False))
    same=copy.deepcopy(policy);same['open_side_tracks'].pop(0);assert same==old;p.write_text(json.dumps(policy,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    p=paths[0];s=p.read_text(encoding='utf-8-sig');lines=s.splitlines();lines[2]='Last updated: 2026-09-14（R132完成邊緣保護研究；16像素為研究試用，尺寸偏差仍未解決）';s='\n'.join(lines)+'\n'
    bullet=f'- **R132 邊緣保護研究完成（2026-09-14）：** [五種保留寬度與真實裁切測試]({rel})。固定R129四次，201張×5政策、615筆SEM與9045個圓心核對；80縮16後细形狀16.397→8.411nm，但尺寸96.380→102.232nm，完整194對橫向仍有退步。外圍20顆形狀全改善、尺寸全退步，中央16不變。提供16像素研究入口，原模型／套件預設不改，不作未知樣品或尺寸認證。\n'
    s=s.replace('### Open Research / Side Tracks\n','### Open Research / Side Tracks\n'+bullet,1)
    detail=f'''### R132 boundary-policy research complete (2026-09-14)

Canonical report: [{rel}]({rel}). SameR129long8192checkpoint/foursteps, vary only finalRawretention widths80/64/32/16/0; nonzero16transition,zero means no retention. Reuse verifiedpre-guard fields,201x5PNGs andall9045LSCcenters;540primarynormalSEM reads+75samepillar contextreads. Currentfullforward verifies storedpre-guard semantics;80float/PNG/SEM/centers reproduce. All615SEM valid,independent615SEM/9045circle fits and1585paircalculations passed. Outer20 shape/correlation/MZC allimprove at16,diameter allworsen;central16 unchanged. All36shape16.397→8.411nm,MZC62.651→9.268,diameter96.380→102.232. Locked120SD6.991→6.929,within4.204→3.808;full194cross7.974→8.069worsens andlockedmaxcross59.088→60.292. Not uniform superiority.

Real context: centralpillar16 at3exposures,measurement-window leftmargins0/16/32/64/96,15currentforwards; actualopticalcontourclosest14.5–15.4pxinside edge. Crop changesglobaloptical/qualitycontexttoo. Pre-guard errorvsfullfield fallsfrommaxwindowmean.188gray/maxpixel14.90 atmargin0 to.00495/.01953 atmargin16;80blending substantiallychanges same-object shape. Existing-normal-field evidence supports16researchtrial,not universalpixel-edge safety. PublicSEM/fullfieldreplay exact; fractionmap isnotconfidence. No training/defaultmodelchange/oldhashrebaseline/confirmationaccess. Sizebias remains a separate model/reference problem; do not compare new16numbers directly toold80counterparts without matching policy.

'''
    s=s.replace('## Full Current State / 完整現況\n\n','## Full Current State / 完整現況\n\n'+detail,1)
    first,rest=s.split('<!-- QUICK_HANDOFF_START -->',1);q,last=rest.split('<!-- QUICK_HANDOFF_END -->',1)
    while len(q.splitlines())>60 and '\n\n' in q:q=q.replace('\n\n','\n',1)
    if len(q.splitlines())>60:q=q.replace('\n**Former baseline:**',' **Former baseline:**',1)
    assert len(q.splitlines())<=60;p.write_text(first+'<!-- QUICK_HANDOFF_START -->'+q+'<!-- QUICK_HANDOFF_END -->'+last,encoding='utf-8')
    p=paths[2];s=p.read_text(encoding='utf-8-sig');needle='| Round | 目錄 | 狀態 |\n|-------|------|------|\n';assert needle in s;s=s.replace(needle,needle+'| R132 邊緣保護研究 | [五種寬度、完整位移及裁切驗證](R132_BoundaryPolicyStudy/reports/R132_RESULTS.md) | 80保留過寬，16研究試用改善外圍細形狀；尺寸偏差與部分橫向結果變差。615筆SEM／9045圓心獨立核對；原模型及預設保留，無正式升級 |\n',1);p.write_text(s,encoding='utf-8')
    p=paths[3];v=load(p);entry=next(x for x in v['entries'] if x.get('id')=='r132_boundary_policy');entry.update(state='complete_research_width16_trial',report=rel,actual_gib=sum(x.stat().st_size for x in ROOT.rglob('*') if x.is_file())/1024**3);v['updated_at']=now();p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name in ['README.md','MANIFEST.md']:
        with (ROOT/name).open('a',encoding='utf-8') as f:f.write('\n研究完成：[實測結果與試用方式](reports/R132_RESULTS.md)。scripts/infer_trial.py預設16像素，只改輸出規則的研究入口；原R129權重與套件預設不變。尺寸偏差未解，不宣稱最佳或正式量測資格。\n')
    assert len(list((ROOT/'results/images').rglob('*.png')))==1005;assert len(list((ROOT/'results/sem_cases').glob('*.png')))==90;verify()
    save(ROOT/'results/registration.json',dict(utc=now(),report=rec(report),updated_files=[rec(p) for p in paths],prior_policy_entries_unchanged=True,model_promoted=False,raw_context_replay_cases=15,guard_scalar_fixture_checks=30))
    status(ROOT/'runs/launcher_logs/active_formal_run.json',dict(status='complete_verified',training=False,frames=201,policies=5,SEM_rows=615,LSC_centers=9045,research_trial_width=16,original_default_unchanged=True))
    print('R132 registered; all prior policy entries preserved',flush=True)

if __name__=='__main__':main()
