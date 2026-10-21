"""Record actual official-backend failures; never replace them with proxy networks."""
from pathlib import Path
import sys,os,subprocess,importlib.util,shutil
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from study import save


def main():
    out=ROOT/'results/backend_checks';out.mkdir(parents=True,exist_ok=True)
    observations={}
    for label,args in [('wsl',['wsl','--list','--verbose']),('docker',['docker','info','--format','{{.OSType}} {{.ServerVersion}}'])]:
        process=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        encoding='utf-16-le' if label=='wsl' else 'utf-8'
        observations[label]={'returncode':process.returncode,'stdout':process.stdout.decode(encoding,errors='replace'),
                             'stderr':process.stderr.decode(encoding,errors='replace')}
    observations['caffe_import_available']=bool(importlib.util.find_spec('caffe'))
    observations['mamba_ssm_import_available']=bool(importlib.util.find_spec('mamba_ssm'))
    observations['msvc_cl_on_path']=shutil.which('cl')
    save(out/'environment.json',observations)
    blocked={}
    if not observations['caffe_import_available'] and observations['wsl']['returncode']!=0 and observations['docker']['returncode']!=0:
        blocked['U-Net']={'status':'blocked','source':'https://github.com/lmb-freiburg/Unet-Segmentation',
                          'reason':'作者官方版本依賴caffe_unet/Linux後端；本機沒有Caffe、沒有可用WSL發行版，Docker Linux後端也無法連線。無法在目前環境直接執行官方版本及共同PyTorch訓練目標。未以自行簡化的網路替代。',
                          'evidence':'results/backend_checks/environment.json','completed_training_updates':0}
    if not observations['mamba_ssm_import_available']:
        temp=out/'build_temp';temp.mkdir(exist_ok=True)
        wheel=out/'wheels';wheel.mkdir(exist_ok=True)
        env=os.environ.copy();env.update(TEMP=str(temp),TMP=str(temp),MAX_JOBS='4',PIP_NO_CACHE_DIR='1')
        command=[sys.executable,'-m','pip','wheel','mamba-ssm==1.0.1','--no-build-isolation','--no-deps','--wheel-dir',str(wheel)]
        try:
            process=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=240,env=env)
            log=process.stdout.decode('utf-8',errors='replace');code=process.returncode
        except subprocess.TimeoutExpired as error:
            log=(error.stdout or b'').decode('utf-8',errors='replace')+'\nBuild exceeded the bounded feasibility check.';code='timeout'
        (out/'mamba_official_build.log').write_text(log,encoding='utf-8')
        observations['mamba_build_returncode']=code
        if code!=0:
            blocked['MambaIRv2']={'status':'blocked','source':'https://github.com/csguoh/MambaIR',
                                 'reason':'官方模型所需mamba_ssm選擇性掃描後端未安裝，依官方舊版相依套件的隔離建置嘗試失敗；目前也無可用Linux執行環境。完整建置錯誤已保存，未改成其他模型或簡化掃描。',
                                 'evidence':'results/backend_checks/mamba_official_build.log','completed_training_updates':0}
        else:
            print('Official Mamba wheel built; install into the study-local dependency folder before evaluating.',flush=True)
    save(out/'environment.json',observations)
    save(ROOT/'config/blocked_models.json',blocked)
    print('Backend assessment:',{k:v['status'] for k,v in blocked.items()},flush=True)
    if 'mamba_build_returncode' in observations:print('Mamba build return:',observations['mamba_build_returncode'],flush=True)


if __name__=='__main__':main()
