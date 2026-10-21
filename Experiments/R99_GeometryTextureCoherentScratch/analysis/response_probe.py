from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "R99_scratch_seed990053_20260814_105831"
WEIGHTS = ROOT / "weights" / "formal" / "seed_990053" / RUN_ID / "weights"
OUT = ROOT / "reports" / "deep_dive"
EPOCHS = (24, 40)
SIZE = 256


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def edge_position(profile: np.ndarray) -> float:
    left = float(np.mean(profile[24:72]))
    right = float(np.mean(profile[-72:-24]))
    middle = 0.5 * (left + right)
    index = int(np.argmin(np.abs(profile - middle)))
    if index <= 0 or index >= len(profile) - 1:
        return float(index)
    x0, x1 = index - 1, index + 1
    y0, y1 = float(profile[x0]), float(profile[x1])
    return float(x0 + (middle - y0) * (x1 - x0) / max(abs(y1 - y0), 1e-8) * np.sign(y1 - y0))


def transition_width(profile: np.ndarray) -> float:
    left = float(np.mean(profile[24:72]))
    right = float(np.mean(profile[-72:-24]))
    low, high = min(left, right), max(left, right)
    p10, p90 = low + 0.1 * (high - low), low + 0.9 * (high - low)
    center = len(profile) // 2
    window = profile[center - 48:center + 49]
    x10 = int(np.argmin(np.abs(window - p10))) + center - 48
    x90 = int(np.argmin(np.abs(window - p90))) + center - 48
    return float(abs(x90 - x10))


def run_model(model: torch.nn.Module, arrays: np.ndarray, device: torch.device) -> dict[str, np.ndarray]:
    tensor = torch.from_numpy(arrays).unsqueeze(1).to(device)
    with torch.inference_mode():
        details = model(tensor, return_details=True)
    return {name: value.detach().float().cpu().numpy()[:, 0] for name, value in details.items() if value.shape[1] == 1}


