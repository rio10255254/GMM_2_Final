"""重新生成R152全部訓練影像，只需要此包內的程式與25顆PSF。

直接執行：完整生成768個場景／3072組清楚與模糊TIFF，另附幾何TIFF。
預設寫入outputs/generated_data，逐張核對原版像素，不覆寫附帶資料。
generate_data.py --resume：接續預設資料夾，先核對已完成影像。
generate_data.py --verify-only：只核對已生成的完整資料。
generate_data.py --output-dir data：資料夾不存在時，可重建正式data資料夾。
train.py --data-dir outputs/generated_data：直接訓練本程式重新生成的影像。

需要numpy、scipy、Pillow。已核對環境版本在generation/recipe.py。
模糊TIFF保存原版無噪聲影像；每輪加噪與八位元轉換由正式訓練程式
按原種子重做，因此同一輪實際送進模型的影像也與原流程相同。
generation/original_sources保存當初原始程式；此入口已處理其路徑依賴。
"""
import argparse
import ast
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import hashlib
import os
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
import platform
import pprint
import sys
sys.dont_write_bytecode=True
import time
from pathlib import Path

import numpy as np
from PIL import Image
import PIL
import scipy

from data_index import ENTRIES
from generation.labels import generate_labels
from generation.lineage import PARENTS
from generation.physical_views import generate_views, digest_array
from generation.scene import parameters, canonical, render_initial_latent
from generation.source_history import SOURCES
from settings import ROOT, resolve_path

REFERENCE={(e['split'],e['index']):e for e in ENTRIES}
LINEAGE={(e['split'],e['index']):e for e in PARENTS}
ORDER={'train':0,'dev':1,'test':2}
IMAGE_KEYS={'clear':'target','blur':'noiseless','geometry':'sdf'}
DTYPES={'valid':np.uint8,'noise_sigma_gray':np.float64,'psf_index':np.int64,
        'shifts_xy':np.float64,'contrast':np.float64,'brightness_gray':np.float64}


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_python(path, name, value, doc):
    source='"""'+doc+'"""\n'+name+' = '+pprint.pformat(value,width=115,sort_dicts=False)+'\n'
    ast.parse(source)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(source,encoding='utf-8')
    temporary.replace(path)


def read_python_assignment(path, name):
    tree=ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
    found=[n for n in tree.body if isinstance(n,ast.Assign)
           and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)]
    if len(found)!=1:
        raise ValueError('Invalid generated index: '+str(path))
    return ast.literal_eval(found[0].value)


def view_paths(split,index,view):
    return {key:f'data/{split}/{folder}/{index:04d}_v{view}.tif'
            for folder,key in IMAGE_KEYS.items()}


def read_generated_parent(output, split, index):
    """Validate actual saved pixels, not only image-file container hashes."""
    e=REFERENCE[(split,index)]
    arrays={key:[] for key in IMAGE_KEYS.values()}
    images=[]
    byte_exact=0
    for view in range(4):
        record={'view':view}
        for key,relative in view_paths(split,index,view).items():
            path=output/Path(relative).relative_to('data')
            with Image.open(path) as image:
                pixels=np.asarray(image).copy()
            shape=(96,96) if key=='sdf' else (384,384)
            if pixels.dtype!=np.float32 or pixels.shape!=shape or not np.isfinite(pixels).all():
                raise ValueError('Invalid generated TIFF: '+str(path))
            original=pixels.astype(np.float16)
            if not np.array_equal(pixels,original.astype(np.float32)):
                raise ValueError('TIFF pixels no longer equal the original float16-to-float32 values: '+str(path))
            arrays[key].append(original)
            record[key]=relative
            record[key+'_sha256']=file_sha(path)
            byte_exact+=record[key+'_sha256']==e['images'][view][key+'_sha256']
        images.append(record)
    for key,values in arrays.items():
        if digest_array(np.stack(values))!=e['array_sha256'][key]:
            raise RuntimeError('Generated values differ from published R152: '+e['parent_id']+' '+key)
    result=deepcopy(e)
    result['images']=images
    return result,byte_exact


