import pathlib,sys,types,unittest,json
import torch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent/'R124_RealFirstPrototype'))
from model.observation import LinearObservation
from training.objectives import objective

class ObjectiveTests(unittest.TestCase):
    def test_exact_references_do_not_pay_resampling_or_geometry_penalties(self):
        torch.set_num_threads(2)
        sdf=torch.linspace(-16,16,640)[None,None,None,:].expand(2,1,640,640).clone()
        target=.2+.6*torch.sigmoid(sdf/2)
        obs=LinearObservation(torch.ones(1,1),sampling_factor=4)
        latent=obs.lift(target);b=(sdf.abs()<=1).float()
        details=types.SimpleNamespace(output=target,latent=latent,geometry={'sdf':sdf,'boundary_logits':torch.where(b>0,torch.full_like(b,80),torch.full_like(b,-80))})
        arrays={'target':target,'latent_target':latent,'sdf':sdf,'boundary':b}
        meta={'motion_observable':True,'shift_xy':[.37,-.23],'flat':False,'photometry':{'low':.2,'high':.8},'polarity':1}
        weights=json.loads((ROOT/'config/pilot.json').read_text())['loss_weights']
        loss,terms=objective(types.SimpleNamespace(observation=obs),details,target,arrays,meta,weights,True)
        for name,value in terms.items():self.assertLess(float(value.abs()),1e-7,name)
        self.assertGreaterEqual(float(loss),0)
        # A view-specific error must trigger the pair term; the target's
        # physical/non-native motion itself is never penalized at exact truth.
        changed=target.clone();changed[1]+=.01;details.output=changed
        _,changed_terms=objective(types.SimpleNamespace(observation=obs),details,target,arrays,meta,weights,False)
        self.assertGreater(float(changed_terms['pair_reference_residual_gray']),1)
        self.assertEqual(float(changed_terms['geometry_sdf']),0)

if __name__=='__main__':unittest.main()
