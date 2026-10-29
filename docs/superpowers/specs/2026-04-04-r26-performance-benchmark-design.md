# R26 Performance Benchmark Design Spec

Date: 2026-04-04

## 1. Purpose

Quantify R26 model training and inference performance across different devices. Any machine with the repo + checkpoint + test data can run the benchmark by editing a single config file. Results are stored per-device and can be aggregated for cross-device comparison.

## 2. Directory Structure

```
Analyses/AnalysisLab/r26/performance/
├── README.md                          # Complete usage tutorial (Chinese)
├── scripts/
│   ├── run_inference_benchmark.py     # Inference benchmark
│   ├── run_training_benchmark.py      # Training benchmark
│   └── run_cross_device_compare.py    # Cross-device aggregation (no GPU needed)
├── tests/
│   └── test_performance_benchmark.py  # pytest structure validation
├── configs/
│   └── device_config.py              # Only file to edit per device
├── results/
│   └── <DEVICE_NAME>/               # One subdirectory per device
│       ├── training_benchmark.json
│       ├── inference_benchmark.json
│       └── *.png
│   └── cross_device/                 # Aggregated comparison
│       ├── device_comparison.json
│       └── *.png
└── reports/
    └── R26_Performance_Report.md
```

## 3. device_config.py

Single point of configuration per device:

```python
DEVICE_NAME = "RTX_3090_Main"
CHECKPOINT = r"path/to/best_tradeoff.pth.tar"
PSF_PATH = r"path/to/PSF_fitted_2D_FOVstack.mat"
TEST_INPUT_DIR = r"path/to/Cropped_Output"
TRAINING_SRC_DIR = r"path/to/tra_src_ring"   # or None to use synthetic data
TRAINING_LBL_DIR = r"path/to/tra_lbl_ring"   # or None to use synthetic data

CUDA_DEVICE = 0          # GPU index, None = CPU only
INCLUDE_CPU = True        # Also run CPU baseline

TRAINING_MODE = "quick"   # "quick" (3-5 epochs) or "full"
TRAINING_QUICK_EPOCHS = 3
TRAINING_FULL_EPOCHS = None

WARMUP_RUNS = 5
BENCHMARK_RUNS = 50
BATCH_SIZES = [1]
```

## 4. Inference Benchmark Metrics

| Metric | Description |
|--------|-------------|
| model_load_time_ms | Checkpoint load time |
| first_inference_ms | First inference (incl. JIT warmup) |
| mean_inference_ms | Mean latency after warmup |
| std_inference_ms | Latency std |
| p95_inference_ms | 95th percentile latency |
| throughput_fps | Frames per second |
| gpu_memory_peak_mb | Peak GPU memory |
| cpu_memory_peak_mb | Peak CPU/RAM usage |
| output_hash | SHA256 of output image (for numerical consistency) |
| device_info | GPU name, CUDA version, driver, torch version, OS |

Implementation: import inference script's model loading + `run_one()`, wrap with timing. Use `torch.cuda.Event` for GPU timing, `time.perf_counter` for CPU.

## 5. Training Benchmark Metrics

| Metric | Description |
|--------|-------------|
| epoch_times | Per-epoch wall time (list of seconds) |
| mean_epoch_time_sec | Mean epoch time |
| throughput_samples_per_sec | Training throughput |
| gpu_memory_peak_mb | Peak GPU memory during training |
| total_time_sec | Total training wall time |
| mode | "quick" or "full" |
| epochs_run | Number of epochs actually run |
| device_info | Same as inference |

Implementation: import training script's `TrainConfig` and core training loop, override epoch count, wrap with timing hooks. Do not rewrite training logic.

## 6. Cross-Device Comparison

`run_cross_device_compare.py` reads all `results/*/inference_benchmark.json` and `training_benchmark.json`:

- Produces comparison table (JSON + PNG bar charts)
- Checks `output_hash` consistency across devices, flags differences
- No GPU required; can run on any machine after pulling results

Charts:
- Inference latency comparison (bar chart, one bar per device)
- Training throughput comparison
- GPU memory comparison
- Numerical consistency matrix (hash match/mismatch)

## 7. Cross-Device Workflow

1. Clone repo on new device
2. Edit `configs/device_config.py` (paths + device name)
3. Run `python run_inference_benchmark.py` and/or `run_training_benchmark.py`
4. Results auto-saved to `results/<DEVICE_NAME>/`
5. Commit + push
6. On any machine: pull + run `run_cross_device_compare.py`

## 8. Design Decisions

- **One config file per device**: follows the `sequence/configs/dataset_config.py` pattern
- **Results per device subdirectory**: devices never overwrite each other
- **Import existing scripts, don't rewrite**: training/inference logic stays in `Model/`, benchmark only wraps timing
- **output_hash for consistency**: detects floating-point divergence across devices
- **Quick/full training modes**: quick (3 epochs) for fast comparison, full for convergence verification
- **device_info auto-collected**: torch.cuda.get_device_name(), torch.version, platform.uname() etc.
