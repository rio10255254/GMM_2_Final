"""CPU mathematical tests; no real candidate outputs or calibration claims."""
from __future__ import annotations
import copy
import io
import sys
from pathlib import Path
import pytest
import torch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from prototype.factorized_observation import FixedFactorizedObservation, from_observation, KERNEL_L1_TOLERANCE
from model.observation import LinearObservation

torch.set_num_threads(4)


def kernels(dtype=torch.float64):
    generator = torch.Generator().manual_seed(1258801)
    random = torch.rand(7, 7, generator=generator, dtype=torch.float64)
    axis = torch.arange(-8, 9, dtype=torch.float64)
    y, x = torch.meshgrid(axis, axis, indexing="ij")
    theta = .63
    a = (x-.7)*torch.cos(torch.tensor(theta))+(y+.35)*torch.sin(torch.tensor(theta))
    b = -(x-.7)*torch.sin(torch.tensor(theta))+(y+.35)*torch.cos(torch.tensor(theta))
    rotated = torch.exp(-.5*((a/3.1)**2+(b/1.1)**2))
    vectors = torch.tensor([.01, .03, .08, .21, .37, .19, .11], dtype=torch.float64)
    separable = vectors[:, None]*vectors.flip(0)[None, :]
    return {name: (value/value.sum()).to(dtype) for name, value in (("random", random), ("rotated", rotated), ("asymmetric_separable", separable))}


@pytest.mark.parametrize("dtype", [torch.float64, torch.float32])
@pytest.mark.parametrize("name", ["random", "rotated", "asymmetric_separable"])
def test_dense_error_bound_adjoint_gradient_and_descent(dtype, name):
    torch.manual_seed(1258802)
    kernel = kernels(dtype)[name]
    untouched = kernel.clone()
    dense = LinearObservation(kernel, sampling_factor=4, gain=1.3, bias=.17, noise_variance=.7,
                              calibration_id="cpu_diagnostic", qualification="unqualified_diagnostic")
    fact = from_observation(dense, checkpoint_ops=True)
    assert torch.equal(kernel, untouched) and torch.equal(fact.kernel, kernel)
    assert not list(fact.parameters())
    assert fact.measured_kernel_L1_error <= KERNEL_L1_TOLERANCE
    x = torch.randn(2, 2, 20, 24, dtype=dtype, requires_grad=True)
    y = torch.randn(2, 2, 5, 6, dtype=dtype)
    tolerance = 2e-11 if dtype == torch.float64 else 2e-5
    predicted, original = fact(x), dense(x)
    bound = float(dense.gain)*fact.measured_kernel_L1_error*float(x.detach().abs().max())
    assert float((predicted-original).abs().max()) <= bound+tolerance
    transposed, dense_transposed = fact.adjoint(y), dense.adjoint(y)
    adjoint_bound = float(dense.gain)/16*fact.measured_kernel_L1_error*float(y.abs().max())
    assert float((transposed-dense_transposed).abs().max()) <= adjoint_bound+tolerance
    lhs = ((predicted-fact.bias)*y).sum()
    rhs = (x*transposed).sum()
    torch.testing.assert_close(lhs, rhs, atol=tolerance*20, rtol=tolerance)
    objective = .5*((predicted-y)**2/fact.noise_variance).sum()
    automatic, = torch.autograd.grad(objective, x, create_graph=False)
    explicit = fact.residual_gradient(x, y)
    torch.testing.assert_close(automatic, explicit, atol=tolerance, rtol=tolerance)
    dense_gradient = dense.residual_gradient(x, y)
    residual_max = float((original-y).detach().abs().max())
    source_l1 = float(kernel.double().abs().sum())
    actual_l1 = source_l1+fact.measured_kernel_L1_error
    e = fact.measured_kernel_L1_error
    gradient_bound = (float(fact.gain)/16*e*residual_max + float(fact.gain)/16*actual_l1*float(fact.gain)*e*float(x.detach().abs().max()))/float(fact.noise_variance)
    assert float((explicit-dense_gradient).abs().max()) <= gradient_bound+tolerance
    next_x = x.detach()-.9/fact.curvature_bound()*explicit.detach()
    next_loss = .5*((fact(next_x)-y)**2/fact.noise_variance).sum()
    assert float(next_loss) <= float(objective.detach())+tolerance*20
    if dtype == torch.float64:
        direction = torch.randn_like(x)
        eps = 1e-5
        objective_at = lambda point: .5*((fact(point)-y)**2/fact.noise_variance).sum()
        finite_difference = (objective_at(x.detach()+eps*direction)-objective_at(x.detach()-eps*direction))/(2*eps)
        torch.testing.assert_close(finite_difference, (explicit.detach()*direction).sum(), atol=2e-8, rtol=2e-7)


