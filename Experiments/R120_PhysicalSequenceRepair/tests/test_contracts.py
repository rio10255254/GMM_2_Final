from pathlib import Path
import sys
import importlib.util
import numpy as np
import torch
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from training.dataset import Scenes
from validation.calibrate import fixtures
from validation.registration import summarize


def test_original_R118_data_parity():
    old=ROOT.parent/'R118_PhysicalCoordinateRepairScratch/training/dataset.py'
    spec=importlib.util.spec_from_file_location('original_r118_dataset',old)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    from training.base import CONFIG
    module.CONFIG['seed']=CONFIG['seed']
    for split,epoch in [('train',1),('train',4),('validation',0)]:
        reference=module.Scenes(split,epoch,limit=12);candidate=Scenes(split,epoch,limit=12,arm='A')
        for i in range(12):
            a,b=reference[i],candidate[i]
            for key in a:
                if isinstance(a[key],torch.Tensor):assert torch.equal(a[key],b[key]),(split,i,key)
                else:assert a[key]==b[key]


def test_all_locator_cases_really_pass():
    result=fixtures()
    assert result['status']=='pass',result
    assert len(result['fixtures'])==15


def test_mixed_scene_rejected():
    rows=[dict(scene_id=s,condition_id='c',method='m',protocol='static',frame=i,valid=True,xy=[i,0],truth=[i,0]) for i,s in enumerate(['a','b'])]
    with pytest.raises(ValueError,match='mixed scene'):summarize(rows)


def test_missing_frame_not_silently_bridged():
    rows=[dict(scene_id='a',condition_id='c',method='m',protocol='motion',frame=i,valid=i!=1,xy=[i,0] if i!=1 else None,truth=[i,0]) for i in range(3)]
    result=summarize(rows)
    assert len(result['steps'])==2 and not any(s['valid'] for s in result['steps'])
    assert result['failure_count']==1


def test_single_observation_not_perfect_repeatability():
    row=dict(scene_id='a',condition_id='c',method='m',protocol='static',frame=0,valid=True,xy=[0,0],truth=[0,0])
    assert summarize([row])['repeat_sd_xy'] is None


def test_A_B_validation_bytes_identical():
    for epoch in [0,7]:
        a,b=Scenes('validation',epoch,12,'A'),Scenes('validation',epoch,12,'B')
        for i in range(12):
            for key in ('source','target','sdf','fine_reliability'):
                assert torch.equal(a[i][key],b[i][key])
