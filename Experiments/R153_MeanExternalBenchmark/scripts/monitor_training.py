"""Inspect the live queue; --ensure restores an absent queue without duplicate workers."""
from pathlib import Path
import argparse,datetime,json,math,os,shutil,subprocess,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import psutil
from study import read,save,sha
from normal_protocol import COMMON

ORDER=['EDSR-x1','NAFNet','RDN-x1','RCAN-x1','Restormer','USRNet-x1','SwinIR']


def human_report(result):
    rows=[]
    for item in result['methods']:
        state={'active':'進行中','waiting':'等待接續','complete':'已完成','failed':'待查明異常','paused_for_validation':'保存後暫停供驗證','user_paused':'依使用者要求暫停'}[item['state']]
        detail=''
        if item['state']=='active' and item.get('progress'):
            progress=item['progress'];phase=progress.get('state');step=int(progress.get('step',0))
            if phase=='validation':detail=f'第 {step//512} 輪訓練完成，正在合成驗證。'
            elif phase=='initial_validation':detail='正在做訓練前的合成驗證。'
            elif phase=='loading_data':detail='正在準備固定訓練影像。'
            elif phase=='synthetic_test':detail='訓練已結束，正在做最後合成測試。'
            else:detail=f'正在第 {max(1,math.ceil(step/512))} 輪；累計已看過 {step/512:.2f} 輪資料。'
        elif item['state']=='complete':detail=f"訓練 {item['epochs_trained']} 輪，選用合成驗證第 {item['selected_epoch']} 輪。"
        rows.append(f"| {item['method']} | {state} | {detail} |")
    text='''# 外部模型訓練監看與自動接續

已啟用本對話的自動巡檢，依目前模型預估完成時間加少量緩衝後，快速確認進度、實際程序、訓練與驗證紀錄、完成權重及下一個模型的接續狀態；每次按目前模型重新安排下一個檢查時間。正常進度保持安靜；完成、接續、恢復、異常或需要使用者介入時才回報。

接續順序：EDSR-x1 → NAFNet → RDN-x1 → RCAN-x1 → Restormer → USRNet-x1 → SwinIR。各模型從零，使用各自的一般訓練目標與設定；停止與權重選擇只看共同合成驗證資料。

| 方法 | 狀態 | 進度 |
| --- | --- | --- |
'''+ '\n'.join(rows)+'''

主管意外消失時，巡檢先確認沒有仍在跑的訓練子程序，再恢复佇列及保存點。使用者的暫停與取消指示優先。U-Net、MambaIRv2目前有官方後端環境阻礙，原因與建置紀錄已保留。

訓練完成後還需完成同批930張實拍驗證、新效率量測、完整benchmark報告及論文修改對照表；訓練結束不代表全部比較已完成。

請保持電腦與Codex開啟，讓自動巡檢持續運作。
'''
    text=text.replace('恢复','恢復')
    if (ROOT/'config/TIME_BUDGET_OVERRIDE.json').exists():
        text += '\n最新時間限制：尚未開始的RCAN-x1、Restormer、USRNet-x1與SwinIR最多8輪。EDSR-x1／NAFNet已完成結果保留；RDN-x1以已保存的合成驗證最佳結果完成測試後結束。完整輪數與保存的未完成輪更新分開記錄；本次為較短訓練比較，所有實拍驗證仍須完成。\n'
    if result.get('validation_priority_active'):
        text += '\n使用者已授權先暫停訓練釋放GPU。正在完成已訓練方法的實拍比較與效率測試，進度見runs/validation_logs/status.json；驗證優先標記存在時不恢復訓練。完成本階段並核對成果後，驗證主管會自動恢復保存的短訓練佇列。\n'
    (ROOT/'reports/TRAINING_MONITOR.md').write_text(text,encoding='utf-8')


def processes():
    managers=[];workers=[]
    for process in psutil.process_iter(['name','cmdline']):
        try:
            command=process.info['cmdline'] or []
            normalized=[str(a).replace('\\','/').lower() for a in command]
            if not (process.info['name'] or '').lower().startswith('python'):continue
            if any(a==str(ROOT/'scripts/train_queue.py').replace('\\','/').lower() for a in normalized):managers.append(process.pid)
            if any(a==str(ROOT/'scripts/train_external.py').replace('\\','/').lower() for a in normalized):
                if '--max-updates' not in command and '--assessment-limit' not in command:
                    workers.append({'pid':process.pid,'method':next((m for m in ORDER if m in command),None)})
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    return managers,workers


def completion(method):
    directory=ROOT/'runs'/method
    receipt=directory/'training_complete.json'
    if not receipt.exists():return None
    done=read(receipt)
    assert done['state']=='complete' and done['method']==method
    assert COMMON['min_epochs']<=done['epochs_trained']<=COMMON['max_epochs']
    assert done['epochs_trained']<=done['common_validation_protocol']['max_epochs']
    partial=done.get('partial_epoch_saved_updates',0)
    assert 0<=partial<512
    assert done['updates']==done['epochs_trained']*512+partial
    if partial:
        assert done['stopping_reason']=='user_authorized_short_budget_stop_using_saved_best'
        assert done['duration_revision']['user_authorized'] is True
    assert 1<=done['selected_epoch']<=done['epochs_trained']
    assert done['selected_step']==done['selected_epoch']*512
    assert done['real_data_used_in_training_or_selection'] is False
    assert sha(directory/'selected.pth')==done['checkpoint_sha256']
    assert (directory/'synthetic_test.json').is_file()
    return done


