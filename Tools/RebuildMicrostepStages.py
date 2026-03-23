import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Training_Data import Data_Simulaion as ds
from Training_Data import PSF_Convolution as pc


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Rebuild microstep stages and their PSF-convolved variants.")
    p.add_argument(
        "--stage-ids",
        type=int,
        nargs="*",
        default=[17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28],
        help="Stage ids to rebuild. Default: 17 18 19 20 21 22",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    stage_ids = [int(x) for x in args.stage_ids]
    print(f"[MICROSTEP] rebuild start stage_ids={stage_ids}")

    stages = ds.select_stages(ds.STAGES, stage_ids)
    print("[MICROSTEP] generating clean stages")
    ds.run_pipeline(stages, base_seed=ds.RUN_BASE_SEED)

    print("[MICROSTEP] loading psfs")
    psfs = pc.load_psfs(pc.PSF_MAT_PATH)

    print("[MICROSTEP] generating convolved stages")
    pc.run(pc.INPUT_ROOT, pc.OUTPUT_ROOT, psfs, noise_seed=pc.RUN_NOISE_SEED, stage_ids=stage_ids)

    print("[MICROSTEP] rebuild completed")


if __name__ == "__main__":
    os.chdir(str(REPO_ROOT))
    main()
