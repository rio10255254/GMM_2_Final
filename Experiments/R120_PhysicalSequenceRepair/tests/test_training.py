from pathlib import Path
import sys
import torch
from torch.utils.data._utils.collate import default_collate
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model.network import build_model,continuous_width
from training.dataset import Scenes,flatten
from training.base import CONFIG
from training.objectives import objective


def test_all_active_groups_receive_gradients():
    torch.set_num_threads(4)
    model=build_model()
    b=flatten(default_collate([Scenes('train',1,16,'B')[i] for i in [0,1]]),'cpu')
    # Head-zero initialization legitimately blocks tower gradient on the first
    # step. Test every intended parameter group after two optimization steps.
    optim=torch.optim.Adam(model.parameters(),lr=.0001)
    for _ in range(2):
        optim.zero_grad();d=model.forward_details(b['source'])
        loss,terms=objective(model,d,b,CONFIG['training']['weights']);loss.backward();optim.step()
    for name,params in model.groups().items():
        assert any(p.grad is not None and p.grad.abs().sum()>0 for p in params),name
    assert set(terms)==set(CONFIG['training']['weights'])


def test_perfect_physical_targets_have_zero_pair_error():
    ds=Scenes('train',5,16,'B');b=flatten(default_collate([ds[0],ds[1]]),'cpu')
    model=build_model()
    with torch.no_grad():d=model.forward_details(b['source'])
    d.output=b['target'];d.sdf=b['sdf'].clamp(-16,16)
    _,terms=objective(model,d,b,CONFIG['training']['weights'])
    for key in ['pair_reference_error','pair_geometry','pair_location_xy','location_xy']:
        assert abs(float(terms[key]))<1e-7
