"""Measure real R94 causal-target preparation throughput before formal launch."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", type=int, default=8)
    parser.add_argument("--patch", type=int, default=512)
    parser.add_argument("--core", type=int, default=256)
    args = parser.parse_args()
    design = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))
    package = Path(PROJECT_ROOT / design["data"]["source_package"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    module = load("r94_loader_benchmark_data", ROOT / "training" / "r94_dataset.py")
    dataset = module.R94SceneDataset(package, manifest, "train", args.patch, args.core, 1)
    rows = []
    for index in range(min(args.items, len(dataset))):
        started = time.perf_counter()
        item = dataset[index]
        rows.append({"index": index, "role": item["role"], "seconds": time.perf_counter() - started})
    report = {
        "patch": args.patch, "items": len(rows), "rows": rows,
        "mean_seconds": sum(row["seconds"] for row in rows) / max(len(rows), 1),
        "maximum_seconds": max((row["seconds"] for row in rows), default=0.0),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
