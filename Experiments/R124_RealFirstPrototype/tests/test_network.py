"""Behavioral checks for the R124 reconstruction prototype.

These use small CPU images and synthetic, explicitly unqualified observation
operators. Passing them establishes executable mechanics, not microscope
calibration or useful learned reconstruction. No model is trained here.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.network import PrototypeConfig, PrototypeModel, build_model
from model.observation import LinearObservation
from inference.tiling import tiled_forward


def observation(blur: bool = False) -> LinearObservation:
    kernel = torch.tensor([[1.0]])
    if blur:
        one = torch.tensor([1.0, 2.0, 1.0])
        kernel = one[:, None] * one[None, :]
        kernel /= kernel.sum()
    return LinearObservation(
        kernel=kernel,
        sampling_factor=2,
        gain=1.0,
        bias=0.0,
        noise_variance=1.0,
        calibration_id="unit_test_synthetic_operator",
        qualification="unqualified_diagnostic",
    )


def model(blur: bool = False, checkpoint: bool = False) -> PrototypeModel:
    return PrototypeModel(
        PrototypeConfig(
            channels=8,
            dilations=(1, 2),
            iterations=4,
            sampling_factor=2,
            checkpoint_blocks=checkpoint,
        ),
        observation=observation(blur),
    )


def activate_prior(network: PrototypeModel) -> None:
    """Leave the initial no-op state to test actual learned update paths."""
    with torch.no_grad():
        torch.nn.init.normal_(network.prior.head.weight, std=0.02)
        if network.prior.head.bias is not None:
            network.prior.head.bias.fill_(0.01)


class NetworkBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        torch.set_num_threads(2)

    def setUp(self) -> None:
        torch.manual_seed(124)

    def test_identity_operator_preserves_small_odd_and_batched_images(self) -> None:
        network = model().eval()
        for shape in [(1, 1, 1, 1), (1, 1, 3, 5), (2, 1, 11, 17)]:
            raw = torch.rand(shape)
            with torch.no_grad():
                details = network.forward_details(raw, trace=True)
                plain = network(raw)
            with self.subTest(shape=shape):
                self.assertEqual(tuple(details.output.shape), shape)
                self.assertEqual(tuple(details.latent.shape), (*shape[:2], shape[2] * 2, shape[3] * 2))
                torch.testing.assert_close(details.output, raw, rtol=0, atol=1e-7)
                torch.testing.assert_close(plain, details.output, rtol=0, atol=0)
                torch.testing.assert_close(network.observation.integrate(details.latent), details.output)
                self.assertEqual(len(details.traces), 4)
                for name in ("boundary_logits", "sdf", "log_scale"):
                    self.assertEqual(tuple(details.geometry[name].shape), shape)
                    self.assertTrue(torch.isfinite(details.geometry[name]).all())

    def test_zero_prior_is_not_a_noop_for_blurred_observation(self) -> None:
        network = model(blur=True).eval()
        # Non-saturated intensities are deliberate: a binary [0, 1] edge can
        # remain a constrained fixed point after the per-step range projection.
        # The contract is that nonidentity optics do not guarantee a no-op,
        # not that every possible image must change.
        raw = torch.full((1, 1, 17, 19), 0.2)
        raw[:, :, 5:12, 6:13] = 0.8
        prior_states = []
        handle = network.prior.register_forward_pre_hook(lambda module, inputs: prior_states.append(inputs[0].detach().clone()))
        with torch.no_grad():
            initial = network.observation.lift(raw)
            initial_loss = (network.observation(initial) - raw).square().sum()
            details = network.forward_details(raw, trace=True)
            final_loss = (network.observation(details.latent) - raw).square().sum()
        handle.remove()
        self.assertGreater((details.output - raw).abs().max().item(), 1e-4)
        self.assertLess(final_loss.item(), initial_loss.item())
        self.assertEqual(len(prior_states), 4, "The same learned prior must be used at all four steps")
        previous_loss = initial_loss.item()
        for index, step in enumerate(details.traces):
            current_loss = (network.observation(step["state_after"]) - raw).square().sum().item()
            with self.subTest(iteration=index):
                self.assertLessEqual(current_loss, previous_loss + 1e-6)
            previous_loss = current_loss

    def test_trace_accounts_for_every_pixel_change(self) -> None:
        network = model(blur=True).eval()
        activate_prior(network)
        raw = torch.rand(1, 1, 13, 15)
        with torch.no_grad():
            details = network.forward_details(raw, trace=True)
        previous = network.observation.lift(raw)
        for index, step in enumerate(details.traces):
            with self.subTest(iteration=index):
                torch.testing.assert_close(step["state_before"], previous)
                torch.testing.assert_close(step["proposal"], previous + step["prior_correction"])
                torch.testing.assert_close(step["observation_at_proposal"], network.observation(step["proposal"]))
                projected = step["proposal"] + step["observation_correction"] + step["projection_correction"]
                torch.testing.assert_close(step["state_after"], projected)
                torch.testing.assert_close(step["native_output"], network.observation.integrate(projected))
                self.assertGreaterEqual(step["state_after"].min().item(), 0)
                self.assertLessEqual(step["state_after"].max().item(), 1)
            previous = step["state_after"]
        torch.testing.assert_close(details.latent, previous, rtol=0, atol=0)
        torch.testing.assert_close(details.output, network.observation.integrate(previous), rtol=0, atol=0)

    def test_zero_residual_does_not_turn_unknown_optics_into_calibration(self) -> None:
        network = model().eval()
        with torch.no_grad():
            details = network.forward_details(torch.full((1, 1, 9, 11), 0.4))
        self.assertFalse(details.metadata["calibration_qualified"])
        self.assertEqual(details.metadata["observation_qualification"], "unqualified_diagnostic")

    def test_direct_operator_label_cannot_bypass_missing_instrument_admission(self) -> None:
        declared_qualified = LinearObservation(
            torch.ones(1, 1), sampling_factor=2,
            calibration_id="unit_test_no_external_evidence",
            qualification="qualified_independent_calibration",
        )
        with self.assertRaises(ValueError):
            PrototypeModel(PrototypeConfig(channels=8, dilations=(1,), iterations=1), declared_qualified)

    def test_shared_prior_nonzero_updates_have_finite_backpropagation(self) -> None:
        network = model(blur=True)
        activate_prior(network)
        raw = torch.rand(1, 1, 13, 15, requires_grad=True)
        target = torch.rand_like(raw)
        output = network(raw)
        ((output - target).square().mean()).backward()
        self.assertIsNotNone(raw.grad)
        self.assertTrue(torch.isfinite(raw.grad).all())
        self.assertGreater(raw.grad.abs().sum().item(), 0)
        prior_parameters = list(network.prior.named_parameters())
        self.assertGreater(len(prior_parameters), 2)
        for name, parameter in prior_parameters:
            with self.subTest(parameter=name):
                self.assertIsNotNone(parameter.grad)
                self.assertTrue(torch.isfinite(parameter.grad).all())
                self.assertGreater(parameter.grad.abs().sum().item(), 0)

    def test_companion_image_cannot_change_an_existing_reconstruction(self) -> None:
        network = model(blur=True).train()
        activate_prior(network)
        raw = torch.rand(1, 1, 13, 15)
        original = raw.clone()
        with torch.no_grad():
            alone = network(raw)
            with_dark = network(torch.cat((raw, torch.zeros_like(raw))))[:1]
            with_bright = network(torch.cat((raw, torch.ones_like(raw))))[:1]
        torch.testing.assert_close(raw, original, rtol=0, atol=0)
        torch.testing.assert_close(alone, with_dark, rtol=2e-6, atol=2e-7)
        torch.testing.assert_close(alone, with_bright, rtol=2e-6, atol=2e-7)

    def test_geometry_is_auxiliary_and_cannot_overwrite_image(self) -> None:
        network = model(blur=True).eval()
        activate_prior(network)
        raw = torch.rand(1, 1, 13, 15)
        with torch.no_grad():
            before = network.forward_details(raw)
            for parameter in network.geometry_head.parameters():
                parameter.add_(torch.randn_like(parameter) * 0.3)
            after = network.forward_details(raw)
        torch.testing.assert_close(before.output, after.output, rtol=0, atol=0)
        torch.testing.assert_close(before.latent, after.latent, rtol=0, atol=0)
        self.assertFalse(torch.equal(before.geometry["boundary_logits"], after.geometry["boundary_logits"]))

    def test_independent_geometry_loss_reaches_reconstruction(self) -> None:
        network = model(blur=True)
        activate_prior(network)
        raw = torch.rand(1, 1, 13, 15, requires_grad=True)
        details = network.forward_details(raw)
        boundary = details.geometry["boundary_logits"]
        sdf = details.geometry["sdf"]
        loss = torch.nn.functional.binary_cross_entropy_with_logits(boundary, torch.rand_like(boundary))
        loss = loss + (sdf - torch.randn_like(sdf)).square().mean()
        loss.backward()
        for group_name, parameters in [("geometry", network.geometry_head.parameters()), ("prior", network.prior.parameters())]:
            gradients = [parameter.grad for parameter in parameters]
            with self.subTest(group=group_name):
                self.assertTrue(all(gradient is not None for gradient in gradients))
                self.assertTrue(all(torch.isfinite(gradient).all() for gradient in gradients))
                self.assertGreater(sum(gradient.abs().sum().item() for gradient in gradients), 0)
        self.assertIsNotNone(raw.grad)
        self.assertGreater(raw.grad.abs().sum().item(), 0)

    def test_checkpoint_recomputation_preserves_outputs_and_gradients(self) -> None:
        plain = model(blur=True, checkpoint=False)
        activate_prior(plain)
        checkpointed = model(blur=True, checkpoint=True)
        checkpointed.load_state_dict(copy.deepcopy(plain.state_dict()))
        raw_plain = torch.rand(1, 1, 13, 15, requires_grad=True)
        raw_checkpoint = raw_plain.detach().clone().requires_grad_(True)
        target = torch.rand_like(raw_plain)
        output_plain = plain(raw_plain)
        output_checkpoint = checkpointed(raw_checkpoint)
        torch.testing.assert_close(output_plain, output_checkpoint, rtol=2e-6, atol=2e-7)
        (output_plain - target).square().mean().backward()
        (output_checkpoint - target).square().mean().backward()
        torch.testing.assert_close(raw_plain.grad, raw_checkpoint.grad, rtol=2e-5, atol=1e-7)
        checkpoint_parameters = dict(checkpointed.named_parameters())
        compared = 0
        for name, parameter in plain.named_parameters():
            other = checkpoint_parameters[name]
            with self.subTest(parameter=name):
                self.assertEqual(parameter.grad is None, other.grad is None)
                if parameter.grad is not None:
                    torch.testing.assert_close(parameter.grad, other.grad, rtol=2e-5, atol=1e-7)
                    compared += 1
        self.assertGreater(compared, 5)

    def test_builder_retains_explicit_operator(self) -> None:
        explicit = observation()
        network = build_model(PrototypeConfig(channels=8, dilations=(1,), iterations=1), explicit)
        self.assertIs(network.observation, explicit)
        with torch.no_grad():
            raw = torch.rand(1, 1, 9, 11)
            torch.testing.assert_close(network(raw), raw, rtol=0, atol=1e-7)

    def test_nonzero_prior_tiles_match_with_changed_grid_on_small_cpu_case(self) -> None:
        network = PrototypeModel(
            PrototypeConfig(channels=8, dilations=(1,), iterations=2),
            observation=observation(blur=True),
        ).eval()
        activate_prior(network)
        raw = torch.rand(1, 1, 57, 61)
        with torch.no_grad():
            whole = network(raw)
        for core, origin in [(17, (0, 0)), (23, (3, 7))]:
            with self.subTest(core=core, origin=origin):
                tiled = tiled_forward(network, raw, core=core, origin=origin)
                torch.testing.assert_close(tiled, whole, rtol=2e-6, atol=2e-7)
        with self.assertRaises(ValueError):
            tiled_forward(network, raw, core=17, halo=network.required_halo - 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