def inspect(ensure=False):
    managers,workers=processes()
    queue_file=ROOT/'runs/launcher_logs/active_formal_run.json'
    queue=read(queue_file) if queue_file.exists() else {}
    priority_file=ROOT/'runs/launcher_logs/VALIDATION_PRIORITY.json'
    priority=read(priority_file) if priority_file.exists() else None
    rows=[];completed=[];failures=[];issues=[]
    for method in ORDER:
        directory=ROOT/'runs'/method
        try:done=completion(method)
        except (AssertionError,ValueError,OSError) as error:
            issues.append({'method':method,'reason':'invalid completion receipt or selected checkpoint','error':str(error)})
            done=None
        active=next((w for w in workers if w['method']==method),None)
        status_file=directory/'status.json'
        current=read(status_file) if status_file.exists() else None
        if done is not None:
            completed.append(method)
            row={'method':method,'state':'complete','epochs_trained':done['epochs_trained'],'selected_epoch':done['selected_epoch'],
                 'validation_PSNR_dB':done['validation_PSNR_dB'],'checkpoint_sha256':done['checkpoint_sha256']}
        elif active is not None:
            row={'method':method,'state':'active','pid':active['pid'],'progress':current}
            log=ROOT/'runs/launcher_logs'/(method+'.log')
            latest=max([p.stat().st_mtime for p in (status_file,log,directory/'last.pth') if p.exists()] or [0])
            silence=datetime.datetime.now().timestamp()-latest
            row['seconds_since_progress_file_change']=silence
            if silence>45*60:issues.append({'method':method,'reason':'no progress file or log change for over 45 minutes; inspect phase before any restart'})
        elif (directory/'failure.json').exists():
            failures.append(method);row={'method':method,'state':'failed','failure':read(directory/'failure.json')}
        else:row={'method':method,'state':'user_paused' if (ROOT/'runs/launcher_logs/USER_STOP_REQUESTED').exists() and method==queue.get('current_method') else 'paused_for_validation' if priority and method==priority['training_queue_before']['current_method'] else 'waiting','saved_checkpoint_available':(directory/'last.pth').is_file()}
        rows.append(row)
    if len(managers)>1 or len(workers)>1:issues.append({'reason':'multiple study training managers/workers; do not start another process'})
    validation_file=ROOT/'runs/validation_logs/status.json'
    validation=read(validation_file) if validation_file.exists() else None
    final_file=ROOT/'runs/final_validation_logs/status.json'
    final_validation=read(final_file) if final_file.exists() else None
    if priority and priority.get('scope')=='final_remaining_validation':validation=final_validation
    completed_file=ROOT/'runs/completed_validation_logs/status.json'
    completed_validation=read(completed_file) if completed_file.exists() else None
    if priority and priority.get('scope')=='completed_only_validation':validation=completed_validation
    if priority and validation and validation['state']=='failed':issues.append({'reason':'validation failed; inspect preserved validation log before restoring training','validation':validation})
    if priority and validation and validation['state']=='active' and not psutil.pid_exists(validation['pid']):
        issues.append({'reason':'validation supervisor absent; check child and measurement processes before resuming validation','validation':validation})
    repaired=False
    paused=(ROOT/'runs/launcher_logs/USER_STOP_REQUESTED').exists()
    validation_priority=(ROOT/'runs/launcher_logs/VALIDATION_PRIORITY.json').exists()
    # A living orphan worker is allowed to finish. The next check restores the manager only after it exits.
    if ensure and not paused and not validation_priority and not managers and not workers and len(completed)<len(ORDER) and not failures and not issues:
        logs=ROOT/'runs/launcher_logs';logs.mkdir(parents=True,exist_ok=True)
        with (logs/'queue_stdout.log').open('a',encoding='utf-8') as stdout,(logs/'queue_stderr.log').open('a',encoding='utf-8') as stderr:
            process=subprocess.Popen([sys.executable,'-B','-X','utf8',str(ROOT/'scripts/train_queue.py')],cwd=str(ROOT),
                 stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        repaired=True;managers=[process.pid]
    result={'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'manager_pids':managers,'workers':workers,
            'queue_state':queue.get('state'),'current_method':queue.get('current_method'),'ordered_methods':ORDER,
            'completed':completed,'failed':failures,'issues':issues,'manager_restored':repaired,
            'user_stop_marker_present':paused,'d_free_gib':shutil.disk_usage(ROOT).free/2**30,
            'validation_priority_active':validation_priority,
            'validation_stage':validation,
            'final_validation_stage':final_validation,
            'completed_only_validation_stage':completed_validation,
            'all_eligible_trainings_verified_complete':len(completed)==len(ORDER),
            'next_stage':'complete real930 comparison and fresh runtime; training completion alone is not benchmark completion',
            'methods':rows}
    save(ROOT/'runs/launcher_logs/monitor_snapshot.json',result)
    human_report(result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--ensure',action='store_true');args=parser.parse_args()
    print(json.dumps(inspect(args.ensure),ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
