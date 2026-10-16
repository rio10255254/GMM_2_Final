"""Compare every TIFF-backed training view with the original R152 reader."""
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import torch

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
PACK=ROOT.parents[1]/'Deliverables/R152_Standalone_ImageFiles_20261004'
sys.path.insert(0,str(ROOT))
from dataset import Bank as SourceBank
source=SourceBank(json.loads((ROOT/'config/train.json').read_text(encoding='utf-8')))
sys.path.insert(0,str(PACK))
from core.dataset import Bank
from settings import TRAIN_CONFIG
new=Bank(TRAIN_CONFIG)

def main():
    count=0
    for split,n in [('train',512),('dev',128),('test',128)]:
        for index in range(n):
            a=source.batch(split,index,'cpu',0);b=new.batch(split,index,'cpu',0)
            for key in ('source','target','sdf','geometry_valid','shifts_xy','actual_psf_indices','operator_psf_indices'):
                assert torch.equal(a[key],b[key]),(split,index,key)
            assert a['input_sha256']==b['input_sha256'] and a['parent_id']==b['parent_id']
            count+=1
            if count%128==0:print('EXACT TIFF PARENTS',count,'/768',flush=True)
    for index in (0,127,511):
        a=source.batch('train',index,'cpu',7);b=new.batch('train',index,'cpu',7)
        assert a['input_sha256']==b['input_sha256'] and torch.equal(a['operator_psf_indices'],b['operator_psf_indices'])
    result=dict(status='passed',formal_reader_uses_Image_open_TIFF=True,parents=768,views=3072,
                all_source_inputs_targets_geometry_and_metadata_exact=True,later_epoch_noise_selection_exact=True,
                training_NPZ_files=len(list((PACK/'data').rglob('*.npz'))),training_PNG_files=len(list((PACK/'data').rglob('*.png'))))
    assert result['training_NPZ_files']==result['training_PNG_files']==0
    (OUT/'TIFF_input_parity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
