"""Freeze exact R79 weights when the protected fine-tune pilot fails its gate."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
DECISION = ROOT / "results" / "pilot_acm_screen" / "decision.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    if bool(decision.get("formal_training_authorized_by_screen")):
        raise RuntimeError("Pilot passed; epoch-zero fallback must not be frozen.")
    source = ROOT / CONFIG["parent_model"]["seed_checkpoint"]
    if sha256(source) != "8aaaa9a85a0a86e77eeb4368bdbc1dd706c8fd9f9654ddd9c6498bd8697f367a":
        raise RuntimeError("R79 exact reset seed hash changed.")
    payload = torch.load(source, map_location="cpu")
    state = payload["state_dict"]
    ema = payload["ema_state_dict"]
    if any(not torch.equal(state[key], ema[key]) for key in state):
        raise RuntimeError("Epoch-zero reset seed is not exact state/EMA parity.")
    selected_dir = ROOT / "weights" / "selected"
    selected_dir.mkdir(parents=True, exist_ok=True)
    destination = selected_dir / "r83_model.pth.tar"
    shutil.copy2(source, destination)
    manifest = {
        "experiment_id": CONFIG["experiment_id"],
        "status": "checkpoint_frozen_pending_reserved_confirmation",
        "selected_method": "R79EpochZero",
        "selected_epoch": 0,
        "fine_tune_promoted_over_r79": False,
        "fine_tune_rejection_reason": "Neither protected four-epoch pilot beat R79 on the locked R74 developmental ACM suite.",
        "source_checkpoint": str(source),
        "source_checkpoint_sha256": sha256(source),
        "frozen_checkpoint": str(destination),
        "frozen_checkpoint_sha256": sha256(destination),
        "state_key": "ema_state_dict",
        "direct_mode_is_exact_r79": True,
        "candidate_system": "exact R79 weights plus the already-frozen QualityModerate safety policy",
        "selection_used_only_developmental_evidence": True,
        "reserved_confirmation_processed": False,
        "frozen_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "safety_policy": CONFIG["frozen_output_safety_policy"],
        "pilot_decision": decision,
    }
    (selected_dir / "selection_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
