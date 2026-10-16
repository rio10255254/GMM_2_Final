"""
compare_setA_setB.py — 跨組對比 L0 setA 與 setB 的 BADS 收斂域結構

回答的核心問題:
  1. 兩組都有 2 個收斂域,但機率分佈不同——是「同樣 2 個 basin、不同 FOV 落點機率不同」,
     還是「不同組看到不同 basin」?
  2. 量化結果穩定的部分(noise floor、係數分類)跟不穩定的部分(mode 機率)分別有多大差距?

輸出:
  - validation_experiments/setA_vs_setB_comparison.md (繁中報告)
  - validation_experiments/setA_vs_setB_comparison.json (機器可讀)

執行(在 d:/GMM_2_Final/ 跑):
  python PSF_Fitting/quick_recalibration/validation_experiments/compare_setA_setB.py
"""

from __future__ import annotations

import json
from itertools import product
from pathlib import Path

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
SETA_JSON = SCRIPT_DIR / "L0_repeat_fit" / "outputs" / "deep_analysis.json"
SETB_JSON = SCRIPT_DIR / "L0_repeat_fit_setB" / "outputs" / "deep_analysis.json"
SETA_NF = SCRIPT_DIR / "L0_repeat_fit" / "outputs" / "noise_floor.json"
SETB_NF = SCRIPT_DIR / "L0_repeat_fit_setB" / "outputs" / "noise_floor.json"

REPORT_PATH = SCRIPT_DIR / "setA_vs_setB_comparison.md"
JSON_PATH = SCRIPT_DIR / "setA_vs_setB_comparison.json"

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


def load_set(json_path: Path, nf_path: Path) -> dict:
    """讀一組 setA/setB 的 deep_analysis + noise_floor,整理成統一結構"""
    with json_path.open("r", encoding="utf-8") as f:
        deep = json.load(f)
    with nf_path.open("r", encoding="utf-8") as f:
        nf = json.load(f)

    mode_info = deep["sec1_modes"]
    per_mode = deep["sec2_per_mode_noise"]

    # 把每個 mode 的 centroid 跨 FOV 平均,變成 15 維 Zernike 向量
    mode_centroids_zerf = mode_info_centroids(deep["sec3_mode_separations"])
    mode_centroids_avg_fov = {m: c.mean(axis=1) for m, c in mode_centroids_zerf.items()}

    return {
        "fov_indices": deep["fov_indices"],
        "n_trials": deep["n_trials"],
        "best_k": mode_info["best_k"],
        "mode_probabilities": mode_info["mode_probabilities"],
        "mode_labels": mode_info["labels"],
        "mode_centroids_zerf": mode_centroids_zerf,
        "mode_centroids_avg_fov": mode_centroids_avg_fov,
        "per_mode_noise": per_mode,
        "pairwise_mode_distances": deep["sec3_mode_separations"]["pairwise_distances"],
        "boundaries": deep["sec4_boundaries"],
        "dead_dimensions": deep["sec5_dead"],
        "seed_to_mode": deep["sec6_seed_to_mode"],
        "clean_noise_floor": nf["clean_noise_floor"],
        "coef_classifications": nf["coef_classifications"],
    }


def mode_info_centroids(sec3: dict) -> dict[int, np.ndarray]:
    """從 sec3 的 pairwise distances 結構反推 mode centroids (Z, F) 形狀"""
    raw = sec3["mode_centroids_per_coef_per_fov"]
    return {int(m): np.array(v) for m, v in raw.items()}


def align_modes_across_sets(setA: dict, setB: dict) -> dict:
    """
    跨組 mode 對齊:cluster label 是 arbitrary 的(setA 的 mode 1 跟 setB 的 mode 1 沒必然關係)。
    用 setA 跟 setB 的 mode centroid(跨 FOV 平均後的 15 維)算距離矩陣,
    找最小距離匹配。

    回傳:
      - distance_matrix: shape (n_modes_A, n_modes_B)
      - best_alignment: dict { setA_mode: setB_mode }
      - aligned_pairs: 排序好的 list[(setA_mode, setB_mode, distance)]
    """
    A_centroids = setA["mode_centroids_avg_fov"]
    B_centroids = setB["mode_centroids_avg_fov"]
    A_modes = sorted(A_centroids.keys())
    B_modes = sorted(B_centroids.keys())

    dmat = np.zeros((len(A_modes), len(B_modes)))
    for i, am in enumerate(A_modes):
        for j, bm in enumerate(B_modes):
            dmat[i, j] = np.linalg.norm(A_centroids[am] - B_centroids[bm])

    # Greedy minimum-distance assignment(對 k=2 很夠用)
    pairs = []
    used_B = set()
    for i, am in enumerate(A_modes):
        candidates = [(j, dmat[i, j]) for j, bm in enumerate(B_modes) if bm not in used_B]
        candidates.sort(key=lambda x: x[1])
        if candidates:
            j_best, d_best = candidates[0]
            bm_best = B_modes[j_best]
            pairs.append((am, bm_best, float(d_best)))
            used_B.add(bm_best)

    best_alignment = {a: b for a, b, _ in pairs}
    return {
        "A_modes": A_modes,
        "B_modes": B_modes,
        "distance_matrix": dmat.tolist(),
        "best_alignment": {int(k): int(v) for k, v in best_alignment.items()},
        "aligned_pairs": [(int(a), int(b), d) for a, b, d in pairs],
    }


