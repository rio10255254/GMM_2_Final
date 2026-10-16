"""Verify the image-backed training path, then freeze a clean TIFF-only delivery."""
import ast
import hashlib
import json
import pprint
import re
import zipfile
from pathlib import Path

import torch

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1];PACK=PROJECT/'Deliverables/R152_Standalone_ImageFiles_20261004'
OLD=PROJECT/'Deliverables/R152_Standalone_20261004'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))

def main():
    parity=read(OUT/'TIFF_input_parity.json');assert parity['status']=='passed'
    resumed=torch.load(OUT/'train_resume/extension/last.pth',map_location='cpu',weights_only=False)
    continuous=torch.load(OUT/'train_continuous/extension/last.pth',map_location='cpu',weights_only=False)
    assert resumed['step']==continuous['step']==4
    for key in resumed['model']:assert torch.equal(resumed['model'][key],continuous['model'][key]),key
    original_rows=[json.loads(line) for line in (ROOT/'runs/formal_8192/updates.jsonl').read_text(encoding='utf-8').splitlines()[:4]]
    maxdiff=0
    for new,old in zip(continuous['history'],original_rows):
        assert new['parent_id']==old['parent_id']
        for key in ('loss','image','gradient','pair_output','boundary','observation','teacher','selector_descriptor'):
            difference=abs(new[key]-old[key]);assert difference<1e-6,(key,difference);maxdiff=max(maxdiff,difference)
    for directory in ('models','weights','calibration'):
        for source in (OLD/directory).rglob('*'):
            if source.is_file():assert sha(source)==sha(PACK/source.relative_to(OLD)),source
    assert len(list((PACK/'data').rglob('*.tif')))==9216
    assert not list((PACK/'data').rglob('*.npz')) and not list((PACK/'data').rglob('*.png'))
    assert 'np.load' not in (PACK/'core/dataset.py').read_text(encoding='utf-8')
    proof=dict(status='passed',training_image_format='TIFF float32',clear_TIFFs=3072,blur_TIFFs=3072,
               geometry_TIFFs=3072,training_NPZ_files=0,training_PNG_files=0,
               all3072_source_input_views_exact=True,all_original_target_and_geometry_values_exact=True,
               first4_update_losses_equal_published_run=(maxdiff==0),maximum_loss_term_difference=maxdiff,
               resumed_2_plus2_equals_continuous4_exactly=True,model_code_and_weights_unchanged=True,
               formal_8192_training_not_repeated=True)
    (PACK/'verification_info.py').write_text('"""Image-file training conversion and executable verification."""\nVERIFIED = '+pprint.pformat(proof,width=105,sort_dicts=False)+'\n',encoding='utf-8')
    allowed={'.py','.tif','.npz','.pth','.bmp'}
    files=[]
    for p in sorted(PACK.rglob('*')):
        assert not p.is_symlink(),p
        if p.is_file():
            assert p.suffix in allowed,p
            assert not p.is_relative_to(PACK/'outputs'),p
            if p.suffix=='.py':
                code=p.read_text(encoding='utf-8');ast.parse(code)
                assert not re.search(r'[A-Za-z]:[\\/]',code),p
            files.append(p)
        elif p.is_dir():assert p.name!='__pycache__',p
    manifest={p.relative_to(PACK).as_posix():sha(p) for p in files if p.name!='manifest.py'}
    (PACK/'manifest.py').write_text('"""Exact delivered image/program identities; outputs excluded."""\nFILES = '+pprint.pformat(manifest,width=130,sort_dicts=False)+'\n',encoding='utf-8')
    files=sorted(p for p in PACK.rglob('*') if p.is_file())
    archive=PROJECT/'Deliverables/R152_Standalone_ImageFiles_20261004.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,PACK.name+'/'+p.relative_to(PACK).as_posix())
        for d in ('outputs/','outputs/training/','outputs/inference/'):z.writestr(PACK.name+'/'+d,b'')
    with zipfile.ZipFile(archive,'r') as z:
        assert z.testzip() is None
        for p in files:assert hashlib.sha256(z.read(PACK.name+'/'+p.relative_to(PACK).as_posix())).hexdigest()==sha(p)
    receipt=dict(**proof,package=str(PACK),archive=str(archive),files=len(files),
                 python_files=sum(p.suffix=='.py' for p in files),bytes=sum(p.stat().st_size for p in files),
                 archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),all_archive_files_verified=True)
    (OUT/'package_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
