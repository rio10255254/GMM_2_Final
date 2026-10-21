"""Move the generation code without TIFF inputs, then execute from another cwd."""
import json
import shutil
import subprocess
import sys
from pathlib import Path
sys.dont_write_bytecode=True

PROJECT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
PACK=PROJECT/'Deliverables/R152_Standalone_ImageFiles_20261004'
MOVED=OUT/'portable_generation_copy'


def main():
    MOVED.mkdir(parents=True,exist_ok=False)
    for name in ('generate_data.py','settings.py','reference_info.py','data_index.py'):
        shutil.copy2(PACK/name,MOVED/name)
    shutil.copytree(PACK/'generation',MOVED/'generation')
    shutil.copytree(PACK/'calibration',MOVED/'calibration')
    assert not (MOVED/'data').exists()
    probe=OUT/'portable_execution.py'
    probe.write_text('''import os,sys,json
from pathlib import Path
sys.dont_write_bytecode=True
source=Path(sys.argv[1]).resolve()
moved=Path(sys.argv[2]).resolve()
output=Path(sys.argv[3]).resolve()
def audit(event,args):
 if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
  path=Path(os.fsdecode(args[0])).resolve()
  if path==source or source in path.parents:
   raise RuntimeError('Moved generator attempted to read the old package: '+str(path))
sys.addaudithook(audit)
sys.path.insert(0,str(moved))
import generate_data
from settings import ROOT
assert ROOT==moved
generate_data.source_checks()
checks=[]
for split,index in [('train',0),('dev',0),('test',0)]:
 record,count,reused=generate_data.build_parent((split,index,str(output),False))
 assert count==12 and not reused
 checks.append(record['parent_id'])
record,count,reused=generate_data.build_parent(('train',0,str(output),True))
assert count==12 and reused
bad=output/'test/geometry/0000_v3.tif'
from PIL import Image
import numpy as np
with Image.open(bad) as image:values=np.asarray(image).copy()
values[0,0]+=.123
Image.fromarray(values).save(bad,compression='tiff_deflate')
try:
 generate_data.build_parent(('test',0,str(output),True))
except (ValueError,RuntimeError):
 corrupted_rejected=True
else:
 raise AssertionError('A changed TIFF must be rejected')
result={'status':'passed','moved_package_root_correct':True,'started_from_foreign_cwd':True,
 'source_package_reads_blocked':True,'no_training_images_in_moved_package':True,
 'exact_generated_parents':checks,'resume_reuses_only_verified_images':True,
 'changed_existing_TIFF_rejected':corrupted_rejected}
(output.parent/'portable_generation_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2),flush=True)
''',encoding='utf-8')
    subprocess.run([sys.executable,'-B','-X','utf8',str(probe),str(PACK),str(MOVED),str(OUT/'portable_generated_samples')],
                   cwd=str(OUT),check=True)
    print('Portable no-image-source generation and invalid-resume checks passed.',flush=True)


if __name__=='__main__':main()
