from pathlib import Path
import importlib.util,sys
import numpy as np,torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from training.factorial_dataset import Scenes
from training.position_loss import local_position
from training.objectives import location_xy

def test_control_replays_corrected_R120():
    path=ROOT.parent/'R120_PhysicalSequenceRepair/training/dataset.py'
    spec=importlib.util.spec_from_file_location('r120_control_comparison',path);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    for epoch in [1,4,5]:
        a=Scenes('train',epoch,512,'A');b=old.Scenes('train',epoch,512,'B')
        for index in [0,1,13,80,200,450]:
            for key,value in a[index].items():
                if isinstance(value,torch.Tensor):assert torch.equal(value,b[index][key]),(epoch,index,key)
                else:assert value==b[index][key]

def test_factor_pairs_receive_identical_training_data():
    for epoch in [1,4,5]:
        ds={arm:Scenes('train',epoch,512,arm) for arm in 'ABCD'}
        changed=0
        for index in [0,1,13,80,200,450]:
            x={arm:d[index] for arm,d in ds.items()}
            for key in ['source','target','sdf','mask','fine_reliability','shift_xy']:
                assert torch.equal(x['A'][key],x['C'][key]);assert torch.equal(x['B'][key],x['D'][key])
            for key in ['sdf','mask','shift_xy']:assert torch.equal(x['A'][key],x['B'][key])
            changed+=not torch.equal(x['A']['source'],x['B']['source'])
            assert torch.isfinite(x['B']['source']).all() and x['B']['target'].min()>=0 and x['B']['target'].max()<=1
        assert changed==6

def test_all_validation_bytes_identical():
    ds={arm:Scenes('validation',0,96,arm) for arm in 'ABCD'}
    for i in range(96):
        a=ds['A'][i]
        for arm in 'BCD':
            b=ds[arm][i]
            for key in ['source','target','sdf','mask','fine_reliability','shift_xy']:assert torch.equal(a[key],b[key])

def fixture(radius=28):
    y,x=torch.meshgrid(torch.arange(128.),torch.arange(128.),indexing='ij')
    sdf=(radius-torch.sqrt((x-63.5)**2+(y-63.5)**2))[None,None]
    image=.75-.5*torch.sigmoid(sdf/1.2)
    return image,sdf

def test_local_position_detects_expansion_missed_by_center():
    target,sdf=fixture();expanded,_=fixture(28.4)
    center,_=location_xy(expanded,target);assert center.abs().max()<1e-4
    loss,delta,weight=local_position(expanded,target,sdf,torch.tensor([False]))
    assert loss>.1 and delta[weight>.5].abs().median()>.25

def test_perfect_and_photometric_targets_do_not_demand_motion():
    target,sdf=fixture();flat=torch.tensor([False])
    perfect,_,_=local_position(target,target,sdf,flat);assert perfect==0
    # A gain/offset change is a nuisance to this position-only measurement.
    photo,delta,weight=local_position(.8*target+.05,target,sdf,flat)
    assert photo<1e-5 and delta[weight>.5].abs().max()<.001

def test_before_detail_penalty_cannot_be_hidden_by_correct_final_output():
    target,sdf=fixture();wrong,_=fixture(28.4)
    before,_,_=local_position(wrong,target,sdf,torch.tensor([False]))
    after,_,_=local_position(target,target,sdf,torch.tensor([False]))
    assert before>.1 and after==0

def test_local_position_gradient_and_flat_reference():
    target,sdf=fixture();prediction=(target+.01*torch.randn_like(target)).requires_grad_()
    loss,_,_=local_position(prediction,target,sdf,torch.tensor([False]));loss.backward()
    assert torch.isfinite(prediction.grad).all() and prediction.grad.abs().sum()>0
    flat=torch.ones_like(target)*.4
    value,_,_=local_position(flat+.01,flat,sdf,torch.tensor([True]));assert value==0
