"""Independent checks of the fixed acquisition operator's numerical contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

import numpy as np
import torch


_SOURCE = Path(__file__).resolve().parents[1] / "model" / "observation.py"
_SPEC = importlib.util.spec_from_file_location("r124_observation_under_test", _SOURCE)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MODULE)
LinearObservation = _MODULE.LinearObservation


def kernel(dtype=torch.float64):
    return torch.tensor([[0.01, 0.03, 0.09], [0.02, 0.20, 0.40], [0.05, 0.05, 0.15]], dtype=dtype)


def manual_forward(x, coefficients, factor, gain, bias):
    """Explicit scalar loops, independent of torch convolution/pooling."""
    out = np.zeros_like(x)
    height, width = x.shape
    radius = coefficients.shape[0] // 2
    for row in range(height):
        for col in range(width):
            for ky in range(coefficients.shape[0]):
                for kx in range(coefficients.shape[1]):
                    iy, ix = row + ky - radius, col + kx - radius
                    if 0 <= iy < height and 0 <= ix < width:
                        out[row, col] += coefficients[ky, kx] * x[iy, ix]
    native = np.zeros((height // factor, width // factor), dtype=x.dtype)
    for row in range(native.shape[0]):
        for col in range(native.shape[1]):
            native[row, col] = gain * out[row * factor:(row + 1) * factor, col * factor:(col + 1) * factor].sum() / factor**2 + bias
    return native


class ObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def setUp(self):
        self.generator = torch.Generator().manual_seed(124010)

    def random(self, shape, dtype=torch.float64):
        return torch.randn(shape, generator=self.generator, dtype=dtype)

    def test_asymmetric_impulse_centroid_and_sign_are_preserved(self):
        coefficients = kernel()
        observation = LinearObservation(coefficients, sampling_factor=1, calibration_id="asymmetric_test")
        image = torch.zeros(1, 1, 21, 21, dtype=torch.float64)
        image[0, 0, 10, 10] = 1
        result = observation(image)[0, 0]
        yy, xx = torch.meshgrid(torch.arange(21, dtype=torch.float64) - 10, torch.arange(21, dtype=torch.float64) - 10, indexing="ij")
        measured = torch.stack(((result * xx).sum(), (result * yy).sum())) / result.sum()
        self.assertTrue(torch.equal(observation.kernel, coefficients))
        torch.testing.assert_close(measured, -observation.kernel_centroid_internal_xy, atol=1e-14, rtol=1e-14)
        torch.testing.assert_close(measured, observation.impulse_centroid_internal_xy, atol=1e-14, rtol=1e-14)
        self.assertLess(float(measured[0]), 0)
        self.assertLess(float(measured[1]), 0)
        self.assertAlmostEqual(float(result.sum()), 1.0, places=14)

    def test_forward_matches_manual_zero_boundary_and_area_integration(self):
        observation = LinearObservation(kernel(), gain=1.7, bias=-0.13)
        image = self.random((1, 1, 10, 14))
        expected = manual_forward(image[0, 0].numpy(), kernel().numpy(), 2, 1.7, -0.13)
        np.testing.assert_allclose(observation(image)[0, 0].numpy(), expected, atol=2e-15, rtol=2e-15)
        # Including the actual field edges is essential: a circular or reflected
        # convolution may agree in the interior but is a different operator.
        constant = torch.ones_like(image)
        self.assertLess(float(observation(constant)[0, 0, 0, 0]), 1.7 - 0.13)

    def test_linear_adjoint_inner_product_multichannel(self):
        for factor in (1, 2, 3):
            observation = LinearObservation(kernel(), sampling_factor=factor, gain=1.7, bias=0.37)
            x = self.random((2, 3, 8 * factor, 11 * factor))
            y = self.random((2, 3, 8, 11))
            left = ((observation(x) - observation.bias) * y).sum()
            right = (x * observation.adjoint(y)).sum()
            torch.testing.assert_close(left, right, atol=2e-13, rtol=2e-13)

    def test_cell_average_initialization_and_transpose_are_distinct(self):
        observation = LinearObservation(torch.ones((1, 1), dtype=torch.float64))
        y = self.random((2, 2, 7, 9))
        torch.testing.assert_close(observation.integrate(observation.lift(y)), y, atol=0, rtol=0)
        torch.testing.assert_close(observation(observation.lift(y)), y, atol=0, rtol=0)
        torch.testing.assert_close(observation.adjoint(y), observation.lift(y) / 4, atol=0, rtol=0)
        self.assertFalse(torch.equal(observation.adjoint(y), observation.lift(y)))

    def test_gradient_matches_autograd_and_finite_difference(self):
        observation = LinearObservation(kernel(), gain=1.43, bias=-0.31, noise_variance=0.27)
        x = self.random((1, 2, 12, 14)).requires_grad_()
        y = self.random((1, 2, 6, 7))
        objective = 0.5 * ((observation(x) - y).square() / observation.noise_variance).sum()
        automatic, = torch.autograd.grad(objective, x)
        explicit = observation.residual_gradient(x, y)
        torch.testing.assert_close(explicit, automatic, atol=2e-14, rtol=2e-14)
        direction = self.random(x.shape)
        direction = direction / direction.norm()
        def energy(z):
            return 0.5 * ((observation(z) - y).square() / observation.noise_variance).sum()
        epsilon = 1e-5
        finite_difference = (energy(x + epsilon * direction) - energy(x - epsilon * direction)) / (2 * epsilon)
        predicted = (explicit * direction).sum()
        torch.testing.assert_close(finite_difference, predicted, atol=2e-8, rtol=2e-8)

    def test_curvature_bound_exceeds_independent_dense_hessian(self):
        height, width, factor = 8, 10, 2
        gain, variance = 2.3, 0.17
        observation = LinearObservation(kernel(), gain=gain, noise_variance=variance)
        columns = []
        for index in range(height * width):
            basis = np.zeros((height, width), dtype=np.float64)
            basis.flat[index] = 1
            columns.append(manual_forward(basis, kernel().numpy(), factor, gain, 0).ravel())
        matrix = np.stack(columns, axis=1)
        exact = float(np.linalg.eigvalsh(matrix.T @ matrix / variance)[-1])
        upper = float(observation.curvature_bound())
        self.assertGreaterEqual(upper, exact)
        self.assertLess(upper, gain**2 / (factor**2 * variance) * (1 + 1e-12))
        # This checks the pooling factor in the bound, not only a loose bound
        # from convolution alone.
        self.assertLess(upper, gain**2 / variance / 3.9)

    def test_bounded_gradient_steps_reduce_quadratic_in_float32_and_float64(self):
        for dtype in (torch.float32, torch.float64):
            for gain, variance in ((0.2, 2.7), (1.0, 1.0), (4.3, 0.003)):
                observation = LinearObservation(kernel(dtype), gain=gain, bias=0.7, noise_variance=variance)
                x = self.random((2, 2, 16, 18), dtype=dtype)
                y = self.random((2, 2, 8, 9), dtype=dtype)
                energy_before = ((observation(x) - y).square() / observation.noise_variance).sum()
                next_x = x - 1.9 / observation.curvature_bound() * observation.residual_gradient(x, y)
                energy_after = ((observation(next_x) - y).square() / observation.noise_variance).sum()
                self.assertLess(float(energy_after), float(energy_before))

    def test_calibration_is_nontrainable_and_provenance_survives_state(self):
        observation = LinearObservation(kernel(), calibration_id="fixture_asymmetric_001", qualification="unqualified_diagnostic")
        self.assertEqual(list(observation.parameters()), [])
        self.assertEqual(set(dict(observation.named_buffers())), {"kernel", "gain", "bias", "noise_variance"})
        restored = LinearObservation(torch.full((3, 3), 1 / 9, dtype=torch.float64))
        restored.load_state_dict(observation.state_dict())
        self.assertEqual(restored.calibration_id, "fixture_asymmetric_001")
        self.assertEqual(restored.qualification, "unqualified_diagnostic")
        torch.testing.assert_close(restored.kernel, observation.kernel, atol=0, rtol=0)
        with self.assertRaises(ValueError):
            LinearObservation(kernel(), sampling_factor=1).load_state_dict(observation.state_dict())

    def test_rejects_invalid_kernels(self):
        invalid = [
            torch.ones((2, 2), dtype=torch.float64),
            torch.ones((3, 5), dtype=torch.float64),
            torch.ones((1, 1, 1), dtype=torch.float64),
            torch.ones((0, 0), dtype=torch.float64),
            torch.ones((1, 1), dtype=torch.int64),
            torch.tensor([[float("nan")]], dtype=torch.float64),
            torch.tensor([[float("inf")]], dtype=torch.float64),
            torch.tensor([[-1.0]], dtype=torch.float64),
            torch.zeros((3, 3), dtype=torch.float64),
            kernel() * 1.01,
            torch.ones((67, 67), dtype=torch.float64) / 67**2,
        ]
        for value in invalid:
            with self.subTest(shape=tuple(value.shape), dtype=value.dtype):
                with self.assertRaises(ValueError):
                    LinearObservation(value)
        allowed = torch.ones((65, 65), dtype=torch.float64) / 65**2
        self.assertEqual(LinearObservation(allowed).kernel_radius_internal, 32)

    def test_rejects_invalid_calibration_and_factor(self):
        for name in ("gain", "noise_variance"):
            for value in (0, -1, float("inf"), float("nan"), True, torch.tensor([1.0, 2.0])):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(ValueError):
                        LinearObservation(kernel(), **{name: value})
        for name in ("calibration_id", "qualification"):
            with self.assertRaises(ValueError):
                LinearObservation(kernel(), **{name: " "})
        for factor in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                LinearObservation(kernel(), sampling_factor=factor)
        with self.assertRaises(ValueError):
            LinearObservation(kernel(), bias=float("nan"))
        with self.assertRaises(ValueError):
            LinearObservation(kernel(torch.float32), noise_variance=1e-90)

    def test_rejects_silent_crop_broadcasting_and_dtype_mismatch(self):
        observation = LinearObservation(kernel())
        for shape in ((1, 1, 11, 14), (1, 1, 12, 13)):
            with self.assertRaisesRegex(ValueError, "divisible"):
                observation(self.random(shape))
            with self.assertRaisesRegex(ValueError, "divisible"):
                observation.integrate(self.random(shape))
        with self.assertRaisesRegex(ValueError, "broadcasting"):
            observation.residual_gradient(self.random((2, 1, 12, 14)), self.random((1, 1, 6, 7)))
        with self.assertRaisesRegex(ValueError, "dtype/device"):
            observation(self.random((1, 1, 12, 14), dtype=torch.float32))
        with self.assertRaisesRegex(ValueError, "NCHW"):
            observation(self.random((12, 14)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
