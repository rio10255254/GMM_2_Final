"""Manual launcher, status, cooperative pause and resume."""
import argparse,subprocess,os,time,sys
from runtime import *
def status(name):
    p=ROOT/'results/training'/name/'status.json'
    if not p.exists():print('No run status yet');return
    s=load(p);print(json.dumps(s,ensure_ascii=False,indent=2))
def launch(name,resume=False):
    logs=ROOT/'results/launcher_logs';logs.mkdir(parents=True,exist_ok=True)
    command=[sys.executable,'-B',str(ROOT/'train_r129.py'),'--run',name]
    if resume:command+=['--resume']
    logpath=logs/f'{name}_{time.time_ns()}.log'
    with logpath.open('xb') as f:proc=subprocess.Popen(command,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    save(logpath.with_suffix('.json'),dict(pid=proc.pid,command=command,utc=now(),mutable_log_path=logpath.relative_to(ROOT).as_posix()))
    print('Started PID',proc.pid,'Log:',logpath)
def pause(name):
    run=ROOT/'results/training'/name
    if not run.exists():raise FileNotFoundError('No such run')
    p=run/'STOP_REQUESTED'
    if not p.exists():p.write_text('Manual pause requested '+now(),encoding='utf-8')
    print('Pause requested. The current update/evaluation will finish and save before stopping.')
def menu():
    name='r129_long_01'
    while True:
        print('\nR129 manual controls\n1 Start long training\n2 Resume\n3 Status\n4 Pause safely\n5 Reconstruct sample images\n6 Verify package\n0 Exit')
        value=input('Select: ').strip()
        try:
            if value=='0':return
            if value=='1':launch(name)
            elif value=='2':launch(name,True)
            elif value=='3':status(name)
            elif value=='4':pause(name)
            elif value=='5':subprocess.run([sys.executable,'-B',str(ROOT/'infer_r129.py'),'--output-name','manual_'+str(time.time_ns())],cwd=ROOT,check=True)
            elif value=='6':subprocess.run([sys.executable,'-B',str(ROOT/'verify_package.py')],cwd=ROOT,check=True)
        except Exception as e:print('Action failed:',e)
if __name__=='__main__':
    import sys
    p=argparse.ArgumentParser();p.add_argument('action',choices=['menu','start','resume','status','pause'],nargs='?',default='menu');p.add_argument('--run',default='r129_long_01');a=p.parse_args()
    if not a.run or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in a.run):p.error('Invalid run name')
    if a.action=='menu':menu()
    elif a.action=='start':launch(a.run)
    elif a.action=='resume':launch(a.run,True)
    elif a.action=='status':status(a.run)
    else:pause(a.run)
