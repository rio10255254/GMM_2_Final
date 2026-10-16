"""
deep_analyze_L0.py — L0 深度分析:把所有「基本雜訊資訊」徹底拆開

不只算單一 noise floor 數字。針對 L0 量到的 BADS 行為,系統化拆解:

  Section 1  解結構 (mode discovery)        — BADS 落在幾個不同的 basin?
  Section 2  每個 mode 的內部真實噪聲       — 同一個 basin 內,係數抖動多大?
  Section 3  Mode 之間的距離                — 不同 basin 之間差多少?哪些係數在區分 mode?
  Section 4  撞邊細節                        — 撞 lb 還是 ub?跟 mode 有沒有關係?
  Section 5  死維度的常駐值                  — 那些 std=0 的係數實際收斂到什麼?
  Section 6  隨機種子對 mode 的控制力        — rng(N) 是否可預測落到哪個 mode?
  Section 7  Per-FOV 行為差異                — 不同 FOV 點是否有不同的 mode 偏好?

設計參考:
  PSF_Fitting/quick_recalibration/DESIGN_TW.md §10.2 (L0 層) — 但本腳本超越 DESIGN
  原意,因為發現 PSF fitting 是多解問題,單一 noise floor 不適用。

執行(在 d:/GMM_2_Final/ 跑):
  python PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit/deep_analyze_L0.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import scipy.io as sio
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist, squareform


SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = SCRIPT_DIR / "outputs"
MANIFEST_PATH = OUTPUTS_DIR / "manifest.json"
REPORT_PATH = OUTPUTS_DIR / "L0_deep_analysis_report.md"
JSON_PATH = OUTPUTS_DIR / "deep_analysis.json"

# BADS 搜尋範圍,跟 candidate_prealign.m line 135-136 同步
LB = np.array([-0.3, -0.3, -0.1, 0.0, -0.1, -0.05, -0.05, -0.05, -0.05, -0.01, -0.01, 0.0,  -0.01, -0.01, 0.8 ])
UB = np.array([ 0.3,  0.3,  0.1, 1.0,  0.1,  0.05,  0.05,  0.05,  0.05,  0.01,  0.01, 0.3,   0.01,  0.01, 1.25])

LOCKED_COEF_INDICES = {0, 1}  # x1, x2

COEF_LABELS = [
    "x1 → Z2 Y-tilt (locked=0)",
    "x2 → Z3 X-tilt (locked=0)",
    "x3 → Z4 astig 45° (sin 2φ)",
    "x4 → Z5 defocus",
    "x5 → Z6 astig 0° (cos 2φ)",
    "x6 → Z7 trefoil (sin 3φ)",
    "x7 → Z8 coma Y (sin φ)",
    "x8 → Z9 coma X (cos φ)",
    "x9 → Z10 trefoil (cos 3φ)",
    "x10 → Z11 quadrafoil (sin 4φ)",
    "x11 → Z12 sec astig (sin 2φ)",
    "x12 → Z13 spherical",
    "x13 → Z14 sec astig (cos 2φ)",
    "x14 → Z15 quadrafoil (cos 4φ)",
    "x15 → AC amplitude",
]


# ============================================================================
# Loading
# ============================================================================

def load_data():
    """回傳 (tensor (T, Z, F), manifest, fov_indices, rng_seeds)"""
    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    trial_dirs = manifest["trial_dirs"]
    if isinstance(trial_dirs, str):
        trial_dirs = [trial_dirs]
    psf_root = SCRIPT_DIR.parents[2]  # PSF_Fitting/

    coefs = []
    for td in trial_dirs:
        td_path = Path(td)
        if not td_path.is_absolute():
            td_path = (psf_root / td).resolve()
        data = sio.loadmat(str(td_path / "PSF_fitted_2D_FOVstack.mat"), squeeze_me=False)
        coef = np.asarray(data["coef_grid"])
        if coef.ndim == 3:
            coef = coef[:, 0, :]
        coefs.append(coef)

    tensor = np.stack(coefs, axis=0)
    fov_indices = manifest["fov_indices"]
    if isinstance(fov_indices, (int, float)):
        fov_indices = [int(fov_indices)]
    rng_seeds = manifest.get("rng_seeds", list(range(1, len(coefs) + 1)))
    if isinstance(rng_seeds, (int, float)):
        rng_seeds = [int(rng_seeds)]
    return tensor, manifest, fov_indices, rng_seeds


# ============================================================================
# Section 1: 解結構 (mode discovery via hierarchical clustering)
# ============================================================================

def discover_modes(tensor, max_k=6):
    """
    用 hierarchical clustering 把 trials 分群。

    Strategy: 把每個 trial 的 (Z × F) 攤平成 135-D vector,
    對「不可信維度」(locked + dead = 已知 artifact) 加權降到 0,
    避免 BADS 在這些維度上隨機亂擲影響 clustering。

    回傳 dict 含:
      - linkage_matrix
      - dendrogram_distances
      - best_k (用 inertia gap 自動決定)
      - labels (每 trial 的 mode label,1-indexed)
      - mode_probabilities
    """
    n_trials, n_zern, n_fov = tensor.shape

    # 把不可信維度遮罩掉(locked + 我們等下會偵測的 dead)
    mask = np.ones(n_zern, dtype=bool)
    for ci in LOCKED_COEF_INDICES:
        mask[ci] = False
    # dead 偵測:跨 trial 跨 FOV std < 1e-7
    for ci in range(n_zern):
        if tensor[:, ci, :].std(ddof=1) < 1e-7:
            mask[ci] = False

    flat = tensor[:, mask, :].reshape(n_trials, -1)

    # Pairwise distance + hierarchy
    dist = pdist(flat, metric="euclidean")
    Z_link = linkage(dist, method="ward")

    # 自動找 best_k:看 dendrogram merge distance 哪裡跳最大
    # Z_link[:, 2] 是 merge distance,從小到大
    merge_distances = Z_link[:, 2]  # length = n_trials - 1
    # 對應「split into k groups」的 distance: 從後往前數第 (k-1) 個
    # gap[i] = merge_distances[-i] - merge_distances[-(i+1)]
    # 大 gap 代表 cluster 結構穩定
    candidate_ks = []
    for k in range(2, min(max_k + 1, n_trials)):
        if k - 1 < len(merge_distances):
            cut_dist = merge_distances[-(k - 1)]
            inner_max = merge_distances[-k] if k < len(merge_distances) else 0
            gap = cut_dist - inner_max
            candidate_ks.append((k, cut_dist, gap))

    # 選 gap 最大的 k(但限制 k >= 2)
    if candidate_ks:
        best_k, _, _ = max(candidate_ks, key=lambda x: x[2])
    else:
        best_k = 2

    labels = fcluster(Z_link, t=best_k, criterion="maxclust")

    # Mode probabilities
    unique, counts = np.unique(labels, return_counts=True)
    probs = {int(u): int(c) / n_trials for u, c in zip(unique, counts)}

    return {
        "linkage_matrix": Z_link.tolist(),
        "merge_distances_sorted": sorted(merge_distances.tolist(), reverse=True),
        "candidate_ks": [(int(k), float(d), float(g)) for k, d, g in candidate_ks],
        "best_k": int(best_k),
        "labels": labels.tolist(),
        "mode_probabilities": probs,
        "mask_used": mask.tolist(),
    }


# ============================================================================
# Section 2: 每個 mode 的內部真實噪聲
# ============================================================================

def per_mode_noise(tensor, mode_labels):
    """
    對每個 mode,算內部 (std/mean per coef per FOV)。
    這個才是「在同一 basin 內,BADS 真實的隨機抖動」。
    """
    labels = np.asarray(mode_labels)
    n_trials, n_zern, n_fov = tensor.shape
    modes = sorted(set(labels.tolist()))

    result = {}
    for m in modes:
        idx = np.where(labels == m)[0]
        if len(idx) < 2:
            result[m] = {
                "trial_count": int(len(idx)),
                "trial_indices": idx.tolist(),
                "note": "only 1 trial in this mode, std undefined",
                "internal_std_per_coef_per_fov": None,
                "internal_mean_per_coef_per_fov": tensor[idx].squeeze(0).tolist() if len(idx) == 1 else None,
            }
            continue
        sub = tensor[idx]  # (k, Z, F)
        std_pcf = sub.std(axis=0, ddof=1)
        mean_pcf = sub.mean(axis=0)
        result[m] = {
            "trial_count": int(len(idx)),
            "trial_indices": idx.tolist(),
            "internal_std_per_coef_per_fov": std_pcf.tolist(),
            "internal_mean_per_coef_per_fov": mean_pcf.tolist(),
            "internal_std_per_coef_avg_over_fov": std_pcf.mean(axis=1).tolist(),
            "internal_std_overall_median": float(np.median(std_pcf)),
            "internal_std_overall_mean": float(std_pcf.mean()),
        }
    return result


# ============================================================================
# Section 3: Mode 之間的距離
# ============================================================================

def mode_separations(tensor, mode_labels):
    """
    算 mode centroid 之間的距離,並找出哪些係數對 mode discrimination 最重要。
    """
    labels = np.asarray(mode_labels)
    modes = sorted(set(labels.tolist()))
    n_trials, n_zern, n_fov = tensor.shape

    centroids = {}
    for m in modes:
        idx = np.where(labels == m)[0]
        centroids[m] = tensor[idx].mean(axis=0)  # (Z, F)

    # Pairwise centroid distance (Euclidean, summed over Z×F)
    pair_distances = {}
    discriminator_per_pair = {}
    for i, m1 in enumerate(modes):
        for m2 in modes[i + 1:]:
            diff = centroids[m1] - centroids[m2]  # (Z, F)
            total_dist = float(np.sqrt((diff ** 2).sum()))
            # 哪些 (zern, fov) 點貢獻最多距離?
            per_zern_dist = np.sqrt((diff ** 2).sum(axis=1))  # (Z,)
            top_zern = np.argsort(-per_zern_dist)[:5]
            pair_distances[f"{m1}-{m2}"] = {
                "total_euclidean": total_dist,
                "top_5_discriminator_coefs": [
                    {
                        "idx": int(z),
                        "label": COEF_LABELS[z],
                        "centroid_diff_per_fov": (centroids[m1][z] - centroids[m2][z]).tolist(),
                        "rms_diff": float(per_zern_dist[z]),
                    }
                    for z in top_zern
                ],
            }
    return {
        "mode_centroids_per_coef_per_fov": {m: c.tolist() for m, c in centroids.items()},
        "pairwise_distances": pair_distances,
    }


# ============================================================================
# Section 4: 撞邊細節
# ============================================================================

def boundary_details(tensor):
    """
    對每個係數,看撞 lb / ub 比例與分布。
    """
    n_trials, n_zern, n_fov = tensor.shape
    result = []
    for ci in range(n_zern):
        all_vals = tensor[:, ci, :].flatten()
        n_total = all_vals.size
        tol = 0.01 * max(UB[ci] - LB[ci], 1e-9)
        near_lb = np.abs(all_vals - LB[ci]) < tol
        near_ub = np.abs(all_vals - UB[ci]) < tol
        in_interior = ~(near_lb | near_ub)
        result.append({
            "idx": ci,
            "label": COEF_LABELS[ci],
            "lb": float(LB[ci]),
            "ub": float(UB[ci]),
            "frac_at_lb": float(near_lb.sum() / n_total),
            "frac_at_ub": float(near_ub.sum() / n_total),
            "frac_interior": float(in_interior.sum() / n_total),
            "interior_std": float(all_vals[in_interior].std(ddof=1)) if in_interior.sum() > 1 else None,
            "interior_mean": float(all_vals[in_interior].mean()) if in_interior.sum() > 0 else None,
        })
    return result


# ============================================================================
# Section 5: 死維度
# ============================================================================

def dead_dimensions(tensor):
    """找出跨 trial 跨 FOV 完全不抖的維度,列出常駐值"""
    n_trials, n_zern, n_fov = tensor.shape
    result = []
    for ci in range(n_zern):
        all_vals = tensor[:, ci, :].flatten()
        std = float(all_vals.std(ddof=1)) if n_trials > 1 else 0.0
        if std < 1e-7:
            result.append({
                "idx": ci,
                "label": COEF_LABELS[ci],
                "constant_value": float(all_vals[0]),
                "lb": float(LB[ci]),
                "ub": float(UB[ci]),
                "at_boundary": "lb" if abs(all_vals[0] - LB[ci]) < 0.01 * (UB[ci] - LB[ci])
                                else ("ub" if abs(all_vals[0] - UB[ci]) < 0.01 * (UB[ci] - LB[ci]) else "interior"),
            })
    return result


# ============================================================================
# Section 6: 隨機種子對 mode 的控制力
# ============================================================================

def seed_to_mode_mapping(rng_seeds, mode_labels):
    """看 rng seed 落到哪個 mode,評估 reproducibility"""
    return [
        {"seed": int(s), "mode": int(m)}
        for s, m in zip(rng_seeds, mode_labels)
    ]


# ============================================================================
# Section 7: Per-FOV 行為差異
# ============================================================================

def per_fov_mode_behavior(tensor, mode_labels, fov_indices):
    """看不同 FOV 點是否傾向不同 mode 的解"""
    labels = np.asarray(mode_labels)
    n_trials, n_zern, n_fov = tensor.shape

    # 對每個 FOV,看它在每個 mode 內的 std (mode-specific FOV variability)
    modes = sorted(set(labels.tolist()))
    per_fov_per_mode_std = {}
    for fi in range(n_fov):
        per_fov_per_mode_std[fov_indices[fi]] = {}
        for m in modes:
            idx = np.where(labels == m)[0]
            if len(idx) < 2:
                continue
            sub = tensor[idx, :, fi]  # (k, Z)
            per_fov_per_mode_std[fov_indices[fi]][int(m)] = float(sub.std(axis=0, ddof=1).mean())

    # 對每個 FOV,跨 mode 中位 mean 看 mode 之間在這個 FOV 差多少
    fov_mode_separation = {}
    for fi in range(n_fov):
        mode_means = []
        for m in modes:
            idx = np.where(labels == m)[0]
            if len(idx) < 1:
                continue
            mode_means.append(tensor[idx, :, fi].mean(axis=0))
        if len(mode_means) >= 2:
            mode_means = np.stack(mode_means)
            # 跨 mode 的 std (對每個係數 separate),summed
            sep = float(np.sqrt(mode_means.var(axis=0).sum()))
            fov_mode_separation[fov_indices[fi]] = sep

    return {
        "per_fov_per_mode_internal_std_avg": per_fov_per_mode_std,
        "per_fov_mode_centroid_separation": fov_mode_separation,
    }


# ============================================================================
# Report writing
# ============================================================================

def write_report(payload):
    n_trials = payload["n_trials"]
    fov_indices = payload["fov_indices"]
    mode_info = payload["sec1_modes"]
    per_mode = payload["sec2_per_mode_noise"]
    seps = payload["sec3_mode_separations"]
    boundaries = payload["sec4_boundaries"]
    dead = payload["sec5_dead"]
    seed_map = payload["sec6_seed_to_mode"]
    fov_behavior = payload["sec7_fov_behavior"]

    L = []
    L.append("# L0 深度分析報告")
    L.append("")
    L.append(f"- Trials:{n_trials}")
    L.append(f"- FOV 點數:{len(fov_indices)}(file indices = {fov_indices})")
    L.append(f"- 偵測到的 mode 數:**{mode_info['best_k']}** (用 hierarchical clustering 自動決定)")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Section 1 — 解結構:BADS 落在幾個不同的 basin?")
    L.append("")
    L.append(f"自動偵測出 **{mode_info['best_k']} 個 mode**(用 ward linkage hierarchical clustering,係數 mask 排除 locked + dead)。")
    L.append("")
    L.append("**Mode 機率分佈**:")
    L.append("")
    L.append("| Mode | Trial 數 | 機率 | 對應 trials |")
    L.append("|---|---|---|---|")
    labels = mode_info["labels"]
    modes_sorted = sorted(set(labels))
    for m in modes_sorted:
        trials_in_m = [i + 1 for i, lab in enumerate(labels) if lab == m]
        prob = mode_info["mode_probabilities"].get(m, 0)
        L.append(f"| {m} | {len(trials_in_m)} | {prob:.1%} | {trials_in_m} |")
    L.append("")
    L.append("**Hierarchical clustering 候選 k(看哪個 cut 點 gap 最大):**")
    L.append("")
    L.append("| k | cut distance | gap to next | 選用? |")
    L.append("|---|---|---|---|")
    for k, d, g in mode_info["candidate_ks"]:
        chosen = " ✓ 選用" if k == mode_info["best_k"] else ""
        L.append(f"| {k} | {d:.4f} | {g:.4f} | {chosen} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Section 2 — 每個 mode 的內部真實噪聲(同一 basin 內 BADS 抖多少)")
    L.append("")
    L.append("這才是傳統意義的「演算法 noise floor」。如果 mode 內 trial 數 < 2 則無法算 std。")
    L.append("")
    L.append("| Mode | Trial 數 | 內部 std 中位數 | 內部 std 平均 | 備註 |")
    L.append("|---|---|---|---|---|")
    for m in modes_sorted:
        info = per_mode[m]
        if info.get("internal_std_per_coef_per_fov") is None:
            L.append(f"| {m} | {info['trial_count']} | — | — | {info.get('note', '')} |")
        else:
            L.append(f"| {m} | {info['trial_count']} | {info['internal_std_overall_median']:.5f} | {info['internal_std_overall_mean']:.5f} | |")
    L.append("")
    L.append("**對比參考**:乾淨版 noise floor(`analyze_L0_noise_floor.py` 算的,**忽略 mode 結構**)= 跨 15 trial 直接算 std。")
    L.append("Section 2 的 per-mode 才是「真實 basin 內 BADS 噪聲」,是更小的數字。")
    L.append("")
    # 各 mode 的 per-coef internal std (只列 non-locked 非 dead 係數)
    for m in modes_sorted:
        info = per_mode[m]
        if info.get("internal_std_per_coef_avg_over_fov") is None:
            continue
        L.append(f"### Mode {m} 內部 std (跨 9 FOV 平均)")
        L.append("")
        L.append("| 係數 | 內部 std (avg over FOV) |")
        L.append("|---|---|")
        for ci, std_val in enumerate(info["internal_std_per_coef_avg_over_fov"]):
            L.append(f"| {COEF_LABELS[ci]} | {std_val:.5f} |")
        L.append("")
    L.append("---")
    L.append("")
    L.append("## Section 3 — Mode 之間的距離(BADS 不同解差多少?)")
    L.append("")
    for pair_key, pair_info in seps["pairwise_distances"].items():
        L.append(f"### {pair_key}")
        L.append(f"- **總 Euclidean 距離(在 (Z×F) 空間)**:{pair_info['total_euclidean']:.4f}")
        L.append(f"- **最能 discriminate 這對 mode 的 5 個係數**:")
        L.append("")
        L.append("| 係數 | RMS diff (跨 FOV) |")
        L.append("|---|---|")
        for entry in pair_info["top_5_discriminator_coefs"]:
            L.append(f"| {entry['label']} | {entry['rms_diff']:.5f} |")
        L.append("")
    L.append("---")
    L.append("")
    L.append("## Section 4 — 撞邊細節(撞 lb 還是 ub?)")
    L.append("")
    L.append("| 係數 | lb | ub | 撞 lb % | 撞 ub % | 內部 % | 內部 std |")
    L.append("|---|---|---|---|---|---|---|")
    for b in boundaries:
        interior_std = f"{b['interior_std']:.5f}" if b["interior_std"] is not None else "—"
        L.append(
            f"| {b['label']} | {b['lb']:+.3f} | {b['ub']:+.3f} | "
            f"{b['frac_at_lb']*100:.0f}% | {b['frac_at_ub']*100:.0f}% | "
            f"{b['frac_interior']*100:.0f}% | {interior_std} |"
        )
    L.append("")
    L.append("**讀法**:")
    L.append("- 撞 lb % + 撞 ub % > 80%:該係數的「噪聲」是「隨機選撞哪邊」(artifact)")
    L.append("- 撞 lb % > 30% 但 < 撞 ub %:解空間在 lb 那側可能更不確定")
    L.append("- 內部 % 高且內部 std 小:該係數真實量到了 BADS 收斂噪聲")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Section 5 — 死維度(完全沒抖動的常駐值)")
    L.append("")
    if not dead:
        L.append("(沒有死維度)")
    else:
        L.append("| 係數 | 常駐值 | lb / ub | 位置 |")
        L.append("|---|---|---|---|")
        for d in dead:
            L.append(f"| {d['label']} | {d['constant_value']:+.5f} | {d['lb']:+.3f} / {d['ub']:+.3f} | {d['at_boundary']} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Section 6 — 隨機種子對 mode 的控制力")
    L.append("")
    L.append("rng(N) 切換是否可預測落到哪個 mode?如果可預測,L0 的隨機性策略有效;如果隨機,代表 BADS 內部某些 RandStream 不受 MATLAB rng 控制。")
    L.append("")
    L.append("| RNG seed | Mode |")
    L.append("|---|---|")
    for entry in seed_map:
        L.append(f"| rng({entry['seed']}) | {entry['mode']} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Section 7 — Per-FOV 行為差異")
    L.append("")
    L.append("### 7.1 各 FOV 點在不同 mode 內的內部 std 平均")
    L.append("")
    header = ["FOV"] + [f"Mode {m}" for m in modes_sorted]
    L.append("| " + " | ".join(header) + " |")
    L.append("|" + "---|" * len(header))
    for fov in fov_indices:
        row = [f"#{fov}"]
        for m in modes_sorted:
            v = fov_behavior["per_fov_per_mode_internal_std_avg"].get(fov, {}).get(m)
            row.append(f"{v:.5f}" if v is not None else "—")
        L.append("| " + " | ".join(row) + " |")
    L.append("")
    L.append("### 7.2 各 FOV 點上,mode 中心之間分離度")
    L.append("(數字大代表這個 FOV 是 mode discriminator)")
    L.append("")
    L.append("| FOV | Mode centroid separation |")
    L.append("|---|---|")
    for fov, sep in fov_behavior["per_fov_mode_centroid_separation"].items():
        L.append(f"| #{fov} | {sep:.4f} |")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 全局結論")
    L.append("")
    n_modes = mode_info["best_k"]
    if n_modes == 1:
        L.append("- BADS 收斂到單一 basin。傳統 noise floor 概念適用,直接用 `analyze_L0_noise_floor.py` 結果。")
    else:
        # 算每個 mode 內的 std 跟 mode 之間距離的比例
        internal_stds = []
        for m in modes_sorted:
            info = per_mode[m]
            if info.get("internal_std_overall_mean") is not None:
                internal_stds.append(info["internal_std_overall_mean"])
        avg_internal = float(np.mean(internal_stds)) if internal_stds else float("nan")
        avg_separation = float(np.mean([p["total_euclidean"] for p in seps["pairwise_distances"].values()]))
        ratio = avg_separation / avg_internal if avg_internal > 1e-9 else float("inf")
        L.append(f"- BADS 在這個 PSF 擬合問題上會落在 **{n_modes} 個不同 basin**。")
        L.append(f"- **Mode 內部平均 std**:{avg_internal:.5f}(這才是真實「演算法收斂噪聲」)")
        L.append(f"- **Mode 之間平均分離**:{avg_separation:.4f}")
        L.append(f"- **分離 / 內部 std 比例**:{ratio:.0f}x")
        if ratio > 100:
            L.append(f"  → **遠大於 1**:mode 之間區別清晰,後續 attribution 應該分兩層處理:")
            L.append(f"    1. 先判別 trial 落在哪個 mode")
            L.append(f"    2. 再用對應 mode 的 internal noise floor 算 z-score")
        else:
            L.append(f"  → mode 之間分離不夠大,可能需要更精細的 cluster 或重新檢視 mode 偵測閾值")
    L.append("")
    L.append("## 後續建議")
    L.append("")
    L.append("根據本深度分析,後續設計選擇:")
    L.append("")
    L.append("1. **Attribution 改成兩層**:先判 mode、再算 mode-internal z-score(如全局結論建議)")
    L.append("2. **Mode 機率納入治理**:如果 mode 出現機率不對稱(例如 mode 1 = 53%, mode 2 = 40%, mode 3 = 27%),代表 BADS 對不同 basin 有偏好,L1 之後要重新驗證這個機率分佈穩不穩定(同機台重拍時 mode 機率會變嗎?)")
    L.append("3. **撞邊係數的處理**:全部標記為 untrustworthy,不參與 noise floor 計算 → 已在 `analyze_L0_noise_floor.py` 實作")
    L.append("4. **死維度**:跳過 attribution 計算,因為 std=0 會讓 z-score 爆炸")
    L.append("")
    REPORT_PATH.write_text("\n".join(L), encoding="utf-8")
    print(f"報告已寫入:{REPORT_PATH}")


# ============================================================================
# Main
# ============================================================================

def main():
    print("讀取 manifest 跟 trial 資料...")
    tensor, manifest, fov_indices, rng_seeds = load_data()
    n_trials, n_zern, n_fov = tensor.shape
    print(f"  shape = {tensor.shape}  (trials, zernike, fov)")

    print("Section 1: 解結構偵測...")
    sec1 = discover_modes(tensor)
    print(f"  best_k = {sec1['best_k']},機率 = {sec1['mode_probabilities']}")

    print("Section 2: 每 mode 內部噪聲...")
    sec2 = per_mode_noise(tensor, sec1["labels"])

    print("Section 3: Mode 間距離...")
    sec3 = mode_separations(tensor, sec1["labels"])

    print("Section 4: 撞邊細節...")
    sec4 = boundary_details(tensor)

    print("Section 5: 死維度...")
    sec5 = dead_dimensions(tensor)

    print("Section 6: 種子 → mode 對應...")
    sec6 = seed_to_mode_mapping(rng_seeds, sec1["labels"])

    print("Section 7: Per-FOV 行為...")
    sec7 = per_fov_mode_behavior(tensor, sec1["labels"], fov_indices)

    payload = {
        "experiment": "L0_deep_analysis",
        "n_trials": n_trials,
        "n_zernike": n_zern,
        "n_fov": n_fov,
        "fov_indices": fov_indices,
        "rng_seeds": rng_seeds,
        "sec1_modes": sec1,
        "sec2_per_mode_noise": sec2,
        "sec3_mode_separations": sec3,
        "sec4_boundaries": sec4,
        "sec5_dead": sec5,
        "sec6_seed_to_mode": sec6,
        "sec7_fov_behavior": sec7,
    }

    print("寫 JSON...")
    with JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
    print(f"JSON 寫入:{JSON_PATH}")

    print("寫報告...")
    write_report(payload)

    print("\n完成。")


if __name__ == "__main__":
    main()
