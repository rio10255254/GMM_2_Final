from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _safe_float(v: Any, default: float = float("nan")) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_estimator_policy(path: Path) -> dict:
    return _load_json(path)


def get_formal_baseline(policy: Mapping[str, Any]) -> dict:
    return dict(policy["formal_baseline"])


def get_measurement_guardrails(policy: Mapping[str, Any]) -> dict:
    return dict(policy["measurement_policy"]["guardrails"])


def get_legacy_sources(policy: Mapping[str, Any]) -> dict:
    return dict(policy["sources"]["legacy"])


def get_macro_estimator(policy: Mapping[str, Any], default: str = "edge_band_refine") -> str:
    baseline = get_formal_baseline(policy)
    estimators = baseline.get("estimators", {})
    return str(estimators.get("macro_8px", default))


def resolve_control_center_ref(policy: Mapping[str, Any], default: float = 1.0) -> float:
    sources = get_legacy_sources(policy)
    reevaluation_json = str(PROJECT_ROOT / sources.get("phase2_reevaluation_json"))
    if reevaluation_json:
        try:
            reevaluation = _load_json(Path(str(reevaluation_json)))
            return _safe_float(reevaluation.get("control_0p8", {}).get("best_center_err"), default)
        except Exception:
            pass

    round26_decision_md = str(PROJECT_ROOT / sources.get("round26_decision_md"))
    if round26_decision_md:
        round26_decision_json = Path(str(round26_decision_md)).with_suffix(".json")
        try:
            decision_payload = _load_json(round26_decision_json)
            return _safe_float(decision_payload.get("control_center_ref"), default)
        except Exception:
            pass

    return default


def load_probe_policy_pack(path: Path) -> dict:
    policy = load_estimator_policy(path)
    guardrails = get_measurement_guardrails(policy)
    return {
        "policy": policy,
        "mid_center_ratio_min": _safe_float(guardrails["mid_0p8"]["center_improvement_ratio_min"], 0.25),
        "mid_step_max": _safe_float(guardrails["mid_0p8"]["step_err_max"], 0.45),
        "macro_step_max": _safe_float(guardrails["macro_8px"]["step_err_max"], 0.30),
        "macro_seq_sign_min": _safe_float(guardrails["macro_8px"]["seq_sign_acc_min"], 0.75),
        "macro_estimator": get_macro_estimator(policy),
        "control_center_ref": resolve_control_center_ref(policy),
    }
