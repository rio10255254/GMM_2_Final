"""Recompute original Round 13-15 selection numbers without running a trainer.

Uses only Python's standard library. Only three fixed, hashed arithmetic
functions are compiled from the preserved original audit source. Importing or
executing that source's training entry point is deliberately unnecessary.
"""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path


CASES = [
    ("R13_131800", "universal", "organized_20260311", "ROUND13_UNIVERSAL", "20260311_131800"),
    ("R13_150225", "universal", "organized_20260311", "ROUND13_UNIVERSAL", "20260311_150225"),
    ("R14_164239", "corridor0p8", "organized_20260311", "ROUND14_CORRIDOR", "20260311_164239"),
    ("R14_174207", "corridor0p8", "organized_20260311", "ROUND14_CORRIDOR", "20260311_174207"),
    ("R15_022742", "centerlock0p8", "organized_20260312", "ROUND15_CENTERLOCK", "20260312_022742"),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arithmetic_from_source(code):
    """Load only the fixed arithmetic functions, never the training entry point."""
    parsed = ast.parse(code.read_text(encoding="utf-8-sig"))
    wanted = {"_safe_float", "_per_scale_deploy_score", "_deployment_score"}
    functions = [node for node in parsed.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    if {node.name for node in functions} != wanted:
        raise ValueError("The preserved original arithmetic functions are incomplete")
    module = ast.Module(body=functions, type_ignores=[])
    scope = {}
    exec(compile(ast.fix_missing_locations(module), str(code), "exec"), scope)
    return scope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Keep the earlier verification record")
    root = args.root.resolve()
    evidence = root / "docs/reproducibility/legacy_multiscale/INPUT_IDENTITIES.json"
    identities = json.loads(evidence.read_text(encoding="utf-8"))
    checked_sources = []
    for row in identities["files"]:
        path = root / row["path"]
        actual = digest(path)
        if actual != row["sha256"] or path.stat().st_size != row["bytes"]:
            raise ValueError("The preserved original input changed: " + row["path"])
        checked_sources.append(row)
    late_source = "Model/GeoEdgeAlignSR_v1_UniversalCheckpointAudit.py"
    early_source = "docs/reproducibility/legacy_multiscale/recovered_sources/20260311_121009/GeoEdgeAlignSR_v1_UniversalCheckpointAudit.py"
    for source in (late_source, early_source):
        if not any(row["path"] == source for row in checked_sources):
            raise ValueError("Arithmetic source is not bound to a verified original: " + source)
    late_scope = arithmetic_from_source(root / late_source)
    early_scope = arithmetic_from_source(root / early_source)
    results = []
    total_numbers = 0
    formula_gaps = []
    for case, mode, folder, prefix, stamp in CASES:
        scope = early_scope if case == "R13_131800" else late_scope
        arithmetic_source = early_source if case == "R13_131800" else late_source
        relative = f"Traing_Progress/{folder}/selected/reports/{prefix}_CHECKPOINT_AUDIT_SUMMARY_{stamp}.json"
        data = json.loads((root / relative).read_text(encoding="utf-8-sig"))
        families = []
        numbers = 0
        for family in data["audits"]:
            ranked = []
            for candidate in family["audit_results"]:
                scales = {float(key): dict(value) for key, value in candidate["per_scale"].items()}
                for scale, row in scales.items():
                    computed = scope["_per_scale_deploy_score"](row["summary"], scale)
                    if not math.isclose(computed, row["deploy_scale_score"], rel_tol=1e-12, abs_tol=1e-10):
                        raise ValueError(f"Original per-scale arithmetic differs: {case}, {family['candidate']}, {scale}")
                    row["deploy_scale_score"] = computed
                    numbers += 1
                computed = (scope["_deployment_score"](scales) if case == "R13_131800"
                            else scope["_deployment_score"](scales, mode))
                if not math.isclose(computed, candidate["deployment_score"], rel_tol=1e-12, abs_tol=1e-10):
                    raise ValueError("Original version-specific total differs: " + case)
                numbers += 1
                score_for_selection = computed
                ranked.append({"checkpoint_label": candidate["checkpoint_label"],
                               "checkpoint_path": candidate["checkpoint_path"], "score": score_for_selection})
            ranked.sort(key=lambda row: row["score"], reverse=True)
            chosen = ranked[0]
            if chosen["checkpoint_label"] != family["best_checkpoint_label"] or chosen["checkpoint_path"] != family["best_checkpoint_path"]:
                raise ValueError("The original within-family choice differs: " + case)
            if not math.isclose(chosen["score"], family["best_deployment_score"], rel_tol=1e-12, abs_tol=1e-10):
                raise ValueError("The original family-best score differs: " + case)
            families.append({"candidate": family["candidate"], "family_pre_rank_score": family["family_score"],
                             "best": chosen, "all_model_results": ranked})
        # Python's stable sort preserves original order at a true tie; no
        # unrecorded secondary rule or rounding is introduced here.
        families.sort(key=lambda row: row["best"]["score"], reverse=True)
        chosen = families[0]
        if chosen["candidate"] != data["best_candidate"] or chosen["best"]["checkpoint_path"] != data["selected_checkpoint"]:
            raise ValueError("The recorded final historical choice differs: " + case)
        best_score = chosen["best"]["score"]
        results.append({"case": case, "mode": mode, "source": relative, "arithmetic_source": arithmetic_source,
                        "numbers_recomputed": numbers,
                        "selected_candidate": chosen["candidate"], "selected_checkpoint": chosen["best"]["checkpoint_path"],
                        "highest_score": best_score,
                        "families_tied_at_highest_exact_score": [row["candidate"] for row in families if row["best"]["score"] == best_score],
                        "families": families})
        total_numbers += numbers
    if total_numbers != 216:
        raise ValueError("The original five-case score population changed")
    report = {"status": "216_NUMBERS_RECOMPUTED_WITH_RECOVERED_EARLY_R13_FORMULA", "recomputed_numbers": total_numbers,
              "earlier_total_formula_gaps": formula_gaps,
              "previous_early_R13_formula_gaps_resolved": 9,
              "recorded_selection_rankings_reconstructed": len(results),
              "original_source_files_verified": checked_sources, "cases": results,
              "training_executed": False, "model_inference_executed": False,
              "absolute_physical_accuracy_claimed": False,
              "limits": "216 original scores recomputed using their original versions, including nine early R13 totals recovered from the successful 2026-03-11 source creation event. Five choices reconstructed from original score order. Does not regenerate model evaluations or prove tied weights equal."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("LEGACY_SELECTION_NUMBERS_AND_CHOICES_REPLAYED_WITH_RECOVERED_EARLY_FORMULA", total_numbers, len(results), len(formula_gaps), flush=True)


if __name__ == "__main__":
    main()
