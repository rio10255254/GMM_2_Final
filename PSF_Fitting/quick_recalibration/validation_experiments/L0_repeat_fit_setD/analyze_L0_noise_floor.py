"""
analyze_L0_noise_floor.py

讀取 run_L0_repeat_fit.m 跑出來的 N 個 trial,計算每個 FOV 點、
每個 Zernike 係數的跨 trial std/MAD,輸出 noise_floor 矩陣與繁中報告。

設計參考:
  PSF_Fitting/quick_recalibration/DESIGN_TW.md §10.6.1
  PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit/README_TW.md §6

執行方式(在 d:/GMM_2_Final/ 跑):
  python PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit/analyze_L0_noise_floor.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import scipy.io as sio


SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = SCRIPT_DIR / "outputs"
MANIFEST_PATH = OUTPUTS_DIR / "manifest.json"
REPORT_PATH = OUTPUTS_DIR / "L0_noise_floor_report.md"
NOISE_FLOOR_JSON = OUTPUTS_DIR / "noise_floor.json"

# BADS 搜尋範圍,跟 candidate_prealign.m line 135-136 同步。
# 如果未來 fitter 修改 lb/ub,這裡也要改。
LB = np.array([-0.3, -0.3, -0.1, 0.0, -0.1, -0.05, -0.05, -0.05, -0.05, -0.01, -0.01, 0.0,  -0.01, -0.01, 0.8 ])
UB = np.array([ 0.3,  0.3,  0.1, 1.0,  0.1,  0.05,  0.05,  0.05,  0.05,  0.01,  0.01, 0.3,   0.01,  0.01, 1.25])

# 哪些係數是 lock_tilt 強制鎖死的(對 loss 沒影響,BADS 隨便擲)
LOCKED_COEF_INDICES = {0, 1}  # x1 (Z2 Y-tilt), x2 (Z3 X-tilt)


def classify_coef(coef_idx: int, all_values: np.ndarray) -> dict:
    """
    判定一個係數是否可信作為 noise floor 來源。

    回傳 dict 含:
      - status: 'trustworthy' / 'locked' / 'bound_saturated' / 'dead'
      - reason: 人讀說明
      - bound_frac: 撞邊比例(0-1)
      - unique_count: 跨全部 trial × FOV 的不重複值數量
    """
    n_total = all_values.size
    unique_vals = np.unique(np.round(all_values, decimals=8))
    unique_count = len(unique_vals)
    overall_std = float(all_values.std(ddof=1)) if n_total > 1 else 0.0

    near_lb = np.abs(all_values - LB[coef_idx]) < 0.01 * max(UB[coef_idx] - LB[coef_idx], 1e-9)
    near_ub = np.abs(all_values - UB[coef_idx]) < 0.01 * max(UB[coef_idx] - LB[coef_idx], 1e-9)
    bound_frac = float((near_lb | near_ub).sum()) / n_total

    if coef_idx in LOCKED_COEF_INDICES:
        return {
            "status": "locked",
            "reason": "lock_tilt=true 強制 Z(2)/Z(3)=0,對 loss 無影響;BADS 隨便擲值",
            "bound_frac": bound_frac,
            "unique_count": int(unique_count),
            "overall_std": overall_std,
        }
    if overall_std < 1e-7:
        return {
            "status": "dead",
            "reason": "跨全部 trial × FOV 完全相同(std≈0);BADS 對此維度收斂得很死,沒有可量噪聲",
            "bound_frac": bound_frac,
            "unique_count": int(unique_count),
            "overall_std": overall_std,
        }
    if bound_frac > 0.8:
        return {
            "status": "bound_saturated",
            "reason": f"{bound_frac*100:.0f}% 的值撞 search bounds [{LB[coef_idx]:+.3f}, {UB[coef_idx]:+.3f}];噪聲是「隨機選撞哪邊」,非真實演算法噪聲",
            "bound_frac": bound_frac,
            "unique_count": int(unique_count),
            "overall_std": overall_std,
        }
    return {
        "status": "trustworthy",
        "reason": f"std=±{overall_std:.5f},在 search bounds 內部(撞邊 {bound_frac*100:.0f}%)",
        "bound_frac": bound_frac,
        "unique_count": int(unique_count),
        "overall_std": overall_std,
    }


def load_manifest() -> dict:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(
            f"找不到 {MANIFEST_PATH}。請先在 MATLAB 跑 run_L0_repeat_fit.m。"
        )
    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_trial_coefs(trial_dir: Path) -> np.ndarray:
    """
    讀單一 trial 的 PSF_fitted_2D_FOVstack.mat,回傳 coef_grid。

    coef_grid 在 reasonable_v1 / candidate_prealign 寫出來時的形狀:
      shape = (n_zernike, 1, n_fov)  ← MATLAB 端是 (15, 1, 9)
    我們把它 squeeze 到 (n_zernike, n_fov)。
    """
    stack_path = trial_dir / "PSF_fitted_2D_FOVstack.mat"
    if not stack_path.is_file():
        raise FileNotFoundError(f"{stack_path} 不存在,該 trial 可能沒跑完")

    data = sio.loadmat(str(stack_path), squeeze_me=False)
    coef_grid = np.asarray(data["coef_grid"])  # (n_zernike, 1, n_fov) 或 (n_zernike, n_fov)
    if coef_grid.ndim == 3:
        coef_grid = coef_grid[:, 0, :]
    if coef_grid.ndim != 2:
        raise ValueError(f"非預期的 coef_grid shape: {coef_grid.shape}")
    return coef_grid


def collect_all_trials(manifest: dict) -> tuple[np.ndarray, list[str]]:
    """
    收集所有 trial 的 coef_grid,組成 shape = (n_trials, n_zernike, n_fov) 的 tensor。
    回傳 (tensor, trial_dirs_used)
    """
    trial_dirs = manifest["trial_dirs"]
    if isinstance(trial_dirs, str):
        trial_dirs = [trial_dirs]

    # MATLAB 寫 manifest 時的 cwd 是 PSF_Fitting/(見 run_L0_repeat_fit.m 環境檢查),
    # 所以 trial_dirs 是相對 PSF_Fitting/ 的路徑。
    # SCRIPT_DIR = .../PSF_Fitting/quick_recalibration/validation_experiments/L0_repeat_fit/
    # SCRIPT_DIR.parents[2] = .../PSF_Fitting/
    psf_fitting_root = SCRIPT_DIR.parents[2]

    tensors = []
    used = []
    for td in trial_dirs:
        td_path = Path(td)
        if not td_path.is_absolute():
            td_path = (psf_fitting_root / td).resolve()
        coefs = load_trial_coefs(td_path)
        tensors.append(coefs)
        used.append(str(td_path))

    if not tensors:
        raise RuntimeError("沒有讀到任何 trial,manifest.json 可能異常")

    shapes = {t.shape for t in tensors}
    if len(shapes) != 1:
        raise ValueError(f"各 trial 的 coef_grid shape 不一致: {shapes}")

    tensor = np.stack(tensors, axis=0)  # (n_trials, n_zernike, n_fov)
    return tensor, used


def compute_noise_floor(tensor: np.ndarray) -> dict:
    """
    從 (n_trials, n_zernike, n_fov) 算統計量。

    主要量:
      std_per_coef_per_fov : (n_zernike, n_fov)   — 跨 trials 的 sample std
      mad_per_coef_per_fov : (n_zernike, n_fov)   — 跨 trials 的 MAD (robust)
      mean_per_coef_per_fov: (n_zernike, n_fov)   — 跨 trials 的 mean(供參考)

    額外彙整:
      std_per_coef        : (n_zernike,)          — 跨 FOV 平均後的 per-coef std
      std_per_fov         : (n_fov,)              — 跨 coef 平均後的 per-fov std(看空間一致性)
    """
    n_trials, n_zern, n_fov = tensor.shape

    mean_pcf = tensor.mean(axis=0)
    std_pcf  = tensor.std(axis=0, ddof=1) if n_trials > 1 else np.zeros((n_zern, n_fov))
    median_pcf = np.median(tensor, axis=0)
    mad_pcf  = np.median(np.abs(tensor - median_pcf[None, :, :]), axis=0)

    # === 對每個係數做可信度判定(看「全部 trial × 全部 FOV」的值分佈)===
    classifications = []
    for ci in range(n_zern):
        all_vals = tensor[:, ci, :].flatten()  # 全 trial × 全 FOV
        classifications.append(classify_coef(ci, all_vals))

    trustworthy_idx = [ci for ci, c in enumerate(classifications) if c["status"] == "trustworthy"]

    # === 乾淨 noise floor:只用 trustworthy 係數 ===
    if trustworthy_idx:
        clean_std_per_fov = std_pcf[trustworthy_idx, :].mean(axis=0)
        clean_std_overall_median = float(np.median(std_pcf[trustworthy_idx, :]))
        clean_std_overall_mean   = float(std_pcf[trustworthy_idx, :].mean())
    else:
        clean_std_per_fov = np.full(n_fov, np.nan)
        clean_std_overall_median = float("nan")
        clean_std_overall_mean = float("nan")

    return {
        "n_trials": int(n_trials),
        "n_zernike": int(n_zern),
        "n_fov": int(n_fov),
        "mean_per_coef_per_fov": mean_pcf,
        "std_per_coef_per_fov": std_pcf,
        "mad_per_coef_per_fov": mad_pcf,
        "median_per_coef_per_fov": median_pcf,
        "std_per_coef": std_pcf.mean(axis=1),
        "mad_per_coef": mad_pcf.mean(axis=1),
        "std_per_fov": std_pcf.mean(axis=0),
        "classifications": classifications,
        "trustworthy_indices": trustworthy_idx,
        "clean_std_per_fov": clean_std_per_fov,
        "clean_std_overall_median": clean_std_overall_median,
        "clean_std_overall_mean": clean_std_overall_mean,
    }


def fov_consistency_ratio(std_per_fov: np.ndarray) -> float:
    """
    各 FOV 之間 std 一致性的簡單指標:max / min。
    < 2 → 大致一致(可用單一 noise floor)
    > 5 → 顯著不一致(需 per-FOV 校準)
    """
    return float(std_per_fov.max() / max(std_per_fov.min(), 1e-12))


def coef_label(idx: int) -> str:
    """
    coef 在 BADS x 向量裡的位置 → 物理意義。
    對應 candidate_build_fitted_psf.m 裡 W_phase 的實際展開公式(line 363–378)。

    注意:程式內的 Z(idx) 編號跟 Noll 標準不完全相同
    (例如程式 Z4 是 astig 45°,Noll Z4 是 defocus)。
    DESIGN_TW.md §7.5.1 的編號是用 Noll 慣例寫的,跟這裡可能對不上,
    後續處理 L3 模態降維時要小心。
    """
    # x(1:14) → Z(2:15);x(15) → AC(振幅縮放)
    # WholeFOV 預設 lock_tilt=true,所以 Z(2)、Z(3) 強制為 0 → x1, x2 應該量到極小 std
    zernike_names = {
        1:  "x1 → Z2 Y-tilt (locked=0)",
        2:  "x2 → Z3 X-tilt (locked=0)",
        3:  "x3 → Z4 astig 45° (sin 2φ)",
        4:  "x4 → Z5 defocus",
        5:  "x5 → Z6 astig 0° (cos 2φ)",
        6:  "x6 → Z7 trefoil (sin 3φ)",
        7:  "x7 → Z8 coma Y (sin φ)",
        8:  "x8 → Z9 coma X (cos φ)",
        9:  "x9 → Z10 trefoil (cos 3φ)",
        10: "x10 → Z11 quadrafoil (sin 4φ)",
        11: "x11 → Z12 sec astig (sin 2φ)",
        12: "x12 → Z13 spherical",
        13: "x13 → Z14 sec astig (cos 2φ)",
        14: "x14 → Z15 quadrafoil (cos 4φ)",
        15: "x15 → AC amplitude",
    }
    return zernike_names.get(idx, f"x{idx}")


def fov_label(file_index: int) -> str:
    """file index (1-100) → 10x10 grid 的 (row, col)"""
    row = (file_index - 1) // 10 + 1
    col = (file_index - 1) % 10 + 1
    return f"#{file_index} (row {row}, col {col})"


def write_report(stats: dict, manifest: dict, used_trial_dirs: list[str]) -> None:
    fov_indices = manifest["fov_indices"]
    if isinstance(fov_indices, (int, float)):
        fov_indices = [int(fov_indices)]
    else:
        fov_indices = [int(i) for i in fov_indices]

    n_trials = stats["n_trials"]
    n_zern   = stats["n_zernike"]
    n_fov    = stats["n_fov"]
    std_pcf  = stats["std_per_coef_per_fov"]
    mad_pcf  = stats["mad_per_coef_per_fov"]
    std_pcoef = stats["std_per_coef"]
    std_pfov  = stats["std_per_fov"]

    consistency = fov_consistency_ratio(std_pfov)

    lines: list[str] = []
    lines.append("# L0 Noise Floor 分析報告\n")
    lines.append(f"- 生成時間:{manifest.get('completed_at', 'unknown')}")
    lines.append(f"- Trials:{n_trials}")
    lines.append(f"- FOV 點數:{n_fov}(file indices = {fov_indices})")
    lines.append(f"- Zernike + AC 維度:{n_zern}")
    lines.append(f"- Git commit:{manifest.get('git_commit', 'unknown')[:12]}")
    lines.append(f"- Git branch:{manifest.get('git_branch', 'unknown')}")
    lines.append(f"- MATLAB:{manifest.get('matlab_version', 'unknown').splitlines()[0]}")
    lines.append("")

    # ----- 主結論 -----
    lines.append("## 主結論")
    lines.append("")

    if consistency < 2.0:
        verdict_consistency = (
            f"**FOV 一致性良好**(max/min = {consistency:.2f},< 2)。"
            "後續 Test 1 可以用 **單一 global noise floor**,不需 per-FOV 校準。"
        )
    elif consistency < 5.0:
        verdict_consistency = (
            f"**FOV 一致性中等**(max/min = {consistency:.2f},2–5)。"
            "建議 per-FOV 校準 z-score,或對特定 FOV 個別處理。"
        )
    else:
        verdict_consistency = (
            f"**FOV 一致性差**(max/min = {consistency:.2f},> 5)。"
            "**必須 per-FOV 校準**,設計需重看為何不同位置 noise floor 差這麼多。"
        )
    lines.append(f"- {verdict_consistency}")

    median_std = float(np.median(std_pcoef[:14]))  # 不含 AC
    if median_std < 0.005:
        verdict_magnitude = f"**全係數噪聲偏小**(中位 std = {median_std:.5f},< 0.005)。"
    elif median_std < 0.02:
        verdict_magnitude = f"**全係數噪聲中等**(中位 std = {median_std:.5f},0.005–0.02)。"
    else:
        verdict_magnitude = f"**全係數噪聲偏大**(中位 std = {median_std:.5f},> 0.02);但要記住這個數字含 lock/bound/dead artifact,看下方乾淨版本。"
    lines.append(f"- {verdict_magnitude}")

    # 乾淨 noise floor 結論
    clean_median = stats["clean_std_overall_median"]
    n_trust = len(stats["trustworthy_indices"])
    if n_trust == 0:
        lines.append(f"- ⚠️ **沒有任何係數被判為 trustworthy**:整個 noise floor 都是 lock/bound/dead artifact,L0 設計失效")
    else:
        lines.append(f"- **乾淨 noise floor**(只算 {n_trust} 個可信係數):中位 std = {clean_median:.5f}")
        lines.append(f"  - 這個數字才是真正的「BADS 演算法在收斂域內的隨機性」量級")
        lines.append(f"  - 後續 attribution Test 1 的 z-score 分母應該用這個,而不是含 artifact 的全係數版本")
    lines.append("")

    # === 係數可信度表 ===
    lines.append("## 係數可信度分類\n")
    lines.append("BADS 對不同係數的行為差很多——有些是真的有噪聲可量,有些是 artifact。")
    lines.append("分類規則:")
    lines.append("- `locked`: lock_tilt 強制鎖 0,對 loss 沒影響(BADS 隨便擲)")
    lines.append("- `bound_saturated`: > 80% 的值撞 search bounds (噪聲是「隨機選撞哪邊」)")
    lines.append("- `dead`: 跨全部 trial × FOV 完全相同(BADS 收斂得很死)")
    lines.append("- `trustworthy`: 在 search bounds 內部,有真實抖動可量")
    lines.append("")
    lines.append("| 係數 | 分類 | 撞邊 % | 跨 trial std (mean) | 原因 |")
    lines.append("|---|---|---|---|---|")
    for ci, classif in enumerate(stats["classifications"]):
        marker = "✓" if classif["status"] == "trustworthy" else "✗"
        lines.append(
            f"| {coef_label(ci + 1)} "
            f"| {marker} {classif['status']} "
            f"| {classif['bound_frac']*100:.0f}% "
            f"| {std_pcoef[ci]:.5f} "
            f"| {classif['reason']} |"
        )
    lines.append("")

    # ----- per-coef noise floor -----
    lines.append("## 各 Zernike 係數的 noise floor(跨 FOV 平均)\n")
    lines.append("| 係數 | mean std | mean MAD | std rank |")
    lines.append("|---|---|---|---|")
    rank_order = np.argsort(-std_pcoef)
    rank_lookup = {idx: r + 1 for r, idx in enumerate(rank_order)}
    for ci in range(n_zern):
        lines.append(
            f"| {coef_label(ci + 1)} "
            f"| {std_pcoef[ci]:.5f} "
            f"| {stats['mad_per_coef'][ci]:.5f} "
            f"| #{rank_lookup[ci]} |"
        )
    lines.append("")

    # ----- per-FOV noise floor -----
    lines.append("## 各 FOV 點的 noise floor(跨 Zernike 平均)\n")
    lines.append("| FOV | mean std |")
    lines.append("|---|---|")
    for fi in range(n_fov):
        lines.append(f"| {fov_label(fov_indices[fi])} | {std_pfov[fi]:.5f} |")
    lines.append("")

    # ----- 完整矩陣(coef × fov) -----
    lines.append("## 完整 std 矩陣 (Zernike × FOV)\n")
    header = "| 係數 \\ FOV | " + " | ".join(f"#{fov_indices[fi]}" for fi in range(n_fov)) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (n_fov + 1))
    for ci in range(n_zern):
        row = (
            f"| {coef_label(ci + 1)} | "
            + " | ".join(f"{std_pcf[ci, fi]:.5f}" for fi in range(n_fov))
            + " |"
        )
        lines.append(row)
    lines.append("")

    # ----- 後續行動建議 -----
    lines.append("## 後續行動建議\n")
    lines.append("1. 把 `noise_floor.json`(本目錄旁邊)當成 Test 1 z-score 的分母 (`noise_floor_std`)。")
    lines.append("2. 之後 L1 (重拍 100 張) 跑完後,跨 trial 算同樣 std,跟本 L0 結果相減即得「拍攝噪聲淨貢獻」。")
    lines.append("3. 若 `std rank` 顯示高階模態 (Z11–Z15) 的 std 顯著大於低階,需重看 DESIGN §7.5.1 的「可解釋模態」清單。")
    lines.append("4. 若 FOV 一致性差,L1 之後的層也要用 per-FOV noise floor,不能合併成單一數字。")
    lines.append("")

    lines.append("## 用到的 trial 目錄\n")
    for td in used_trial_dirs:
        lines.append(f"- `{td}`")
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"報告已寫入:{REPORT_PATH}")


def write_noise_floor_json(stats: dict, manifest: dict) -> None:
    """
    機器可讀版本,給後續 L1+ 跟 attribution Test 1 直接讀。
    所有矩陣都展平成 list of list,確保 JSON 可序列化。
    """
    fov_indices = manifest["fov_indices"]
    if isinstance(fov_indices, (int, float)):
        fov_indices = [int(fov_indices)]
    else:
        fov_indices = [int(i) for i in fov_indices]

    payload = {
        "experiment": "L0_repeat_fit",
        "n_trials": stats["n_trials"],
        "n_zernike": stats["n_zernike"],
        "n_fov": stats["n_fov"],
        "fov_indices": fov_indices,
        "coef_labels": [coef_label(i + 1) for i in range(stats["n_zernike"])],
        # === 全係數版(含 lock/bound/dead artifact),供對照 ===
        "std_per_coef_per_fov": stats["std_per_coef_per_fov"].tolist(),
        "mad_per_coef_per_fov": stats["mad_per_coef_per_fov"].tolist(),
        "median_per_coef_per_fov": stats["median_per_coef_per_fov"].tolist(),
        "mean_per_coef_per_fov": stats["mean_per_coef_per_fov"].tolist(),
        "std_per_coef_avg_over_fov": stats["std_per_coef"].tolist(),
        "mad_per_coef_avg_over_fov": stats["mad_per_coef"].tolist(),
        "std_per_fov_avg_over_coef": stats["std_per_fov"].tolist(),
        "fov_consistency_ratio_max_over_min": fov_consistency_ratio(stats["std_per_fov"]),
        # === 可信度分類 + 乾淨 noise floor(後續 attribution 應該用這個)===
        "coef_classifications": stats["classifications"],
        "trustworthy_coef_indices": stats["trustworthy_indices"],
        "clean_noise_floor": {
            "trustworthy_count": len(stats["trustworthy_indices"]),
            "std_per_fov_avg_over_trustworthy_coefs": stats["clean_std_per_fov"].tolist(),
            "overall_median_std": stats["clean_std_overall_median"],
            "overall_mean_std":   stats["clean_std_overall_mean"],
            "usage_note": (
                "這個欄位才是給 attribution Test 1 z-score 分母用的乾淨 noise floor。"
                "全係數版本(std_per_coef_avg_over_fov)含 lock/bound/dead artifact,"
                "直接用會把 BADS 的搜尋範圍設計問題誤判為演算法噪聲。"
            ),
        },
        "source_manifest": str(MANIFEST_PATH),
    }

    with NOISE_FLOOR_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"noise_floor.json 已寫入:{NOISE_FLOOR_JSON}")


def main() -> None:
    print("讀取 manifest...")
    manifest = load_manifest()
    print(f"  trials = {manifest['n_trials']}, fov_indices = {manifest['fov_indices']}")

    print("收集所有 trial 的 coef_grid...")
    tensor, used_dirs = collect_all_trials(manifest)
    print(f"  tensor shape = {tensor.shape}  (n_trials, n_zernike, n_fov)")

    print("計算 noise floor 統計量...")
    stats = compute_noise_floor(tensor)

    print("寫入報告與 JSON...")
    write_report(stats, manifest, used_dirs)
    write_noise_floor_json(stats, manifest)

    print("\n完成。")


if __name__ == "__main__":
    main()
