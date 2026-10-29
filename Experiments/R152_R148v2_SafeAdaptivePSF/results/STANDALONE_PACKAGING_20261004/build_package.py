"""Prepare the exact R152 assets with package-local Python configuration."""
from __future__ import annotations
import ast
import hashlib
import json
import pprint
import shutil
from pathlib import Path

import numpy as np
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[4]

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
DEST=ROOT.parents[1]/'Deliverables/Standalone_Models/R152_Standalone_20261004'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def array_sha(a):return hashlib.sha256(a.tobytes(order='C')).hexdigest()
def py_value(value):return pprint.pformat(value,width=110,sort_dicts=False)
def write(path,content):
    path=DEST/path;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf-8')
def reformatted(code):return ast.unparse(ast.parse(code))+'\n'

def main():
    OUT.mkdir(parents=True,exist_ok=True);DEST.mkdir(parents=True,exist_ok=True)
    cfg=read(ROOT/'config/model.json');train=read(ROOT/'config/train.json');reference=read(ROOT/'config/data.json')
    base=Path(PROJECT_ROOT / reference['source_experiment']);base_cfg=read(base/'config/model.json');base_train=read(base/'config/train.json')
    for relative,expected in read(ROOT/'config/SOURCE_LOCK.json')['files'].items():assert sha(ROOT/relative)==expected,relative
    payload_root=base/'data/payload';geo_root=base/'data/geometry'
    assert sha(payload_root/'manifest.json')==reference['payload_manifest_sha256']
    assert sha(geo_root/'manifest.json')==reference['geometry_manifest_sha256']
    payload=read(payload_root/'manifest.json');geometry=read(geo_root/'manifest.json')
    geo={(e['split'],e['index']):e for e in geometry['entries']}
    rows=[];verified=0
    for i,e in enumerate(payload['entries'],1):
        g=geo[(e['split'],e['index'])];p=payload_root/e['arrays'];m=payload_root/e['metadata'];gp=geo_root/g['path']
        assert sha(p)==e['arrays_sha256'] and sha(m)==e['metadata_sha256'] and sha(gp)==g['sha256']
        meta=read(m)
        with np.load(p,allow_pickle=False) as z:arrays={k:z[k].copy() for k in ('target','noiseless')}
        with np.load(gp,allow_pickle=False) as z:arrays.update({k:z[k].copy() for k in ('sdf','valid')})
        # Preserve the original FP16 storage; conversion to FP32 remains in the reader.
        assert arrays['target'].shape==arrays['noiseless'].shape==(4,384,384)
        assert arrays['sdf'].shape==(4,96,96) and arrays['valid'].shape==(4,)
        arrays.update(noise_sigma_gray=np.array([v['noise_sigma_gray'] for v in meta['views']],np.float64),
                      psf_index=np.array([v['psf_index'] for v in meta['views']],np.int64),
                      shifts_xy=np.array([v['shift_xy'] for v in meta['views']],np.float64),
                      contrast=np.array([v['contrast'] for v in meta['views']],np.float64),
                      brightness_gray=np.array([v['brightness_gray'] for v in meta['views']],np.float64))
        relative=f"data/{e['split']}/{e['index']:04d}.npz";target=DEST/relative;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('wb') as stream:np.savez_compressed(stream,**arrays)
        with np.load(target,allow_pickle=False) as z:
            for k,a in arrays.items():assert z[k].dtype==a.dtype and np.array_equal(z[k],a),k
        rows.append(dict(split=e['split'],index=e['index'],parent_id=e['parent_id'],category=e['category'],
                         file=relative,sha256=sha(target),array_sha256={k:array_sha(a) for k,a in arrays.items()},
                         source_arrays_sha256=e['arrays_sha256'],source_metadata_sha256=e['metadata_sha256'],
                         source_geometry_sha256=g['sha256']))
        verified+=1
        if i%128==0:print('DATA',i,'/ 768',flush=True)
    assert len(rows)==768
    write('data_index.py','"""Fixed 512/128/128 split and exact copied/repacked data identities."""\nENTRIES = '+py_value(rows)+'\n')
    (DEST/'calibration').mkdir(exist_ok=True)
    shutil.copy2(ROOT/'calibration/measured_psf_bank.npz',DEST/'calibration/psf25_bank.npz')
    complete=read(ROOT/'runs/formal_8192/training_complete.json')
    base_cp=torch.load(str(PROJECT_ROOT / cfg['base_checkpoint']),map_location='cpu',weights_only=False)
    train_cp=torch.load(str(PROJECT_ROOT / complete['training_checkpoint']['path']),map_location='cpu',weights_only=False)
    deployed=torch.load(str(PROJECT_ROOT / complete['deployed_checkpoint']['path']),map_location='cpu',weights_only=False)
    assert sha(str(PROJECT_ROOT / cfg['base_checkpoint']))==cfg['base_checkpoint_sha256']
    assert sha(str(PROJECT_ROOT / complete['training_checkpoint']['path']))==complete['training_checkpoint']['sha256']
    assert sha(str(PROJECT_ROOT / complete['deployed_checkpoint']['path']))==complete['deployed_checkpoint']['sha256']
    (DEST/'weights').mkdir(exist_ok=True)
    torch.save(dict(model=base_cp['model'],step=8192,phase='base',model_name='R152 frozen base',
                    source_checkpoint_sha256=cfg['base_checkpoint_sha256']),DEST/'weights/base_reference.pth')
    cfg['base_checkpoint']='weights/base_reference.pth';cfg['base_checkpoint_sha256']=sha(DEST/'weights/base_reference.pth')
    cfg['base_model_config']=dict(base_cfg);cfg['psf_bank']='calibration/psf25_bank.npz'
    cfg['base_model_config']['psf_bank']='calibration/psf25_bank.npz';base_cfg['psf_bank']='calibration/psf25_bank.npz'
    train['device']='auto';base_train['device']='auto'
    # The executable checkpoints contain no old machine paths. All tensor values are unchanged.
    for name,original,source_sha in [('r152_training_complete.pth',train_cp,complete['training_checkpoint']['sha256']),
                                   ('r152_deployed.pth',deployed,complete['deployed_checkpoint']['sha256'])]:
        checkpoint=dict(model=original['model'],step=original['step'],phase='extension',seed=original['seed'],
                        model_name='R152-R148v2-SafeAdaptivePSF',model_config=cfg,train_config=train,
                        source_checkpoint_sha256=source_sha,checkpoint_kind=original['checkpoint_kind'])
        for key in ('optimizer','torch_rng','cuda_rng'):
            if key in original:checkpoint[key]=original[key]
        torch.save(checkpoint,DEST/'weights'/name)
        again=torch.load(DEST/'weights'/name,map_location='cpu',weights_only=False)
        assert set(again['model'])==set(original['model'])
        assert all(torch.equal(again['model'][k],original['model'][k]) for k in original['model'])
    settings='''"""R152設定：所有預設路徑相對這個資料夾，可直接修改此檔。"""
from pathlib import Path
from copy import deepcopy

ROOT = Path(__file__).resolve().parent
DATA_ROOT = ROOT / "data"
INPUT_ROOT = ROOT / "input"
OUTPUT_ROOT = ROOT / "outputs"
DEFAULT_DEVICE = "auto"
DEFAULT_WEIGHT = ROOT / "weights/r152_deployed.pth"

'''
    settings+='BASE_MODEL_CONFIG = '+py_value(base_cfg)+'\n\nMODEL_CONFIG = '+py_value(cfg)+'\n\n'
    settings+='TRAIN_CONFIG = '+py_value(train)+'\n\nBASE_TRAIN_CONFIG = '+py_value(base_train)+'\n\n'
    settings+='''def model_config(base_checkpoint=None):
    cfg = deepcopy(MODEL_CONFIG)
    cfg["base_model_config"] = deepcopy(BASE_MODEL_CONFIG)
    if base_checkpoint is not None:
        cfg["base_checkpoint"] = str(base_checkpoint)
    return cfg

def resolve_path(value):
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()
'''
    write('settings.py',settings)
    r152=(ROOT/'model.py').read_text(encoding='utf-8')
    r152=r152.replace('import json,math','import math')
    r152=r152.replace('from base_model import Model as BaseModel','from .base_model import Model as BaseModel')
    r152=r152.replace('from optical.adaptive_fourier_psf import AdaptiveFourierPSFFusion','from .adaptive_fourier_psf import AdaptiveFourierPSFFusion')
    r152=r152.replace('Path(__file__).resolve().parent','Path(__file__).resolve().parent.parent')
    r152=r152.replace("base_cfg=json.loads(Path(cfg['base_model_config']).read_text(encoding='utf-8'))", "base_cfg=dict(cfg['base_model_config'])")
    r152=r152.replace("checkpoint_path=Path(cfg['base_checkpoint'])", "checkpoint_path=root/Path(cfg['base_checkpoint'])")
    write('models/r152_model.py',reformatted(r152))
    base_code=(ROOT/'base_model.py').read_text(encoding='utf-8').replace('from optical.fullres_psf import FullResPSF','from .fullres_psf import FullResPSF')
    base_code=base_code.replace('Path(__file__).resolve().parent','Path(__file__).resolve().parent.parent')
    write('models/base_model.py',reformatted(base_code))
    for name in ('adaptive_fourier_psf.py','fullres_psf.py'):
        write('models/'+name,reformatted((ROOT/'optical'/name).read_text(encoding='utf-8')))
    write('models/__init__.py','from .r152_model import Model\n')
    write('core/losses.py',reformatted((ROOT/'losses.py').read_text(encoding='utf-8')))
    write('core/base_losses.py',reformatted((base/'losses.py').read_text(encoding='utf-8')))
    write('core/__init__.py','"""Package-local training and inference utilities."""\n')
    plan=read(ROOT/'evaluation/capture_plan.json');frame=plan['frames'][0]
    receipt=read(ROOT/'results/reconstruction'/frame['run']/'01.json')
    assert sha(frame['source']['path'])==frame['source']['sha256'] and sha(receipt['output_path'])==receipt['output_sha256']
    (DEST/'input').mkdir(exist_ok=True);(DEST/'reference').mkdir(exist_ok=True)
    shutil.copy2(frame['source']['path'],DEST/'input/demo_raw.bmp')
    shutil.copy2(receipt['output_path'],DEST/'reference/demo_expected_output.npz')
    info=dict(model='R152-R148v2-SafeAdaptivePSF',source_deployed_checkpoint_sha256=complete['deployed_checkpoint']['sha256'],
              source_base_checkpoint_sha256=read(ROOT/'config/model.json')['base_checkpoint_sha256'],
              source_training_checkpoint_sha256=complete['training_checkpoint']['sha256'],
              PSF_bank_sha256=sha(DEST/'calibration/psf25_bank.npz'),
              parent_counts={'train':512,'dev':128,'test':128},views_per_parent=4,native_size=384,
              total_parameters=1207105,trainable_extension_parameters=12699,
              data_arrays_preserved_in_original_storage_dtype=True,checkpoint_tensors_identical=True,
              tested_environment=dict(torch=torch.__version__,numpy=np.__version__),
              sample_RAW_sha256=frame['source']['sha256'],sample_output_sha256=receipt['output_sha256'])
    write('reference_info.py','"""Published R152 identity and complete bundled data counts."""\nREFERENCE = '+py_value(info)+'\n')
    (DEST/'outputs/training').mkdir(parents=True,exist_ok=True);(DEST/'outputs/inference').mkdir(parents=True,exist_ok=True)
    (OUT/'asset_copy_checks.json').write_text(json.dumps(dict(status='passed',parents=verified,views=verified*4,
                                                            destination=str(DEST),weight_tensors_identical=True,
                                                            source_data_root=str(base)),ensure_ascii=False,indent=2),encoding='utf-8')
    print('ASSETS READY',DEST,flush=True)

if __name__=='__main__':main()
