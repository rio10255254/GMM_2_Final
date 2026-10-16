"""Continue all four unchanged runs; distinguish interruption from completion."""
import sys,os,time,subprocess,traceback,ctypes
from pathlib import Path
REC=Path(__file__).resolve().parent;ROOT=REC.parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT))
from common import load,save,sha,record,now
from robust_io import atomic,progress,read_json_retry
from run_child import verify_recovery
from train import verify_binding

def completed(run,cfg):
    cp=run/'completion.json'
    if not cp.exists():return False
    result=load(cp)
    if result['completed_updates']!=cfg['updates_per_run']:raise RuntimeError('Incorrect completion count')
    for item in result['records']:
        if sha(item['path'])!=item['sha256']:raise RuntimeError('Completed result missing or changed')
    return True

def snapshot(cfg,phase,current=None,error=None):
    rows=[]
    for item in cfg['run_order']:
        run=ROOT/'runs'/f"{item['arm']}_s{item['seed']}";p=run/'status.json'
        row=read_json_retry(p) if p.exists() else dict(**item,status='queued',completed_updates=0,planned_updates=8192)
        if phase=='failed' and row['status'] not in ['queued','complete']:row={**row,'status':'interrupted','last_trainer_status':row['status']}
        rows.append(row)
    data=dict(round='R128',status=phase,active=phase=='running',pid=os.getpid(),current_run=current,planned_runs=4,planned_updates_per_run=8192,planned_total_updates=32768,completed_full_training_updates=sum(r['completed_updates'] for r in rows),completed_runs=sum(r['status']=='complete' for r in rows),runs=rows,updated_utc=now(),recovery_manifest=record(REC/'recovery_manifest.json'),model_promoted=False,real_calibration_qualified=False)
    if error:data['error']=error
    atomic(ROOT/'runs/launcher_logs/active_formal_run.json',data)
    labels={'queued':'等候開始','training':'訓練中','evaluating_generated_dev':'檢查独立生成場景','evaluating_real_microscopy_and_SEM':'檢查真實顯微與SEM','evaluating_final_generated_test':'最後生成影像測試','complete':'訓練與預定檢查完成','failed':'中斷','interrupted':'中斷'}
    overall={'running':'執行中','failed':'中斷，尚未完成','complete':'四組訓練與預定檢查全部完成'}[phase]
    text=['# R128 訓練進度','',f'總狀態：**{overall}**',f"紀錄時間：{data['updated_utc']}（UTC）",'',f"四組已完成 {data['completed_full_training_updates']:,} / 32,768 次更新。重算的步驟不重複累計。",'','| 組別 | 更新次數 | 狀態 |','|---|---:|---|']
    for r in rows:
        name=('影像學習' if r['arm']=='I' else '影像學習加成像核對')+('，第一次' if r['seed']==1285001 else '，第二次')
        text.append(f"| {name} | {r['completed_updates']:,} / 8,192 | {labels.get(r['status'],r['status'])} |")
    text+=['','先前在第1,393次更新後因進度寫入失敗中斷，已保留紀錄並從第1,280次完整存檔續跑。','','訓練全部完成後，仍須一起檢視真實影像的效果與失敗案例，才能決定是否採用。']
    progress('\n'.join(text)+'\n')
    return data

def main():
    verify_recovery();cfg=load(ROOT/'config/study.json');verify_binding(load(ROOT/'config/frozen_training.json'))
    lock=REC/'coordinator.lock';save(lock,dict(pid=os.getpid(),started_utc=now()))
    power=ctypes.windll.kernel32.SetThreadExecutionState;power(0x80000001);child=None
    try:
        for item in cfg['run_order']:
            run=ROOT/'runs'/f"{item['arm']}_s{item['seed']}"
            if completed(run,cfg):continue
            name=run.name;stamp=now().replace(':','').replace('.','_')
            args=[sys.executable,'-u',str(REC/'run_child.py'),'--arm',item['arm'],'--seed',str(item['seed'])]
            if run.exists():args+=['--resume']
            with (REC/f'{name}_{stamp}.stdout.log').open('x',encoding='utf-8') as out,(REC/f'{name}_{stamp}.stderr.log').open('x',encoding='utf-8') as err:
                child=subprocess.Popen(args,cwd=ROOT,stdout=out,stderr=err,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','CUBLAS_WORKSPACE_CONFIG':':4096:8'},creationflags=subprocess.CREATE_NO_WINDOW)
                while child.poll() is None:
                    snapshot(cfg,'running',dict(name=name,pid=child.pid));time.sleep(5)
                if child.returncode!=0:raise RuntimeError(f'{name} interrupted: exit{child.returncode}')
            if not completed(run,cfg):raise RuntimeError('Child exited without complete training/evaluations')
            verify_recovery();verify_binding(load(ROOT/'config/frozen_training.json'))
        data=snapshot(cfg,'complete')
        if data['completed_runs']!=4 or data['completed_full_training_updates']!=32768:raise RuntimeError('Incomplete declared study')
        save(ROOT/'results/full_training_execution_complete.json',dict(**data,scientific_effectiveness_requires_result_review=True))
    except BaseException:
        # No silent orphan may continue under a stopped-coordinator display.
        if child is not None and child.poll() is None:
            child.terminate();child.wait(timeout=20)
        snapshot(cfg,'failed',error=traceback.format_exc());raise
    finally:
        power(0x80000000)
        if lock.exists():lock.rename(REC/f'coordinator_{os.getpid()}_closed.json')

if __name__=='__main__':main()
