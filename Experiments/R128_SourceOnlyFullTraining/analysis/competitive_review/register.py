"""Add verified supplemental findings to mutable project indexes only."""
import copy
import json
import re
import sys
import time
import uuid
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent.parent
sys.path.insert(0, str(ROOT/'scripts'))
from common import load, save, record, sha, now


def replace_file(path, content):
    temp = path.with_name(path.name+'.competitive-'+uuid.uuid4().hex+'.tmp')
    temp.write_text(content, encoding='utf-8')
    for attempt in range(15):
        try:
            temp.replace(path)
            return
        except PermissionError:
            if attempt == 14:
                raise
            time.sleep(.2)


def main():
    out = ROOT/'results/competitive_review'
    assert load(out/'verification.json')['sources_unchanged']
    names = ['PROJECT_STATE.md', 'ESTIMATOR_POLICY.json', 'Experiments/INDEX.md', 'RECON_GALLERY.md', 'Experiments/R128_SourceOnlyFullTraining/README.md']
    before_dir = out/'mutable_context_before'
    before_dir.mkdir(exist_ok=False)
    before = {}
    for name in names:
        p = REPO/name
        snapshot = before_dir/name.replace('/', '__')
        with snapshot.open('xb') as f:
            f.write(p.read_bytes())
        before[name] = record(p)
    report_rel = 'Experiments/R128_SourceOnlyFullTraining/reports/R128_COMPETITIVE_REVIEW.md'
    p = REPO/'PROJECT_STATE.md'
    text = p.read_text(encoding='utf-8-sig')
    lines = text.splitlines()
    lines[2] = 'Last updated: 2026-09-10（同條件盤點：R128完整輪廓、面積與周長領先所列研究候選；圓度受參考影響，R128正式LSC仍未測）'
    matches = [i for i, line in enumerate(lines) if line.startswith('- **R128 paired full-contour check')]
    assert len(matches) == 1
    lines[matches[0]] = '- **R128 matched competitive review complete (2026-09-10):** [LSC/contour/circularity comparison]('+report_rel+') / [full contour](Experiments/R128_SourceOnlyFullTraining/reports/R128_FULL_CONTOUR_SEM.md). Same36pillars and normal13/14/15,all5methods/common Raw shifts/two fixed SEMreferences;1080rows independently verified. P_s1285002has best aggregate boundary/area/perimeter among Raw,R61v16,R109E48,R119E42,R128;boundary difference about24–26%belowRaw and15%belowR109,33/36pillar medians beatR109. Circularity improves under historical reference but worsens underglobal-pitch reference;worst local distance can worsen. Historical120-pair LSC reproduced:Raw9.745,R1097.003,R1197.261nmmean sequence SD. R128hasNOsame-protocolLSC;0.01319pxRaw-relative registration is not anLSCscore. Next:same lockedLSCcomparison for the single retained model,resolve circularityreference sensitivity. No training,promotion,newconfirmationor oldhashreplacement.'
    text = '\n'.join(lines)+'\n'
    anchor = '### R128 completed four-run study, one follow-up candidate, no production adoption (2026-09-09)\n\n'
    assert text.count(anchor) == 1
    detail = ('2026-09-10 matched competitive review: '+report_rel+'. Reused identical Raw/SEMmask sources for36pillars xnormal13/14/15 xRaw,R61v16,R109E48,R119E42,R128PNG x2references. No per-model alignment fitting. All1080rows independently recomputed;432previousRaw/R128rows reproduce. After median per-pillar across3exposures, R128historical/global boundary medians0.585814/0.375708px vsRaw0.769901/0.508201 andR1090.690251/0.442433. R128boundary beatsR109on33/36pillars with bothreferences and remains strongest aggregateboundary/area/perimeter among listedmethods in the16fully-neuralinterior. Circularity medianerrorsRaw0.016188toR1280.012494historical,but0.011769to0.015056global. Predictedcircularity is identicalacrossrefs;SEMreference per-object absolute difference median0.014586shows referenceconstruction sensitivity. Worstlocalerror canincrease. These are one reuseddevelopment specimen,notfreshconfirmation or universal geometry certification.\n\n'
              'LSC summaries independently recomputed from the same120Raw-lockedpairs: mean per-sequence stepSDRaw9.745101,Wiener7.391651,V42E1206.922744,R109E487.002564,R119E427.260884nm. R128was notrun through this protocol; its0.013190pxfull-fieldRaw-relative registrationdifference is notformalLSC improvement. V42specifictrainingdataoverlap andR119causalauditcorrection remain authoritative. Nextdecision: same120-pairLSCevaluation of the singleP_s1285002model with Raw,Wiener,R109references and worst-case inspection,then resolve reference-sensitivecircularity before precisionadoption. No newinference/training,promotionor oldconfirmationaccess in thisreview.\n\n')
    text = text.replace(anchor, anchor+detail)
    quick = text.split('<!-- QUICK_HANDOFF_START -->', 1)[1].split('<!-- QUICK_HANDOFF_END -->', 1)[0]
    assert len(quick.strip().splitlines()) <= 60
    replace_file(p, text)

    p = REPO/'ESTIMATOR_POLICY.json'
    policy = load(p)
    original = copy.deepcopy(policy)
    found = []
    def visit(node):
        if isinstance(node, dict):
            if node.get('candidate_id') == 'R128_source_only_full_training':
                found.append(node)
            for value in list(node.values()):
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
    visit(policy)
    assert len(found) == 1 and 'competitive_review' not in found[0]
    found[0]['competitive_review'] = dict(report=report_rel,
        verification='Experiments/R128_SourceOnlyFullTraining/results/competitive_review/verification.json',
        measured_contour_rows=1080, same_physical_specimens=1, pillars=36, repeated_exposures=[13,14,15],
        models=['Raw','R61v16','R109_E48','R119_E42','R128_P_s1285002'],
        R128_best_aggregate_boundary_area_perimeter_among_listed=True,
        R128_vs_R109_improved_pillar_boundary_medians=[33,33],
        circularity_reference_sensitive=True, all_local_contour_errors_improved=False,
        LSC_existing_pairs_recomputed=120, R128_same_protocol_LSC_measured=False,
        Raw_relative_registration_is_not_LSC_score=True,
        next_action='Evaluate the existing single R128 with the same locked LSC pairs and reader; qualify SEM circularity reference before precision claims',
        new_training_updates=0, production_adopted=False, original_expected_hashes_unchanged=True)
    assert policy['formal_baseline'] == original['formal_baseline']
    replace_file(p, json.dumps(policy, indent=2, ensure_ascii=False)+'\n')

    p = REPO/'Experiments/INDEX.md'
    lines = p.read_text(encoding='utf-8-sig').splitlines()
    lines[2] = 'Last updated: 2026-09-10（R128同條件輪廓與近期模型比較完成；圓度未全面改善，同流程LSC仍待測）'
    idx = [i for i, line in enumerate(lines) if line.startswith('| R128 完整研究訓練 |')]
    assert len(idx) == 1
    lines[idx[0]] = '| R128 完整研究訓練 | [近期模型同條件比較](R128_SourceOnlyFullTraining/reports/R128_COMPETITIVE_REVIEW.md)・[完整SEM輪廓](R128_SourceOnlyFullTraining/reports/R128_FULL_CONTOUR_SEM.md) | 唯一保留版本：正常拍攝下輪廓、面積與周長整體領先所列R61/R109/R119；33/36顆輪廓勝R109，圓度結論依SEM參考改變，局部仍有退步。1080筆同條件比較與舊120對LSC彙整已核對，R128同流程LSC尚未測；未正式採用 |'
    replace_file(p, '\n'.join(lines)+'\n')
    p = ROOT/'README.md'
    text = p.read_text(encoding='utf-8-sig')
    assert 'R128_COMPETITIVE_REVIEW.md' not in text
    replace_file(p, text+'\n2026-09-10 matched competitive review: five fixed methods on the same36pillars xnormal13/14/15, with common Raw-derived alignment and both fixedSEMreferences. All1080rows independently verified. R128has best aggregateboundary/area/perimeter among listedRaw/R61/R109/R119/R128methods; circularityremains reference-sensitive and localworstcases canworsen. Historical120-pairLSC summaries reproduce, but R128has no same-protocolLSC result; the0.01319pxRaw-relative registrationdifference is notLSC improvement. See [comparison and next decision](reports/R128_COMPETITIVE_REVIEW.md). No newtraining or promotion.\n')
    p = REPO/'RECON_GALLERY.md'
    text = p.read_text(encoding='utf-8-sig')
    marker = '## R128 — 配對SEM上的完整外輪廓（2026-09-10）'
    assert text.count(marker) == 1
    entry = ('## R128 — 與近期模型的同條件比較（2026-09-10）\n\n'
             '同一試片36顆柱體、三張正常拍攝照片：R128的整體輪廓、面積與周長領先所列舊候選，圓度卻隨SEM參考輪廓改變結論。同流程LSC尚未測，不能把之前的原圖位移一致性當成LSC勝出。見 [完整比較與下一個判斷]('+report_rel+')。\n\n'
             '![相同照片的輪廓與圓度比較](Experiments/R128_SourceOnlyFullTraining/reports/figures/competitive_contour_circularity.png)\n\n')
    replace_file(p, text.replace(marker, entry+marker))
    for name in names:
        p = REPO/name
        if p.suffix == '.json':
            load(p)
    report = ROOT/'reports/R128_COMPETITIVE_REVIEW.md'
    missing = []
    for dest in re.findall(r'\]\(([^)]+)\)', report.read_text(encoding='utf-8')):
        if not (report.parent/dest).resolve().is_file():
            missing.append(dest)
    assert not missing
    save(out/'registration.json', dict(completed_utc=now(), report_links_valid=True, quick_handoff_lines=len(quick.strip().splitlines()), formal_baseline_unchanged=True, before=before, after={name:record(REPO/name) for name in names}, registration_source=record(__file__)))
    print('Supplemental report indexed; all links resolve; formal baseline unchanged.')


if __name__ == '__main__':
    main()
