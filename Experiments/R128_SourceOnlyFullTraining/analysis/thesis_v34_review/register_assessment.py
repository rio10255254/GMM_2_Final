"""Register the completed thesis-specific assessment, preserving prior studies."""
import sys,json,time,uuid,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];REPO=ROOT.parent.parent;BASE=ROOT/'results/thesis_v34_review_20260912';sys.path.insert(0,str(ROOT/'scripts'))
from common import *

def write(p,text):
    temp=p.with_name(p.name+'.v34-'+uuid.uuid4().hex+'.tmp');temp.write_text(text,encoding='utf-8')
    for i in range(15):
        try:temp.replace(p);return
        except PermissionError:
            if i==14:raise
            time.sleep(.2)

def main():
    report=ROOT/'reports/R128_THESIS_V34_REPLACEMENT_ASSESSMENT_VERIFIED.md';assert report.is_file();v=load(BASE/'bridge_verification.json');assert v['all_nine_methods_same_v34_120pairs']
    for dest in re.findall(r'\]\(([^)]+)\)',report.read_text(encoding='utf-8')):assert (report.parent/dest).resolve().is_file(),dest
    names=['PROJECT_STATE.md','ESTIMATOR_POLICY.json','Experiments/INDEX.md','RECON_GALLERY.md','Experiments/R128_SourceOnlyFullTraining/README.md'];before=BASE/'mutable_context_before';before.mkdir(exist_ok=False)
    for name in names:
        with (before/name.replace('/','__')).open('xb') as f:f.write((REPO/name).read_bytes())
    rel='Experiments/R128_SourceOnlyFullTraining/reports/R128_THESIS_V34_REPLACEMENT_ASSESSMENT_VERIFIED.md'
    p=REPO/'PROJECT_STATE.md';lines=p.read_text(encoding='utf-8-sig').splitlines();lines[2]='Last updated: 2026-09-12（完整審閱v34並同條件補測：R128跨柱一致性較好，細部非圓輪廓與速度較弱，暫不直接替換論文主模型）'
    target=[i for i,line in enumerate(lines) if line.startswith('- **R128/R61 matched LSC follow-up complete')];assert len(target)==1
    lines[target[0]]='- **R128 thesis-v34 assessment complete (2026-09-12):** [Full reading and matched tests]('+rel+'). Samev34actual120pairs require166frames,only87pairs overlapSep10study;22newR128forwards+144verifiedreuses. Raw/V42readerparity reproduced. R128/V42stepSD7.250/7.292nm,nominalMAE5.767/5.743,within-grid3.416/4.886;replacement8-modelranks3/1/3vsold3/1/7. ThesisfineSEMreader onnormal13–15:radial38.705vs43.324nm andCD76.647vs86.295 improve,butcontourcorrelation.767vs.943andMZCerror50.990vs5.816nmworsen. FreshstrictFP32commonruntime28.066sR128vs2.342sV42;validatedR128pipeline16.834s. Source-onlytraining/provenance remain strengths,butR128doesnotcontainoldmeasuredPSFfusion/AAdecoder/qualitygate. No immediatev34modelreplacement,promotion,retrainingoroldconfirmationaccess. Preserveoldstudies;priorcoarsemask/R61gainsdo nottransferdirectlytoV42fineSEMclaims.'
    text='\n'.join(lines)+'\n';anchor='### R128 completed four-run study, one follow-up candidate, no production adoption (2026-09-09)\n\n';assert text.count(anchor)==1
    detail='2026-09-12 full annotated-v34thesis review and replacement assessment: '+rel+'. Read7chapters,111referenceentries,252livecommentsandannotationindex,viewed60embeddedfigures andkeyrenderedpages. Source13,121,560bytes/SHA256d85a7987bbea8f5f58585334104f9d0425f3a42a92e51bbbb187cca2c5a9fc12capturedread-only;originalDOCXnotedited. Thev34modelisV42E120anditsclaimchainincludesmeasuredPSFfusion,AAupsampling,raw-anchoroutput,refinedSEMshape/MZC,LSC/MZCchoice,eight-modelcomparisonandruntime. R128hasdifferentimage-only4sharedupdatesandsimulationobservationsupervision,notalloldmodules. Traceabilityisnotcompletephysicalinterpretability.\n\nActualv34bridge uses166frames/120pairs,only87pairscommonwithSep10R128study.22newfullR128images+144verifiedreuses;Raw/V42all2988centersreproducev34to4.55e-13px. NewR128LSC7.250296nmstepSD,5.767442nominalMAE,3.416135within-grid,6.764177crossaxis;V427.292303/5.742972/4.885544/6.551281. ReplacingV42inold7baselinecomparison yieldsranks3/1/3,notpurearchitecturecomparison. Oldv34readerprocessing-orderstate isexplicit;do notmixwithSep10per-pillar-resetreader.\n\nFineSEMnormal3exposure bridge usesexactlegacyper-cellnormalizationandmaxgradientcontours,180SEM/144opticalpointsand720radialsignature. Initialnativecellparityfailureisretained;separatev2restoresdocumentedim2uint8(mat2gray(cell))andall108Rawcellsreproduce. All216Raw/V42metricrowsreproduce;324rowsretained. R128vsV42radialMAE38.705044vs43.324390nm,CD76.646764vs86.295184nm;correlation.767368vs.942754(all36worse),MZCerror50.989858vs5.816055nm(33/36worse). CenteredshapeMAEdiagnostic16.118916vs6.809732nm;R128reducessizebiasbutdoesnotpreserveirregularshapeaswellintheseexistingreferences. SEMnonroundnessisnotperfect-circlepreference. Only13–15testedhere,notwhole12exposurepaperclaim.\n\nFreshA6000strictFP32pairedcommonrecipe(tile256,overlap128,batch8,2warmups/8runs):V422341.82msvsR12828066.46ms,about11.98times. R128validatedfullFOVcore256/halo64/Rawguardpipeline16834.22msmedian(1warmup/3runs),outputbitwiseequaltoexisting. Differentrecipeoutputqualitynotpromoted;donotmixnewtimeswitholdpaper1102.3ms/oldsevenmodelranks. Modelparametercountsmallerdoesnotimplyfaster. Decision:retainR128researchdirectionbutdonotimmediatelyreplacev34;prioritizeirregularshapeandcostbeforeadaptingclaims. PreserveoriginalPSF/systemworkasactualcharacterizationandWienerreference;do notclaimcurrentR128ingestsmeasuredPSFbank. No training,checkpointchange,sourceDOCXedit,oldexpectedhashreplacementorproductionpromotion.\n\n'
    text=text.replace(anchor,anchor+detail);q=text.split('<!-- QUICK_HANDOFF_START -->')[1].split('<!-- QUICK_HANDOFF_END -->')[0];assert len(q.strip().splitlines())<=60;write(p,text)
    p=REPO/'ESTIMATOR_POLICY.json';policy=load(p);baseline=policy['formal_baseline'].copy();found=[]
    def visit(node):
        if isinstance(node,dict):
            if node.get('candidate_id')=='R128_source_only_full_training':found.append(node)
            for v in list(node.values()):visit(v)
        elif isinstance(node,list):
            for v in node:visit(v)
    visit(policy);assert len(found)==1 and 'thesis_v34_assessment' not in found[0]
    found[0]['thesis_v34_assessment']=dict(completed_utc=now(),report=rel,source_docx_sha256='d85a7987bbea8f5f58585334104f9d0425f3a42a92e51bbbb187cca2c5a9fc12',source_docx_edited=False,actual_thesis_pairs=120,actual_thesis_frames=166,pairs_shared_with_prior_study=87,new_R128_inference_frames=22,reused_R128_frames=144,
        R128_v34_LSC=dict(step_sd_nm=7.250296,nominal_mae_nm=5.767442,within_grid_nm=3.416135,cross_axis_nm=6.764177,replacement_ranks=[3,1,3]),
        refined_SEM_normal_exposures=[13,14,15],refined_SEM_all36_correlation_worse_than_V42=True,refined_SEM_MZC_worse_pillars=33,
        runtime_common_R128_ms=28066.46155,runtime_common_V42_ms=2341.82,runtime_validated_R128_ms=16834.2197,
        decision='No immediate drop-in replacement of v34. Retain R128researchdirection; improve irregular-shape preservation and validated cost,thenrewrite architecture/data/claims.',
        traceable_training_not_full_physical_interpretability=True,old_coarse_metrics_do_not_equal_thesis_refined_metrics=True,new_training_updates=0,production_adopted=False)
    assert policy['formal_baseline']==baseline;write(p,json.dumps(policy,ensure_ascii=False,indent=2)+'\n')
    p=REPO/'Experiments/INDEX.md';lines=p.read_text(encoding='utf-8-sig').splitlines();lines[2]='Last updated: 2026-09-12（v34全文審阅與模型替換補測完成；R128一致性改善，但非圓細節及效率尚不能完整接替原論文）'
    idx=[i for i,line in enumerate(lines) if line.startswith('| R128 完整研究訓練 |')];assert len(idx)==1
    lines[idx[0]]='| R128 完整研究訓練 | [v34論文替換評估](R128_SourceOnlyFullTraining/reports/R128_THESIS_V34_REPLACEMENT_ASSESSMENT_VERIFIED.md)・[先前R61比較](R128_SourceOnlyFullTraining/reports/R128_LSC_R61_COMPARISON.md) | 同v34名單補測：跨柱一致性改善約30%，位移波動相近；正常三張平均輪廓與尺寸較好，細部起伏相關及MZC較V42差。共同速度約慢12倍；暫不直接替換論文主模型，無重訓或正式升級 |';write(p,'\n'.join(lines)+'\n')
    p=ROOT/'README.md';text=p.read_text(encoding='utf-8-sig');assert 'R128_THESIS_V34_REPLACEMENT_ASSESSMENT_VERIFIED.md' not in text
    write(p,text+'\n2026-09-12 thesis-specific assessment: [full annotated-v34 review and matched bridge](reports/R128_THESIS_V34_REPLACEMENT_ASSESSMENT_VERIFIED.md) finds stronger inter-pillarconsistency andlowermeanradial/CDerror, butweakerrefinedSEMnonrounddetail/MZC andsubstantiallyhighercompute. Only87/120pairs overlap thepriorcomparison;new166-framebridge and3normal-exposurefineSEM metrics reproduceoldcontrols. Do notdirectlyreplacev34orinherititsPSFfusion,AAablation,full12exposureclaimsoroldruntime. R128remainsresearchcandidate;nonewtrainingororiginalDOCXedit.\n')
    p=REPO/'RECON_GALLERY.md';text=p.read_text(encoding='utf-8-sig');marker='## R128 — 補齊與R61的LSC及輪廓對照（2026-09-10）';assert text.count(marker)==1
    section='## R128與v34論文模型的真正取捨（2026-09-12）\n\n按論文真正名單和量法重比：R128跨柱一致性較好，平均尺寸與輪廓位置改善；細部非圓起伏與共同條件下的速度較弱。暫不直接替換整篇論文。見 [完整評估]('+rel+')。\n\n![相同條件下的模型取捨](Experiments/R128_SourceOnlyFullTraining/reports/figures/R128_v34_replacement_tradeoffs.png)\n\n![同顆柱體的非圓起伏](Experiments/R128_SourceOnlyFullTraining/reports/figures/R128_v34_nonround_profile_verified.png)\n\n';write(p,text.replace(marker,section+marker))
    save(BASE/'registration.json',dict(completed_utc=now(),report_links_valid=True,quick_handoff_lines=len(q.strip().splitlines()),formal_baseline_unchanged=True,files={name:record(REPO/name) for name in names},source=record(__file__)))
    print('Verified assessment registered; source thesis and prior study records preserved.')
if __name__=='__main__':main()
