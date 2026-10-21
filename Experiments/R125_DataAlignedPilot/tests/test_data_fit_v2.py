"""Tests of v2's unchanged gates and changed physical grid contract."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("r125_v2_data_audit_test",ROOT/"scripts/audit_data_fit_v2.py")
audit=importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit)


class DataFitV2Tests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(2)

    def test_unchanged_admission_limits(self):
        self.assertEqual(audit.base.LIMITS["operator_discrepancy_rms_over_declared_sigma"],0.25)
        self.assertEqual(audit.base.LIMITS["operator_discrepancy_p99_over_declared_sigma"],1.0)
        rejected=audit.base.discrepancy_stats(np.full((64,64),0.3),1)
        self.assertFalse(audit.base.model_discrepancy_admissible(rejected))

    def test_exact4x_identity_integration(self):
        profile={"calibration_id":"audit_v2_identity","qualification":"unqualified_diagnostic","kernel_convention":"physical_psf",
                 "sampling_factor":4,"kernel":{"type":"explicit","values":[[1.0]]},"gain":1,"bias":0,"noise_variance":.001}
        rng=np.random.default_rng(1259912)
        latent=rng.random((2,128,128),dtype=np.float32)
        predicted=audit.core_prediction(latent,profile,core=(4,28,4,28))
        expected=audit.base.area_mean(latent,4)[:,4:28,4:28]
        np.testing.assert_allclose(predicted,expected,atol=2e-7,rtol=0)
        wrong=dict(profile,sampling_factor=2)
        with self.assertRaises(ValueError):audit.core_prediction(latent,wrong,core=(4,28,4,28))

    def test_independent8x_kernel_centroid_and_support(self):
        metadata={"rendering_profile":{"sigma_native_xy":[.6,.75],"rotation_rad":.7,"radius_native":4}}
        kernel=audit.independent_kernel(metadata)
        self.assertEqual(kernel.shape,(65,65))
        self.assertAlmostEqual(float(kernel.sum()),1,places=14)
        axis=np.arange(-32,33)/8
        self.assertAlmostEqual(float((kernel*axis[None,:]).sum()),0,places=14)
        self.assertAlmostEqual(float((kernel*axis[:,None]).sum()),0,places=14)

    def test_factor4_adjoint_and_gradient_keep_area_scale(self):
        profile={"calibration_id":"audit_v2_asymmetric","qualification":"unqualified_diagnostic","kernel_convention":"physical_psf",
                 "sampling_factor":4,"kernel":{"type":"explicit","values":[[.01,.03,.09],[.02,.20,.40],[.05,.05,.15]]},"gain":1.4,"bias":.2,"noise_variance":.003}
        observation=audit.base.observation_from_profile(profile).double()
        generator=torch.Generator().manual_seed(1259924)
        x=torch.randn(1,2,32,40,generator=generator,dtype=torch.float64,requires_grad=True)
        y=torch.randn(1,2,8,10,generator=generator,dtype=torch.float64)
        lhs=((observation(x)-observation.bias)*y).sum()
        rhs=(x*observation.adjoint(y)).sum()
        torch.testing.assert_close(lhs,rhs,atol=1e-12,rtol=1e-12)
        objective=.5*((observation(x)-y).square()/observation.noise_variance).sum()
        auto,=torch.autograd.grad(objective,x)
        torch.testing.assert_close(auto,observation.residual_gradient(x,y),atol=1e-12,rtol=1e-12)

    def test_noise_change_and_deleted_hard_scene_cannot_be_hidden(self):
        metadata={"rendering_profile":{"sigma_native_xy":[.6,.75],"rotation_rad":0,"radius_native":4},"profile":{"noise_variance":.001},"noise_sigma_gray":.5}
        self.assertTrue(audit.same_conditions(metadata,metadata)["all_physical_conditions_preserved"])
        changed=dict(metadata,noise_sigma_gray=1.5)
        self.assertFalse(audit.same_conditions(changed,metadata)["all_physical_conditions_preserved"])
        self.assertEqual(audit.HARD_SCENES,(7,13,20,50))


if __name__=="__main__":unittest.main(verbosity=2)
