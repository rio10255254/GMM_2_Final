"""Execute copied code in a different location, denying original experiment reads."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
sys.dont_write_bytecode=True

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1];PACK=PROJECT/'Deliverables/R152_Standalone_20261004'
RELOC=OUT/'relocated_runtime';FOREIGN=OUT/'foreign_working_directory'

def main():
    RELOC.mkdir(exist_ok=True);FOREIGN.mkdir(exist_ok=True)
    for source in PACK.rglob('*.py'):
        target=RELOC/source.relative_to(PACK);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    for relative in ('weights','calibration'):
        shutil.copytree(PACK/relative,RELOC/relative,dirs_exist_ok=True)
    sys.path.insert(0,str(PACK))
    from settings import TRAIN_CONFIG
    from core.dataset import Bank
    from infer import load_gray
    order=Bank(TRAIN_CONFIG).order(0)
    for split,index in [('train',int(order[0])),('train',int(order[1])),('dev',0),('test',0)]:
        target=RELOC/'data'/split/f'{index:04d}.npz';target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(PACK/'data'/split/f'{index:04d}.npz',target)
    (RELOC/'input').mkdir(exist_ok=True)
    raw=np.asarray(Image.open(PACK/'input/demo_raw.bmp'))
    crop=raw[600:856,1450:1706].copy();Image.fromarray(crop).save(RELOC/'input/crop.bmp')
    u16=(np.arange(256*256,dtype=np.uint32)%65536).astype(np.uint16).reshape(256,256)
    Image.fromarray(u16).save(OUT/'reader_u16.png');Image.fromarray(crop).save(OUT/'reader_u8.png')
    assert np.array_equal(load_gray(OUT/'reader_u16.png'),u16.astype(np.float32)/65535)
    assert np.array_equal(load_gray(OUT/'reader_u8.png'),crop.astype(np.float32)/255)
    launcher=OUT/'run_with_source_reads_denied.py'
    launcher.write_text('''from pathlib import Path
import runpy, sys
sys.dont_write_bytecode=True
package, original, output, script = map(Path, sys.argv[1:5])
blocked = [original.resolve(), original.parent/'R148v2_HybridContextNativePSF']
allowed = [package.resolve(), output.resolve()]
def guard(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        path = Path(args[0]).resolve()
        if any(path.is_relative_to(p) for p in blocked) and not any(path.is_relative_to(p) for p in allowed):
            raise PermissionError('Attempt to read original experiment: ' + str(path))
sys.addaudithook(guard)
sys.path.insert(0, str(package))
sys.argv = [str(package/script)] + sys.argv[5:]
runpy.run_path(str(package/script), run_name='__main__')
''',encoding='utf-8')
    def run(script,*arguments):
        command=[sys.executable,'-B','-X','utf8',str(launcher),str(RELOC),str(ROOT),str(OUT),script,*arguments]
        result=subprocess.run(command,cwd=FOREIGN,capture_output=True,text=True,encoding='utf-8',timeout=180)
        print(result.stdout,flush=True)
        if result.returncode:raise RuntimeError(result.stderr)
        return result
    run('train.py','--device','cuda','--max-updates','2','--assessment-limit','1','--output-dir',str(OUT/'relocated_training'))
    run('infer.py','--device','cpu','--output',str(OUT/'relocated_cpu_inference'))
    # Same copied code/configuration/weights on CPU, in the delivered location.
    subprocess.run([sys.executable,'-B','-X','utf8',str(PACK/'infer.py'),'--device','cpu','--input',str(RELOC/'input/crop.bmp'),
                    '--output',str(OUT/'original_location_cpu_inference')],cwd=FOREIGN,check=True,timeout=180)
    a=np.load(OUT/'relocated_cpu_inference/crop_R152.npz')['output']
    b=np.load(OUT/'original_location_cpu_inference/crop_R152.npz')['output']
    assert np.array_equal(a,b)
    result=dict(status='passed',different_package_location=True,foreign_working_directory=True,
                original_experiment_file_reads_denied=True,relocated_training_updates=2,
                relocated_CPU_inference_exact=True,grayscale_uint8_and_uint16_reader_verified=True,
                relocated_data_scope='only the parents touched by the two-update check; delivered package has all768')
    (OUT/'portability_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
