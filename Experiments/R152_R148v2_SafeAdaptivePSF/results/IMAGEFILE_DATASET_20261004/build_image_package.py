"""Make formal training consume genuine lossless TIFF image files."""
import hashlib
import json
import pprint
import shutil
import sys
sys.dont_write_bytecode=True
from pathlib import Path

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
SOURCE=PROJECT/'Deliverables/Standalone_Models/R152_Standalone_20261004'
DEST=PROJECT/'Deliverables/Standalone_Models/R152_Standalone_ImageFiles_20261004'
sys.path.insert(0,str(SOURCE))
from data_index import ENTRIES
from reference_info import REFERENCE

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(relative,content):
    path=DEST/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf-8')

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    for p in SOURCE.rglob('*.py'):
        if p.name in ('data_index.py','manifest.py','verification_info.py','check_package.py','start_here.py'):continue
        if p.relative_to(SOURCE).as_posix()=='core/dataset.py':continue
        target=DEST/p.relative_to(SOURCE);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    for directory in ('calibration','weights','input','reference'):
        shutil.copytree(SOURCE/directory,DEST/directory,dirs_exist_ok=True)
    for directory in ('outputs/training','outputs/inference'):(DEST/directory).mkdir(parents=True,exist_ok=True)
    entries=[]
    for i,old in enumerate(ENTRIES,1):
        with np.load(SOURCE/old['file'],allow_pickle=False) as archive:
            arrays={k:archive[k].copy() for k in archive.files}
        split,index=old['split'],old['index'];paths=[]
        for view in range(4):
            record={'view':view}
            for folder,key in [('clear','target'),('blur','noiseless'),('geometry','sdf')]:
                name=f'data/{split}/{folder}/{index:04d}_v{view}.tif';target=DEST/name
                target.parent.mkdir(parents=True,exist_ok=True)
                array=arrays[key][view].astype(np.float32)
                Image.fromarray(array).save(target,compression='tiff_deflate')
                with Image.open(target) as image:returned=np.asarray(image).copy()
                assert returned.dtype==np.float32 and np.array_equal(returned,array),(name,returned.dtype)
                record[key]=name;record[key+'_sha256']=sha(target)
            paths.append(record)
        meta={key:arrays[key].tolist() for key in ('valid','noise_sigma_gray','psf_index','shifts_xy','contrast','brightness_gray')}
        entries.append(dict(split=split,index=index,parent_id=old['parent_id'],category=old['category'],
                            images=paths,metadata=meta,array_sha256=old['array_sha256'],
                            original_container_sha256=old['sha256'],
                            source_arrays_sha256=old['source_arrays_sha256'],
                            source_metadata_sha256=old['source_metadata_sha256'],source_geometry_sha256=old['source_geometry_sha256']))
        if i%128==0:print('CONVERTED',i,'/768',flush=True)
    write('data_index.py','"""Actual TIFF training pairs and fixed split/labels."""\nENTRIES = '+pprint.pformat(entries,width=115,sort_dicts=False)+'\n')
    info=dict(REFERENCE)
    info.update(formal_training_image_format='TIFF float32',data_arrays_preserved_in_original_storage_dtype=False,
                original_dataset_storage_dtype='float16',training_float32_values_identical=True,
                clear_images=3072,blur_images=3072,geometry_images=3072,PNG_previews=0)
    write('reference_info.py','"""Published R152 identity and exact TIFF training image counts."""\nREFERENCE = '+pprint.pformat(info,width=110,sort_dicts=False)+'\n')
    (OUT/'image_conversion_checks.json').write_text(json.dumps(dict(status='passed',destination=str(DEST),
                                                               parents=768,views=3072,clear_TIFFs=3072,blur_TIFFs=3072,
                                                               geometry_TIFFs=3072,PNG_previews=0,
                                                               all_TIFF_pixels_equal_original_training_float32=True),ensure_ascii=False,indent=2),encoding='utf-8')
    print('IMAGE DATA READY',DEST,flush=True)

if __name__=='__main__':main()
