from pathlib import Path
import json
import hashlib
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.build_sequences import poses,sha


def main():
    seen={};result={};total=0
    for split,count in [('train',96),('validation',48)]:
        folder=ROOT/'data/sequences'/split
        data=json.loads((folder/'manifest.json').read_text())
        assert data['status']=='complete' and data['scene_count']==count
        ids=[r['scene_index'] for r in data['records']]
        assert len(set(ids))==count
        for record in data['records']:
            path=folder/record['file'];assert sha(path)==record['sha256']
            assert record['source_anchor_byte_equal'] and record['target_anchor_byte_equal']
            with np.load(path) as f:
                assert np.array_equal(f['xy'],np.array(poses(),np.float32))
                for key in ['source','target','mask','sdf']:
                    assert f[key].shape==(49,256,256)
                    assert np.isfinite(f[key]).all()
        seen[split]=set(ids);total+=data['new_payload_bytes']
        result[split]={'scenes':count,'physical_positions':count*49,'manifest_sha256':sha(folder/'manifest.json')}
    assert not seen['train']&seen['validation']
    assert total<8*2**30
    result.update(status='pass',payload_gib=total/2**30,partitions_disjoint=True,source_and_target_anchors_byte_equal=True)
    with (ROOT/'results/bank_audit.json').open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
