"""Run the entire declared four-run schedule, with durable live state."""
import os,sys,time,subprocess,traceback,ctypes,argparse
from common import *
from train import verify_binding

def snapshot(cfg,status,pid,current=None,error=None):
    rows=[]
    for item in cfg['run_order']:
        p=ROOT/'runs'/f"{item['arm']}_s{item['seed']}"/'status.json'
        rows.append(load(p) if p.exists() else dict(**item,status='queued',completed_updates=0,planned_updates=cfg['updates_per_run']))
    result=dict(round='R128',status=status,active=status in ['starting','running'],pid=pid,current_run=current,planned_runs=4,planned_updates_per_run=cfg['updates_per_run'],planned_total_updates=4*cfg['updates_per_run'],completed_full_training_updates=sum(r['completed_updates'] for r in rows),completed_runs=sum(r['status']=='complete' for r in rows),runs=rows,updated_utc=now(),model_promoted=False,real_calibration_qualified=False)
    if error:result['error']=error
    atomic(ROOT/'runs/launcher_logs/active_formal_run.json',result)
    labels={'queued':'等候開始','training':'訓練中','evaluating_generated_dev':'正在檢查獨立生成場景','evaluating_real_microscopy_and_SEM':'正在檢查真實顯微影像與SEM','evaluating_final_generated_test':'正在做最後的生成影像測試','complete':'訓練與預定檢查完成','failed':'發生錯誤，已停止'}
    lines=['# R128 訓練進度','',f"紀錄時間：{result['updated_utc']}（UTC）", '',f"四組合計已完成 {result['completed_full_training_updates']:,} / {result['planned_total_updates']:,} 次更新。", '', '| 組別 | 已完成更新 | 狀態 |','|---|---:|---|']
    for r in rows:
        name=('影像學習' if r['arm']=='I' else '影像學習加成像核對')+('，第一次' if r['seed']==cfg['model_seeds'][0] else '，第二次')
        lines.append(f"| {name} | {r['completed_updates']:,} / {r['planned_updates']:,} | {labels.get(r['status'],r['status'])} |")
    lines+=['','這是執行中的進度紀錄。完整訓練和檢查跑完後，仍需一起檢視真實影像的效果與失敗案例，才能決定是否採用。']
    if error:lines+=['','背景執行已停止；詳細錯誤與最後存檔保留在執行紀錄中。']
    report=ROOT/'reports/TRAINING_PROGRESS.md';temporary=report.with_suffix('.writing')
    temporary.write_text('\n'.join(lines)+'\n',encoding='utf-8');temporary.replace(report)
    return result

def main(resume=False):
    cfg=load(ROOT/'config/study.json');binding=load(ROOT/'config/frozen_training.json');verify_binding(binding)
    lock=ROOT/'runs/launcher_logs/coordinator.lock'
    if lock.exists():
        previous=load(lock)
        # Never assume a lock is stale from a missing child or marker alone.
        raise RuntimeError(f'Existing coordinator lock requires process inspection: {previous}')
    save(lock,dict(pid=os.getpid(),started_utc=now(),resume=resume))
    power=ctypes.windll.kernel32.SetThreadExecutionState
    power(0x80000001)
    try:
        snapshot(cfg,'starting',os.getpid())
        for item in cfg['run_order']:
            name=f"{item['arm']}_s{item['seed']}";run=ROOT/'runs'/name;state_path=run/'status.json'
            if state_path.exists() and load(state_path)['status']=='complete':
                if not resume:raise RuntimeError('An earlier run exists; explicit resume required')
                completed=load(run/'completion.json')
                if completed['completed_updates']!=cfg['updates_per_run']:raise RuntimeError('Incomplete run mislabeled complete')
                for r in completed['records']:
                    if sha(r['path'])!=r['sha256']:raise RuntimeError('Completed run output changed')
                continue
            args=[sys.executable,'-u',str(ROOT/'scripts/train.py'),'--arm',item['arm'],'--seed',str(item['seed'])]
            if run.exists():
                if not resume:raise RuntimeError('Run directory already exists')
                args+=['--resume']
            stamp=now().replace(':','').replace('.','_')
            with (ROOT/'runs/launcher_logs'/f'{name}_{stamp}.stdout.log').open('x',encoding='utf-8') as stdout,(ROOT/'runs/launcher_logs'/f'{name}_{stamp}.stderr.log').open('x',encoding='utf-8') as stderr:
                child=subprocess.Popen(args,cwd=ROOT,stdout=stdout,stderr=stderr,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','CUBLAS_WORKSPACE_CONFIG':':4096:8'},creationflags=subprocess.CREATE_NO_WINDOW)
                while child.poll() is None:
                    snapshot(cfg,'running',os.getpid(),dict(name=name,pid=child.pid))
                    time.sleep(5)
                if child.returncode!=0:raise RuntimeError(f'{name} failed with exit{child.returncode}; retained logs and exact checkpoint')
            verify_binding(binding)
        result=snapshot(cfg,'complete',os.getpid())
        if result['completed_full_training_updates']!=32768 or result['completed_runs']!=4:raise RuntimeError('Incomplete declared schedule')
        save(ROOT/'results/full_training_execution_complete.json',dict(**result,scientific_effectiveness_requires_result_review=True))
    except BaseException:
        snapshot(cfg,'failed',os.getpid(),error=traceback.format_exc());raise
    finally:
        power(0x80000000)
        # Rename the execution lock to an immutable record, never erase it.
        if lock.exists():lock.rename(lock.with_name(f'coordinator_{os.getpid()}_closed.json'))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true');main(parser.parse_args().resume)
