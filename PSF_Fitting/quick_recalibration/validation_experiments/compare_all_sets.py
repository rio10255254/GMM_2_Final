"""
compare_all_sets.py — N 組通用的 L0 跨組對比 + 深度疑問分析

§1-5:跨組基本對比
  - 各組基本資料、核心結論、mode 對齊、reference basins、綜合判決
§6:為什麼 noise floor 跨組差 21.5%?
  6.1 主解佔比 vs noise floor 的關聯
  6.2 fval 跟迭代次數跨組對比
  6.3 每個視野點貢獻的 basin 內 std
§7:兩個 basin 的物理意義
  7.1 主/次 basin 各 Zernike 中心值
  7.2 Basin pair distance 跨組變動
  7.3 主 vs 次 basin 的 fval 哪個更低
§8:BADS 內部隨機性
  8.1 rng seed → basin 跨組對比
  8.2 每個視野點落到主/次的偏好 + trial 內 9 視野一致性
§9:撞邊細節
  9.1 撞邊飽和係數 lb/ub 分佈跨組

執行(在 d:/GMM_2_Final/ 跑):
  python PSF_Fitting/quick_recalibration/validation_experiments/compare_all_sets.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import scipy.io as sio


SCRIPT_DIR = Path(__file__).resolve().parent

REPORT_PATH = SCRIPT_DIR / "all_sets_comparison.md"
JSON_PATH = SCRIPT_DIR / "all_sets_comparison.json"

SETS_CONFIG = [
    {"name": "setA", "subdir": "L0_repeat_fit"},
    {"name": "setB", "subdir": "L0_repeat_fit_setB"},
    {"name": "setC", "subdir": "L0_repeat_fit_setC"},
    {"name": "setD", "subdir": "L0_repeat_fit_setD"},
]

REFERENCE_SET = "setA"

COEF_LABELS = [
    "Z2 Y-tilt (locked)",
    "Z3 X-tilt (locked)",
    "Z4 astig 45°",
    "Z5 defocus",
    "Z6 astig 0°",
    "Z7 trefoil (sin 3φ)",
    "Z8 coma Y",
    "Z9 coma X",
    "Z10 trefoil (cos 3φ)",
    "Z11 quadrafoil (sin 4φ)",
    "Z12 sec astig (sin 2φ)",
    "Z13 spherical",
    "Z14 sec astig (cos 2φ)",
    "Z15 quadrafoil (cos 4φ)",
    "AC amplitude",
]

LB = np.array([-0.3, -0.3, -0.1, 0.0, -0.1, -0.05, -0.05, -0.05, -0.05, -0.01, -0.01, 0.0,  -0.01, -0.01, 0.8 ])
UB = np.array([ 0.3,  0.3,  0.1, 1.0,  0.1,  0.05,  0.05,  0.05,  0.05,  0.01,  0.01, 0.3,   0.01,  0.01, 1.25])


# ============================================================================
# Loading
# ============================================================================

def load_raw_coef_tensor(subdir: str, n_trials: int = 15) -> np.ndarray | None:
    """讀所有 trial 的 coef_grid,組成 (T, Z, F) tensor"""
    tensors = []
    for trial_idx in range(1, n_trials + 1):
        stack_path = SCRIPT_DIR / subdir / "outputs" / f"trial_{trial_idx:02d}" / "PSF_fitted_2D_FOVstack.mat"
        if not stack_path.is_file():
            return None
        data = sio.loadmat(str(stack_path), squeeze_me=False)
        coef = np.asarray(data["coef_grid"])
        if coef.ndim == 3:
            coef = coef[:, 0, :]
        tensors.append(coef)
    return np.stack(tensors, axis=0)


def load_per_trial_csv(subdir: str, n_trials: int = 15) -> list[list[dict]] | None:
    """讀每 trial 的 batch_results.csv(9 個 FOV 的 fval, iterations, seconds)
    回傳 list[trial][fov_idx] = {fval, iterations, seconds, file_index}
    """
    all_trials = []
    for trial_idx in range(1, n_trials + 1):
        csv_path = SCRIPT_DIR / subdir / "outputs" / f"trial_{trial_idx:02d}" / "batch_results.csv"
        if not csv_path.is_file():
            return None
        rows = []
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append({
                    "file_index": int(r["file_index"]),
                    "fval": float(r["fval"]),
                    "iterations": int(r["iterations"]),
                    "seconds": float(r["seconds"]),
                })
        all_trials.append(rows)
    return all_trials


def load_one_set(name: str, subdir: str) -> dict | None:
    """讀一組(deep_analysis + noise_floor + raw stack + batch csvs)"""
    json_path = SCRIPT_DIR / subdir / "outputs" / "deep_analysis.json"
    nf_path = SCRIPT_DIR / subdir / "outputs" / "noise_floor.json"

    if not json_path.is_file() or not nf_path.is_file():
        print(f"  跳過 {name}:deep_analysis 或 noise_floor 不存在")
        return None

    with json_path.open("r", encoding="utf-8") as f:
        deep = json.load(f)
    with nf_path.open("r", encoding="utf-8") as f:
        nf = json.load(f)

    centroids_zerf = {
        int(m): np.array(v)
        for m, v in deep["sec3_mode_separations"]["mode_centroids_per_coef_per_fov"].items()
    }
    centroids_avg_fov = {m: c.mean(axis=1) for m, c in centroids_zerf.items()}

    raw_tensor = load_raw_coef_tensor(subdir, deep["n_trials"])
    per_trial_csv = load_per_trial_csv(subdir, deep["n_trials"])

    return {
        "name": name,
        "subdir": subdir,
        "fov_indices": deep["fov_indices"],
        "n_trials": deep["n_trials"],
        "best_k": deep["sec1_modes"]["best_k"],
        "mode_probabilities": {int(k): v for k, v in deep["sec1_modes"]["mode_probabilities"].items()},
        "mode_labels": deep["sec1_modes"]["labels"],
        "mode_centroids_zerf": centroids_zerf,
        "mode_centroids_avg_fov": centroids_avg_fov,
        "per_mode_noise": deep["sec2_per_mode_noise"],
        "pairwise_mode_distances": deep["sec3_mode_separations"]["pairwise_distances"],
        "boundaries": deep["sec4_boundaries"],
        "clean_noise_floor": nf["clean_noise_floor"],
        "coef_classifications": nf["coef_classifications"],
        "rng_seeds": deep.get("rng_seeds", list(range(1, deep["n_trials"] + 1))),
        "raw_tensor": raw_tensor,                # (T, Z, F)
        "per_trial_csv": per_trial_csv,           # list[trial][fov]
    }


# ============================================================================
# §1-5:基本對比(原版邏輯)
# ============================================================================

def align_set_to_reference(target: dict, reference: dict) -> dict:
    ref_modes = sorted(reference["mode_centroids_avg_fov"].keys())
    tgt_modes = sorted(target["mode_centroids_avg_fov"].keys())

    dmat = np.zeros((len(ref_modes), len(tgt_modes)))
    for i, rm in enumerate(ref_modes):
        for j, tm in enumerate(tgt_modes):
            dmat[i, j] = np.linalg.norm(
                reference["mode_centroids_avg_fov"][rm] - target["mode_centroids_avg_fov"][tm]
            )

    pairs = []
    used_target = set()
    for i, rm in enumerate(ref_modes):
        candidates = [(j, dmat[i, j]) for j, tm in enumerate(tgt_modes) if tm not in used_target]
        candidates.sort(key=lambda x: x[1])
        if candidates:
            j_best, d_best = candidates[0]
            tm_best = tgt_modes[j_best]
            pairs.append((rm, tm_best, float(d_best)))
            used_target.add(tm_best)

    return {
        "ref_modes": ref_modes,
        "tgt_modes": tgt_modes,
        "distance_matrix": dmat.tolist(),
        "target_to_reference": {int(b): int(a) for a, b, _ in pairs},
        "aligned_pairs": [(int(a), int(b), d) for a, b, d in pairs],
    }


def compute_reference_basins(sets: dict, reference_name: str) -> dict:
    ref = sets[reference_name]
    centroids = ref["mode_centroids_avg_fov"]
    probs = ref["mode_probabilities"]
    sorted_modes = sorted(centroids.keys(), key=lambda m: -probs.get(m, 0))

    return {
        "source_set": reference_name,
        "primary_basin": {
            "raw_mode_id": int(sorted_modes[0]),
            "centroid_15d": centroids[sorted_modes[0]].tolist(),
            "probability_in_reference": probs.get(sorted_modes[0]),
        },
        "secondary_basin": {
            "raw_mode_id": int(sorted_modes[1]),
            "centroid_15d": centroids[sorted_modes[1]].tolist(),
            "probability_in_reference": probs.get(sorted_modes[1]),
        } if len(sorted_modes) >= 2 else None,
        "basin_pair_distance": float(np.linalg.norm(
            centroids[sorted_modes[0]] - centroids[sorted_modes[1]]
        )) if len(sorted_modes) >= 2 else None,
    }


def find_target_main_mode(name: str, sets: dict, alignments: dict, ref_name: str) -> int:
    """找該組對應到 reference 主 basin 的 mode label"""
    ref_main = max(sets[ref_name]["mode_probabilities"], key=sets[ref_name]["mode_probabilities"].get)
    if name == ref_name:
        return ref_main
    alignment = alignments[name]
    for rm, tm, _ in alignment["aligned_pairs"]:
        if rm == ref_main:
            return tm
    return None


def collect_aligned_probabilities(sets: dict, alignments: dict, ref_name: str) -> list[dict]:
    ref = sets[ref_name]
    ref_probs = ref["mode_probabilities"]
    primary_ref_mode = max(ref_probs, key=ref_probs.get)
    secondary_ref_modes = [m for m in ref_probs if m != primary_ref_mode]

    rows = []
    for name, s in sets.items():
        if name == ref_name:
            primary_prob = ref_probs[primary_ref_mode]
            secondary_prob = sum(ref_probs[m] for m in secondary_ref_modes)
            rows.append({
                "set": name, "is_reference": True,
                "primary_basin_prob": primary_prob,
                "secondary_basin_prob": secondary_prob,
                "alignment_note": "(reference)",
            })
            continue
        alignment = alignments[name]
        target_for_primary = None
        target_for_secondary = []
        for rm, tm, _ in alignment["aligned_pairs"]:
            if rm == primary_ref_mode:
                target_for_primary = tm
            else:
                target_for_secondary.append(tm)
        primary_prob = s["mode_probabilities"].get(target_for_primary, 0)
        secondary_prob = sum(s["mode_probabilities"].get(m, 0) for m in target_for_secondary)
        rows.append({
            "set": name, "is_reference": False,
            "primary_basin_prob": primary_prob,
            "secondary_basin_prob": secondary_prob,
            "alignment_note": f"{ref_name} mode {primary_ref_mode} ↔ {name} mode {target_for_primary}",
        })
    return rows


def compute_summary(sets: dict, alignments: dict, ref_name: str, ref_basins: dict) -> dict:
    n_modes_list = {name: s["best_k"] for name, s in sets.items()}
    all_same_n_modes = len(set(n_modes_list.values())) == 1

    aligned_probs = collect_aligned_probabilities(sets, alignments, ref_name)
    primary_probs = [r["primary_basin_prob"] for r in aligned_probs if r["primary_basin_prob"] is not None]

    noise_floors = {name: s["clean_noise_floor"]["overall_median_std"] for name, s in sets.items()}
    nf_min, nf_max = min(noise_floors.values()), max(noise_floors.values())

    top1_discriminators = {}
    for name, s in sets.items():
        first_pair = list(s["pairwise_mode_distances"].values())[0]
        top1_discriminators[name] = first_pair["top_5_discriminator_coefs"][0]["label"]

    return {
        "n_sets": len(sets),
        "set_names": list(sets.keys()),
        "reference_set": ref_name,
        "n_modes_per_set": n_modes_list,
        "all_same_n_modes": all_same_n_modes,
        "common_n_modes": list(n_modes_list.values())[0] if all_same_n_modes else None,
        "aligned_probabilities": aligned_probs,
        "primary_prob_range": (max(primary_probs) - min(primary_probs)) if primary_probs else None,
        "primary_prob_mean": float(np.mean(primary_probs)) if primary_probs else None,
        "primary_prob_std": float(np.std(primary_probs, ddof=1)) if len(primary_probs) > 1 else None,
        "noise_floors": noise_floors,
        "nf_min": nf_min, "nf_max": nf_max,
        "nf_diff_pct": (nf_max - nf_min) / nf_max * 100 if nf_max > 0 else 0,
        "top1_discriminators": top1_discriminators,
        "all_top1_same": len(set(top1_discriminators.values())) == 1,
        "within_set_mode_distances": {
            name: list(s["pairwise_mode_distances"].values())[0]["total_euclidean"]
            for name, s in sets.items()
        },
        "reference_basins": ref_basins,
    }


# ============================================================================
# §6:為什麼 noise floor 跨組差?
# ============================================================================

def analyze_main_prob_vs_noise_floor(sets: dict, summary: dict) -> dict:
    """§6.1 主解佔比 vs noise floor 的關聯"""
    rows = []
    for r in summary["aligned_probabilities"]:
        rows.append({
            "set": r["set"],
            "main_basin_prob": r["primary_basin_prob"],
            "noise_floor": summary["noise_floors"][r["set"]],
        })
    probs = np.array([x["main_basin_prob"] for x in rows])
    floors = np.array([x["noise_floor"] for x in rows])
    correlation = float(np.corrcoef(probs, floors)[0, 1])
    return {"rows": rows, "pearson_correlation": correlation}


def analyze_fval_iter_across_sets(sets: dict) -> list[dict]:
    """§6.2 fval 跟迭代次數跨組對比"""
    rows = []
    for name, s in sets.items():
        if s["per_trial_csv"] is None:
            continue
        all_fval = []
        all_iter = []
        all_sec = []
        for trial_rows in s["per_trial_csv"]:
            for row in trial_rows:
                all_fval.append(row["fval"])
                all_iter.append(row["iterations"])
                all_sec.append(row["seconds"])
        rows.append({
            "set": name,
            "n_obs": len(all_fval),
            "fval_median": float(np.median(all_fval)),
            "fval_mean": float(np.mean(all_fval)),
            "fval_std": float(np.std(all_fval, ddof=1)),
            "fval_min": float(np.min(all_fval)),
            "fval_max": float(np.max(all_fval)),
            "iter_median": float(np.median(all_iter)),
            "iter_mean": float(np.mean(all_iter)),
            "iter_std": float(np.std(all_iter, ddof=1)),
            "seconds_median": float(np.median(all_sec)),
        })
    return rows


def analyze_per_fov_main_basin_std(sets: dict, alignments: dict, ref_name: str) -> dict:
    """§6.3 每個視野點貢獻的 main basin 內 std"""
    per_set_rows = {}
    for name, s in sets.items():
        target_main = find_target_main_mode(name, sets, alignments, ref_name)
        if target_main is None:
            continue
        main_info = s["per_mode_noise"].get(str(target_main))
        if main_info is None or main_info.get("internal_std_per_coef_per_fov") is None:
            continue
        std_zf = np.array(main_info["internal_std_per_coef_per_fov"])  # (Z, F)
        # 只用 trustworthy 係數
        trustworthy_idx = [
            ci for ci, c in enumerate(s["coef_classifications"]) if c["status"] == "trustworthy"
        ]
        if not trustworthy_idx:
            continue
        clean_std_per_fov = std_zf[trustworthy_idx, :].mean(axis=0)
        per_set_rows[name] = {
            "fov_indices": s["fov_indices"],
            "main_basin_std_per_fov": clean_std_per_fov.tolist(),
            "median": float(np.median(clean_std_per_fov)),
            "max": float(np.max(clean_std_per_fov)),
            "max_fov_idx": int(s["fov_indices"][np.argmax(clean_std_per_fov)]),
        }
    return per_set_rows


# ============================================================================
# §7:兩個 basin 的物理意義
# ============================================================================

def analyze_basin_centroid_physical(sets: dict, ref_name: str) -> dict:
    """§7.1 主/次 basin 各 Zernike 中心值(用 reference 組的 centroid)"""
    ref = sets[ref_name]
    probs = ref["mode_probabilities"]
    main_mode = max(probs, key=probs.get)
    sec_mode = [m for m in probs if m != main_mode][0]
    main_c = ref["mode_centroids_avg_fov"][main_mode]
    sec_c = ref["mode_centroids_avg_fov"][sec_mode]
    classif = ref["coef_classifications"]
    rows = []
    for ci in range(15):
        rows.append({
            "idx": ci,
            "label": COEF_LABELS[ci],
            "status": classif[ci]["status"],
            "main_basin_center": float(main_c[ci]),
            "sec_basin_center": float(sec_c[ci]),
            "diff_main_minus_sec": float(main_c[ci] - sec_c[ci]),
        })
    return {"source_set": ref_name, "rows": rows}


def analyze_basin_pair_distance(sets: dict) -> dict:
    """§7.2 Basin pair distance 跨組變動"""
    rows = []
    for name, s in sets.items():
        first_pair = list(s["pairwise_mode_distances"].values())[0]
        rows.append({"set": name, "pair_distance": first_pair["total_euclidean"]})
    distances = [r["pair_distance"] for r in rows]
    return {
        "rows": rows,
        "min": float(min(distances)),
        "max": float(max(distances)),
        "mean": float(np.mean(distances)),
        "std": float(np.std(distances, ddof=1)),
        "range_pct": float((max(distances) - min(distances)) / min(distances) * 100),
    }


def analyze_main_vs_sec_fval(sets: dict, alignments: dict, ref_name: str) -> list[dict]:
    """§7.3 主 vs 次 basin 的 fval 哪個更低"""
    rows = []
    for name, s in sets.items():
        if s["per_trial_csv"] is None:
            continue
        target_main = find_target_main_mode(name, sets, alignments, ref_name)
        labels = s["mode_labels"]
        main_fvals = []
        sec_fvals = []
        for trial_idx, trial_rows in enumerate(s["per_trial_csv"]):
            trial_label = labels[trial_idx]
            for row in trial_rows:
                if trial_label == target_main:
                    main_fvals.append(row["fval"])
                else:
                    sec_fvals.append(row["fval"])
        rows.append({
            "set": name,
            "main_basin_fval_median": float(np.median(main_fvals)) if main_fvals else None,
            "main_basin_fval_count": len(main_fvals),
            "sec_basin_fval_median": float(np.median(sec_fvals)) if sec_fvals else None,
            "sec_basin_fval_count": len(sec_fvals),
            "main_minus_sec_fval": (
                float(np.median(main_fvals) - np.median(sec_fvals))
                if main_fvals and sec_fvals else None
            ),
        })
    return rows


# ============================================================================
# §8:BADS 內部隨機性
# ============================================================================

def analyze_rng_seed_basin_mapping(sets: dict, alignments: dict, ref_name: str) -> dict:
    """§8.1 rng seed → basin(對齊後)跨組對比"""
    rows = []
    for seed_offset, seed in enumerate(sets[ref_name]["rng_seeds"]):
        row = {"seed": seed}
        for name, s in sets.items():
            target_main = find_target_main_mode(name, sets, alignments, ref_name)
            label = s["mode_labels"][seed_offset]
            row[name] = "main" if label == target_main else "sec"
        rows.append(row)
    # 跨組一致性:同一 seed 落到同一 basin 的次數
    agreements = 0
    for r in rows:
        vals = [v for k, v in r.items() if k != "seed"]
        if len(set(vals)) == 1:
            agreements += 1
    return {
        "rows": rows,
        "cross_set_agreement_count": agreements,
        "cross_set_agreement_pct": agreements / len(rows) * 100,
    }


def analyze_per_fov_basin_preference(sets: dict, alignments: dict, ref_name: str) -> dict:
    """
    §8.2 每個 (trial, FOV) 屬於主還是次 basin
    用「該組主 basin 在 FOV f 的 trial 平均」當參考中心,看每個 (t, f) 比較靠近誰
    順便算 trial 內 9 視野的 basin 歸屬一致性
    """
    per_set_results = {}
    for name, s in sets.items():
        if s["raw_tensor"] is None:
            continue
        target_main = find_target_main_mode(name, sets, alignments, ref_name)
        sec_modes = [int(m) for m in s["per_mode_noise"] if int(m) != target_main]
        if not sec_modes:
            continue
        target_sec = sec_modes[0]

        main_info = s["per_mode_noise"].get(str(target_main))
        sec_info = s["per_mode_noise"].get(str(target_sec))
        if main_info is None or sec_info is None:
            continue
        main_mean_zf = main_info.get("internal_mean_per_coef_per_fov")
        sec_mean_zf = sec_info.get("internal_mean_per_coef_per_fov")
        if main_mean_zf is None or sec_mean_zf is None:
            continue
        main_mean_zf = np.array(main_mean_zf)
        sec_mean_zf = np.array(sec_mean_zf)

        raw = s["raw_tensor"]  # (T, Z, F)
        T, Z, F = raw.shape
        # 只用 trustworthy 係數做分類(撞邊跟死維度會誤導距離)
        trustworthy_idx = np.array([
            ci for ci, c in enumerate(s["coef_classifications"]) if c["status"] == "trustworthy"
        ])

        belongs_to_main = np.zeros((T, F), dtype=bool)
        for t in range(T):
            for f in range(F):
                d_main = np.linalg.norm(raw[t, trustworthy_idx, f] - main_mean_zf[trustworthy_idx, f])
                d_sec = np.linalg.norm(raw[t, trustworthy_idx, f] - sec_mean_zf[trustworthy_idx, f])
                belongs_to_main[t, f] = d_main < d_sec

        # Per-FOV 落到主 basin 的比例(跨 trial)
        per_fov_main_pct = belongs_to_main.mean(axis=0)
        # Trial 內 9 視野是否全部一致(全主 / 全次)
        all_main = belongs_to_main.all(axis=1)
        all_sec = (~belongs_to_main).all(axis=1)
        mixed = ~(all_main | all_sec)
        # 跟 trial-level cluster label 比較:全主 vs 全次 是否跟 cluster label 一致?
        labels = np.array(s["mode_labels"])
        cluster_main = (labels == target_main)
        # 一致定義:cluster 認為主 → 全部 FOV 都主;cluster 認為次 → 全部 FOV 都次
        consistent = (cluster_main & all_main) | (~cluster_main & all_sec)

        per_set_results[name] = {
            "fov_indices": s["fov_indices"],
            "per_fov_main_basin_pct": per_fov_main_pct.tolist(),
            "n_trials": int(T),
            "n_trials_all_main_fov": int(all_main.sum()),
            "n_trials_all_sec_fov": int(all_sec.sum()),
            "n_trials_mixed": int(mixed.sum()),
            "n_trials_consistent_with_cluster": int(consistent.sum()),
        }
    return per_set_results


# ============================================================================
# §9:撞邊細節
# ============================================================================

def analyze_boundary_split_across_sets(sets: dict) -> list[dict]:
    """§9.1 撞邊飽和係數的 lb/ub 分佈跨組對比"""
    ref = list(sets.values())[0]
    bs_indices = []
    for ci, b in enumerate(ref["boundaries"]):
        if (b["frac_at_lb"] + b["frac_at_ub"]) > 0.8:
            bs_indices.append(ci)

    rows = []
    for ci in bs_indices:
        row = {"coef_idx": ci, "label": COEF_LABELS[ci]}
        for name, s in sets.items():
            b = s["boundaries"][ci]
            row[f"{name}_at_lb_pct"] = b["frac_at_lb"] * 100
            row[f"{name}_at_ub_pct"] = b["frac_at_ub"] * 100
        rows.append(row)
    return rows


# ============================================================================
# Report writing
# ============================================================================

def write_report(sets, alignments, summary, deep) -> None:
    L = []
    set_names = list(sets.keys())

    L.append(f"# L0 跨組對比({len(set_names)} 組:{', '.join(set_names)})")
    L.append("")
    L.append(f"> 用 {summary['reference_set']} 當 mode 對齊的 reference。")
    L.append(f"> 各組設定完全相同(同 GT、同 fitter、同搜尋範圍、同 lock_tilt、同 rng 策略),只換 fov_indices。")
    L.append("")
    L.append("---")
    L.append("")

    # ===== §1 各組基本資料 =====
    L.append("## 1. 各組基本資料")
    L.append("")
    L.append("| Set | FOV indices | Trials | best_k |")
    L.append("|---|---|---|---|")
    for name, s in sets.items():
        L.append(f"| {name} | {s['fov_indices']} | {s['n_trials']} | {s['best_k']} |")
    L.append("")

    # ===== §2 核心結論 =====
    L.append("## 2. 核心結論")
    L.append("")
    if summary["all_same_n_modes"]:
        L.append(f"### ✓ 所有 {summary['n_sets']} 組都偵測到 **{summary['common_n_modes']} 個 mode**")
    L.append("")
    L.append("### 主 basin 機率(對齊後)穩不穩?")
    L.append("")
    L.append("| Set | 主 basin 機率 | 次 basin 機率 | 對齊備註 |")
    L.append("|---|---|---|---|")
    for r in summary["aligned_probabilities"]:
        marker = " (ref)" if r["is_reference"] else ""
        primary_str = f"{r['primary_basin_prob']:.1%}" if r["primary_basin_prob"] is not None else "—"
        secondary_str = f"{r['secondary_basin_prob']:.1%}" if r["secondary_basin_prob"] is not None else "—"
        L.append(f"| {r['set']}{marker} | {primary_str} | {secondary_str} | {r['alignment_note']} |")
    L.append("")
    if summary["primary_prob_range"] is not None:
        L.append(f"- 主 basin 機率範圍:{summary['primary_prob_range']*100:.1f} 個百分點")
        L.append(f"- 平均 ± std:{summary['primary_prob_mean']*100:.1f}% ± {summary['primary_prob_std']*100:.1f}%(N={summary['n_sets']})")
        if summary["primary_prob_range"] < 0.15:
            L.append("- **機率分佈穩定** → 可以當穩定先驗")
    L.append("")

    L.append("### Noise floor 量級穩不穩?")
    L.append("")
    L.append("| Set | 乾淨 noise floor 中位 std |")
    L.append("|---|---|")
    for name, nf in summary["noise_floors"].items():
        L.append(f"| {name} | {nf:.5f} |")
    L.append(f"")
    L.append(f"- 跨組差距:**{summary['nf_diff_pct']:.1f}%**(這條是 §6 要深挖的問題)")
    L.append("")

    L.append("### Top 1 區別維度跨組一致嗎?")
    L.append("")
    L.append("| Set | Top 1 區別維度 |")
    L.append("|---|---|")
    for name, label in summary["top1_discriminators"].items():
        L.append(f"| {name} | {label} |")
    L.append("")
    if summary["all_top1_same"]:
        L.append(f"**全部 {summary['n_sets']} 組的 top 1 區別維度都相同**")
    L.append("")

    L.append("---")
    L.append("")

    # ===== §3 對齊細節 =====
    L.append(f"## 3. Mode 對齊細節(以 {summary['reference_set']} 為基準)")
    L.append("")
    for name in set_names:
        if name == summary["reference_set"]:
            continue
        alignment = alignments[name]
        L.append(f"### {summary['reference_set']} ↔ {name}")
        for ref_mode, tgt_mode, d in alignment["aligned_pairs"]:
            L.append(f"- {summary['reference_set']} mode {ref_mode} ↔ {name} mode {tgt_mode}(centroid 距離 = {d:.4f})")
        within = summary["within_set_mode_distances"][name]
        avg_align = float(np.mean([d for _, _, d in alignment["aligned_pairs"]]))
        L.append(f"- 組內距離 {within:.4f} vs 跨組對齊距離 {avg_align:.4f}")
        L.append("")
    L.append("---")
    L.append("")

    # ===== §4 Reference Basins =====
    rb = summary["reference_basins"]
    L.append("## 4. Reference Basins(給 attribution Test 1 用)")
    L.append("")
    L.append(f"從 {rb['source_set']} 的 mode centroids 抽取。完整數值寫在同目錄 `reference_basins.json`。")
    L.append("")
    L.append(f"- Primary basin:來自 {rb['source_set']} mode {rb['primary_basin']['raw_mode_id']},機率 {rb['primary_basin']['probability_in_reference']:.1%}")
    L.append(f"- Secondary basin:來自 {rb['source_set']} mode {rb['secondary_basin']['raw_mode_id']},機率 {rb['secondary_basin']['probability_in_reference']:.1%}")
    L.append(f"- Basin pair distance:{rb['basin_pair_distance']:.4f}")
    L.append("")
    L.append("---")
    L.append("")

    # ===== §5 綜合判決 =====
    L.append("## 5. 綜合判決")
    L.append("")
    L.append("| 屬性 | 結論 |")
    L.append("|---|---|")
    if summary["all_same_n_modes"] and summary["common_n_modes"] == 2:
        L.append("| Mode 數量 = 2 | 常態 ✓ |")
    if summary["all_top1_same"]:
        L.append(f"| 主要區別維度 | 常態 ✓ |")
    if summary["primary_prob_range"] is not None and summary["primary_prob_range"] < 0.15:
        L.append(f"| Basin 機率(跨組變動 {summary['primary_prob_range']*100:.1f}%) | 常態 ✓ |")
    L.append(f"| Noise floor 量級(差 {summary['nf_diff_pct']:.1f}%) | 大致穩定但比預期大,§6 深挖 |")
    L.append("")
    L.append("---")
    L.append("")

    # ===== §6 為什麼 noise floor 跨組差? =====
    L.append("## 6. 為什麼 noise floor 跨組差 21.5%?")
    L.append("")

    # 6.1
    L.append("### 6.1 主解佔比 vs noise floor 的關聯")
    L.append("")
    L.append("| Set | 主 basin 機率 | Noise floor |")
    L.append("|---|---|---|")
    for r in deep["main_prob_vs_noise_floor"]["rows"]:
        L.append(f"| {r['set']} | {r['main_basin_prob']:.1%} | {r['noise_floor']:.5f} |")
    corr = deep["main_prob_vs_noise_floor"]["pearson_correlation"]
    L.append("")
    L.append(f"- Pearson 相關係數:**{corr:+.3f}**(N=4,要小心過度詮釋)")
    if corr < -0.5:
        L.append("- 看起來主解佔比越高,noise floor 越低——可能是「主解吸引力強,trial 在主解內收斂得更精確」")
    elif corr > 0.5:
        L.append("- 看起來主解佔比越高,noise floor 越高——不直觀,要查")
    else:
        L.append("- 相關性不強,可能不是主因")
    L.append("")

    # 6.2
    L.append("### 6.2 Fval 跟迭代次數跨組對比")
    L.append("")
    L.append("如果 setC/setD 的 fval 中位數明顯比 setA/setB 低,代表擬合品質本身比較好,雜訊下限低是結果不是原因。")
    L.append("")
    L.append("| Set | fval median | fval mean ± std | fval range | iter median | iter mean ± std |")
    L.append("|---|---|---|---|---|---|")
    for r in deep["fval_iter"]:
        L.append(
            f"| {r['set']} | {r['fval_median']:.2f} | {r['fval_mean']:.2f} ± {r['fval_std']:.2f} | "
            f"{r['fval_min']:.2f}–{r['fval_max']:.2f} | {r['iter_median']:.0f} | "
            f"{r['iter_mean']:.0f} ± {r['iter_std']:.0f} |"
        )
    L.append("")

    # 6.3
    L.append("### 6.3 每個視野點貢獻的 main basin 內 std")
    L.append("")
    L.append("看哪些視野把組平均 noise floor 拉高。只用 trustworthy 係數平均。")
    L.append("")
    for name, info in deep["per_fov_main_std"].items():
        L.append(f"**{name}** — 中位 {info['median']:.4f},最大 {info['max']:.4f}(視野 #{info['max_fov_idx']})")
        L.append("")
        L.append("| FOV | main basin 內 std |")
        L.append("|---|---|")
        for fov, std_val in zip(info["fov_indices"], info["main_basin_std_per_fov"]):
            L.append(f"| #{fov} | {std_val:.5f} |")
        L.append("")

    L.append("---")
    L.append("")

    # ===== §7 兩個 basin 的物理意義 =====
    L.append("## 7. 兩個 basin 的物理意義")
    L.append("")

    # 7.1
    L.append(f"### 7.1 主/次 basin 各 Zernike 中心值(用 {deep['basin_centroid_physical']['source_set']})")
    L.append("")
    L.append("| 係數 | 狀態 | 主 basin 中心 | 次 basin 中心 | 主−次 |")
    L.append("|---|---|---|---|---|")
    for r in deep["basin_centroid_physical"]["rows"]:
        L.append(f"| {r['label']} | {r['status']} | {r['main_basin_center']:+.4f} | {r['sec_basin_center']:+.4f} | {r['diff_main_minus_sec']:+.4f} |")
    L.append("")

    # 7.2
    L.append("### 7.2 Basin pair distance 跨組變動")
    L.append("")
    bpd = deep["basin_pair_distance"]
    L.append("| Set | Basin pair distance |")
    L.append("|---|---|")
    for r in bpd["rows"]:
        L.append(f"| {r['set']} | {r['pair_distance']:.4f} |")
    L.append("")
    L.append(f"- 跨組 min/max:{bpd['min']:.4f} / {bpd['max']:.4f},變動 {bpd['range_pct']:.1f}%")
    L.append(f"- 平均 ± std:{bpd['mean']:.4f} ± {bpd['std']:.4f}")
    L.append("")

    # 7.3
    L.append("### 7.3 主 vs 次 basin 的 fval 哪個更低?")
    L.append("")
    L.append("如果次 basin fval 反而更低,代表 BADS 有 bias 不愛跑去全局最佳解;如果主 basin fval 更低,代表 BADS 確實偏好全局最佳。")
    L.append("")
    L.append("| Set | 主 basin fval 中位 (N) | 次 basin fval 中位 (N) | 主−次 |")
    L.append("|---|---|---|---|")
    for r in deep["main_vs_sec_fval"]:
        main_str = f"{r['main_basin_fval_median']:.2f} ({r['main_basin_fval_count']})" if r['main_basin_fval_median'] is not None else "—"
        sec_str = f"{r['sec_basin_fval_median']:.2f} ({r['sec_basin_fval_count']})" if r['sec_basin_fval_median'] is not None else "—"
        diff_str = f"{r['main_minus_sec_fval']:+.2f}" if r['main_minus_sec_fval'] is not None else "—"
        L.append(f"| {r['set']} | {main_str} | {sec_str} | {diff_str} |")
    L.append("")

    L.append("---")
    L.append("")

    # ===== §8 BADS 內部隨機性 =====
    L.append("## 8. BADS 內部隨機性")
    L.append("")

    # 8.1
    L.append("### 8.1 rng seed → basin(對齊後)跨組對比")
    L.append("")
    L.append("如果相同 rng seed 跨組都落到同一 basin → MATLAB rng 控制得住;如果隨機 → BADS 內部有不受控的隨機性。")
    L.append("")
    rng_data = deep["rng_seed_mapping"]
    header = "| seed | " + " | ".join(set_names) + " |"
    L.append(header)
    L.append("|" + "---|" * (len(set_names) + 1))
    for r in rng_data["rows"]:
        row_str = f"| {r['seed']} | " + " | ".join(r[name] for name in set_names) + " |"
        L.append(row_str)
    L.append("")
    L.append(f"- 跨組完全一致(同 seed 4 組都落到同 basin):{rng_data['cross_set_agreement_count']} / {len(rng_data['rows'])} ({rng_data['cross_set_agreement_pct']:.1f}%)")
    if rng_data["cross_set_agreement_pct"] < 30:
        L.append("- → BADS 內部隨機性**不受 MATLAB rng 控制**(同 seed 跨組落點隨機)")
    elif rng_data["cross_set_agreement_pct"] > 70:
        L.append("- → BADS 內部隨機性**受 MATLAB rng 控制**(同 seed 跨組落點一致)")
    else:
        L.append("- → 介於兩者之間,rng 部分受控")
    L.append("")

    # 8.2 + 8.3
    L.append("### 8.2 每個 (trial, FOV) 落到主/次 basin(per-FOV nearest-basin)")
    L.append("")
    L.append("用該組主 basin 在 FOV f 的 trial 平均當參考中心,看每個 (trial, FOV) 較靠近誰。")
    L.append("**Mixed trial** = trial 內 9 個視野不是全主也不是全次,代表 BADS 在 trial 內不同 FOV 之間有混合行為。")
    L.append("")
    for name, info in deep["per_fov_basin_preference"].items():
        L.append(f"**{name}** — Trial 內 9 視野全部一致 = 全主 {info['n_trials_all_main_fov']} + 全次 {info['n_trials_all_sec_fov']};混合 {info['n_trials_mixed']};跟 cluster 一致 {info['n_trials_consistent_with_cluster']} / {info['n_trials']}")
        L.append("")
        L.append("| FOV | 落到主 basin 的比例 |")
        L.append("|---|---|")
        for fov, pct in zip(info["fov_indices"], info["per_fov_main_basin_pct"]):
            L.append(f"| #{fov} | {pct:.1%} |")
        L.append("")

    L.append("---")
    L.append("")

    # ===== §9 撞邊細節 =====
    L.append("## 9. 撞邊飽和係數的 lb/ub 分佈跨組")
    L.append("")
    L.append("如果同個係數跨組的撞 lb / 撞 ub 比例一致,代表「隨機選撞哪邊」這個解釋成立;如果偏移,代表撞邊有 systematic preference。")
    L.append("")
    bs_rows = deep["boundary_split"]
    if bs_rows:
        first = bs_rows[0]
        set_cols = [k.replace("_at_lb_pct", "") for k in first.keys() if k.endswith("_at_lb_pct")]
        header = "| 係數 | " + " | ".join(f"{n} lb%/ub%" for n in set_cols) + " |"
        L.append(header)
        L.append("|" + "---|" * (len(set_cols) + 1))
        for r in bs_rows:
            parts = [r["label"]]
            for n in set_cols:
                parts.append(f"{r[f'{n}_at_lb_pct']:.0f}/{r[f'{n}_at_ub_pct']:.0f}")
            L.append("| " + " | ".join(parts) + " |")
        L.append("")

    REPORT_PATH.write_text("\n".join(L), encoding="utf-8")
    print(f"報告已寫入:{REPORT_PATH}")


def write_reference_basins_json(ref_basins: dict) -> None:
    path = SCRIPT_DIR / "reference_basins.json"
    payload = {
        "description": "Reference basins for attribution Test 1 (Layer 1a basin classification). Generated by compare_all_sets.py.",
        "coef_labels": COEF_LABELS,
        **ref_basins,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
    print(f"reference_basins.json 已寫入:{path}")


def main() -> None:
    print(f"讀取 {len(SETS_CONFIG)} 組設定...")
    sets = {}
    for cfg in SETS_CONFIG:
        loaded = load_one_set(cfg["name"], cfg["subdir"])
        if loaded is not None:
            sets[cfg["name"]] = loaded
            raw_str = f"raw={loaded['raw_tensor'].shape}" if loaded["raw_tensor"] is not None else "no raw"
            csv_str = f"csv={len(loaded['per_trial_csv'])} trials" if loaded["per_trial_csv"] is not None else "no csv"
            print(f"  載入 {cfg['name']}:{loaded['n_trials']} trials, best_k={loaded['best_k']}, {raw_str}, {csv_str}")

    if len(sets) < 2:
        print(f"\n至少需要 2 組才能做對比。目前載入 {len(sets)} 組。")
        return

    ref_name = REFERENCE_SET if REFERENCE_SET in sets else list(sets.keys())[0]

    print(f"\n以 {ref_name} 為 reference 做 mode 對齊...")
    alignments = {}
    for name, s in sets.items():
        if name == ref_name:
            continue
        alignments[name] = align_set_to_reference(s, sets[ref_name])
        print(f"  {ref_name} vs {name}: {alignments[name]['aligned_pairs']}")

    print("\n計算基本 summary...")
    ref_basins = compute_reference_basins(sets, ref_name)
    summary = compute_summary(sets, alignments, ref_name, ref_basins)

    print("\n深度分析 §6-9...")
    deep = {}
    print("  6.1 主解佔比 vs noise floor")
    deep["main_prob_vs_noise_floor"] = analyze_main_prob_vs_noise_floor(sets, summary)
    print("  6.2 fval/iter 跨組")
    deep["fval_iter"] = analyze_fval_iter_across_sets(sets)
    print("  6.3 per-FOV main basin std")
    deep["per_fov_main_std"] = analyze_per_fov_main_basin_std(sets, alignments, ref_name)
    print("  7.1 basin centroid 物理意義")
    deep["basin_centroid_physical"] = analyze_basin_centroid_physical(sets, ref_name)
    print("  7.2 basin pair distance 跨組")
    deep["basin_pair_distance"] = analyze_basin_pair_distance(sets)
    print("  7.3 main vs sec basin fval")
    deep["main_vs_sec_fval"] = analyze_main_vs_sec_fval(sets, alignments, ref_name)
    print("  8.1 rng seed → basin 跨組")
    deep["rng_seed_mapping"] = analyze_rng_seed_basin_mapping(sets, alignments, ref_name)
    print("  8.2 per-FOV basin preference")
    deep["per_fov_basin_preference"] = analyze_per_fov_basin_preference(sets, alignments, ref_name)
    print("  9.1 bound_saturated lb/ub split")
    deep["boundary_split"] = analyze_boundary_split_across_sets(sets)

    print("\n寫 JSON...")
    payload = {
        "experiment": f"L0_all_sets_comparison_N{len(sets)}",
        "set_names": list(sets.keys()),
        "alignments": alignments,
        "summary": summary,
        "deep_analysis": deep,
    }
    with JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
    print(f"JSON 寫入:{JSON_PATH}")

    print("寫報告...")
    write_report(sets, alignments, summary, deep)

    print("寫 reference_basins.json...")
    write_reference_basins_json(ref_basins)

    print("\n完成。")


if __name__ == "__main__":
    main()
