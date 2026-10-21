import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN_JSON = ROOT / "R114_MASTER_PLAN.json"
PLAN_MD = ROOT / "R114_MASTER_PLAN_ZH.md"
OUTPUT = ROOT / "results" / "r114_plan_validation.json"


def check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> None:
    failures: list[str] = []
    check(PLAN_JSON.is_file(), "missing machine-readable plan", failures)
    check(PLAN_MD.is_file(), "missing Chinese master plan", failures)

    plan = json.loads(PLAN_JSON.read_text(encoding="utf-8"))
    markdown = PLAN_MD.read_text(encoding="utf-8")

    check(plan.get("name") == "R114_ConfidenceGatedRecoverableScratch", "wrong plan name", failures)
    check(plan.get("status") == "planned_not_implemented", "plan must remain unimplemented", failures)
    check(plan.get("formal_training_authorized") is False, "formal training must not be authorized", failures)

    non_negotiable = plan.get("non_negotiable", {})
    for key in ("single_image", "tile_safe", "scratch_only"):
        check(non_negotiable.get(key) is True, f"missing non-negotiable: {key}", failures)
    check(non_negotiable.get("weight_inheritance") is False, "weight inheritance must be disabled", failures)
    check(non_negotiable.get("real_or_sem_training_labels") is False, "real/SEM labels must be disabled", failures)

    expected_problems = {
        "dead_controller",
        "dense_edge_dominance",
        "clear_pairing_dominance",
        "scalar_width_target",
        "information_ceiling",
        "domain_gap",
    }
    actual_problems = {item.get("problem") for item in plan.get("evidence_to_fix", [])}
    check(expected_problems == actual_problems, "evidence-to-fix mapping is incomplete", failures)

    expected_stages = ["controller_probe", "geometry_probe", "detail_probe", "formal"]
    actual_stages = [item.get("stage") for item in plan.get("campaign", [])]
    check(actual_stages == expected_stages, "campaign stages are missing or out of order", failures)

    controller_outputs = set(plan.get("model", {}).get("controller_outputs", []))
    check(
        {"normalized_sdf", "normal_x", "normal_y", "boundary_confidence", "correction_need", "recoverability_uncertainty"}
        <= controller_outputs,
        "controller outputs are incomplete",
        failures,
    )
    check(plan.get("model", {}).get("patch_size") == 256, "primary patch size must remain 256", failures)
    check(plan.get("training", {}).get("minimum_gpu_free_gib") == 7, "GPU reserve must be 7 GiB", failures)
    check(plan.get("validation_order", [])[-1:] == ["external_GMF_compatibility_last"], "external GMF must be last", failures)
    check(plan.get("promotion", {}).get("worst_case_first") is True, "promotion must use worst-case first", failures)

    required_sections = [
        "## 二、證據對應修正",
        "## 三、資料設計",
        "## 四、新模型架構",
        "## 五、分階段、完全獨立的實驗",
        "## 七、即時驗證與選模",
        "## 九、明確禁止帶入R114的舊做法",
    ]
    for section in required_sections:
        check(section in markdown, f"missing markdown section: {section}", failures)

    result = {
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if not failures else "fail",
        "checks": 24,
        "failures": failures,
        "formal_training_started": False,
        "next_authorized_action": "controller_viability_probe_only",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
