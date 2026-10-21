"""Freeze and archive only after complete independent regeneration and training checks."""
import ast
from copy import deepcopy
import hashlib
import json
import pprint
import re
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import zipfile

PROJECT=Path(__file__).resolve().parents[4]
ROOT=PROJECT/'Experiments/R152_R148v2_SafeAdaptivePSF'
OUT=Path(__file__).resolve().parent
PACK=PROJECT/'Deliverables/R152_Standalone_ImageFiles_20261004'
OLD=PROJECT/'Deliverables/R152_Standalone_20261004'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_python(path,name):
    tree=ast.parse(path.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError((str(path),name))


def save_python(path,name,value,doc):
    path.write_text('"""'+doc+'"""\n'+name+' = '+pprint.pformat(value,width=110,sort_dicts=False)+'\n',encoding='utf-8')


def main():
    generation=read_python(OUT/'regenerated_bank/generation_result.py','RESULT')
    probes=json.loads((OUT/'source_probe_checks.json').read_text(encoding='utf-8'))
    portable=json.loads((OUT/'portable_generation_checks.json').read_text(encoding='utf-8'))
    training=json.loads((OUT/'generated_training_checks.json').read_text(encoding='utf-8'))
    assert generation['state']=='complete' and generation['reused_verified_parents']==0
    assert generation['all_original_pixel_values_exact'] and generation['byte_identical_TIFFs']==9216
    assert probes['status']==portable['status']==training['status']=='passed'
    for directory in ('models','weights','calibration'):
        for p in (OLD/directory).rglob('*'):
            if p.is_file():assert sha(p)==sha(PACK/p.relative_to(OLD)),p
    for name in ('core/losses.py','core/base_losses.py','core/runtime.py','core/training.py','settings.py','infer.py'):
        assert sha(PACK/name)==sha(OLD/name),name
    for name in ('generation_guide.py','start_here.py'):
        p=PACK/name
        text=p.read_text(encoding='utf-8')
        for old,new in [('变化','變化'),('资料夹','資料夾'),('資料夹','資料夾'),('实际','實際'),('改变','改變')]:
            text=text.replace(old,new)
        p.write_text(text,encoding='utf-8')
    info=read_python(PACK/'reference_info.py','REFERENCE')
    info.update(generation_entry='generate_data.py',original_generation_sources=5,
                source_only_generation_requires_no_external_training_images=True,
                generation_environment=generation['environment'])
    save_python(PACK/'reference_info.py','REFERENCE',info,'Published R152, TIFF identities and independent generation recipe.')
    verified=read_python(PACK/'verification_info.py','VERIFIED')
    verified.update(original_generation_sources_preserved_exactly=5,
                    all768_seed_parameters_exact=True,representative_original_4x_latents_exact=True,
                    complete_from_seed_generation_passed=True,regenerated_views=3072,
                    regenerated_TIFFs_exact=9216,regenerated_TIFF_files_byte_identical=9216,
                    old_experiment_and_bundled_TIFF_reads_blocked_during_full_generation=True,
                    moved_generation_without_training_images_passed=True,
                    generated_all_actual_training_inputs_exact=True,
                    generated_first4_update_losses_exact=True,
                    generated_four_update_state_equal_original_image_delivery=True,
                    generation_seconds=generation['seconds'],generation_environment=generation['environment'])
    save_python(PACK/'verification_info.py','VERIFIED',verified,'Actual package, source regeneration and executable training verification.')
    assert len(list((PACK/'data').rglob('*.tif')))==9216
    assert not list((PACK/'data').rglob('*.npz')) and not list((PACK/'data').rglob('*.png'))
    assert not list((PACK/'outputs').rglob('*.*'))
    files=[]
    for p in sorted(PACK.rglob('*')):
        assert not p.is_symlink(),p
        if p.is_file():
            assert p.suffix in {'.py','.tif','.npz','.pth','.bmp'},p
            if p.suffix=='.py':
                source=p.read_text(encoding='utf-8');ast.parse(source,filename=str(p))
                assert not re.search(r'[A-Za-z]:[\\/]',source),p
            files.append(p)
        elif p.is_dir():assert p.name!='__pycache__',p
    identities={p.relative_to(PACK).as_posix():sha(p) for p in files if p.name!='manifest.py'}
    save_python(PACK/'manifest.py','FILES',identities,'Exact delivered files, including historical generation sources; outputs excluded.')
    files=sorted(p for p in PACK.rglob('*') if p.is_file())
    archive=PROJECT/'Deliverables/R152_Standalone_ImageFiles_20261004.zip'
    temporary=archive.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,PACK.name+'/'+p.relative_to(PACK).as_posix())
        for directory in ('outputs/','outputs/training/','outputs/inference/'):
            z.writestr(PACK.name+'/'+directory,b'')
    with zipfile.ZipFile(temporary,'r') as z:
        assert z.testzip() is None
        for p in files:
            assert hashlib.sha256(z.read(PACK.name+'/'+p.relative_to(PACK).as_posix())).hexdigest()==sha(p)
    temporary.replace(archive)
    receipt={'status':'passed','package':str(PACK),'archive':str(archive),
             'file_count':len(files),'python_files':sum(p.suffix=='.py' for p in files),
             'package_bytes':sum(p.stat().st_size for p in files),'archive_bytes':archive.stat().st_size,
             'archive_sha256':sha(archive),'all_archive_files_verified':True,
             'generation':generation,'training':training,'portable':portable,
             'historical_sources_exact':5,'outputs_in_delivery_empty':True,
             'original_model_weights_and_PSF_unchanged':True}
    (OUT/'package_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
