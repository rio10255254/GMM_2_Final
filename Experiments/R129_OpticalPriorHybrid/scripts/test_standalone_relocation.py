"""Temporarily relocate only the newly built package and run its public entrypoints."""
import sys,subprocess,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import cv2,numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[3]
def main():
    original=Path(PROJECT_ROOT / load(ROOT/'config/standalone_build.json')['path']).resolve()
    expected=(REPO/'Thesis_MOSR_Evidence/LabSystem_MOSR/Model_Packages').resolve()
    moved=expected/'R129_RelocationCheck'
    assert original.parent==expected and original.name=='R129_OpticalHybrid_Standalone_20260912'
    assert moved.parent==expected and not moved.exists()
    assert load(original/'results/preflight/complete.json')['passed']
    original.rename(moved)
    results=[]
    try:
        commands=[['verify_package.py','--quick'],['train_r129.py','--dry-run','--device','cpu'],['infer_r129.py','--output-name','relocation_sample']]
        for command in commands:
            r=subprocess.run([sys.executable,'-B',str(moved/command[0]),*command[1:]],cwd=expected,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240)
            results.append(dict(command=command,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
            if r.returncode:raise RuntimeError(r.stdout+r.stderr)
            print('Relocated entry passed:',command[0],flush=True)
        r=subprocess.run(['cmd.exe','/d','/c',str(moved/'START_R129.cmd')],cwd=expected,input='3\n0\n\n',capture_output=True,text=True,errors='replace',timeout=120)
        assert r.returncode==0 and 'R129 manual controls' in r.stdout
        results.append(dict(command=['START_R129.cmd','status then exit'],returncode=r.returncode,stdout=r.stdout))
        a=cv2.imread(str(moved/'results/inference/relocation_sample/pillar_normal.png'),0)
        b=cv2.imread(str(moved/'validation/baseline/sem14.png'),0)
        assert np.array_equal(a,b)
    finally:
        assert moved.resolve().parent==expected and not original.exists()
        moved.rename(original)
    save(original/'results/relocation_test.json',dict(completed_utc=now(),passed=True,moved_and_restored=True,independent_working_directory=True,public_inference_equal=True,manual_menu_executed=True,commands=results))
    save(ROOT/'results/standalone_relocation.json',dict(completed_utc=now(),source=record(__file__),package=str(original),result=record(original/'results/relocation_test.json')))
    print('Package restored to final location; sample output exactly matches original')
if __name__=='__main__':main()
