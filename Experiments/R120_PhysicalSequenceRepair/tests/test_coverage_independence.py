from pathlib import Path
import sys
import torch
from torch.utils.data._utils.collate import default_collate
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from training.dataset import Scenes,flatten
from training.base import CONFIG
from training.objectives import objective
from model.network import build_model


def test_unused_coverage_cannot_change_current_objective_or_gradients():
    torch.set_num_threads(4)
    ds=Scenes('train',5,16,'B');batch=flatten(default_collate([ds[0],ds[1]]),'cpu')
    model=build_model()
    details=model.forward_details(batch['source'])
    original,original_terms=objective(model,details,batch,CONFIG['training']['weights'])
    changed=dict(batch);changed['mask']=torch.zeros_like(batch['mask'],requires_grad=True)
    new,new_terms=objective(model,details,changed,CONFIG['training']['weights'])
    assert torch.equal(original,new)
    assert all(torch.equal(original_terms[k],new_terms[k]) for k in original_terms)
    assert torch.autograd.grad(new,changed['mask'],allow_unused=True)[0] is None
