"""
GeoEdge R26 Cross-Device Performance Comparison
================================================
Reads benchmark results from all devices under results/ and produces
comparison tables, charts, and a numerical consistency report.

This script does NOT require a GPU — it only reads JSON files and produces
charts. Run it on any machine after collecting results from multiple devices.

Usage:
    python AnalysisLab/r26/performance/scripts/run_cross_device_compare.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PERF_ROOT = SCRIPT_DIR.parent
RESULTS_ROOT = PERF_ROOT / "results"
CROSS_DIR = RESULTS_ROOT / "cross_device"


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def load_all_results() -> dict[str, dict]:
    """Load all device results into a unified dict."""
    devices: dict[str, dict] = {}
    for device_dir in sorted(RESULTS_ROOT.iterdir()):
        if not device_dir.is_dir() or device_dir.name == "cross_device":
            continue
        entry: dict = {"name": device_dir.name}
        infer_path = device_dir / "inference_benchmark.json"
        train_path = device_dir / "training_benchmark.json"
        if infer_path.exists():
            with open(infer_path, "r", encoding="utf-8") as f:
                entry["inference"] = json.load(f)
        if train_path.exists():
            with open(train_path, "r", encoding="utf-8") as f:
                entry["training"] = json.load(f)
        if "inference" in entry or "training" in entry:
            devices[device_dir.name] = entry
    return devices


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------

def extract_inference_summary(devices: dict) -> list[dict]:
    """Extract key inference metrics across devices for comparison."""
    rows = []
    for name, data in devices.items():
        infer = data.get("inference", {})
        for dev_key, result in infer.items():
            row = {
                "device_config_name": name,
                "torch_device": dev_key,
                "gpu_name": result.get("device_info", {}).get("gpu_name", "CPU"),
                "model_load_time_ms": result.get("model_load_time_ms"),
                "mean_inference_ms": result.get("mean_inference_ms"),
                "std_inference_ms": result.get("std_inference_ms"),
                "p95_inference_ms": result.get("p95_inference_ms"),
                "throughput_fps": result.get("throughput_fps"),
                "gpu_memory_peak_mb": result.get("gpu_memory_peak_mb"),
                "output_hash": result.get("output_hash"),
            }
            rows.append(row)
    return rows


def extract_training_summary(devices: dict) -> list[dict]:
    """Extract key training metrics across devices."""
    rows = []
    for name, data in devices.items():
        train = data.get("training", {})
        for dev_key, result in train.items():
            row = {
                "device_config_name": name,
                "torch_device": dev_key,
                "gpu_name": result.get("device_info", {}).get("gpu_name", "CPU"),
                "mode": result.get("mode"),
                "epochs_run": result.get("epochs_run"),
                "mean_epoch_time_sec": result.get("mean_epoch_time_sec"),
                "throughput_samples_per_sec": result.get("throughput_samples_per_sec"),
                "gpu_memory_peak_mb": result.get("gpu_memory_peak_mb"),
                "total_time_sec": result.get("total_time_sec"),
            }
            rows.append(row)
    return rows


def check_numerical_consistency(infer_rows: list[dict]) -> dict:
    """Check if output hashes match across devices."""
    hashes: dict[str, list[str]] = {}
    for row in infer_rows:
        h = row.get("output_hash")
        if h is not None:
            label = f"{row['device_config_name']}:{row['torch_device']}"
            hashes.setdefault(h, []).append(label)

    unique_hashes = list(hashes.keys())
    all_match = len(unique_hashes) <= 1
    return {
        "all_match": all_match,
        "num_unique_hashes": len(unique_hashes),
        "hash_groups": {h: devs for h, devs in hashes.items()},
        "note": (
            "All devices produce identical output."
            if all_match
            else "WARNING: Different devices produce numerically different outputs. "
                 "This may be due to floating-point differences across GPU architectures."
        ),
    }


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def plot_inference_latency(infer_rows: list[dict], out_dir: Path):
    """Bar chart comparing inference latency across devices."""
    if not infer_rows:
        return
    labels = [f"{r['device_config_name']}\n({r['torch_device']})" for r in infer_rows]
    means = [r["mean_inference_ms"] or 0 for r in infer_rows]
    stds = [r["std_inference_ms"] or 0 for r in infer_rows]

    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.5), 5))
    x = np.arange(len(labels))
    bars = ax.bar(x, means, yerr=stds, capsize=5, color="steelblue", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Inference Latency (ms)")
    ax.set_title("Cross-Device Inference Latency Comparison")
    for bar, val in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f"{val:.1f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_dir / "01_inference_latency_comparison.png", dpi=150)
    plt.close(fig)


def plot_inference_throughput(infer_rows: list[dict], out_dir: Path):
    """Bar chart comparing inference throughput (FPS)."""
    if not infer_rows:
        return
    labels = [f"{r['device_config_name']}\n({r['torch_device']})" for r in infer_rows]
    fps = [r["throughput_fps"] or 0 for r in infer_rows]

    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.5), 5))
    x = np.arange(len(labels))
    bars = ax.bar(x, fps, color="crimson", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Throughput (FPS)")
    ax.set_title("Cross-Device Inference Throughput Comparison")
    for bar, val in zip(bars, fps):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f"{val:.1f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_dir / "02_inference_throughput_comparison.png", dpi=150)
    plt.close(fig)


def plot_training_throughput(train_rows: list[dict], out_dir: Path):
    """Bar chart comparing training throughput (samples/sec)."""
    if not train_rows:
        return
    labels = [f"{r['device_config_name']}\n({r['torch_device']})" for r in train_rows]
    throughput = [r["throughput_samples_per_sec"] or 0 for r in train_rows]

    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 1.5), 5))
    x = np.arange(len(labels))
    bars = ax.bar(x, throughput, color="forestgreen", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Throughput (samples/sec)")
    ax.set_title("Cross-Device Training Throughput Comparison")
    for bar, val in zip(bars, throughput):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f"{val:.1f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_dir / "03_training_throughput_comparison.png", dpi=150)
    plt.close(fig)


def plot_gpu_memory(infer_rows: list[dict], train_rows: list[dict], out_dir: Path):
    """Grouped bar chart comparing GPU memory usage."""
    # Only include GPU entries
    gpu_infer = [r for r in infer_rows if r.get("gpu_memory_peak_mb") is not None]
    gpu_train = [r for r in train_rows if r.get("gpu_memory_peak_mb") is not None]
    if not gpu_infer and not gpu_train:
        return

    # Merge device labels
    all_labels = []
    infer_mem = {}
    train_mem = {}
    for r in gpu_infer:
        label = f"{r['device_config_name']}\n({r['gpu_name']})"
        all_labels.append(label)
        infer_mem[label] = r["gpu_memory_peak_mb"]
    for r in gpu_train:
        label = f"{r['device_config_name']}\n({r['gpu_name']})"
        if label not in all_labels:
            all_labels.append(label)
        train_mem[label] = r["gpu_memory_peak_mb"]

    x = np.arange(len(all_labels))
    width = 0.35
    fig, ax = plt.subplots(figsize=(max(6, len(all_labels) * 2), 5))

    infer_vals = [infer_mem.get(l, 0) for l in all_labels]
    train_vals = [train_mem.get(l, 0) for l in all_labels]

    if any(v > 0 for v in infer_vals):
        ax.bar(x - width/2, infer_vals, width, label="Inference", color="steelblue", alpha=0.85)
    if any(v > 0 for v in train_vals):
        ax.bar(x + width/2, train_vals, width, label="Training", color="forestgreen", alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(all_labels, fontsize=9)
    ax.set_ylabel("Peak GPU Memory (MB)")
    ax.set_title("Cross-Device GPU Memory Usage")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "04_gpu_memory_comparison.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    devices = load_all_results()
    if not devices:
        print("No benchmark results found under results/.")
        print("Run inference and/or training benchmarks first on at least one device.")
        sys.exit(0)

    print(f"Found results for {len(devices)} device(s): {', '.join(devices.keys())}")

    infer_rows = extract_inference_summary(devices)
    train_rows = extract_training_summary(devices)
    consistency = check_numerical_consistency(infer_rows)

    # Print summary table
    if infer_rows:
        print(f"\n{'='*70}")
        print("  Inference Comparison")
        print(f"{'='*70}")
        print(f"  {'Device':<25} {'Mean(ms)':>10} {'P95(ms)':>10} {'FPS':>10} {'GPU Mem':>10}")
        print(f"  {'-'*25} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
        for r in infer_rows:
            gpu = f"{r['gpu_memory_peak_mb']} MB" if r['gpu_memory_peak_mb'] else "N/A"
            dev_label = f"{r['device_config_name']}:{r['torch_device']}"
            print(f"  {dev_label:<25} {r['mean_inference_ms'] or 0:>10.1f} "
                  f"{r['p95_inference_ms'] or 0:>10.1f} "
                  f"{r['throughput_fps'] or 0:>10.1f} {gpu:>10}")

    if train_rows:
        print(f"\n{'='*70}")
        print("  Training Comparison")
        print(f"{'='*70}")
        print(f"  {'Device':<25} {'Epoch(s)':>10} {'Samples/s':>12} {'GPU Mem':>10}")
        print(f"  {'-'*25} {'-'*10} {'-'*12} {'-'*10}")
        for r in train_rows:
            gpu = f"{r['gpu_memory_peak_mb']} MB" if r['gpu_memory_peak_mb'] else "N/A"
            dev_label = f"{r['device_config_name']}:{r['torch_device']}"
            print(f"  {dev_label:<25} {r['mean_epoch_time_sec'] or 0:>10.1f} "
                  f"{r['throughput_samples_per_sec'] or 0:>12.1f} {gpu:>10}")

    print(f"\n  Numerical consistency: {consistency['note']}")

    # Save
    CROSS_DIR.mkdir(parents=True, exist_ok=True)

    comparison = {
        "num_devices": len(devices),
        "device_names": list(devices.keys()),
        "inference": infer_rows,
        "training": train_rows,
        "numerical_consistency": consistency,
    }
    out_path = CROSS_DIR / "device_comparison.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)
    print(f"\n  Comparison JSON: {out_path}")

    # Charts
    plot_inference_latency(infer_rows, CROSS_DIR)
    plot_inference_throughput(infer_rows, CROSS_DIR)
    plot_training_throughput(train_rows, CROSS_DIR)
    plot_gpu_memory(infer_rows, train_rows, CROSS_DIR)
    print(f"  Charts saved to: {CROSS_DIR}")


if __name__ == "__main__":
    main()
