"""Register a verified implementation-only organization without changing verdicts."""
import sys,json,ast,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import cv2,numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def main():
    check=load(ROOT/'results/organization/verification.json')
    assert check['passed'] and check['real_count']==11 and check['new_training_updates']==0
    for item in load(ROOT/'config/organization_plan.json')['original_files']+load(ROOT/'config/organization_plan.json')['organized_files']:
        assert sha(str(PROJECT_ROOT / item['path']))==item['sha256']
    output=ROOT/'results/organization/cli_sem13.png'
    assert np.array_equal(cv2.imread(str(output),0),cv2.imread(str(ROOT/'results/real/D_24/sem13.png'),0))
    before=sha(output)
    run=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/infer_organized.py'),'--input',str(ROOT/'results/real/D_24/sem13.png'),'--output',str(output)],capture_output=True)
    assert run.returncode==2 and b'Output already exists' in run.stderr and sha(output)==before
    python_files=list((ROOT/'model/organized').glob('*.py'))+[ROOT/'scripts/infer_organized.py']
    for path in python_files:ast.parse(path.read_text(encoding='utf-8-sig'))
    report='Experiments/R129_OpticalPriorHybrid/reports/R129_ARCHITECTURE.md'
    backup=ROOT/'results/organization/index_before';backup.mkdir(exist_ok=False)
    paths=[REPO/'PROJECT_STATE.md',REPO/'ESTIMATOR_POLICY.json',REPO/'Experiments/INDEX.md',ROOT/'README.md',ROOT/'MANIFEST.md',ROOT/'reports/R129_RESULTS.md',ROOT/'results/README.md']
    for n,path in enumerate(paths):(backup/f'{n}_{path.name}').write_bytes(path.read_bytes())
    path=REPO/'ESTIMATOR_POLICY.json';old=load(path);data=load(path)
    index=next(i for i,x in enumerate(data['open_side_tracks']) if x.get('round')=='R129')
    assert 'organization' not in data['open_side_tracks'][index]
    data['open_side_tracks'][index]['organization']=dict(date='2026-09-12',status='verified_behavior_preserving_organization',report=report,implementation='Experiments/R129_OpticalPriorHybrid/model/organized/hybrid.py',inference='Experiments/R129_OpticalPriorHybrid/scripts/infer_organized.py',same_D_checkpoint=True,exact_real_images=11,exact_forward_backward_checkpoints=8,new_training_updates=0,missing_modules_not_claimed_implemented=True,scientific_verdict_unchanged=True)
    assert data['formal_baseline']==old['formal_baseline'] and data['approved_alternates']==old['approved_alternates']
    for i in range(len(data['open_side_tracks'])):
        if i!=index:assert data['open_side_tracks'][i]==old['open_side_tracks'][i]
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    path=REPO/'PROJECT_STATE.md';text=path.read_text(encoding='utf-8-sig')
    needle='- **R129 thesis-design integration pilot complete (2026-09-12):**';assert text.count(needle)==1
    lines=text.splitlines()
    for i,line in enumerate(lines):
        if line.startswith(needle):lines[i]+=f' [Architecture organization]({report}) now verified: same weights, all8 checkpoint forward/backward checks and11 real outputs exact; step inspection is non-mutating. Zero new updates or efficacy change.'
    text='\n'.join(lines)+'\n'
    needle='### R129 V42-design integration: completed bounded pilot, retained prototype (2026-09-12)\n\n';assert text.count(needle)==1
    note=f'2026-09-12 organization follow-up: [{report}]({report}). User retains R129 as the next architecture; do not switch back to the old V42 backbone by default. Split optics/shared reconstruction/original-image output into an organized package without changing arithmetic, registered parameter names, checkpoint or active modules. All8 saved states have exact forward/input-gradient/parameter-gradient agreement; D three full SEM fields and eight fixed motion ROIs match old float outputs and historical PNGs exactly. Four observed intermediate states match independently reconstructed old states, and mutation of observation copies does not affect output. Existing source/weights remain unchanged. A new tested image entry uses the same D checkpoint. This does not implement the missing direction-specific branch, per-step full physical correction or uncertainty estimate, and does not establish speedup or new scientific efficacy. Zero new training; previous mixed-result verdict and qualification limits remain.\n\n'
    text=text.replace(needle,needle+note,1)
    quick=text.split('<!-- QUICK_HANDOFF_START -->')[1].split('<!-- QUICK_HANDOFF_END -->')[0]
    assert len(quick.splitlines())<=60
    path.write_text(text,encoding='utf-8')
    path=REPO/'Experiments/INDEX.md';text=path.read_text(encoding='utf-8-sig');lines=text.splitlines()
    for i,line in enumerate(lines):
        if line.startswith('| R129 保留論文設計的原型 |'):
            lines[i]=line[:-1]+f' [架構整理與原樣驗證](R129_OpticalPriorHybrid/reports/R129_ARCHITECTURE.md)：8份權重輸出／梯度、11張實拍完全一致；未新增訓練。 |'
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for relative,note in [
        ('README.md','\n## Verified architecture organization\n\n[Current architecture and module inventory](reports/R129_ARCHITECTURE.md) describes the organized implementation. `scripts/infer_organized.py` uses the same D step24 checkpoint and has been executed on a real full SEM-paired image. All eight checkpoint forward/backward checks and 11 original real-image outputs match exactly. New per-step inspection is non-mutating. The earlier `infer_image.py` remains available unchanged; this adds no training or scientific improvement claim.\n'),
        ('MANIFEST.md','\nOrganization supplement: model/organized/ contains seven files with hashes fixed in config/organization_plan.json. scripts/infer_organized.py is the tested new entry; the same D checkpoint is used. results/organization/verification.json covers exact outputs/gradients and safe step inspection. reports/R129_ARCHITECTURE.md plus reports/figures/R129_organized_architecture.png and .svg document current modules and explicit gaps. Original sources and checkpoints remain available.\n'),
        ('reports/R129_RESULTS.md','\n## 2026-09-12 架構整理補充\n\n[完整架構與各部分作用清單](R129_ARCHITECTURE.md) 已完成。整理後使用同一份 D 權重，八份既有權重的輸出／梯度一致，11 張既有實拍輸出逐像素一致；可查看四次修正而不改變結果。没有新增訓練或功能，也没有改寫以上短程實測結論。R129 保留作後續架構主體，缺少的分支與未證實的作用均另列。\n'),
        ('results/README.md','\n- `organization/`: completed behavior-preserving organization checks, one public-entry real output and four intermediate states. These are technical parity checks, not new model-performance results. Architecture PNG/SVG are under `reports/figures/`.\n')]:
        path=ROOT/relative
        with path.open('a',encoding='utf-8') as f:f.write(note)
    save(ROOT/'results/organization/delivery.json',dict(completed_utc=now(),source=record(__file__),report=record(REPO/report),entry=record(ROOT/'scripts/infer_organized.py'),verification=record(ROOT/'results/organization/verification.json'),public_entry_exact=True,public_entry_refuses_overwrite=True,parsed_files=len(python_files),original_research_verdict_preserved=True,new_training_updates=0,previous_current_indexes=[record(p) for p in backup.iterdir()],updated_files=[record(p) for p in paths]))
    print('Architecture, tested entry and current indexes registered; verdict unchanged')

if __name__=='__main__':main()
