"""Use the already installed CUDA-supported MSVC toolset, without bypassing checks."""
from pathlib import Path
import argparse,os,shutil,subprocess,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from study import read,save


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--math-defines',action='store_true');args=parser.parse_args()
    base=ROOT.parents[1]/'Experiments' / 'R153_MeanExternalBenchmark' / '_build153'
    source=base/'mamba-msvc'
    if not source.exists():shutil.copytree(base/'mamba-1.0.1',source,ignore=shutil.ignore_patterns('build','dist','*.egg-info','__pycache__'))
    vcvars=Path(r'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat')
    command=f'""{vcvars}" -vcvars_ver=14.44 >nul && set"'
    env_output=subprocess.check_output('cmd.exe /d /s /c '+command)
    env=os.environ.copy()
    for line in env_output.decode('mbcs',errors='replace').splitlines():
        if '=' in line:
            name,value=line.split('=',1)
            if name:env[name]=value
    out=ROOT/'results/backend_checks'
    env.update(TEMP=str(base/'tmp'),TMP=str(base/'tmp'),MAX_JOBS='4',PIP_NO_CACHE_DIR='1',DISTUTILS_USE_SDK='1',MSSdk='1')
    if args.math_defines:
        env['NVCC_PREPEND_FLAGS']='-D_USE_MATH_DEFINES'
        env['CL']='/D_USE_MATH_DEFINES'
    assert '14.44.' in env.get('VCToolsVersion',''),env.get('VCToolsVersion')
    command=[sys.executable,'-m','pip','wheel',str(source),'--no-build-isolation','--no-deps','--wheel-dir',str(out/'wheels')]
    try:
        p=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=360,env=env)
        output=p.stdout.decode('utf-8',errors='replace');code=p.returncode
    except subprocess.TimeoutExpired as error:
        output=(error.stdout or b'').decode('utf-8',errors='replace')+'\nBounded supported-toolset build timed out.';code='timeout'
    tag='mamba_windows_math_build' if args.math_defines else 'mamba_supported_compiler_build'
    (out/(tag+'.log')).write_text(output,encoding='utf-8')
    save(out/(tag+'.json'),{'returncode':code,'VCToolsVersion':env['VCToolsVersion'],'standard_math_definitions_enabled':args.math_defines,
         'unsupported_compiler_override':False,'source_directory':str(source)})
    blocked=read(ROOT/'config/blocked_models.json')
    if code==0:
        blocked.pop('MambaIRv2',None)
        print('MAMBA SUPPORTED COMPILER BUILD PASSED',flush=True)
    else:
        blocked['MambaIRv2']['reason']='官方後端在PyPI來源及完整作者來源兩次建置失敗後，再指定本機既有、符合CUDA版本條件的MSVC 14.44工具組嘗試；仍未完成可用後端。完整錯誤保留，未以其他網路替代。'
        blocked['MambaIRv2']['evidence']='results/backend_checks/'+tag+'.log'
        print('MAMBA SUPPORTED COMPILER BUILD RESULT',code,flush=True)
    save(ROOT/'config/blocked_models.json',blocked)


if __name__=='__main__':main()