def main() -> int:
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model_module = load_module("r99_response_model", ROOT / "model" / "r99_model.py")
    yy, xx = np.mgrid[:SIZE, :SIZE].astype(np.float32)
    result: dict[str, object] = {}
    plot_payload: dict[int, dict[str, object]] = {}

    for epoch in EPOCHS:
        checkpoint = torch.load(WEIGHTS / f"epoch_{epoch:03d}.pth.tar", map_location="cpu", weights_only=False)
        model = model_module.build_model().to(device).eval()
        model.load_state_dict(checkpoint["ema_state_dict"], strict=True)

        levels = np.linspace(0.05, 0.95, 19, dtype=np.float32)
        uniform = np.stack([np.full((SIZE, SIZE), level, np.float32) for level in levels])
        uniform_details = run_model(model, uniform, device)
        uniform_output = uniform_details["output"][:, 48:-48, 48:-48].mean(axis=(1, 2))
        uniform_low = uniform_details["low_delta"][:, 48:-48, 48:-48].mean(axis=(1, 2))

        frequencies = np.asarray([1, 2, 4, 8, 16, 32, 48, 64], dtype=np.int32)
        amplitude = 0.025
        sine = np.stack([0.5 + amplitude * np.sin(2.0 * np.pi * frequency * xx / SIZE) for frequency in frequencies]).astype(np.float32)
        sine_details = run_model(model, sine, device)
        uniform_half = run_model(model, np.full((1, SIZE, SIZE), 0.5, np.float32), device)["output"][0]
        gains = []
        harmonic_residual = []
        mask = np.s_[48:-48, 48:-48]
        for index, frequency in enumerate(frequencies):
            basis_sin = np.sin(2.0 * np.pi * frequency * xx / SIZE)[mask]
            basis_cos = np.cos(2.0 * np.pi * frequency * xx / SIZE)[mask]
            response = (sine_details["output"][index] - uniform_half)[mask]
            a = 2.0 * float(np.mean(response * basis_sin))
            b = 2.0 * float(np.mean(response * basis_cos))
            fitted = a * basis_sin + b * basis_cos
            gains.append(float(np.hypot(a, b) / amplitude))
            harmonic_residual.append(float(np.sqrt(np.mean((response - fitted) ** 2)) / amplitude))

        step_sigmas = [0.0, 1.0, 2.0, 4.0, 8.0]
        step_inputs = []
        for sigma in step_sigmas:
            image = np.where(xx < SIZE / 2, 0.35, 0.70).astype(np.float32)
            if sigma > 0:
                image = cv2.GaussianBlur(image, (0, 0), sigma)
            step_inputs.append(image)
        step_inputs = np.stack(step_inputs)
        step_details = run_model(model, step_inputs, device)
        step_summary = []
        step_profiles = {}
        for index, sigma in enumerate(step_sigmas):
            raw_profile = step_inputs[index, 64:-64].mean(axis=0)
            output_profile = step_details["output"][index, 64:-64].mean(axis=0)
            raw_contrast = float(np.mean(raw_profile[-72:-24]) - np.mean(raw_profile[24:72]))
            out_contrast = float(np.mean(output_profile[-72:-24]) - np.mean(output_profile[24:72]))
            step_summary.append({
                "sigma": sigma,
                "contrast_gain": out_contrast / max(raw_contrast, 1e-9),
                "raw_width_px": transition_width(raw_profile),
                "output_width_px": transition_width(output_profile),
                "edge_shift_px": edge_position(output_profile) - edge_position(raw_profile),
                "undershoot_gray": max(0.0, float(raw_profile.min() - output_profile.min()) * 255.0),
                "overshoot_gray": max(0.0, float(output_profile.max() - raw_profile.max()) * 255.0),
            })
            if sigma == 4.0:
                step_profiles = {"raw": raw_profile.tolist(), "output": output_profile.tolist()}

        contrasts = [0.05, 0.10, 0.20, 0.35]
        blur_sigmas = [0.0, 2.0, 4.0, 8.0]
        disk_inputs = []
        disk_keys = []
        radius = np.sqrt((xx - SIZE / 2) ** 2 + (yy - SIZE / 2) ** 2)
        for contrast in contrasts:
            for sigma in blur_sigmas:
                image = np.full((SIZE, SIZE), 0.60, np.float32)
                image[radius <= 52] = 0.60 - contrast
                if sigma > 0:
                    image = cv2.GaussianBlur(image, (0, 0), sigma)
                disk_inputs.append(image)
                disk_keys.append((contrast, sigma))
        disk_inputs = np.stack(disk_inputs)
        disk_details = run_model(model, disk_inputs, device)
        disk_summary = []
        for index, (contrast, sigma) in enumerate(disk_keys):
            raw = disk_inputs[index]
            output = disk_details["output"][index]
            foreground = radius < 34
            background = radius > 78
            raw_contrast = float(raw[background].mean() - raw[foreground].mean())
            output_contrast = float(output[background].mean() - output[foreground].mean())
            disk_summary.append({
                "input_contrast": contrast,
                "sigma": sigma,
                "contrast_gain": output_contrast / max(raw_contrast, 1e-9),
                "mean_change_gray": float(np.mean(np.abs(output - raw)) * 255.0),
                "low_branch_mean_abs_gray": float(np.mean(np.abs(disk_details["low_delta"][index])) * 255.0),
                "transport_mean_abs_gray": float(np.mean(np.abs(disk_details["transport_delta"][index])) * 255.0),
                "edge_mean_abs_gray": float(np.mean(np.abs(disk_details["edge_delta"][index])) * 255.0),
                "texture_mean_abs_gray": float(np.mean(np.abs(disk_details["detail_delta"][index])) * 255.0),
            })

        result[str(epoch)] = {
            "uniform_transfer": {"input": levels.tolist(), "output": uniform_output.tolist(), "low_delta": uniform_low.tolist()},
            "frequency_response": {"cycles_per_image": frequencies.tolist(), "gain": gains, "nonlinear_residual_ratio": harmonic_residual},
            "step_response": step_summary,
            "disk_response": disk_summary,
        }
        plot_payload[epoch] = {
            "levels": levels, "uniform_output": uniform_output,
            "frequencies": frequencies, "gains": np.asarray(gains),
            "step_profiles": step_profiles,
            "disk_summary": disk_summary,
        }
        del model
        if device.type == "cuda":
            torch.cuda.empty_cache()

    (OUT / "response_probe.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=160)
    for epoch in EPOCHS:
        payload = plot_payload[epoch]
        axes[0, 0].plot(payload["levels"], payload["uniform_output"], "o-", label=f"E{epoch}")
        axes[0, 1].semilogx(payload["frequencies"], payload["gains"], "o-", base=2, label=f"E{epoch}")
        axes[1, 0].plot(payload["step_profiles"]["output"], label=f"E{epoch}")
        matrix = np.asarray([row["contrast_gain"] for row in payload["disk_summary"]]).reshape(4, 4)
        axes[1, 1].plot([0.05, 0.10, 0.20, 0.35], matrix[:, 2], "o-", label=f"E{epoch}, blur4")
    axes[0, 0].plot([0.05, 0.95], [0.05, 0.95], "k--", label="identity")
    axes[0, 0].set_title("Uniform-gray transfer"); axes[0, 0].set_xlabel("input"); axes[0, 0].set_ylabel("output")
    axes[0, 1].axhline(1.0, color="k", linestyle="--"); axes[0, 1].set_title("Small-signal spatial-frequency gain"); axes[0, 1].set_xlabel("cycles / 256 px")
    raw_profile = plot_payload[24]["step_profiles"]["raw"]
    axes[1, 0].plot(raw_profile, "k--", label="raw blur4"); axes[1, 0].set_xlim(100, 156); axes[1, 0].set_title("Blurred-step response")
    axes[1, 1].axhline(1.0, color="k", linestyle="--"); axes[1, 1].set_title("Dark-disk contrast gain"); axes[1, 1].set_xlabel("input contrast")
    for ax in axes.flat:
        ax.grid(alpha=.3); ax.legend()
    fig.tight_layout(); fig.savefig(OUT / "response_probe.png"); plt.close(fig)

    print(json.dumps({
        "report": str(OUT / "response_probe.json"),
        "figure": str(OUT / "response_probe.png"),
        "uniform_max_deviation": {str(e): float(np.max(np.abs(plot_payload[e]["uniform_output"] - plot_payload[e]["levels"]))) for e in EPOCHS},
        "frequency_gain": {str(e): result[str(e)]["frequency_response"] for e in EPOCHS},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