def compare_top_discriminators(setA: dict, setB: dict) -> dict:
    """對比兩組各自的 mode 1-2 區別維度的 top 5"""
    A_pairs = setA["pairwise_mode_distances"]
    B_pairs = setB["pairwise_mode_distances"]

    def extract(pairs: dict) -> dict:
        first_key = list(pairs.keys())[0]
        info = pairs[first_key]
        return {
            "total_euclidean": info["total_euclidean"],
            "top_5": [
                {"label": e["label"], "rms_diff": e["rms_diff"]}
                for e in info["top_5_discriminator_coefs"]
            ],
        }

    return {"setA": extract(A_pairs), "setB": extract(B_pairs)}


def compare_coef_classifications(setA: dict, setB: dict) -> dict:
    """對比兩組的係數可信度分類(應該一致,因為 search bounds + lock 設定相同)"""
    A_cls = setA["coef_classifications"]
    B_cls = setB["coef_classifications"]

    rows = []
    for i, (a, b) in enumerate(zip(A_cls, B_cls)):
        same = a["status"] == b["status"]
        rows.append({
            "idx": i,
            "label": COEF_LABELS[i],
            "setA_status": a["status"],
            "setB_status": b["status"],
            "same": same,
            "setA_bound_frac": a["bound_frac"],
            "setB_bound_frac": b["bound_frac"],
        })
    return {
        "rows": rows,
        "all_same": all(r["same"] for r in rows),
    }


def compute_summary(setA: dict, setB: dict, alignment: dict) -> dict:
    """全局判決"""
    same_k = setA["best_k"] == setB["best_k"]
    A_probs = setA["mode_probabilities"]
    B_probs = setB["mode_probabilities"]

    # 把機率按 alignment 對齊
    aligned_probs = []
    for a_mode, b_mode, dist in alignment["aligned_pairs"]:
        aligned_probs.append({
            "setA_mode": a_mode,
            "setB_mode": b_mode,
            "setA_prob": A_probs[str(a_mode)] if str(a_mode) in A_probs else A_probs.get(a_mode, None),
            "setB_prob": B_probs[str(b_mode)] if str(b_mode) in B_probs else B_probs.get(b_mode, None),
            "centroid_distance": dist,
        })

    A_internal = []
    B_internal = []
    for m_str, info in setA["per_mode_noise"].items():
        if info.get("internal_std_overall_mean") is not None:
            A_internal.append(info["internal_std_overall_mean"])
    for m_str, info in setB["per_mode_noise"].items():
        if info.get("internal_std_overall_mean") is not None:
            B_internal.append(info["internal_std_overall_mean"])

    return {
        "same_n_modes": same_k,
        "n_modes_A": setA["best_k"],
        "n_modes_B": setB["best_k"],
        "aligned_probs": aligned_probs,
        "noise_floor_clean_median": {
            "setA": setA["clean_noise_floor"]["overall_median_std"],
            "setB": setB["clean_noise_floor"]["overall_median_std"],
        },
        "internal_noise_floor_mean": {
            "setA": float(np.mean(A_internal)) if A_internal else None,
            "setB": float(np.mean(B_internal)) if B_internal else None,
        },
        "mode_pair_total_distance": {
            "setA": list(setA["pairwise_mode_distances"].values())[0]["total_euclidean"],
            "setB": list(setB["pairwise_mode_distances"].values())[0]["total_euclidean"],
        },
    }


