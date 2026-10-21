"""Verify optional PSF labels without modifying the bundled 768-scene data."""
import json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dataset import Bank
from utils import train_config,load,sha

def main():
    bank=Bank(train_config())
    entry=dict(bank.entries['train',0])
    metadata=load(bank.root/entry['metadata'])
    assert 'psf_index' not in metadata
    metadata['psf_index']=[0,8]
    with tempfile.TemporaryDirectory(prefix='mosr_labeled_sidecar_') as d:
        sidecar=Path(d)/'0000_labeled.json'
        sidecar.write_text(json.dumps(metadata),encoding='utf-8')
        entry['metadata']=str(sidecar)
        entry['metadata_sha256']=sha(sidecar)
        bank.entries['train',0]=entry
        item=bank.batch('train',0,'cpu',epoch=0)
        assert item['psf_index'].tolist()==[0,8]
    assert 'psf_index' not in load(bank.root/'train/0000.json')
    print('EXTERNAL_LABEL_READ_PASS',item['psf_index'].tolist(),'bundled_metadata_unchanged')
if __name__=='__main__':main()
