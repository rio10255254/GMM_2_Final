"""Properties tied directly to the previously demonstrated failure cases."""
from pathlib import Path
import sys
import torch
import torch.nn.functional as F
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model.network import build_model,geometric_normals,continuous_width,Details
from model.ops import warp_local
from training.objectives import location_xy,per_scene,objective
from training.dataset import Scenes,FamilyOrder,flatten,fine_reliability
from torch.utils.data._utils.collate import default_collate

torch.set_num_threads(4)

def circle(dx=0.,dy=0.):
    yy,xx=torch.meshgrid(torch.arange(128),torch.arange(128),indexing='ij')
    sdf=30-torch.sqrt((xx-63.5-dx).square()+(yy-63.5-dy).square())
    return torch.sigmoid(sdf/1.8)[None,None],sdf[None,None]

def test_geometric_direction_independent_of_brightness():
    x=torch.arange(97,dtype=torch.float32)-48
    sdf=x[None,None,None].expand(1,1,33,97)
    nx,ny=geometric_normals(sdf)
    sampled=warp_local(sdf,torch.cat((-sdf*nx,-sdf*ny),1))
    assert sampled[...,4:-4,42:55].abs().max()<1e-4
    for polarity in (1,-1):
        image=.5+polarity*.4*torch.tanh(sdf/3)
        assert torch.isfinite(image).all()
        # Normals are derived only from SDF, so complementing intensity cannot reverse them.
        assert torch.equal(nx,geometric_normals(sdf)[0])

def test_reversing_distance_and_normal_together_preserves_sampling_center():
    _,sdf=circle()
    normal=torch.cat(geometric_normals(sdf),1)
    reverse=torch.cat(geometric_normals(-sdf),1)
    assert torch.allclose(-sdf*normal,-(-sdf)*reverse,atol=1e-6)

def test_true_xy_location_detects_translation():
    target,_=circle()
    for dx,dy in ((1.,0.),(-1.,0.),(0.,1.),(.5,-.5)):
        shifted,_=circle(dx,dy)
        measured,_=location_xy(shifted,target)
        assert torch.max(torch.abs(measured-torch.tensor([[dx,dy]])))<.08

def test_flat_image_does_not_supply_position_evidence():
    flat=torch.ones(2,1,64,64)*.4
    _,confidence=location_xy(flat+.01,flat)
    assert confidence.max()==0

def test_erased_texture_is_distinguished_from_flat_denoising():
    x=np.arange(64,dtype=np.float32)[None,:]
    target=np.broadcast_to(.5+.1*np.cos(2*np.pi*x/4),(64,64)).copy()
    blank=np.full((64,64),.5,np.float32)
    erased=fine_reliability(blank,target,.005)
    flat=fine_reliability(blank,blank,.005)
    assert erased[8:-8,8:-8].mean()<.1
    assert flat.min()==1

def test_neutral_width_is_continuous_and_ring_free():
    coordinate=torch.arange(129,dtype=torch.float32)-64
    raw=(.2+.6*torch.sigmoid(coordinate/3))[None,None,None].expand(1,1,33,129)
    sdf=coordinate[None,None,None].expand_as(raw)
    normals=torch.cat(geometric_normals(sdf),1)
    assert torch.equal(continuous_width(raw,torch.ones_like(raw),sdf,normals),raw)
    tiny=continuous_width(raw,torch.ones_like(raw)*1.000001,sdf,normals)
    assert (tiny-raw).abs().max()<1e-6
    for sign in (1,-1):
        image=raw if sign>0 else 1-raw
        result=continuous_width(image,torch.ones_like(image)*2,sdf,normals)
        difference=(result[...,1:]-result[...,:-1])*sign
        assert difference[...,16:-16].min()>-1e-5

def test_boundary_weight_equal_per_scene_not_perimeter():
    value=torch.zeros(2,1,16,16);weight=torch.zeros_like(value)
    value[0]=2;value[1]=4
    weight[0,0,1,1]=1;weight[1]=1
    assert torch.allclose(per_scene(value,weight),torch.tensor([2.,4.]))

def test_no_repeated_clear_view_and_sampler_no_duplicates():
    ds=Scenes('train',limit=100);order=list(FamilyOrder(ds,123))
    assert sorted(order)==list(range(len(ds)))
    for i in range(10):
        sample=ds[i]
        assert sample['source'].shape[0]==2
        if sample['role']!='identity':assert not sample['identity'].any()

def test_perfect_reference_zero_pair_penalty():
    ds=Scenes('train');batch=flatten(default_collate([ds[0],ds[1]]),'cpu')
    model=build_model()
    with torch.no_grad():d=model.forward_details(batch['source'])
    d.output=batch['target'];d.sdf=batch['sdf'].clamp(-16,16)
    import json
    weights=json.loads((ROOT/'config/experiment.json').read_text())['training']['weights']
    _,terms=objective(model,d,batch,weights)
    for key in ('pair_reference_error','pair_geometry','pair_location_xy','location_xy'):
        assert abs(float(terms[key]))<1e-7

def test_uniform_low_reliability_reduces_actual_gradient_objective():
    ds=Scenes('train');batch=flatten(default_collate([ds[0],ds[1]]),'cpu');model=build_model()
    import json
    weights=json.loads((ROOT/'config/experiment.json').read_text())['training']['weights']
    with torch.no_grad():d=model.forward_details(batch['source'])
    batch['fine_reliability']=torch.ones_like(batch['source'])
    _,full=objective(model,d,batch,weights)
    batch['fine_reliability']=torch.ones_like(batch['source'])*.01
    _,weak=objective(model,d,batch,weights)
    assert torch.allclose(weak['gradient_reference'],full['gradient_reference']*.01,rtol=1e-5,atol=1e-7)

def test_geometry_pair_reaches_geometry_weights_and_detail_keeps_shape_losses():
    ds=Scenes('train');batch=flatten(default_collate([ds[0],ds[1]]),'cpu');model=build_model()
    import json
    weights=json.loads((ROOT/'config/experiment.json').read_text())['training']['weights']
    d=model.forward_details(batch['source']);loss,terms=objective(model,d,batch,weights)
    assert terms['pair_geometry'].requires_grad
    gradients=torch.autograd.grad(terms['pair_geometry'],model.groups()['geometry'],retain_graph=True,allow_unused=True)
    assert sum(float(g.abs().sum()) for g in gradients if g is not None)>0
    assert all(k in terms and weights[k]>0 for k in ('location_xy','local_edge_error','pair_reference_error','pair_geometry','pair_location_xy'))
    assert torch.isfinite(loss)