def build_parent(job):
    split,index,output,resume=job
    output=Path(output)
    e=REFERENCE[(split,index)]
    paths=[output/Path(p).relative_to('data') for view in range(4)
           for p in view_paths(split,index,view).values()]
    if resume and all(p.is_file() for p in paths):
        record,byte_exact=read_generated_parent(output,split,index)
        return record,byte_exact,True
    metadata,_=parameters(split,index)
    if hashlib.sha256(canonical(metadata).encode()).hexdigest()!=LINEAGE[(split,index)]['seed_parameter_sha256']:
        raise RuntimeError('Original scene parameters changed: '+e['parent_id'])
    latent=render_initial_latent(metadata)
    arrays,views=generate_views(latent,metadata)
    arrays.update(generate_labels(metadata['shape'],metadata['category'],views))
    arrays.update({
        'noise_sigma_gray':np.asarray([v['noise_sigma_gray'] for v in views],dtype=np.float64),
        'psf_index':np.asarray([v['psf_index'] for v in views],dtype=np.int64),
        'shifts_xy':np.asarray([v['shift_xy'] for v in views],dtype=np.float64),
        'contrast':np.asarray([v['contrast'] for v in views],dtype=np.float64),
        'brightness_gray':np.asarray([v['brightness_gray'] for v in views],dtype=np.float64),
    })
    for key,expected in e['array_sha256'].items():
        if digest_array(arrays[key])!=expected:
            raise RuntimeError('Regenerated arrays differ: '+e['parent_id']+' '+key)
    fixed_metadata={key:arrays[key].tolist() for key in DTYPES}
    if fixed_metadata!=e['metadata']:
        raise RuntimeError('Generated shifts/PSF/noise settings differ: '+e['parent_id'])
    for view in range(4):
        for key,relative in view_paths(split,index,view).items():
            path=output/Path(relative).relative_to('data')
            values=arrays[key][view].astype(np.float32)
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():
                if not resume:
                    raise FileExistsError('Refuse to overwrite '+str(path))
                with Image.open(path) as image:
                    existing=np.asarray(image).copy()
                if existing.dtype!=np.float32 or not np.array_equal(existing,values):
                    raise RuntimeError('Existing partial image differs: '+str(path))
            else:
                temporary=path.with_suffix('.tmp')
                Image.fromarray(values).save(temporary,format='TIFF',compression='tiff_deflate')
                temporary.replace(path)
    result,byte_exact=read_generated_parent(output,split,index)
    result['metadata']=fixed_metadata
    return result,byte_exact,False


def source_checks():
    from reference_info import REFERENCE as published
    if file_sha(ROOT/'calibration/psf25_bank.npz')!=published['PSF_bank_sha256']:
        raise RuntimeError('The 25-PSF bank changed')
    for e in SOURCES.values():
        if file_sha(ROOT/e['delivered_path'])!=e['sha256']:
            raise RuntimeError('Historical source changed: '+e['delivered_path'])
    if len(REFERENCE)!=768 or len(LINEAGE)!=768:
        raise RuntimeError('Incomplete generation reference')