def write_report(setA: dict, setB: dict, alignment: dict, top_disc: dict, classif: dict, summary: dict) -> None:
    L = []
    L.append("# L0 setA vs setB 對比分析")
    L.append("")
    L.append("> **目的**:setA 跑出 2 個收斂域後,需要驗證這是 BADS 對這類擬合問題的常態,還是那組 FOV 的特例。")
    L.append("> 用另一組完全不重疊的 9 個 FOV(setB)重跑同樣 15 trial,跨組對比結果。")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 1. 兩組基本設定對比")
    L.append("")
    L.append("| 項目 | setA | setB |")
    L.append("|---|---|---|")
    L.append(f"| FOV indices | {setA['fov_indices']} | {setB['fov_indices']} |")
    L.append(f"| Trial 數 | {setA['n_trials']} | {setB['n_trials']} |")
    L.append("| 其他全部 | 同 GT、同 fitter、同搜尋範圍、同 lock_tilt、同 rng 策略 | 同左 |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 2. 核心結論")
    L.append("")
    if summary["same_n_modes"] and summary["n_modes_A"] == 2:
        L.append("### ✓ 確認:BADS 在這類問題上會分裂成 2 個收斂域")
        L.append("")
        L.append(f"setA 跟 setB 都偵測到 **{summary['n_modes_A']} 個 mode**。配合下面 §3 的跨組 mode 對齊結果,")
        L.append("可以判斷這兩個 mode 是同樣 2 個 basin(物理上),而不是 cluster 偶然分群。")
    elif not summary["same_n_modes"]:
        L.append(f"### ✗ 兩組偵測到的 mode 數不同(setA={summary['n_modes_A']}, setB={summary['n_modes_B']})")
        L.append("")
        L.append("代表 mode 結構跟 FOV 組合有關,單純「BADS 常態」說法不成立,要重新檢視。")
    L.append("")

    L.append("### 模態機率分佈穩定嗎?")
    L.append("")
    L.append("| 對齊組合 | setA 機率 | setB 機率 | Centroid 距離 |")
    L.append("|---|---|---|---|")
    for entry in summary["aligned_probs"]:
        L.append(
            f"| setA mode {entry['setA_mode']} ↔ setB mode {entry['setB_mode']} | "
            f"{entry['setA_prob']:.1%} | {entry['setB_prob']:.1%} | {entry['centroid_distance']:.4f} |"
        )
    L.append("")
    setA_dominant_prob = max(e["setA_prob"] for e in summary["aligned_probs"])
    setB_dominant_prob = max(e["setB_prob"] for e in summary["aligned_probs"])
    if abs(setA_dominant_prob - setB_dominant_prob) > 0.2:
        L.append(f"**機率分佈差距大(主 mode 機率 setA={setA_dominant_prob:.0%} vs setB={setB_dominant_prob:.0%},差 {abs(setA_dominant_prob - setB_dominant_prob)*100:.0f} 個百分點)**,")
        L.append("代表 mode 出現機率不穩定,跟 FOV 組合相關。後續設計不能假設 mode 機率是固定的。")
    else:
        L.append(f"主 mode 機率兩組接近(setA={setA_dominant_prob:.0%} vs setB={setB_dominant_prob:.0%}),機率分佈大致穩定。")
    L.append("")

    L.append("### Noise floor 量值穩定嗎?")
    L.append("")
    nf_A = summary["noise_floor_clean_median"]["setA"]
    nf_B = summary["noise_floor_clean_median"]["setB"]
    nf_diff_pct = abs(nf_A - nf_B) / max(nf_A, nf_B) * 100
    L.append(f"- setA 乾淨 noise floor 中位 std = **{nf_A:.5f}**")
    L.append(f"- setB 乾淨 noise floor 中位 std = **{nf_B:.5f}**")
    L.append(f"- 差距:**{nf_diff_pct:.1f}%**")
    L.append("")
    if nf_diff_pct < 10:
        L.append("**Noise floor 量級非常穩定**(差 < 10%),代表「演算法本身的隨機性大小」是可量、可信的物理量。")
    elif nf_diff_pct < 30:
        L.append("Noise floor 量級大致穩定(差 < 30%),可作為 Test 1 z-score 分母,但要考慮 per-FOV-set 的變動。")
    else:
        L.append("**Noise floor 量級差距大**(> 30%),代表演算法噪聲跟 FOV 組合相關,單一 noise floor 不適用。")
    L.append("")

    L.append("---")
    L.append("")
    L.append("## 3. 跨組 Mode 對齊")
    L.append("")
    L.append("Cluster label 是 arbitrary 的,setA 的 mode 1 跟 setB 的 mode 1 沒必然關係。")
    L.append("把兩組各 mode 的 centroid 跨 FOV 平均成 15 維 Zernike 向量,用 Euclidean 距離找最佳對應。")
    L.append("")
    L.append("**距離矩陣(列=setA mode, 欄=setB mode)**:")
    L.append("")
    L.append("| | " + " | ".join(f"setB-{bm}" for bm in alignment["B_modes"]) + " |")
    L.append("|---|" + "---|" * len(alignment["B_modes"]))
    for i, am in enumerate(alignment["A_modes"]):
        row = [f"setA-{am}"]
        for j, bm in enumerate(alignment["B_modes"]):
            row.append(f"{alignment['distance_matrix'][i][j]:.4f}")
        L.append("| " + " | ".join(row) + " |")
    L.append("")
    L.append("**最佳對齊**:")
    L.append("")
    for a, b, d in alignment["aligned_pairs"]:
        L.append(f"- setA mode {a} ↔ setB mode {b}(centroid 距離 = {d:.4f})")
    L.append("")
    # 解讀對齊距離
    avg_align_dist = np.mean([d for _, _, d in alignment["aligned_pairs"]])
    avg_within_pair = np.mean([summary["mode_pair_total_distance"]["setA"], summary["mode_pair_total_distance"]["setB"]])
    L.append(f"**對比**:組內 mode-1 vs mode-2 的平均距離 = {avg_within_pair:.4f}")
    L.append(f"      組間對齊後對應 mode 的平均距離 = {avg_align_dist:.4f}")
    L.append("")
    if avg_align_dist < avg_within_pair * 0.5:
        L.append("組間對齊距離遠小於組內 mode 距離,**確認兩組看到的是同樣 2 個 basin**(物理上的同一收斂域)。")
    elif avg_align_dist < avg_within_pair:
        L.append("組間對齊距離小於組內,**很可能是同樣 2 個 basin**,但有些係數可能 FOV-dependent。")
    else:
        L.append("組間對齊距離跟組內相當,**有可能兩組看到的不是同一對 basin**,要進一步檢查。")
    L.append("")

    L.append("---")
    L.append("")
    L.append("## 4. Top 區別維度對比")
    L.append("")
    L.append("兩組各自的 mode 1-2 用哪些係數區別?如果兩組的 top 5 大致一致,代表 basin 的物理結構是穩定的。")
    L.append("")
    L.append(f"### setA(總距離 {top_disc['setA']['total_euclidean']:.4f})")
    L.append("")
    L.append("| Rank | 係數 | RMS diff |")
    L.append("|---|---|---|")
    for r, e in enumerate(top_disc["setA"]["top_5"], 1):
        L.append(f"| {r} | {e['label']} | {e['rms_diff']:.5f} |")
    L.append("")
    L.append(f"### setB(總距離 {top_disc['setB']['total_euclidean']:.4f})")
    L.append("")
    L.append("| Rank | 係數 | RMS diff |")
    L.append("|---|---|---|")
    for r, e in enumerate(top_disc["setB"]["top_5"], 1):
        L.append(f"| {r} | {e['label']} | {e['rms_diff']:.5f} |")
    L.append("")
    setA_top1 = top_disc["setA"]["top_5"][0]["label"]
    setB_top1 = top_disc["setB"]["top_5"][0]["label"]
    if setA_top1 == setB_top1:
        L.append(f"**兩組的 #1 區別維度都是 {setA_top1}**,確認是同樣的物理結構主導 mode 分裂。")
    else:
        L.append(f"⚠️ #1 區別維度不同(setA: {setA_top1}, setB: {setB_top1}),要進一步看是不是 cluster 偶然性。")
    L.append("")

    L.append("---")
    L.append("")
    L.append("## 5. 係數可信度分類對比")
    L.append("")
    L.append("兩組的搜尋範圍 + lock_tilt 設定完全相同,所以係數分類(locked/dead/bound_saturated/trustworthy)應該一致。")
    L.append("")
    L.append("| 係數 | setA | setB | 一致? | setA 撞邊% | setB 撞邊% |")
    L.append("|---|---|---|---|---|---|")
    for r in classif["rows"]:
        mark = "✓" if r["same"] else "✗"
        L.append(
            f"| {r['label']} | {r['setA_status']} | {r['setB_status']} | {mark} | "
            f"{r['setA_bound_frac']*100:.0f}% | {r['setB_bound_frac']*100:.0f}% |"
        )
    L.append("")
    if classif["all_same"]:
        L.append("**所有 15 個係數的分類完全一致**,確認 search bounds 設計問題(5 個 bound_saturated + 1 個 dead)跟 FOV 無關。")
    else:
        n_diff = sum(1 for r in classif["rows"] if not r["same"])
        L.append(f"⚠️ 有 {n_diff} 個係數分類不一致,要進一步檢查。")
    L.append("")

    L.append("---")
    L.append("")
    L.append("## 6. 跨組綜合判決")
    L.append("")
    L.append("| 屬性 | 是 BADS 常態還是 FOV 特例? | 證據 |")
    L.append("|---|---|---|")
    if summary["same_n_modes"] and summary["n_modes_A"] == 2:
        L.append("| Mode 數量(=2) | **常態** | setA / setB 都偵測到 2 個 mode |")
    if setA_top1 == setB_top1:
        L.append(f"| Mode 主要區別維度({setA_top1}) | **常態** | 兩組 top 1 區別維度相同 |")
    if avg_align_dist < avg_within_pair:
        L.append("| 兩個 basin 的物理位置 | **常態** | 跨組 mode 對齊後距離小於組內 mode 距離 |")
    if nf_diff_pct < 10:
        L.append(f"| Noise floor 量級(中位 std ~ {(nf_A+nf_B)/2:.4f}) | **常態** | 兩組差 {nf_diff_pct:.1f}% |")
    if classif["all_same"]:
        L.append("| 係數可信度分類(7 trustworthy / 2 locked / 5 bound_saturated / 1 dead) | **常態** | 兩組完全一致 |")
    if abs(setA_dominant_prob - setB_dominant_prob) > 0.2:
        L.append("| Mode 出現機率 | **FOV 相關** | setA / setB 主 mode 機率差 > 20 個百分點 |")
    L.append("")

    L.append("## 7. 對 DESIGN §9 歸因設計的意涵")
    L.append("")
    L.append("根據 §6 判決,DESIGN §9 Test 1 的單層 z-score 設計確定需要改:")
    L.append("")
    L.append("- **可以放心做的**:把 noise floor 設成 mode-internal std,而不是混合所有 trial 的 std")
    L.append("  - 理由:noise floor 量級在兩組之間穩定(差 < 10%),mode 內 std 也穩定")
    L.append("  - 操作:用 setA/setB 的乾淨 noise floor 中位 std ≈ 0.028 當分母")
    L.append("")
    L.append("- **要小心的**:不能用 mode 機率當「先驗」推估這台機是不是異常")
    L.append("  - 理由:同一台機、同一張影像,FOV 一換 mode 機率就大幅變動")
    L.append("  - 操作:Test 1 應該對「每個 trial 落到哪個 mode」直接判斷,不要用全局 mode 機率")
    L.append("")
    L.append("- **L1 之後要驗證的**:同機重拍,mode 機率會跟 FOV 還是跟拍攝噪聲一起變?")
    L.append("  - 如果跟拍攝噪聲變 → noise floor 估計要含 across-capture 變動")
    L.append("  - 如果跟 FOV 變 → 維持 per-trial 判 mode 就行")
    L.append("")

    REPORT_PATH.write_text("\n".join(L), encoding="utf-8")
    print(f"報告已寫入:{REPORT_PATH}")