def test_rank_one_centroid_and_no_recentering():
    kernel = kernels()["asymmetric_separable"]
    observation = FixedFactorizedObservation(kernel, sampling_factor=4, checkpoint_ops=False)
    assert observation.rank == 1
    meta = observation.factorization_metadata()
    assert abs(meta["original_centroid_internal_xy"][0]) > .5
    assert max(abs(x) for x in meta["centroid_difference_internal_xy"]) < 1e-12
    assert meta["original_kernel_retained"] and not meta["exact_original_kernel_claimed"]
    impulse = torch.zeros(1, 1, 36, 36, dtype=torch.float64)
    impulse[0, 0, 17, 17] = 1
    dense = LinearObservation(kernel, sampling_factor=4)
    torch.testing.assert_close(observation(impulse), dense(impulse), atol=1e-14, rtol=1e-12)


def test_checkpointing_and_state_roundtrip_preserve_provenance():
    kernel = kernels(torch.float32)["rotated"]
    base = LinearObservation(kernel, sampling_factor=4, gain=.9, bias=-.1, noise_variance=.04,
                             calibration_id="original_identity", qualification="unqualified_diagnostic")
    base.profile = {"qualification": "unqualified_diagnostic", "kernel_origin": "test_only"}
    yes, no = from_observation(base), from_observation(base, checkpoint_ops=False)
    assert yes.get_extra_state()["calibration_id"] == base.get_extra_state()["calibration_id"]
    assert yes.profile == base.profile and yes.profile is not base.profile
    original_kernel = base.kernel.clone()
    torch.manual_seed(1258803)
    x1 = torch.rand(1, 1, 24, 28, requires_grad=True)
    x2 = x1.detach().clone().requires_grad_(True)
    loss1, loss2 = yes(x1).square().sum(), no(x2).square().sum()
    g1, = torch.autograd.grad(loss1, x1)
    g2, = torch.autograd.grad(loss2, x2)
    torch.testing.assert_close(loss1, loss2, atol=0, rtol=0)
    torch.testing.assert_close(g1, g2, atol=0, rtol=0)
    buffer = io.BytesIO()
    torch.save(yes.state_dict(), buffer)
    buffer.seek(0)
    restored = from_observation(base)
    restored.load_state_dict(torch.load(buffer, weights_only=False))
    assert set(yes.state_dict()) == set(restored.state_dict())
    torch.testing.assert_close(restored(x1.detach()), yes(x1.detach()), atol=0, rtol=0)
    assert restored.get_extra_state() == yes.get_extra_state()
    assert torch.equal(original_kernel, base.kernel)
    corrupt = copy.deepcopy(yes.state_dict())
    corrupt["_extra_state"]["factorization"]["kernel_L1_tolerance"] = 1e-3
    with pytest.raises(ValueError, match="rank/tolerance"):
        from_observation(base).load_state_dict(corrupt)


def test_large_rotated_kernel_and_dtype_conversion():
    axis = torch.arange(-64, 65, dtype=torch.float64)
    y, x = torch.meshgrid(axis, axis, indexing="ij")
    a, b = .8*(x-.3)+.6*(y+.4), -.6*(x-.3)+.8*(y+.4)
    kernel = torch.exp(-.5*((a/12)**2+(b/4)**2))
    kernel /= kernel.sum()
    factor = FixedFactorizedObservation(kernel, sampling_factor=4)
    assert factor.rank < 40
    assert factor.measured_kernel_L1_error <= 1e-6
    factor.float()
    assert factor.kernel.dtype == torch.float32
    assert factor.measured_kernel_L1_error <= 1e-6
    assert float(factor.curvature_bound()) > 0


def test_boundary_transpose_and_shape_contracts():
    kernel = kernels()["random"]
    op = FixedFactorizedObservation(kernel, sampling_factor=4, bias=.4)
    x = torch.zeros(1, 1, 8, 12, dtype=torch.float64)
    x[..., 0, 0] = 1
    y = torch.randn(1, 1, 2, 3, dtype=torch.float64)
    torch.testing.assert_close(((op(x)-op.bias)*y).sum(), (x*op.adjoint(y)).sum(), atol=1e-14, rtol=1e-12)
    assert torch.count_nonzero(op.adjoint(torch.zeros_like(y))) == 0
    with pytest.raises(ValueError, match="divisible"):
        op(torch.zeros(1, 1, 9, 12, dtype=torch.float64))
    with pytest.raises(ValueError, match="dtype/device"):
        op(x.float())
    with pytest.raises(ValueError, match="sum to one"):
        FixedFactorizedObservation(kernel*2, sampling_factor=4)
