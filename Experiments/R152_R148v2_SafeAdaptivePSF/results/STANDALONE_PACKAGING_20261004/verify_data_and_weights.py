"""Independent source-versus-package input, tensor and resume comparisons."""
from pathlib import Path
import ast
import hashlib
import json
import sys
sys.dont_write_bytecode=True

import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
PACK=ROOT.parents[1]/'Deliverables/Standalone_Models/R152_Standalone_20261004'
sys.path.insert(0,str(ROOT))
from dataset import Bank as SourceBank
source_cfg=json.loads((ROOT/'config/train.json').read_text(encoding='utf-8'))
source=SourceBank(source_cfg)
sys.path.insert(0,str(PACK))
from core.dataset import Bank
from settings import TRAIN_CONFIG,model_config
from models import Model
PROJECT_ROOT = Path(__file__).resolve().parents[4]
target=Bank(TRAIN_CONFIG)

def main():
    parents=0
    for split,count in [('train',512),('dev',128),('test',128)]:
        for index in range(count):
            a=source.batch(split,index,'cpu',0);b=target.batch(split,index,'cpu',0)
            for key in ('source','target','sdf','geometry_valid','shifts_xy','actual_psf_indices','operator_psf_indices'):
                assert torch.equal(a[key],b[key]),(split,index,key)
            assert a['input_sha256']==b['input_sha256'] and a['parent_id']==b['parent_id'] and a['category']==b['category']
            parents+=1
            if parents%128==0:print('MATCHED PARENTS',parents,'/ 768',flush=True)
    for index in (0,127,511):
        a=source.batch('train',index,'cpu',7);b=target.batch('train',index,'cpu',7)
        assert a['input_sha256']==b['input_sha256']
        assert torch.equal(a['operator_psf_indices'],b['operator_psf_indices'])
    published=json.loads((ROOT/'runs/formal_8192/training_complete.json').read_text(encoding='utf-8'))
    original=torch.load(str(PROJECT_ROOT / published['deployed_checkpoint']['path']),map_location='cpu',weights_only=False)
    packaged=torch.load(PACK/'weights/r152_deployed.pth',map_location='cpu',weights_only=False)
    assert set(original['model'])==set(packaged['model'])
    for name in original['model']:assert torch.equal(original['model'][name],packaged['model'][name]),name
    m=Model(model_config(),PACK);m.load_state_dict(packaged['model'],strict=True)
    assert sum(p.numel() for p in m.parameters())==1207105
    assert sum(p.numel() for p in m.parameters() if p.requires_grad)==12699
    paused=torch.load(OUT/'verify_short_resume/extension/last.pth',map_location='cpu',weights_only=False)
    continuous=torch.load(OUT/'verify_continuous/extension/last.pth',map_location='cpu',weights_only=False)
    assert paused['step']==continuous['step']==4
    for name in paused['model']:assert torch.equal(paused['model'][name],continuous['model'][name]),name
    for name,value in packaged['model'].items():
        if name.startswith('base.'):assert torch.equal(continuous['model'][name],value),name
    initial_published=[json.loads(line) for line in (ROOT/'runs/formal_8192/updates.jsonl').read_text(encoding='utf-8').splitlines()[:4]]
    differences=[]
    for new,old in zip(continuous['history'],initial_published):
        assert new['parent_id']==old['parent_id']
        for name in ('loss','image','gradient','pair_output','boundary','observation','teacher','selector_descriptor'):
            difference=abs(new[name]-old[name]);assert difference<1e-6,(name,difference)
            differences.append(difference)
    # Runtime code/configuration and checkpoint metadata contain no old machine paths.
    import re
    for path in PACK.rglob('*.py'):
        code=path.read_text(encoding='utf-8');ast.parse(code)
        assert not re.search(r'[A-Za-z]:[\\/]',code),path
    def strings(value):
        if isinstance(value,str):yield value
        elif isinstance(value,dict):
            for key,v in value.items():yield from strings(key);yield from strings(v)
        elif isinstance(value,(list,tuple)):
            for v in value:yield from strings(v)
    assert not any(re.search(r'[A-Za-z]:[\\/]',s) for s in strings(packaged))
    result=dict(status='passed',all768_parent_inputs_exact=True,all3072_views_exact=True,
                later_epoch_noise_and_operator_selection_exact=True,original_weight_tensor_count=len(original['model']),
                all_published_tensors_identical=True,parameters=1207105,trainable_extension_parameters=12699,
                resume_two_plus_two_equals_continuous_four_exactly=True,all_frozen_base_tensors_unchanged=True,
                first_four_updates_match_published_training=True,maximum_initial_loss_term_difference=max(differences),
                old_machine_paths_in_runnable_code_or_checkpoint_metadata=0)
    (OUT/'source_and_resume_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
