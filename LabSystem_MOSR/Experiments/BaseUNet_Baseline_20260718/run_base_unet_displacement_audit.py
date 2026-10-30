from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]


EXPERIMENT = Path(__file__).resolve().parent
EVIDENCE = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures'))
CURRENT = EVIDENCE / "01_CURRENT_THESIS_RESULTS_V42_CENTER9"
SCRIPT_ROOT = CURRENT / "scripts"
DEFAULT_RESULTS_ROOT = EXPERIMENT / "results"

sys.path.insert(0, str(SCRIPT_ROOT))
from audit_all_displacement_sequences import run_unified_audit  # noqa: E402


def main(results_root: Path) -> None:
    reconstruction_root = results_root / "real_inference" / "sequences"
    output_root = results_root / "displacement_audit"
    source_config_path = CURRENT / "config" / "sequence_center9_50x20x.json"
    config = json.loads(source_config_path.read_text(encoding="utf-8"))
    for sequence_name, sequence in config["sequences"].items():
        directory = reconstruction_root / sequence_name
        expected = int(sequence["frame_count"])
        actual = len(list(directory.glob("frame_*.bmp")))
        if actual != expected:
            raise RuntimeError(
                f"{sequence_name}: expected {expected} Base U-Net frames, found {actual}"
            )
        sequence["v42_dir"] = directory.as_posix()

    config["comparison_method"] = "Base U-Net"
    config_path = results_root / "base_unet_displacement_config.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    outputs = run_unified_audit(
        output_root=output_root,
        candidate_root=output_root / "candidate",
        config_path=config_path,
    )
    print(json.dumps({key: str(Path(value).resolve()) for key, value in outputs.items()}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT)
    arguments = parser.parse_args()
    main(arguments.results_root.resolve())
