"""Run the established displacement audit with Wiener images in the comparison slot."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = PACKAGE_ROOT.parent
CURRENT_PACKAGE = EVIDENCE_ROOT / "01_CURRENT_THESIS_RESULTS_V42_CENTER9"
WIENER_ROOT = PACKAGE_ROOT / "source_validation" / "wiener_baseline_20260715"
AUDIT_SCRIPT_ROOT = CURRENT_PACKAGE / "scripts"

sys.path.insert(0, str(AUDIT_SCRIPT_ROOT))
from audit_all_displacement_sequences import run_unified_audit  # noqa: E402


def main() -> None:
    source_config_path = CURRENT_PACKAGE / "config" / "sequence_center9_50x20x.json"
    config = json.loads(source_config_path.read_text(encoding="utf-8"))
    reconstruction_root = WIENER_ROOT / "reconstructions"
    directories = {
        "50x_x_0p5um": reconstruction_root / "x50x_x_0p5um",
        "50x_x_1um": reconstruction_root / "x50x_x_1um",
        "20x_0p5um": reconstruction_root / "x20x_0p5um",
        "20x_1um": reconstruction_root / "x20x_1um",
    }
    for sequence_name, directory in directories.items():
        expected = int(config["sequences"][sequence_name]["frame_count"])
        actual = len(list(directory.glob("frame_*.bmp")))
        if actual != expected:
            raise RuntimeError(
                f"{sequence_name}: expected {expected} Wiener frames, found {actual}"
            )
        config["sequences"][sequence_name]["v42_dir"] = directory.as_posix()

    config_path = WIENER_ROOT / "wiener_displacement_config.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    output_root = WIENER_ROOT / "displacement_audit"
    outputs = run_unified_audit(
        output_root=output_root,
        candidate_root=output_root / "candidate",
        config_path=config_path,
    )
    print(Path(outputs["pairs"]).resolve())
    print(Path(outputs["candidate"]).resolve())


if __name__ == "__main__":
    main()
