"""Retry the author's tagged source after the PyPI archive omitted C++ sources."""
from pathlib import Path
import io,os,subprocess,sys,zipfile,requests
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from study import read,save


def main():
    work=ROOT.parents[1]/'_build153'
    work.mkdir(exist_ok=True)
    response=requests.get('https://github.com/state-spaces/mamba/archive/refs/tags/v1.0.1.zip',timeout=90)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        for name in archive.namelist():
            dest=(work/name).resolve()
            if work.resolve() not in dest.parents:raise ValueError('Archive path escapes scoped build directory')
        archive.extractall(work)
    source=work/'mamba-1.0.1'
    assert (source/'csrc/selective_scan/selective_scan.cpp').is_file()
    temp=work/'tmp';temp.mkdir(exist_ok=True)
    out=ROOT/'results/backend_checks'
    env=os.environ.copy();env.update(TEMP=str(temp),TMP=str(temp),MAX_JOBS='4',PIP_NO_CACHE_DIR='1')
    command=[sys.executable,'-m','pip','wheel',str(source),'--no-build-isolation','--no-deps','--wheel-dir',str(out/'wheels')]
    try:
        p=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300,env=env)
        output=p.stdout.decode('utf-8',errors='replace');code=p.returncode
    except subprocess.TimeoutExpired as error:
        output=(error.stdout or b'').decode('utf-8',errors='replace')+'\nBounded author-source build timed out.';code='timeout'
    (out/'mamba_author_source_build.log').write_text(output,encoding='utf-8')
    result={'author_source':'https://github.com/state-spaces/mamba/tree/v1.0.1',
            'cpp_source_confirmed_present':True,'short_build_path':str(source),'returncode':code}
    save(out/'mamba_author_source_build.json',result)
    blocked=read(ROOT/'config/blocked_models.json')
    if code==0:
        blocked.pop('MambaIRv2',None)
        print('MAMBA AUTHOR SOURCE BUILT SUCCESSFULLY',flush=True)
    else:
        blocked['MambaIRv2']['reason']='官方mamba_ssm後端缺少相容預編譯套件。先前PyPI建置因缺少C++來源失敗；改用作者v1.0.1完整來源及較短建置路徑後，仍無法在本機完成建置。未替換官方選擇性掃描或模型架構。'
        blocked['MambaIRv2']['evidence']='results/backend_checks/mamba_author_source_build.log'
        print('MAMBA AUTHOR SOURCE BUILD RESULT',code,flush=True)
    save(ROOT/'config/blocked_models.json',blocked)


if __name__=='__main__':main()
