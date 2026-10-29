"""Register the actually running independent R129 training package."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import psutil
PROJECT_ROOT = Path(__file__).resolve().parents[3]
def main():
    pkg=Path(PROJECT_ROOT / load(ROOT/'config/standalone_build.json')['path']);cycle=load(pkg/'results/manual_training_cycle.json')
    ready=load(pkg/'results/preflight/complete.json');moved=load(pkg/'results/relocation_test.json')
    status=load(pkg/'results/training/r129_long_01/status.json')
    assert ready['passed'] and moved['passed'] and cycle['passed']
    assert status['status']=='training' and status['completed_updates']>=cycle['verified_continued_updates'] and psutil.pid_exists(status['pid'])
    assert not (pkg/'results/training/r129_long_01/completion.json').exists()
    source_manifest=load(pkg/'PROVENANCE.json')
    # Recheck every original resource copied into the package. No old file was edited.
    for item in source_manifest['copied_files']:
        assert sha(item['source'])==item['sha256'],item['source']
        assert sha(pkg/item['destination'])==item['sha256'],item['destination']
    report=ROOT/'reports/R129_STANDALONE_TRAINING.md';relative=report.relative_to(REPO).as_posix();size=sum(p.stat().st_size for p in pkg.rglob('*') if p.is_file())/1024**3
    text=f'''# R129 獨立操作套件與長訓練

日期：2026-09-12。已完成獨立套件、實際試跑及正式訓練啟動；**長訓練尚未完成**，没有模型升級。

## 套件與操作

套件位置：`{pkg}`。

操作入口是包內 **START_R129.cmd**；說明是 **README_TW.md**。可開始新訓練、安全暫停、續訓、查看狀態、核對套件與重建範例影像。訓練在背景執行，關閉選單不會停止訓練；以選單 Pause safely 暫停。相同名稱不能重複開始，已有訓練請選 Resume。

自帶768組完整合成來源（512訓練／128開發／128測試）、起始模型、固定光學資料、三張完整SEM配對光學影像與八張位移區域，以及同讀法的SEM／位移工具。靜態清單共 {load(pkg/'PACKAGE_MANIFEST.json')['count']} 個檔案，交付檢查時含試跑與活動結果約 {size:.3f} GiB。原資料與模型均保留；複製資料是使用者要求獨立操作而明確建立的套件副本。

套件程式／資料不依赖原 R128/R129/R61 實驗路徑，**Python/CUDA 和 MATLAB 沿用本機安裝，沒有內藏軟體本體或授權**。MATLAB 與 Image Processing Toolbox 是重現既有SEM粗輪廓的必要工具；Python、PyTorch及相關庫的本機版本記於 ENVIRONMENT.json。已用實際主機驗證，不以依賴清單存在就宣稱環境可用。

## 本次訓練設定

| 項目 | 固定設定 |
|---|---|
| 主模型 | R129 D 整理版，光學融合及改善上取樣都保留 |
| 起始位置 | D 第24次既有權重；重新建立優化器，沒有隨機重新初始化主幹 |
| 次數 | 一個模型，16個資料循環，共8192次新更新 |
| 每次資料 | 一個來源的兩張影像；每循環重加獨立雜訊，不把重用幾何當作新場景 |
| 優化 | AdamW，128次暖身，最高1e-4逐步降至1e-5，梯度上限5 |
| 訓練要求 | 沿用R129短測的原生影像＋0.2邊緣＋0.2配對殘差，沒有聲稱補上不存在的物理或方向分支 |
| 保存 | 每128次，以及指定驗證點、安全暫停時 |
| 開發驗證 | 第0次及之後每512次，128組全部評估 |
| 真實影像驗證 | 第0、512、2048、4096、8192次，同一正常SEM／位移面板 |
| 最終合成測試 | 完成8192次後評估既有128組測試資料，非新未知測試 |
| 模型選擇 | 報告全部指定保存點，預定終點8192；不自動覆寫原起始模型或推廣到正式模型 |

所有既有可學習參數都參與訓練。固定光學核與固定放大濾波不當作學習參數。模型結構與初始輸出維持上一輪原樣；原 R129 的細節不足不會因為這份套件已完成就變成已解決。

## 已實際驗證

1. 全部 {load(pkg/'PACKAGE_MANIFEST.json')['count']} 個靜態資源逐檔核對，512／128／128分組的幾何來源不重疊，所有訓練紀錄的外部實拍／SEM答案來源標記為空。
2. 從同一初值跑8次更新，與先跑4次、保存、重新載入再跑4次比較：模型及優化器狀態完全一致。共16次測試用更新，測試權重獨立保存，沒有混入正式8192次訓練。
3. 三張完整SEM光學圖與八張位移區域的重建均與原R129完全一致；108筆細輪廓量與72個位移圓心也重現原讀值。
4. 整包實際移到另一個位置，從不同工作目錄執行套件核對、CPU訓練試跑、GPU影像重建與Windows操作選單，再移回；範例輸出與原R129完全一致。
5. 正式訓練已實際開始，於第 {cycle['paused_updates']} 次更新測試安全暫停並保存，之後續跑到至少第 {cycle['verified_continued_updates']} 次；交付檢查時為第 {status['completed_updates']}/8192 次，PID {status['pid']} 存活且狀態為training。進度是時間點快照，之後看包內status.json。

起始SEM中位數與原D相同：輪廓半徑誤差41.579nm、細部形狀相關0.668942、尺寸誤差80.679nm、扣除平均尺寸的形狀誤差21.352nm、非圓程度差距86.605nm。這些是訓練前的基準，不能當作長訓練改善成績。

## 適用性與判讀邊界

合成資料覆蓋不規則曲線、線角、密集結構、紋理、乾淨／有雜訊與空白情況，足以進行現有架構的可追溯研究訓練。固定光學先驗是V42歷史校準資料，不是每個場景的真實PSF，也沒有本次新增20×／50×獨立儀器校準。故這次要研究充分訓練後的真實效果，不能事先保證真實尺寸與位移改善。

每次的真實面板仍是36顆既有配對柱子與四對位移區域；不支持完整時間波動、跨樣品或未知場景保證。訓練標籤未使用實拍／SEM影像答案，但光學先驗有歷史SEM校準背景，不能把整個系統稱為與SEM來源完全無關。舊144張封存確認集沒有重新取用；舊R119因果更正依然優先。

程序消失、訓練數字到頂或存在權重，都不能單獨算完成；只有8192次及全部指定驗證輸出完成後才建立completion.json。現階段只完成「套件與啟動」。

## 證據入口

- 包內 PACKAGE_MANIFEST.json／PROVENANCE.json：靜態清單與原始複製來源。
- results/preflight/complete.json：資料、實際續訓與真實量測一致性。
- results/relocation_test.json：搬動後的公開入口及操作選單試跑。
- results/manual_training_cycle.json：正式訓練的安全暫停、保存與續跑實測。
- results/training/r129_long_01/status.json／latest_checkpoint.json／updates_*.jsonl：活動進度、可續訓位置及每次實际消耗資料。
- results/training/r129_long_01/evaluations/：各指定保存點的合成／真實結果。

COMBO正式基準不變；R129目前仍為研究模型。原始實驗來源、結果與收據的預期雜湊沒有為這次打包重設。
'''
    report.write_text(text,encoding='utf-8')
    backups=ROOT/'results/standalone_registration_before';backups.mkdir(exist_ok=False)
    paths=[REPO/'PROJECT_STATE.md',REPO/'ESTIMATOR_POLICY.json',REPO/'Experiments/INDEX.md',REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json',ROOT/'README.md',ROOT/'reports/R129_RESULTS.md']
    for i,p in enumerate(paths):(backups/f'{i}_{p.name}').write_bytes(p.read_bytes())
    path=REPO/'ESTIMATOR_POLICY.json';policy=load(path);original_baseline=policy['formal_baseline'];item=next(x for x in policy['open_side_tracks'] if x.get('round')=='R129')
    item['prior_pilot_status']=item['status'];item['status']='standalone_long_training_running'
    item['long_training']=dict(package=str(pkg),report=relative,run='r129_long_01',planned_updates=8192,observed_updates=status['completed_updates'],observed_utc=status['updated_utc'],observed_pid=status['pid'],status='running',live_status=str(pkg/'results/training/r129_long_01/status.json'),all_data_local=True,preflight_passed=True,relocation_passed=True,manual_pause_resume_passed=True,default_model_not_replaced=True,full_training_complete=False,model_promoted=False)
    assert policy['formal_baseline']==original_baseline
    path.write_text(json.dumps(policy,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    path=REPO/'PROJECT_STATE.md';s=path.read_text(encoding='utf-8-sig');lines=s.splitlines();lines[2]='Last updated: 2026-09-12（R129獨立套件與試跑完成，一個8192次長訓練已啟動；尚未訓練完成或升級）'
    for i,line in enumerate(lines):
        if line.startswith('- **R129 thesis-design integration'):
            lines[i]=f'- **R129 standalone long training active (2026-09-12):** [Package and verified launch]({relative}). Self-contained data/model/evaluation package at Model_Packages/R129_OpticalHybrid_Standalone_20260912;1603staticfiles,768sourceparents,oneDcontinuation8192updates. Full data, exact optimizer resume,11real outputs/108SEMmetrics/72motioncenters and actual relocation/menu tests pass. Manual pause/resume of live run verified. Training is active, not complete or promoted; initial model remains default. Prior pilot mixed results and organized-model equality remain documented in R129_RESULTS/R129_ARCHITECTURE.'
    s='\n'.join(lines)+'\n';needle='### R129 V42-design integration: completed bounded pilot, retained prototype (2026-09-12)\n\n'
    note=f'2026-09-12 standalone training follow-up: [{relative}]({relative}). User requested a manually operated independent package and start of full training. All768source parents copied with hashes; hostPython/CUDA andMATLAB remain external software dependencies. SingleD continuation,16epochs/8192new updates,128-update saves,128devcases every512,real3SEM/4motionpairs at0/512/2048/4096/8192; native image+gradient+pair loss matches pilot. All inputs/code/weights local, full audit,16discarded probe updates, exact optimizer resume and original real-reader parity pass. Package physically relocated for public dry-run/inference/menu checks, then restored. Real training paused/saved at{cycle["paused_updates"]} and resumed; observed{status["completed_updates"]}/8192 at{status["updated_utc"]}, PID{status["pid"]}. Current status file is inside package results/training/r129_long_01. This is a verified start, not training completion, superiority or production promotion. Default inference remains originalD; old records and confirmation remain untouched.\n\n'
    assert needle in s;s=s.replace(needle,needle+note,1)
    assert len(s.split('<!-- QUICK_HANDOFF_START -->')[1].split('<!-- QUICK_HANDOFF_END -->')[0].splitlines())<=60
    path.write_text(s,encoding='utf-8')
    path=REPO/'Experiments/INDEX.md';s=path.read_text(encoding='utf-8-sig');lines=s.splitlines()
    for i,line in enumerate(lines):
        if line.startswith('| R129 保留論文設計的原型 |'):
            lines[i]=f'| R129 架構與獨立長訓練 | [套件與啟動驗證](R129_OpticalPriorHybrid/reports/R129_STANDALONE_TRAINING.md)・[架構](R129_OpticalPriorHybrid/reports/R129_ARCHITECTURE.md) | 獨立資料／模型／真實驗證包已通過搬動、試跑與實際暫停續訓；一個8192次R129 D長訓練正在執行。尚未完成或升級，原型及既有混合結果保留 |'
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    path=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json';registry=load(path);item=next(x for x in registry['entries'] if x.get('id')=='r129_standalone_long_training');item.update(state='long_training_running',size_gib_snapshot=size,report=relative);registry['updated_at']=now();path.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (ROOT/'README.md').open('a',encoding='utf-8') as f:f.write('\n## Standalone full-training follow-up\n\nThe user-requested independent package and one8192-update continuation are now running. See [package, manual controls and verified launch](reports/R129_STANDALONE_TRAINING.md). This does not replace the initial model or mean long training is complete.\n')
    with (ROOT/'reports/R129_RESULTS.md').open('a',encoding='utf-8') as f:f.write('\n## 2026-09-12 獨立套件與長訓練\n\n[套件與啟動實測](R129_STANDALONE_TRAINING.md) 已完成，使用者要求的一個8192次D延續訓練正在執行。資料、公開入口、搬動與實際暫停續訓已核對；未宣稱訓練完成或改善，以上短測結果保持原義。\n')
    save(ROOT/'results/standalone_delivery.json',dict(completed_utc=now(),source=record(__file__),package=str(pkg),report=record(report),preflight=record(pkg/'results/preflight/complete.json'),relocation=record(pkg/'results/relocation_test.json'),manual_cycle=record(pkg/'results/manual_training_cycle.json'),observed_status=status,source_copies_verified=len(source_manifest['copied_files']),original_baseline_unchanged=True,full_training_complete=False,updated_current_indexes=[record(p) for p in paths]))
    print('Standalone package delivered; verified live training at',status['completed_updates'],'/',status['planned_updates'])
if __name__=='__main__':main()
