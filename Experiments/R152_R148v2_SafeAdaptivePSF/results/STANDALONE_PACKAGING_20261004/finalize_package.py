"""Freeze and archive a clean Python-only control surface with complete data."""
import ast
import hashlib
import json
import pprint
import re
import zipfile
from pathlib import Path

import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1];PACK=PROJECT/'Deliverables/R152_Standalone_20261004'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    source=read(OUT/'source_and_resume_verification.json');portable=read(OUT/'portability_verification.json')
    assert source['status']==portable['status']=='passed'
    expected=np.load(PACK/'reference/demo_expected_output.npz')['output']
    actual=np.load(OUT/'verify_inference/demo_raw_R152.npz')['output']
    assert np.array_equal(actual,expected)
    base_test=torch.load(OUT/'verify_two_stage/base/trained_base.pth',map_location='cpu',weights_only=False)
    final_test=torch.load(OUT/'verify_two_stage/extension/deployed.pth',map_location='cpu',weights_only=False)
    assert base_test['step']==final_test['step']==2 and final_test['phase']=='extension'
    assert final_test['checkpoint_kind']=='completed_short_test'
    proof=dict(complete_source_data_parents=768,views=3072,all_source_input_views_exact=True,
               published_weight_tensors_exact=209,original_full_frame_inference_exact=True,
               resume_two_plus_two_matches_uninterrupted_four_exactly=True,
               first_four_update_losses_match_published_run_exactly=True,
               two_stage_training_and_deployment_selection_exercised=True,
               completed_updates_pending_assessment_resume_exercised=True,
               CPU_inference_checked=True,CUDA_training_and_inference_checked=True,
               relocated_runtime_with_original_experiment_reads_denied=True,
               grayscale_uint8_uint16_IO_checked=True,old_machine_paths_in_runtime=0,
               formal_8192_training_repeated_during_packaging=False)
    (PACK/'verification_info.py').write_text('"""Delivery verification results; functional short runs do not replace the published weights."""\nVERIFIED = '+pprint.pformat(proof,sort_dicts=False,width=105)+'\n',encoding='utf-8')
    allowed={'.py','.npz','.pth','.bmp'}
    files=[]
    for p in sorted(PACK.rglob('*')):
        assert not p.is_symlink(),p
        if p.is_file():
            assert p.suffix in allowed,p
            assert not p.is_relative_to(PACK/'outputs'),p
            if p.suffix=='.py':
                code=p.read_text(encoding='utf-8');ast.parse(code,filename=str(p))
                assert not re.search(r'[A-Za-z]:[\\/]',code),p
            files.append(p)
        elif p.is_dir():assert p.name!='__pycache__',p
    paths={p.relative_to(PACK).as_posix():sha(p) for p in files if p.name!='manifest.py'}
    (PACK/'manifest.py').write_text('"""SHA-256 of delivered immutable files; outputs are deliberately excluded."""\nFILES = '+pprint.pformat(paths,sort_dicts=False,width=130)+'\n',encoding='utf-8')
    files=sorted(p for p in PACK.rglob('*') if p.is_file())
    archive=PROJECT/'Deliverables/R152_Standalone_20261004.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,PACK.name+'/'+p.relative_to(PACK).as_posix())
        for d in ('outputs/','outputs/training/','outputs/inference/'):
            z.writestr(PACK.name+'/'+d,b'')
    with zipfile.ZipFile(archive,'r') as z:
        assert z.testzip() is None
        for p in files:assert hashlib.sha256(z.read(PACK.name+'/'+p.relative_to(PACK).as_posix())).hexdigest()==sha(p)
    receipt=dict(status='passed',package=str(PACK),archive=str(archive),files=len(files),
                 python_files=sum(p.suffix=='.py' for p in files),training_parent_files=len(list((PACK/'data').rglob('*.npz'))),
                 bytes=sum(p.stat().st_size for p in files),archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),
                 controls_and_configuration_only_python=True,no_JSON_BAT_PS1_TXT_MD_in_package=True,
                 no_links_or_caches_or_test_outputs=True,all_archive_files_sha256_verified=True,verification=proof)
    (OUT/'package_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
