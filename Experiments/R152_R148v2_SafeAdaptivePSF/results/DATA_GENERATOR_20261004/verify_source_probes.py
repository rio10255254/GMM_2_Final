"""Check every seed parameter and representative original latent arrays."""
import hashlib
import json
import sys
import time
from pathlib import Path
sys.dont_write_bytecode=True
import numpy as np

PROJECT=Path(__file__).resolve().parents[4]
PACK=PROJECT/'Deliverables/Standalone_Models/R152_Standalone_ImageFiles_20261004'
sys.path.insert(0,str(PACK))
from data_index import ENTRIES
from generation.scene import parameters,canonical,render_initial_latent
from generation.lineage import PARENTS
from generation.physical_views import generate_views,digest_array
from generation.labels import generate_labels


def main():
    start=time.perf_counter()
    reference={(e['split'],e['index']):e for e in PARENTS}
    metadata_manifest=json.loads((PROJECT/'Experiments/R147_FullResPSFConsistency/data/manifest.json').read_text(encoding='utf-8'))
    original={(e['split'],e['index']):e for e in metadata_manifest['entries']}
    samples={}
    for e in ENTRIES:
        metadata,_=parameters(e['split'],e['index'])
        assert hashlib.sha256(canonical(metadata).encode()).hexdigest()==reference[(e['split'],e['index'])]['seed_parameter_sha256']
        samples.setdefault(e['category'],e)
    for category,e in samples.items():
        metadata,_=parameters(e['split'],e['index'])
        latent=render_initial_latent(metadata)
        with np.load(original[(e['split'],e['index'])]['original_arrays']['path'],allow_pickle=False) as z:
            expected=z['latent_target'][0]
        assert latent.dtype==expected.dtype and np.array_equal(latent,expected),category
        arrays,views=generate_views(latent,metadata)
        arrays.update(generate_labels(metadata['shape'],category,views))
        for key in ('target','noiseless','sdf','valid'):
            assert digest_array(arrays[key])==e['array_sha256'][key],(category,key)
        print('SOURCE AND FINAL PIXELS EXACT',e['parent_id'],category,flush=True)
    result={'status':'passed','all768_seed_parameters_exact':True,'categories':list(samples),
            'representative_original_4x_latents_exact':True,'representative_final_arrays_exact':True,
            'seconds':time.perf_counter()-start}
    (Path(__file__).resolve().parent/'source_probe_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
