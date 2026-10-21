from pathlib import Path
import sys
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));torch.set_num_threads(4)
from training.position_loss_v2 import local_position
from training.objectives import location_xy

def fixtures(shape):
    y,x=torch.meshgrid(torch.arange(128.),torch.arange(128.),indexing='ij')
    sdf=(63.5-x) if shape=='line' else 28-torch.hypot(x-63.5,y-63.5)
    return sdf[None,None]

def test_width_change_is_not_position_change():
    for shape in ['line','circle']:
        sdf=fixtures(shape)
        for polarity in [-1,1]:
            target=.5+polarity*.5*(torch.sigmoid(sdf/1.2)-.5)
            for width in [1.2,1.8,3.]:
                output=.5+polarity*.5*(torch.sigmoid(sdf/width)-.5)
                loss,delta,weight=local_position(output,target,sdf,torch.tensor([False]))
                assert delta[weight>.5].abs().max()<.04,(shape,polarity,width,float(delta.abs().max()))

def test_expansion_is_detected_in_both_polarities():
    sdf=fixtures('circle')
    for polarity in [-1,1]:
        target=.5+polarity*.5*(torch.sigmoid(sdf/1.2)-.5)
        output=.5+polarity*.5*(torch.sigmoid((sdf+.4)/1.2)-.5)
        center,_=location_xy(output,target);assert center.abs().max()<1e-4
        loss,delta,weight=local_position(output,target,sdf,torch.tensor([False]))
        assert delta[weight>.5].abs().median()>.30 and loss>1.

def test_gain_offset_and_exact_target():
    sdf=fixtures('circle');target=.75-.5*torch.sigmoid(sdf/1.2)
    for image in [target,.8*target+.05]:
        loss,delta,weight=local_position(image,target,sdf,torch.tensor([False]));assert delta[weight>.5].abs().max()<.001

def test_gradients_flat_and_geometry_before_detail():
    sdf=fixtures('circle');target=.75-.5*torch.sigmoid(sdf/1.2)
    wrong=(.75-.5*torch.sigmoid((sdf+.4)/1.2)).requires_grad_()
    loss,_,_=local_position(wrong,target,sdf,torch.tensor([False]));loss.backward()
    assert torch.isfinite(wrong.grad).all() and wrong.grad.abs().sum()>0
    after,_,_=local_position(target,target,sdf,torch.tensor([False]));assert after==0 and loss>1
    flat=torch.ones_like(target)*.4
    zero,_,_=local_position(flat+.01,flat,sdf,torch.tensor([True]));assert zero==0