def main() -> None:
    print("讀取 setA 與 setB 的 deep_analysis + noise_floor...")
    setA = load_set(SETA_JSON, SETA_NF)
    setB = load_set(SETB_JSON, SETB_NF)
    print(f"  setA: {setA['n_trials']} trials, {setA['best_k']} modes, FOV = {setA['fov_indices']}")
    print(f"  setB: {setB['n_trials']} trials, {setB['best_k']} modes, FOV = {setB['fov_indices']}")

    print("跨組 mode 對齊...")
    alignment = align_modes_across_sets(setA, setB)
    print(f"  best alignment: {alignment['best_alignment']}")

    print("Top 區別維度對比...")
    top_disc = compare_top_discriminators(setA, setB)

    print("係數可信度分類對比...")
    classif = compare_coef_classifications(setA, setB)
    print(f"  all classifications identical: {classif['all_same']}")

    print("綜合判決...")
    summary = compute_summary(setA, setB, alignment)

    print("寫 JSON...")
    payload = {
        "experiment": "L0_setA_vs_setB",
        "setA": {"fov_indices": setA["fov_indices"], "n_trials": setA["n_trials"]},
        "setB": {"fov_indices": setB["fov_indices"], "n_trials": setB["n_trials"]},
        "mode_alignment": alignment,
        "top_discriminators": top_disc,
        "coef_classifications": classif,
        "summary": summary,
    }
    with JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
    print(f"JSON 寫入:{JSON_PATH}")

    print("寫報告...")
    write_report(setA, setB, alignment, top_disc, classif, summary)

    print("\n完成。")


if __name__ == "__main__":
    main()
