"""Loader and artifact checks independent of the image-quality question."""
import copy, json, pathlib, sys, tempfile, unittest
import torch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model.calibration import observation_from_profile
from model.checkpoint import save_initialization,load_initialization
from model.network import build_model

class CalibrationArtifactTests(unittest.TestCase):
    def setUp(self):
        self.profile=json.loads((ROOT/'config/identity_diagnostic.json').read_text())

    def test_physical_psf_is_flipped_once_without_recentering(self):
        p=copy.deepcopy(self.profile);p['kernel']={'type':'explicit','values':[[0,0,0],[0,.25,.75],[0,0,0]]}
        o=observation_from_profile(p)
        torch.testing.assert_close(o.impulse_centroid_internal_xy,torch.tensor([.75,0.]))
        p['kernel_convention']='correlation';c=observation_from_profile(p)
        torch.testing.assert_close(c.impulse_centroid_internal_xy,torch.tensor([-.75,0.]))

    def test_qualification_string_is_not_instrument_evidence(self):
        p=copy.deepcopy(self.profile);p['qualification']='qualified_independent_calibration'
        with self.assertRaises(ValueError):observation_from_profile(p)

    def test_checkpoint_reloads_and_rejects_hidden_operator_change(self):
        torch.manual_seed(44);model=build_model({'channels':4,'dilations':(1,)},observation_from_profile(self.profile)).eval()
        raw=torch.rand(1,1,9,13)
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'init.pth';save_initialization(p,model,self.profile,44)
            with self.assertRaises(FileExistsError):save_initialization(p,model,self.profile,44)
            loaded,_=load_initialization(p)
            with torch.no_grad():torch.testing.assert_close(model(raw),loaded(raw),atol=0,rtol=0)
            payload=torch.load(p,weights_only=True);payload['state_dict']['observation.gain']*=2
            bad=pathlib.Path(tmp)/'changed.pth';torch.save(payload,bad)
            with self.assertRaises(ValueError):load_initialization(bad)

if __name__=='__main__':unittest.main()
