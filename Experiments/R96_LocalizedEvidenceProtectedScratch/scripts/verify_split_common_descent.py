"""Verify split gradients and individual private-task protection."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import torch
from torch import nn


ROOT = Path(__file__).resolve().parents[1]


def load_trainer():
    path = ROOT / "training" / "train_r96.py"
    spec = importlib.util.spec_from_file_location("r96_train_verify", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TinyModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.shared = nn.Linear(5, 7)
        self.left = nn.Linear(7, 3)
        self.right = nn.Linear(7, 3)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = torch.tanh(self.shared(x))
        return self.left(features), self.right(features)


def flatten_gradients(model: nn.Module) -> torch.Tensor:
    return torch.cat([
        (torch.zeros_like(parameter) if parameter.grad is None else parameter.grad).reshape(-1)
        for parameter in model.parameters()
    ])


def flatten_tuple(values, parameters) -> torch.Tensor:
    return torch.cat([
        (torch.zeros_like(parameter) if value is None else value).reshape(-1)
        for parameter, value in zip(parameters, values)
    ])


def main() -> int:
    trainer = load_trainer()
    torch.manual_seed(960041)
    model = TinyModel()
    x = torch.randn(11, 5)
    y = torch.randn(11, 3)
    z = torch.randn(11, 3)
    parameters = list(model.parameters())
    left_output, right_output = model(x)
    left_loss = (left_output - y).square().mean()
    right_loss = (right_output - z).square().mean()
    global_loss = (left_output + right_output).abs().mean()
    left_task = trainer.protected_group_gradients(
        left_loss, parameters, list(model.left.parameters()), 1.0, retain_graph=True,
    )
    right_task = trainer.protected_group_gradients(
        right_loss, parameters, list(model.right.parameters()), 1.0, retain_graph=True,
    )
    trainer.backward_common_descent(
        left_loss + right_loss + global_loss,
        [], parameters, 1.0, return_diagnostics=False,
        auxiliary_gradient_prefixes=[left_task, right_task],
    )
    applied = flatten_gradients(model)
    left_flat = flatten_tuple(left_task, parameters)
    right_flat = flatten_tuple(right_task, parameters)
    left_dot = float(torch.dot(applied, left_flat))
    right_dot = float(torch.dot(applied, right_flat))
    private_is_sparse = all(
        value is None for value, parameter in zip(left_task, parameters)
        if id(parameter) not in {id(p) for p in model.left.parameters()}
    )
    passed = left_dot >= -1e-7 and right_dot >= -1e-7 and private_is_sparse
    report = {
        "passed": passed,
        "left_private_task_dot": left_dot,
        "right_private_task_dot": right_dot,
        "private_task_is_sparse": private_is_sparse,
    }
    output = ROOT / "reports" / "protected_update_verification.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
