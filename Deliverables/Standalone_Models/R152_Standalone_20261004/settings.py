"""R152設定：所有預設路徑相對這個資料夾，可直接修改此檔。"""
from pathlib import Path
from copy import deepcopy

ROOT = Path(__file__).resolve().parent
DATA_ROOT = ROOT / "data"
INPUT_ROOT = ROOT / "input"
OUTPUT_ROOT = ROOT / "outputs"
DEFAULT_DEVICE = "auto"
DEFAULT_WEIGHT = ROOT / "weights/r152_deployed.pth"

BASE_MODEL_CONFIG = {'model_name': 'R148v2-HybridContextNativePSF',
 'architecture': 'one_pass_context_unet_features_plus_three_independent_native_boundary_stages',
 'context_channels': [24, 40, 64],
 'context_output_channels': 16,
 'context_gain': 0.05,
 'native_channels': 64,
 'native_dilations': [1, 2, 4, 2],
 'native_stages': 3,
 'r_max': 0.35,
 'eta_max': 0.25,
 'eta_initial': 0.05,
 'checkpoint_blocks': True,
 'output_logit_gain': 0.1,
 'psf_bank': 'calibration/psf25_bank.npz',
 'psf_count': 25,
 'psf_mode': 'single_fixed_input_cue_known_or_mean_training_mean_inference',
 'optical_feature_gain': 0.1,
 'inference_core': 512,
 'inference_halo': 24}

MODEL_CONFIG = {'model_name': 'R152-R148v2-SafeAdaptivePSF',
 'architecture': 'frozen_r148v2_plus_adaptive_fourier_psf_residual',
 'base_checkpoint': 'weights/base_reference.pth',
 'base_checkpoint_sha256': '4661bdfccc9d55c3e3d946ccfbf549d9ae9d8f3b8463ef836e40b2ac7140f88f',
 'base_model_config': {'model_name': 'R148v2-HybridContextNativePSF',
                       'architecture': 'one_pass_context_unet_features_plus_three_independent_native_boundary_stages',
                       'context_channels': [24, 40, 64],
                       'context_output_channels': 16,
                       'context_gain': 0.05,
                       'native_channels': 64,
                       'native_dilations': [1, 2, 4, 2],
                       'native_stages': 3,
                       'r_max': 0.35,
                       'eta_max': 0.25,
                       'eta_initial': 0.05,
                       'checkpoint_blocks': True,
                       'output_logit_gain': 0.1,
                       'psf_bank': 'calibration/psf25_bank.npz',
                       'psf_count': 25,
                       'psf_mode': 'single_fixed_input_cue_known_or_mean_training_mean_inference',
                       'optical_feature_gain': 0.1,
                       'inference_core': 512,
                       'inference_halo': 24},
 'context_output_channels': 16,
 'psf_bank': 'calibration/psf25_bank.npz',
 'psf_count': 25,
 'psf_mode': 'adaptive_all25_fourier_weighted_fusion_bounded_addition_to_frozen_r148v2',
 'selector_temperature': 1.0,
 'selector_hidden_channels': 24,
 'selector_input_channels': 16,
 'selector_input': 'frozen_r148v2_context_plus_radial_spectrum',
 'psf_regularization': 0.03,
 'psf_lowfreq_ratio': 0.25,
 'psf_max_inverse_gain': 2.0,
 'psf_correction_clip': 0.25,
 'psf_beta_min': 0.0025,
 'psf_beta_initial': 0.01,
 'psf_beta_max': 0.03,
 'safe_scale_initial': 0.01,
 'safe_scale_max': 0.25,
 'inference_core': 512,
 'inference_halo': 24}

TRAIN_CONFIG = {'model_seed': 1522101,
 'order_seed': 1482102,
 'noise_seed': 1481003,
 'operator_seed': 1482104,
 'splits': {'train': 512, 'dev': 128, 'test': 128},
 'views_per_parent': 4,
 'updates': 8192,
 'epochs': 16,
 'warmup': 128,
 'save_every': 128,
 'dev_every': 512,
 'optimizer': {'name': 'AdamW',
               'max_lr': 0.0003,
               'min_lr': 3e-06,
               'weight_decay': 1e-05,
               'gradient_clip': 1.0},
 'loss': {'image': 1.0,
          'gradient': 0.2,
          'pair_output': 0.2,
          'boundary': 0.2,
          'observation': 0.01,
          'teacher': 0.2,
          'selector_descriptor': 0.01},
 'known_operator_probability': 0.25,
 'precision': 'FP32',
 'tf32': False,
 'deterministic': True,
 'device': 'auto',
 'supervised_core': [144, 240],
 'observation_core': [160, 224],
 'deployment_scale_candidates': [0.0, 0.25, 0.5, 0.75, 1.0],
 'deployment_guard_relative': 0.005}

BASE_TRAIN_CONFIG = {'model_seed': 1482101,
 'order_seed': 1482102,
 'noise_seed': 1481003,
 'operator_seed': 1482104,
 'splits': {'train': 512, 'dev': 128, 'test': 128},
 'views_per_parent': 4,
 'updates': 8192,
 'epochs': 16,
 'warmup': 128,
 'save_every': 128,
 'dev_every': 512,
 'optimizer': {'name': 'AdamW',
               'max_lr': 0.0003,
               'min_lr': 3e-06,
               'weight_decay': 1e-05,
               'gradient_clip': 1.0},
 'loss': {'image': 1.0, 'gradient': 0.2, 'pair_output': 0.2, 'boundary': 0.2, 'observation': 0.01},
 'stage_weights': [0.25, 0.35, 0.4],
 'known_operator_probability': 0.25,
 'precision': 'FP32',
 'tf32': False,
 'deterministic': True,
 'device': 'auto',
 'train_crop': [0, 384, 0, 384],
 'supervised_core': [144, 240],
 'observation_core': [160, 224]}

def model_config(base_checkpoint=None):
    cfg = deepcopy(MODEL_CONFIG)
    cfg["base_model_config"] = deepcopy(BASE_MODEL_CONFIG)
    if base_checkpoint is not None:
        cfg["base_checkpoint"] = str(base_checkpoint)
    return cfg

def resolve_path(value):
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()
