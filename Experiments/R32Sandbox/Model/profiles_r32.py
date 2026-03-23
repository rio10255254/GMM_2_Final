from pathlib import Path


SANDBOX_ROOT = Path(__file__).resolve().parents[1]
SHARED_ROOT = Path(__file__).resolve().parents[3]
REAL_EQ_DIR_ABS = str((SHARED_ROOT / "Training_Data" / "generated_convolved" / "Real_Image").resolve())


def build_round32_domain_capacity_probe(r30_seed_ckpt: str, r25_seed_ckpt: str):
    static_annulus_core = (
        "stage_08_annulus_focus",
        "stage_09_annulus_non_overlap",
        "stage_10_annulus_overlap",
        "stage_14_annulus_edge_defect_focus",
        "stage_15_annulus_sparse_clean",
        "stage_16_annulus_sparse_defect_clean",
    )
    mid_primary_dirs = (
        "stage_08_annulus_focus",
        "stage_09_annulus_non_overlap",
        "stage_10_annulus_overlap",
    )
    r32_base_probe = {
        "LOAD_MODEL": True,
        "PRETRAINED_PATH": str(r30_seed_ckpt),
        "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + mid_primary_dirs,
        "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
        "LR": 1.10e-6,
        "W_GRADMAG": 0.70,
        "W_EDGE_ORI_SIMPLE": 0.22,
        "SEQ_LOSS_WEIGHT": 0.045,
        "SEQ_GRAD_WEIGHT": 0.016,
        "SEQ_GEOM_METHOD": "pairmix_algblend",
        "SEQ_MONO_WEIGHT": 0.0,
        "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
        "SEQ_GEOM_THICK_WEIGHT": 0.12,
        "SEQ_ABS_CENTER_WEIGHT": 0.0,
        "SEQ_GEOM_CENTER_WEIGHT": 0.70,
        "SEQ_GEOM_DRIFT_WEIGHT": 0.28,
        "SEQ_SINGLE_ABS_CENTER_WEIGHT": 0.10,
        "SEQ_STEP_MAG_WEIGHT": 0.35,
        "EQ_GEOM_USE_DIRECTION": True,
        "EQ_GEOM_DIR_EDGE_RATIO": 0.5,
        "W_EQ_GEOM": 0.26,
        "EQ_PROB": 0.06,
        "LEARNABLE_BLUR": False,
        "USE_BOTTLENECK_SE": False,
        "GMF_VAL_NUM_FRAMES": 5,
        "PROXY_SEARCH_RADIUS": 8,
        "PROXY_COARSE_STRIDE": 4,
        "PROXY_FINE_STRIDE": 2,
    }
    return [
        {
            "name": "r32_real_eq_finetune",
            "tag": "r32realeq",
            "overrides": {
                **r32_base_probe,
                "REAL_EQ_ENABLE": True,
                "REAL_EQ_DIR": REAL_EQ_DIR_ABS,
                "REAL_EQ_PROB": 0.30,
            },
        },
        {
            "name": "r32_long_from_r25",
            "tag": "r32longr25",
            "overrides": {
                **r32_base_probe,
                "PRETRAINED_PATH": str(r25_seed_ckpt),
                "LR": 2.0e-6,
                "SIMPLETEST_MAX_EPOCH": 40,
                "EQ_WARMUP_OFF_E": 2,
                "EQ_RAMP_START_E": 3,
                "EQ_RAMP_END_E": 15,
            },
        },
        {
            "name": "r32_wider_b1",
            "tag": "r32wide",
            "overrides": {
                **r32_base_probe,
                "MODEL_BASE": 64,
                "LOAD_MODEL": False,
                "LR": 5.0e-5,
                "SIMPLETEST_MAX_EPOCH": 30,
                "EQ_WARMUP_OFF_E": 5,
                "EQ_RAMP_START_E": 6,
                "EQ_RAMP_END_E": 18,
            },
        },
    ]