def verify_bank(output):
    index_path=output/'data_index.py'
    if not index_path.is_file():
        raise FileNotFoundError('Generation has not completed: '+str(index_path))
    delivered=read_python_assignment(index_path,'ENTRIES')
    by_key={(e['split'],e['index']):e for e in delivered}
    if len(delivered)!=768 or set(by_key)!=set(REFERENCE):
        raise ValueError('Generated bank is incomplete')
    byte_exact=0
    for n,key in enumerate(REFERENCE,1):
        record,count=read_generated_parent(output,*key)
        if record!=by_key[key]:
            raise RuntimeError('Generated index no longer matches images: '+record['parent_id'])
        byte_exact+=count
        if n%128==0:
            print('VERIFIED',n,'/768',flush=True)
    if len(list(output.rglob('*.tif')))!=9216 or list(output.rglob('*.npz')) or list(output.rglob('*.png')):
        raise ValueError('The generated training bank must contain exactly 9216 TIFFs')
    return byte_exact


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output-dir',help='完整新資料夾；相對路徑由獨立包位置定位')
    parser.add_argument('--workers',type=int,default=4,help='同時生成場景數；預設4，記憶體有限可填1')
    parser.add_argument('--resume',action='store_true',help='核對並接續同一輸出資料夾')
    parser.add_argument('--verify-only',action='store_true',help='只核對完整生成資料')
    args=parser.parse_args(argv)
    if args.workers<1:
        parser.error('--workers must be positive')
    output=resolve_path(args.output_dir) if args.output_dir else ROOT/'outputs/generated_data'
    source_checks()
    if args.verify_only:
        count=verify_bank(output)
        print('PASS：全部9216張TIFF像素與原版相同。影像檔內容也完全相同：',count,'/9216',flush=True)
        return
    if output.exists() and any(output.iterdir()) and not args.resume:
        raise FileExistsError('輸出資料夾已有檔案；使用--resume核對並接續，或選擇新的--output-dir：'+str(output))
    output.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter()
    status={'state':'running','total_parents':768,'completed_parents':0,'reused_verified_parents':0}
    save_python(output/'generation_progress.py','PROGRESS',status,'Actual data-generation progress; not a completion receipt.')
    records=[]
    byte_exact=0
    reused=0
    jobs=[(e['split'],e['index'],str(output),args.resume) for e in ENTRIES]
    pool=ProcessPoolExecutor(max_workers=args.workers)
    try:
        futures=[pool.submit(build_parent,job) for job in jobs]
        for future in as_completed(futures):
            record,count,was_reused=future.result()
            records.append(record);byte_exact+=count;reused+=was_reused
            status.update(completed_parents=len(records),reused_verified_parents=reused,
                          seconds=time.perf_counter()-start)
            if len(records)%16==0 or len(records)==768:
                save_python(output/'generation_progress.py','PROGRESS',status,'Actual data-generation progress; not a completion receipt.')
                print('GENERATED',len(records),'/768','seconds='+str(round(status['seconds'],1)),flush=True)
    except BaseException as error:
        status.update(state='interrupted_or_failed',error=str(error),seconds=time.perf_counter()-start)
        save_python(output/'generation_progress.py','PROGRESS',status,'Generation did not complete; verify/resume the existing TIFFs.')
        raise
    finally:
        pool.shutdown(wait=True,cancel_futures=True)
    records.sort(key=lambda e:(ORDER[e['split']],e['index']))
    save_python(output/'data_index.py','ENTRIES',records,'Fully regenerated TIFF training pairs; image paths are relative to this bank.')
    confirmed=verify_bank(output)
    assert confirmed==byte_exact
    receipt={'state':'complete','parents':768,'views':3072,'clear_TIFFs':3072,'blur_TIFFs':3072,
             'geometry_TIFFs':3072,'all_original_pixel_values_exact':True,
             'all_original_fixed_metadata_exact':True,'byte_identical_TIFFs':byte_exact,
             'no_original_training_image_files_read':True,'reused_verified_parents':reused,
             'workers':args.workers,'seconds':time.perf_counter()-start,
             'environment':{'Python':platform.python_version(),'numpy':np.__version__,
                            'scipy':scipy.__version__,'Pillow':PIL.__version__},
             'recipe':'original_seeded_8x_scene_to_4x_latent_to_measured_PSF25_to_native_TIFF',
             'noise':'original_epoch-dependent_noise_and_uint8_quantization_in_core/dataset.py'}
    save_python(output/'generation_result.py','RESULT',receipt,'Complete generation and actual pixel-parity verification.')
    save_python(output/'generation_progress.py','PROGRESS',receipt,'Complete generation, verified after all images were written.')
    print('PASS：全部訓練影像已從頭生成並逐張核對。',flush=True)
    print('資料夾：',output,flush=True)
    print('實際耗時：',round(receipt['seconds']/60,2),'分鐘',flush=True)
    return receipt


if __name__=='__main__':
    main()
