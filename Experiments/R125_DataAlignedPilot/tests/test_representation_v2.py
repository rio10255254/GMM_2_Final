import pathlib,sys,unittest
import torch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT.parent/'R124_RealFirstPrototype'))
from prototype.network import build_model
from model.observation import LinearObservation
from inference.tiling import tiled_forward
from training.objectives import robust_gray,translated

class RepresentationTests(unittest.TestCase):
    def setUp(self):torch.manual_seed(125);torch.set_num_threads(2)
    def test_native_identity_and_four_subcell_freedom(self):
        m=build_model({'channels':4,'dilations':[1],'observation_steps':False}).eval();x=torch.full((1,1,13,17),.5)
        with torch.no_grad():d=m.forward_details(x,trace=True)
        torch.testing.assert_close(d.output,x,atol=1e-7,rtol=0);self.assertEqual(d.latent.shape[-2:],(52,68))
        with torch.no_grad():m.prior.head.bias.copy_(torch.tensor([.1,-.1,.1,-.1]));d=m.forward_details(x)
        torch.testing.assert_close(d.output,x,atol=1e-7,rtol=0)
        self.assertGreater(float((d.latent[...,::2,::2]-d.latent[...,::2,1::2]).abs().max()),.01)
    def test_four_phase_heads_and_geometry_have_gradients(self):
        m=build_model({'channels':4,'dilations':[1]});x=.2+.6*torch.rand(1,1,11,15)
        with torch.no_grad():m.prior.head.weight.normal_(0,.03)
        d=m.forward_details(x);loss=d.latent.square().mean()+.01*d.geometry['sdf'].square().mean();loss.backward()
        self.assertTrue(torch.isfinite(m.prior.stem.weight.grad).all())
        self.assertTrue((m.prior.head.weight.grad.flatten(1).norm(dim=1)>0).all())
        self.assertGreater(float(m.geometry_head[-1].weight.grad.norm()),0)
    def test_nonzero_model_tile_phase_and_trace_close(self):
        k=torch.tensor([[0.,.05,.1],[.05,.5,.15],[0.,.1,.05]])
        obs=LinearObservation(k,sampling_factor=4)
        m=build_model({'channels':4,'dilations':[1],'iterations':2},obs).eval();x=.2+.6*torch.rand(1,1,93,101)
        with torch.no_grad():m.prior.head.weight.normal_(0,.02);d=m.forward_details(x,trace=True)
        y=tiled_forward(m,x,core=31,origin=(7,11));torch.testing.assert_close(d.output,y,atol=2e-6,rtol=0)
        for r in d.traces:torch.testing.assert_close(r['state_before']+r['prior_correction']+r['observation_correction']+r['projection_correction'],r['state_after'],atol=2e-7,rtol=0)
        self.assertFalse(d.metadata['calibration_qualified'])
    def test_exact_zero_stable_image_penalty_and_motion_sign(self):
        z=torch.zeros(1,1,5,5,requires_grad=True);loss=robust_gray(z);self.assertEqual(float(loss),0.);loss.backward();self.assertEqual(float(z.grad.abs().max()),0.)
        x=torch.zeros(1,1,17,19);x[...,8,9]=1;y=translated(x,[2,-1]);self.assertAlmostEqual(float(y[...,7,11]),1.,places=5)
    def test_context_bound_max_optics(self):
        k=torch.ones(129,129)/129**2;m=build_model(observation=LinearObservation(k,sampling_factor=4));self.assertEqual(m.required_halo,256)

if __name__=='__main__':unittest.main()
