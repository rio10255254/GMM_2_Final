"""Run the delivered recipe with access to all historical Lab sources denied."""
from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[3]

VALIDATION = Path(__file__).resolve().parent
PACKAGE = VALIDATION / "portable_copy_v2" / "R61_TrainingData_Regenerator_20261004"
HISTORICAL_LAB = Path(str(PROJECT_ROOT / 'LabSystem_MOSR'))
DENIED_ROOT = os.path.normcase(str(HISTORICAL_LAB.resolve()))
denied = []


def prohibit_old_sources(event: str, arguments: tuple) -> None:
    if event not in {"open", "os.listdir", "os.scandir"} or not arguments:
        return
    value = arguments[0]
    if not isinstance(value, (str, bytes, os.PathLike)):
        return
    path = os.path.normcase(os.path.abspath(os.fsdecode(value)))
    if path == DENIED_ROOT or path.startswith(DENIED_ROOT + os.sep):
        denied.append(path)
        raise PermissionError("Historical Lab files are disabled during the portable-package check")


sys.addaudithook(prohibit_old_sources)
self_test_passed = False
try:
    with (HISTORICAL_LAB / "Training_Data/r61_universal_boundary_generalization/hs100mg_basler/r61_universal_boundary_train_motion_texture_step_guard_v16/manifest.json").open("rb"):
        pass
except PermissionError:
    self_test_passed = True
if not self_test_passed:
    raise RuntimeError("Historical source read guard did not work")
denied.clear()

sys.path.insert(0, str(PACKAGE))
sys.argv = [
    str(PACKAGE / "regenerate_r61.py"),
    "--output-root", str(VALIDATION / "generated_v2"),
    "--report", str(VALIDATION / "full_rebuild_check.json"),
]
status = 1
try:
    runpy.run_path(str(PACKAGE / "regenerate_r61.py"), run_name="__main__")
except SystemExit as error:
    status = error.code if isinstance(error.code, int) else 1

report = {
    "status": "pass" if status == 0 and not denied else "fail",
    "clean_python_environment": str(Path(sys.executable).resolve()),
    "package_location": str(PACKAGE),
    "working_directory": str(Path.cwd()),
    "historical_source_guard_self_test": self_test_passed,
    "blocked_historical_reads_during_rebuild": denied,
    "regeneration_exit_code": status,
    "full_rebuild_report": str(VALIDATION / "full_rebuild_check.json"),
}
(VALIDATION / "portability_check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2), flush=True)
raise SystemExit(0 if report["status"] == "pass" else 2)
