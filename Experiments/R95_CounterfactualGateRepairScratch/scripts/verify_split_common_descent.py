"""Prove that split objective graphs preserve R95's common-descent update."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import torch
from torch import nn


ROOT = Path(__file__).resolve().parents[1]


def load_trainer():
    path = ROOT / "training" / "train_r95.py"
    spec = importlib.util.spec_from_file_location("r95_train_verify", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TinyModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.a = nn.Linear(5, 7)
        self.b = nn.Linear(7, 3)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.b(torch.tanh(self.a(x)))


def gradients(model: nn.Module) -> torch.Tensor:
    return torch.cat([parameter.grad.reshape(-1) for parameter in model.parameters()])


def main() -> int:
    trainer = load_trainer()
    torch.manual_seed(950041)
    reference = TinyModel()
    split = TinyModel()
    split.load_state_dict(reference.state_dict())
    x = torch.randn(11, 5)
    y = torch.randn(11, 3)
    z = torch.randn(11, 3)
    divisor = 4.0

    output = reference(x)
    primary = (output - y).square().mean() + 0.3 * output.abs().mean()
    auxiliary = (output - z).abs().mean()
    independent = reference(x * 0.7 + 0.1).square().mean()
    independent_auxiliary = reference(x * -0.4 + 0.2).abs().mean()
    trainer.backward_common_descent(
        primary + 0.55 * independent,
        [0.25 * auxiliary, 0.15 * independent_auxiliary],
        list(reference.parameters()),
        divisor,
        return_diagnostics=False,
    )

    independent_split = split(x * 0.7 + 0.1).square().mean()
    prefix = trainer.detached_objective_gradients(
        0.55 * independent_split,
        list(split.parameters()),
        divisor,
    )
    independent_auxiliary_split = split(x * -0.4 + 0.2).abs().mean()
    auxiliary_prefix = trainer.detached_objective_gradients(
        0.15 * independent_auxiliary_split,
        list(split.parameters()),
        divisor,
    )
    output_split = split(x)
    primary_split = (output_split - y).square().mean() + 0.3 * output_split.abs().mean()
    auxiliary_split = (output_split - z).abs().mean()
    trainer.backward_common_descent(
        primary_split,
        [0.25 * auxiliary_split],
        list(split.parameters()),
        divisor,
        return_diagnostics=False,
        primary_gradient_prefix=prefix,
        auxiliary_gradient_prefixes=[auxiliary_prefix],
    )

    delta = (gradients(reference) - gradients(split)).abs()
    max_abs = float(delta.max())
    mean_abs = float(delta.mean())
    passed = max_abs <= 2e-7
    print({"passed": passed, "max_abs": max_abs, "mean_abs": mean_abs})
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
