"""Publish the independently recovered negative result, preserving prior failure records."""
from pathlib import Path
import sys,re,shutil,os
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rt import *
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def main():
    decision=load(ROOT/'results/long_admission.json');result=load(decision['motion201']['path']);assert not decision['eligible']
    assert sha(decision['motion201']['path'])==decision['motion201']['sha256'];failures=[x for x in result['checks'] if not x['passed']];assert len(failures)==1
    before=ROOT/'results/full_motion_recovery_v2/publication_before';before.mkdir(exist_ok=False);repo=ROOT.parent.parent
    paths=[ROOT/'results/continuation/status.json',ROOT/'reports/R134_RESULTS.md',ROOT/'README.md',repo/'PROJECT_STATE.md',repo/'ESTIMATOR_POLICY.json',repo/'Experiments/INDEX.md',repo/'docs/operations/PROJECT_STORAGE_REGISTRY.json']
    for i,p in enumerate(paths):shutil.copy2(p,before/f'{i}_{p.name}')
    status=dict(phase='not_admitted',pid=os.getpid(),updated_utc=now(),B_D_complete=False,model_promoted=False,long_training_started=False,reason=decision['reason'],recovery=record(Path(decision['motion201']['path'])),failed_requirements=failures)
    atomic(ROOT/'results/continuation/status.json',status)
    report=ROOT/'reports/R134_RESULTS.md';text=report.read_text(encoding='utf-8');body=text.split('## 已完成的比較',1)[1];body=body.split('執行錯誤原文：',1)[0]
    intro='''# R134 執行結果與目前狀態

**201張完整影像已完成並重新獨立核算；20項條件中19項通過、1項未通過，因此尚未打包或開始長訓練。**

原程序在輸出最後結果時遇到數值型別的儲存錯誤，留下不完整JSON；影像及量測已全部算完。舊錯誤記錄、不完整JSON、影像、量測、模型及事先門檻均原封保留。另建恢復結果，獨立重算1809個中心及634筆新模型／原始影像配對計算。

唯一未通過的是固定120對中的最大非預期方向偏移：20倍、0.5微米移動的第16至17張，同一例由原始影像43.2404nm增加至新模型48.6658nm，增加5.4254nm（12.547%），超過事先設定的10%上限。其餘19項通過。這個上限是工程篩選條件，不是物理真值認證；未通過也不能推導成整個模型毫無價值。

**下一步應先釐清這組連續影像的退步來源，再決定是否設計新的候選版本或新的訓練計畫。不能改寫本輪條件把此結果算成通過，也不以另一個起點替換原先選定者來迴避結果。** 每個真正合格的長訓練版本，仍維持單獨整合一包的要求。

恢復證據：`results/full_motion_recovery_v2/complete.json`；長訓練判定：`results/long_admission.json`。首次恢復時，逐張和總表的文字儲存往返差距最大4.55e-13像素，過度嚴格的完全相等檢查失敗；保留該版本，第二版以1e-10像素核對文字往返差距。科學門檻完全未變，最终仍判定不通過。

## 已完成的比較'''
    text=intro+body;text=text.replace('執行遇到錯誤，已保留記錄；未宣告完成。','已恢復核算，長訓練資格未通過。');report.write_text(text,encoding='utf-8')
    p=ROOT/'README.md';t=p.read_text(encoding='utf-8');t=t.replace('全部201張影像的後續檢查正在執行；不能將這個階段稱為長訓練完成。','全部201張影像已完成並恢復核算，20項條件有1項未通過；沒有建立獨立長訓練包，也沒有開始長訓練。').replace('後續執行程序會依次檢查','本輪已停止後續推進。原先設計的程序會依次檢查');p.write_text(t,encoding='utf-8')
    p=repo/'PROJECT_STATE.md';t=p.read_text(encoding='utf-8-sig');t=re.sub(r'(?m)^Last updated:.*$', 'Last updated: 2026-09-15（R134完整201張恢復核算；19/20條件通過，未啟動長訓練）',t,count=1)
    t=re.sub(r'\*\*R134執行中（2026-09-15）：\*\*.*?(?= \*\*R133)', '**R134（2026-09-15）：** 201張及獨立核算完成；19/20項通過，20倍同一例非預期方向偏移43.240→48.666nm（+12.55%，上限+10%），未打包或長訓練。[結果](Experiments/R134_DirectStateRepair/reports/R134_RESULTS.md)。原儲存錯誤與全部輸出保留，門檻未變；B/D仍待獨立校準。',t,count=1)
    start=t.index('### R134 ');end=t.index('### R133 ',start);t=t[:start]+'''### R134 complete full201 screening, not admitted (2026-09-15)

All201 images were computed; closeout failed because a NumPy boolean could not be serialized. The original partial JSON and every output remain unchanged. Independent recovery refit1809centers and recomputed634candidate/Raw pair rows, using unchanged prospective thresholds.19/20checks pass; locked120maximum cross-axis48.665763nm vsRaw43.240395nm (same20x_0p5umframes16to17), ratio1.125470 exceeds1.10. No long package or long training, no alternate-seed substitution or promotion. Canonical report: Experiments/R134_DirectStateRepair/reports/R134_RESULTS.md. Correct recovery is results/full_motion_recovery_v2/complete.json, referenced by long_admission.json; do not parse the retained incomplete original as a completion. Original A/C short results remain valid within their scope. B/D unexecuted pending independent calibration.

'''+t[end:];p.write_text(t,encoding='utf-8')
    p=repo/'ESTIMATOR_POLICY.json';v=load(p);x=next(x for x in v['open_side_tracks'] if x.get('candidate_id')=='R134_direct_state');x.update(status='full201_recovered_not_admitted',completed_short_updates=2048,full201_complete=True,full201_checks_passed=19,full201_checks_total=20,long_training_started=False,long_package_created=False,recovery='Experiments/R134_DirectStateRepair/results/full_motion_recovery_v2/complete.json',model_promoted=False);atomic(p,v)
    p=repo/'Experiments/INDEX.md';t=p.read_text(encoding='utf-8-sig');t=re.sub(r'(?m)^\| R134 .*$', '| R134 直接影像狀態修正 | [當前結果](R134_DirectStateRepair/reports/R134_RESULTS.md) | 完整201張恢復核算：19/20項通過，最大非預期方向偏移超限；未打包或長訓練；B/D待校準 |',t);p.write_text(t,encoding='utf-8')
    p=repo/'docs/operations/PROJECT_STORAGE_REGISTRY.json';v=load(p);x=next(x for x in v['entries'] if x['id']=='r134_direct_state');x['state']='full201_recovered_not_admitted';atomic(p,v)
    verify();assert all(sha(str(PROJECT_ROOT / x['path']))==x['sha256'] for x in load(ROOT/'config/packaging_source_binding.json')['sources']);save(ROOT/'results/full_motion_recovery_v2/publication_verified.json',dict(original_frozen_sources_unchanged=True,thresholds_unchanged=True,decision=record(ROOT/'results/long_admission.json'),long_training_started=False));print('Negative admission published; original sources and thresholds unchanged')
if __name__=='__main__':main()
