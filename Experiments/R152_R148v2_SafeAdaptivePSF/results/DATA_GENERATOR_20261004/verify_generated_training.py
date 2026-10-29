"""Compare all regenerated training inputs, then exercise the data-dir entry."""
from copy import deepcopy
import json
import subprocess
import sys
from pathlib import Path
sys.dont_write_bytecode=True
import torch
torch.set_num_threads(1)

ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT.parents[1]
OUT=Path(__file__).resolve().parent
PACK=PROJECT/'Deliverables/Standalone_Models/R152_Standalone_ImageFiles_20261004'
sys.path.insert(0,str(ROOT))
from dataset import Bank as SourceBank
source=SourceBank(json.loads((ROOT/'config/train.json').read_text(encoding='utf-8')))
sys.path.insert(0,str(PACK))
from core.dataset import Bank
from settings import TRAIN_CONFIG


def main():
    cfg=deepcopy(TRAIN_CONFIG)
    cfg['data_root']=str(OUT/'regenerated_bank')
    new=Bank(cfg)
    assert new.root.resolve()==(OUT/'regenerated_bank').resolve()
    count=0
    for split,n in [('train',512),('dev',128),('test',128)]:
        for index in range(n):
            a=source.batch(split,index,'cpu',0);b=new.batch(split,index,'cpu',0)
            for key in ('source','target','sdf','geometry_valid','shifts_xy','actual_psf_indices','operator_psf_indices'):
                assert torch.equal(a[key],b[key]),(split,index,key)
            assert a['input_sha256']==b['input_sha256'] and a['parent_id']==b['parent_id']
            count+=1
            if count%128==0:print('REGENERATED INPUT PARENTS EXACT',count,'/768',flush=True)
    for index in (0,127,511):
        a=source.batch('train',index,'cpu',7);b=new.batch('train',index,'cpu',7)
        assert a['input_sha256']==b['input_sha256'] and torch.equal(a['operator_psf_indices'],b['operator_psf_indices'])
    subprocess.run([sys.executable,'-B','-X','utf8',str(PACK/'train.py'),
                    '--data-dir',str(OUT/'regenerated_bank'),'--output-dir',str(OUT/'regenerated_training'),
                    '--max-updates','4','--assessment-limit','1'],cwd=str(OUT),check=True)
    trained=torch.load(OUT/'regenerated_training/extension/last.pth',map_location='cpu',weights_only=False)
    assert trained['step']==4 and trained['train_config']['data_root']==str(OUT/'regenerated_bank')
    original_rows=[json.loads(line) for line in (ROOT/'runs/formal_8192/updates.jsonl').read_text(encoding='utf-8').splitlines()[:4]]
    difference=0
    for newrow,oldrow in zip(trained['history'],original_rows):
        assert newrow['parent_id']==oldrow['parent_id']
        for key in ('loss','image','gradient','pair_output','boundary','observation','teacher','selector_descriptor'):
            diff=abs(newrow[key]-oldrow[key])
            assert diff==0,(key,diff)
            difference=max(difference,diff)
    reference=torch.load(ROOT/'results/IMAGEFILE_DATASET_20261004/train_continuous/extension/last.pth',
                         map_location='cpu',weights_only=False)
    assert trained['step']==reference['step']
    for key,value in trained['model'].items():
        assert torch.equal(value,reference['model'][key]),key
    result={'status':'passed','parents':768,'views':3072,'all_actual_training_inputs_exact':True,
            'later_epoch_noise_and_operator_selection_exact':True,'data_dir_entry_exercised':True,
            'actual_GPU_updates':4,'first4_loss_terms_equal_original_formal_run':True,
            'maximum_loss_difference':difference,'four_update_state_equal_previous_TIFF_training':True}
    (OUT/'generated_training_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
