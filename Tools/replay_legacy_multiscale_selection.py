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
    code = root / "Model/GeoEdgeAlignSR_v1_UniversalCheckpointAudit.py"
    parsed = ast.parse(code.read_text(encoding="utf-8-sig"))
    wanted = {"_safe_float", "_per_scale_deploy_score", "_deployment_score"}
    functions = [node for node in parsed.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    if {node.name for node in functions} != wanted:
        raise ValueError("The preserved original arithmetic functions are incomplete")
    module = ast.Module(body=functions, type_ignores=[])
    scope = {}
    exec(compile(ast.fix_missing_locations(module), str(code), "exec"), scope)
    results = []
    total_numbers = 0
    formula_gaps = []
    for case, mode, folder, prefix, stamp in CASES:
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
                computed = scope["_deployment_score"](scales, mode)
                if not math.isclose(computed, candidate["deployment_score"], rel_tol=1e-12, abs_tol=1e-10):
                    # The earlier 13:18 summary predates the preserved total
                    # formula. Its nine original totals remain evidence, not
                    # numbers silently replaced with a later scoring rule.
                    if case != "R13_131800":
                        raise ValueError("An unrecorded arithmetic difference appeared: " + case)
                    formula_gaps.append({"case": case, "candidate": family["candidate"],
                                         "checkpoint_label": candidate["checkpoint_label"],
                                         "original_saved_total": candidate["deployment_score"],
                                         "later_source_formula_total": computed,
                                         "original_total_formula_recovered": False})
                    score_for_selection = candidate["deployment_score"]
                else:
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
        results.append({"case": case, "mode": mode, "source": relative, "numbers_recomputed": numbers,
                        "selected_candidate": chosen["candidate"], "selected_checkpoint": chosen["best"]["checkpoint_path"],
                        "highest_score": best_score,
                        "families_tied_at_highest_exact_score": [row["candidate"] for row in families if row["best"]["score"] == best_score],
                        "families": families})
        total_numbers += numbers
    if len(formula_gaps) != 9:
        raise ValueError("The fixed earlier formula-gap evidence changed; review the original source version")
    report = {"status": "207_NUMBERS_RECOMPUTED_9_EARLIER_FORMULA_GAPS_PRESERVED", "recomputed_numbers": total_numbers,
              "earlier_total_formula_gaps": formula_gaps,
              "recorded_selection_rankings_reconstructed": len(results),
              "original_source_files_verified": checked_sources, "cases": results,
              "training_executed": False, "model_inference_executed": False,
              "absolute_physical_accuracy_claimed": False,
              "limits": "207 matching original scores recomputed; nine earlier R13 totals retained because their original formula version is not recovered. Five choices reconstructed from original score order. Does not regenerate model evaluations or prove tied weights equal."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("LEGACY_SELECTION_NUMBERS_AND_CHOICES_REPLAYED_WITH_EXPLICIT_FORMULA_GAP", total_numbers, len(results), len(formula_gaps), flush=True)


if __name__ == "__main__":
    main()
