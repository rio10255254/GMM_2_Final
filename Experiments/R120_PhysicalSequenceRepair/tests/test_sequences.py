from pathlib import Path
import json
import sys
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from training.dataset import Scenes
from data.kernels import centered_asymmetric,centroid,convolve
from data.replay import latent_reference,image_formation,CONFIG
import cv2
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_centered_asymmetry_really_has_no_impulse_translation():
    for factor in [1,8]:
        k=centered_asymmetric(factor)
        assert np.max(np.abs(centroid(k)))<1e-8
        assert abs(k.sum()-1)<1e-12 and k.min()>=0
    k=centered_asymmetric();impulse=np.zeros((129,129));impulse[64,64]=1
    out=convolve(impulse,k)
    assert np.max(np.abs(centroid(out)))<1e-8


def test_manifest_arrays_are_really_consumed():
    ds=Scenes('train',epoch=1,limit=512,arm='B')
    i=next(i for i,r in enumerate(ds.records) if r['scene_index'] in ds.entries and r['role']=='edge')
    record=ds.records[i]
    before=ds[i]
    assert record['scene_index'] in ds.cache
    # Mutate only the dataset's in-memory copy; actual data files stay intact.
    ds.cache[record['scene_index']]['source']=np.full_like(ds.cache[record['scene_index']]['source'],.3)
    after=ds[i]
    assert not torch.equal(before['source'],after['source'])
    assert torch.equal(before['target'],after['target'])


def test_B_static_pair_and_physical_motion_label():
    ds=Scenes('train',epoch=4,limit=512,arm='B')
    i=next(i for i,r in enumerate(ds.records) if r['scene_index'] in ds.entries and r['role']=='edge')
    item=ds[i]
    assert torch.equal(item['target'][0],item['target'][1])
    assert item['shift_xy'].abs().sum()==0
    assert not torch.equal(item['source'][0],item['source'][1])
    motion=Scenes('train',epoch=5,limit=512,arm='B')[i]
    assert motion['shift_xy'].abs().sum()>0
    assert not torch.equal(motion['target'][0],motion['target'][1])


def test_foreground_direction_independent_of_brightness():
    ds=Scenes('train',epoch=5,limit=512,arm='B')
    for polarity in [-1,1]:
        i=next(i for i,r in enumerate(ds.records) if r['scene_index'] in ds.entries and r['polarity']==polarity and r['role']=='edge')
        item=ds[i];inside=item['mask']>.99;outside=item['mask']<.01
        assert item['sdf'][inside].median()>0
        assert item['sdf'][outside].median()<0


def test_nonzero_phase_replays_before_sensor_sampling():
    folder=ROOT/'data/sequences/train'
    item=json.loads((folder/'manifest.json').read_text())['records'][0]
    records=json.loads((Path(PROJECT_ROOT / CONFIG['data']['package_root'])/'manifest.json').read_text())['records']
    row=next(r for r in records if r['scene_index']==item['scene_index'])
    high=latent_reference(row)
    assert high.shape==(2048,2048)
    with np.load(folder/item['file']) as f:
        index=next(i for i,xy in enumerate(f['xy']) if np.array_equal(xy,[.125,0]))
        shifted=cv2.warpAffine(high,np.float32([[1,0,1],[0,1,0]]),(2048,2048),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101)
        expected_source=cv2.resize(image_formation(shifted,item['optics']),(256,256),interpolation=cv2.INTER_AREA).astype(np.float16)
        expected_target=np.rint(cv2.resize(shifted,(256,256),interpolation=cv2.INTER_AREA)*255).astype(np.uint8)
        assert np.array_equal(f['source'][index],expected_source)
        assert np.array_equal(f['target'][index],expected_target)


def test_all_zero_phase_geometry_matches_original_labels():
    base=Path(PROJECT_ROOT / CONFIG['data']['package_root'])
    records={r['scene_index']:r for r in json.loads((base/'manifest.json').read_text())['records']}
    folder=ROOT/'data/sequences/train'
    for item in json.loads((folder/'manifest.json').read_text())['records']:
        row=records[item['scene_index']]
        with np.load(folder/item['file']) as f:
            assert np.array_equal(f['sdf'][0],np.load(base/row['sdf_a']))
            with np.load(folder/'coverage_v2'/item['file']) as coverage:
                assert np.array_equal(coverage['mask'][0],np.load(base/row['mask_a']))


def test_loader_consumes_corrected_coverage():
    ds=Scenes('train',epoch=1,limit=512,arm='B')
    row=next(r for r in ds.records if r['scene_index'] in ds.entries)
    saved=ds.bank(row)
    with np.load(ds.sequence_root/'coverage_v2'/ds.entries[row['scene_index']]['file']) as f:
        assert np.array_equal(saved['mask'],f['mask'])
