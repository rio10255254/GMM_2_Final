"""Wait for authorized short trainings, then validate methods missing from the verified handoff."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,subprocess,sys,time,traceback,zipfile
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from study import read,save,sha
from scripts.monitor_training import ORDER,completion,processes
import psutil

NEW=['Restormer','USRNet-x1','SwinIR']
LOGS=ROOT/'runs/final_validation_logs'


def main():
    global NEW,LOGS
    parser=argparse.ArgumentParser();parser.add_argument('--watch',action='store_true');parser.add_argument('--inspect',action='store_true');parser.add_argument('--completed-only',action='store_true');args=parser.parse_args()
    required=list(ORDER)
    scope='final_remaining_validation'
    reused_methods=[]
    if args.completed_only:
        config=read(ROOT/'config/COMPLETED_ONLY_SCOPE.json');assert config['user_explicitly_paused_SwinIR'] and config['validation_of_completed_models_authorized']
        NEW=config['new_methods'];required=[m for m in ORDER if m not in config['exclude_paused_methods']]
        LOGS=ROOT/'runs/completed_validation_logs';scope='completed_only_validation'
    elif (ROOT/'config/USER_RESUME_20261006.json').exists():
        authorization=read(ROOT/'config/USER_RESUME_20261006.json')
        assert authorization['automatic_training_resume_allowed'] is True
        previous_handoff=read(ROOT/'results/completed_models/handoff_verified.json')
        assert previous_handoff['state']=='passed'
        assert sha(previous_handoff['archive'])==previous_handoff['archive_sha256']
        reused_methods=previous_handoff['completed_scope']
        assert len(reused_methods)==9 and 'SwinIR' not in reused_methods
        for method in ('Restormer','USRNet-x1'):
            assert completion(method) is not None
            assert read(ROOT/'results/runtime'/(method+'.json'))['state']=='complete'
            assert read(ROOT/'results/reconstruction'/method/'reconstruction_complete.json')['images']==930
            assert read(ROOT/'results/readouts'/method/'measurement_complete.json')['attempted_pillars']==8370
        NEW=['SwinIR']
    if args.inspect:
        print(json.dumps({'new_runtime_and_real_methods':NEW,'old_seven_repeated':False,'verified_methods_reused':reused_methods,'required_trainings':required,
                          'ready':all((ROOT/'runs'/m/'training_complete.json').exists() for m in required)},ensure_ascii=False));return
    LOGS.mkdir(parents=True,exist_ok=True)
    status_file=LOGS/'status.json'
    if status_file.exists():
        previous=read(status_file);pid=previous.get('pid')
        if pid and pid!=os.getpid() and psutil.pid_exists(pid):
            command=psutil.Process(pid).cmdline()
            if any(str(ROOT/'scripts/run_final_validation.py').replace('\\','/').lower()==c.replace('\\','/').lower() for c in command):
                raise RuntimeError('Final-validation supervisor already alive; do not duplicate')
        child=previous.get('child_pid')
        if child and psutil.pid_exists(child):raise RuntimeError('Previous validation child still alive; wait before restoration')
    status={'state':'waiting_training','pid':os.getpid(),'new_methods':NEW,'runtime_completed':[],'reconstruction_completed':[],
            'measurement_completed':[],'old_seven_repeated':False,'verified_methods_reused':reused_methods,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    save(status_file,status)
    while True:
        stop=(ROOT/'runs/launcher_logs/USER_STOP_REQUESTED').exists()
        ready=all((ROOT/'runs'/m/'training_complete.json').exists() for m in required)
        managers,workers=processes()
        if ready and (not stop or args.completed_only) and not managers and not workers:break
        if not args.watch:raise RuntimeError('Trainings not complete or training programs still alive; defer GPU work')
        failures=[m for m in required if (ROOT/'runs'/m/'failure.json').exists() and not (ROOT/'runs'/m/'training_complete.json').exists()]
        if failures:
            status.update(state='failed',error='Training failure requires repair before final validation: '+','.join(failures));save(status_file,status)
            raise RuntimeError(status['error'])
        status.update(state='waiting_gpu_release' if args.completed_only else 'waiting_user_resume' if stop else 'waiting_training',completed_trainings=[m for m in required if (ROOT/'runs'/m/'training_complete.json').exists()],checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        save(status_file,status);time.sleep(30)
    for method in required:assert completion(method) is not None
    complete=ROOT/'results'/('completed_models' if args.completed_only else 'full_benchmark')/'handoff_verified.json'
    if complete.exists() and read(complete)['state']=='passed':
        status.update(state='complete_pending_delivery',already_complete=True);save(status_file,status);return
    marker=ROOT/'runs/launcher_logs/VALIDATION_PRIORITY.json'
    if marker.exists():
        assert read(marker).get('scope')==scope,'Different validation priority active'
    else:
        queue=read(ROOT/'runs/launcher_logs/active_formal_run.json')
        save(marker,{'scope':scope,'state':'active','user_authorized_validation_after_training':True,
                     'training_queue_before':queue,'new_methods':NEW,'supervisor_pid':os.getpid()})
    env=os.environ.copy();env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    def execute(script,argv,tag):
        status.update(state='active',current_stage=tag,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        save(status_file,status)
        with (LOGS/(tag+'.log')).open('a',encoding='utf-8') as out:
            child=subprocess.Popen([sys.executable,'-B','-X','utf8',str(ROOT/'scripts'/script),*argv],cwd=ROOT,env=env,
                                   stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            status['child_pid']=child.pid;save(status_file,status);code=child.wait()
        status['child_pid']=None;save(status_file,status)
        if code!=0:raise RuntimeError(tag+' failed; preserved log exit='+str(code))
    try:
        for method in NEW:
            path=ROOT/'results/runtime'/(method+'.json')
            if not path.exists():execute('benchmark_runtime.py',['--method',method],'runtime_'+method)
            assert read(path)['state']=='complete';status['runtime_completed'].append(method)
        for method in NEW:
            path=ROOT/'results/reconstruction'/method/'reconstruction_complete.json'
            if not path.exists() or read(path)['state']!='complete':execute('evaluate_real_method.py',[method,'--stage','reconstruct'],'reconstruct_'+method)
            assert read(path)['state']=='complete' and read(path)['images']==930;status['reconstruction_completed'].append(method)
            path=ROOT/'results/readouts'/method/'measurement_complete.json'
            if not path.exists():execute('evaluate_real_method.py',[method,'--stage','measure'],'measure_'+method)
            assert read(path)['state']=='complete' and read(path)['attempted_pillars']==8370;status['measurement_completed'].append(method)
        mode='--completed-only' if args.completed_only else '--final'
        execute('write_available_efficiency.py',[mode],'efficiency_report')
        execute('summarize_available_real.py',[mode],'final_statistics_handoff')
        receipt=read(complete);assert receipt['state']=='passed'
        archive=Path(receipt['archive']);assert sha(archive)==receipt['archive_sha256']
        directory=ROOT/'reports'/('COMPLETED_MODELS_THESIS_HANDOFF' if args.completed_only else 'FINAL_BENCHMARK_THESIS_HANDOFF');manifest=read(directory/'MANIFEST.json')
        assert (manifest['completed_models_user_scope_complete'] if args.completed_only else manifest['full_external_benchmark_complete']) and len(manifest['completed_scope'])==(9 if args.completed_only else 10)
        for row in manifest['files']:assert sha(directory/row['file'])==row['sha256']
        with zipfile.ZipFile(archive) as z:assert z.testzip() is None
        for row in read(ROOT/'config/source_lock.json')['files']:assert sha(row['path'])==row['sha256']
        save(ROOT/'results'/('completed_models' if args.completed_only else 'full_benchmark')/'final_audit.json',{'state':'passed','complete_methods':manifest['completed_scope'],
             'blocked_official_backends':manifest['blocked_official_backends'],'new_methods_only':NEW,
             'old_seven_repeated':False,'verified_methods_reused':reused_methods,'original_sources_unchanged':True,'archive_sha256':sha(archive),
             'paused_methods':['SwinIR'] if args.completed_only else [],'automatic_training_resume_allowed':not args.completed_only,
             'requires_model_visual_review_and_user_delivery':True})
        record=read(marker);save(LOGS/'priority_completed.json',record);marker.unlink()
        status.update(state='complete_pending_delivery',current_stage=None,child_pid=None,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());save(status_file,status)
        print('FINAL COMPARISON READY FOR VISUAL REVIEW AND DELIVERY',flush=True)
    except BaseException as error:
        status.update(state='failed',error=repr(error),traceback=traceback.format_exc());save(status_file,status);raise


if __name__=='__main__':main()
