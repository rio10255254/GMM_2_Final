"""Compute within-scan 30-step fluctuation and paired 30-scan improvement."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASE = Path(r"D:\GMM_2_Final\Experiments\R148v2_HybridContextNativePSF")
SOURCE = ROOT / "results/comparison/all_displacements.csv"
OUTPUT_JSON = ROOT / "results/comparison/single_scan_step_sd_20260930.json"
OUTPUT_MD = ROOT / "reports/R152_SINGLE_SCAN_STEP_SD_20260930.md"
MODELS = {
    "Raw": ("RAW", ROOT / "evaluation/baseline_centers/Raw"),
    "R140v2-StableUNet": ("R140v2", ROOT / "evaluation/baseline_centers/R140v2-StableUNet"),
    "R148v2-HybridContextNativePSF": ("R148v2", BASE / "results/centers"),
    "R152-R148v2-SafeAdaptivePSF": ("R152", ROOT / "results/centers"),
}


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize(values: np.ndarray) -> dict:
    return {
        "n_scans": int(values.size),
        "mean_of_scan_sds_nm": float(values.mean()),
        "median_of_scan_sds_nm": float(np.median(values)),
        "pooled_within_scan_sd_nm": float(np.sqrt(np.mean(values**2))),
        "scan_sd_min_nm": float(values.min()),
        "scan_sd_max_nm": float(values.max()),
        "between_scan_sd_of_scan_sds_nm": float(values.std(ddof=1)),
    }


def main() -> None:
    audit = json.loads((ROOT / "results/final_audit.json").read_text(encoding="utf-8"))
    assert audit["passed"] and (audit["images"], audit["circles"], audit["scans"]) == (930, 8370, 30)
    data = pd.read_csv(SOURCE)
    selected = data[(data["kind"] == "adjacent") & data["model"].isin(MODELS)].copy()
    assert len(selected) == 4 * 30 * 30
    assert not selected.duplicated(["model", "run", "j"]).any()
    assert (selected["i"] == selected["j"] - 1).all()

    # One row means one full scan of 30 adjacent displacements. Use sample SD.
    rows = []
    for (model, run), group in selected.groupby(["model", "run"], sort=True):
        group = group.sort_values("j")
        assert len(group) == 30 and np.array_equal(group["j"].to_numpy(), np.arange(1, 31))
        assert group["run_index"].nunique() == 1
        observed = group["image_displacement_um"].to_numpy(dtype=np.float64) * 1000.0
        pi = group["pi_displacement_um"].to_numpy(dtype=np.float64) * 1000.0
        error = group["error_nm"].to_numpy(dtype=np.float64)
        assert np.max(np.abs(observed - pi - error)) < 1e-8
        rows.append({
            "model": model, "run": run, "run_index": int(group["run_index"].iloc[0]),
            "steps": 30, "mean_step_nm": float(observed.mean()),
            "sd_observed_nm": float(observed.std(ddof=1)),
            "sd_pi_corrected_nm": float(error.std(ddof=1)),
            "sd_pi_motion_nm": float(pi.std(ddof=1)),
        })
    frame = pd.DataFrame(rows)
    runs = sorted(frame["run"].unique())
    assert len(runs) == 30 and frame.groupby("model")["run"].nunique().eq(30).all()
    observed = frame.pivot(index="run", columns="model", values="sd_observed_nm").loc[runs]
    corrected = frame.pivot(index="run", columns="model", values="sd_pi_corrected_nm").loc[runs]
    assert observed.notna().all().all() and corrected.notna().all().all()

    # Independently reconstruct every exported step from the saved circle centers.
    calibration = json.loads((ROOT / "evaluation/calibration.json").read_text(encoding="utf-8"))
    axis = np.asarray(calibration["axis_unit_vector"], dtype=np.float64)
    maximum_center_replay_difference_um = 0.0
    for model, (_, centers_root) in MODELS.items():
        for run in runs:
            centers = (pd.read_csv(centers_root / (run + ".csv"))
                       .sort_values(["index", "pillar_id"])[["center_x_px", "center_y_px"]]
                       .to_numpy(dtype=np.float64).reshape(31, 9, 2))
            recomputed = np.median(centers[1:] - centers[:-1], axis=1) @ axis * 0.1725
            exported = (selected[(selected["model"] == model) & (selected["run"] == run)]
                        .sort_values("j")["image_displacement_um"].to_numpy(dtype=np.float64))
            maximum_center_replay_difference_um = max(
                maximum_center_replay_difference_um,
                float(np.max(np.abs(recomputed - exported))),
            )
    assert maximum_center_replay_difference_um < 1e-12

    # The common SD removes each scan's own mean before combining all 30 scans.
    pooled_checks = {}
    for model in MODELS:
        groups = selected[selected["model"] == model].groupby("run")
        sum_squares = sum(float(np.square(g["image_displacement_um"].to_numpy() * 1000
                                           - g["image_displacement_um"].mean() * 1000).sum())
                          for _, g in groups)
        direct_pooled = float(np.sqrt(sum_squares / (30 * 29)))
        from_scan_sds = float(np.sqrt(np.mean(observed[model].to_numpy() ** 2)))
        assert abs(direct_pooled - from_scan_sds) < 1e-10
        pooled_checks[model] = direct_pooled

    raw = observed["Raw"].to_numpy()
    new = observed["R152-R148v2-SafeAdaptivePSF"].to_numpy()
    old = observed["R148v2-HybridContextNativePSF"].to_numpy()
    r140 = observed["R140v2-StableUNet"].to_numpy()
    gain = raw - new
    gain_percent = 100.0 * gain / raw
    assert np.all(gain > 0)
    rng = np.random.default_rng(20260930)
    draws = rng.integers(0, 30, size=(20_000, 30))
    pooled_raw = np.sqrt(np.mean(raw[draws] ** 2, axis=1))
    pooled_new = np.sqrt(np.mean(new[draws] ** 2, axis=1))
    pooled_gain = pooled_raw - pooled_new
    pooled_gain_percent = 100.0 * (1.0 - pooled_new / pooled_raw)
    mean_gain = gain[draws].mean(axis=1)
    mean_gain_percent = gain_percent[draws].mean(axis=1)
    per_scan = []
    index_lookup = frame[frame["model"] == "Raw"].set_index("run")["run_index"]
    for index, run in enumerate(runs):
        per_scan.append({
            "run_index": int(index_lookup.loc[run]), "run": run,
            "raw_sd_nm": float(raw[index]), "r140_sd_nm": float(r140[index]),
            "r148_sd_nm": float(old[index]), "r152_sd_nm": float(new[index]),
            "gain_raw_minus_r152_nm": float(gain[index]),
            "gain_raw_minus_r152_percent": float(gain_percent[index]),
        })
    per_scan.sort(key=lambda row: row["run_index"])
    summary = {
        "primary_quantity": "sample SD of 30 image-measured adjacent steps within each scan",
        "unit": "nm", "n_scans": 30, "steps_per_scan": 30,
        "model": {name: {**summarize(observed[name].to_numpy()),
                          "pooled_pi_corrected_within_scan_sd_nm": float(np.sqrt(np.mean(corrected[name].to_numpy() ** 2)))}
                  for name in MODELS},
        "r152_vs_raw": {
            "improved_scans": int((gain > 0).sum()),
            "per_scan_absolute_gain_range_nm": [float(gain.min()), float(gain.max())],
            "per_scan_percent_gain_range": [float(gain_percent.min()), float(gain_percent.max())],
            "per_scan_percent_gain_p05_p95": np.quantile(gain_percent, [.05, .95]).tolist(),
            "mean_scan_gain_nm": float(gain.mean()),
            "mean_scan_gain_percent": float(gain_percent.mean()),
            "mean_scan_gain_nm_bootstrap_ci95": np.quantile(mean_gain, [.025, .975]).tolist(),
            "mean_scan_gain_percent_bootstrap_ci95": np.quantile(mean_gain_percent, [.025, .975]).tolist(),
            "pooled_gain_nm": float(np.sqrt(np.mean(raw ** 2)) - np.sqrt(np.mean(new ** 2))),
            "pooled_gain_percent": float(100 * (1 - np.sqrt(np.mean(new ** 2)) / np.sqrt(np.mean(raw ** 2)))),
            "pooled_gain_nm_bootstrap_ci95": np.quantile(pooled_gain, [.025, .975]).tolist(),
            "pooled_gain_percent_bootstrap_ci95": np.quantile(pooled_gain_percent, [.025, .975]).tolist(),
        },
        "r152_vs_r148": {
            "pooled_gain_nm": float(np.sqrt(np.mean(old ** 2)) - np.sqrt(np.mean(new ** 2))),
            "per_scan_gain_range_nm": [float((old - new).min()), float((old - new).max())],
        },
        "r140_vs_r152": {
            "r140_lower_sd_scans": int((r140 < new).sum()),
            "r152_lower_sd_scans": int((new < r140).sum()),
            "r152_minus_r140_pooled_sd_nm": float(np.sqrt(np.mean(new ** 2)) - np.sqrt(np.mean(r140 ** 2))),
        },
        "calibration_period_sensitivity": {},
        "bootstrap": {"unit": "complete scan", "draws": 20_000, "seed": 20260930},
        "checks": {"all_model_scan_step_groups_complete": True,
                   "center_replay_max_difference_um": maximum_center_replay_difference_um,
                   "independent_pooled_formula_agreement": True},
        "source_sha256": file_sha(SOURCE),
        "per_scan": per_scan,
    }
    assert calibration["raw_calibration_runs"] == 6 and calibration["evaluation_runs"] == 24
    for label, chosen in (("first6", per_scan[:6]), ("later24", per_scan[6:])):
        a = np.asarray([r["raw_sd_nm"] for r in chosen])
        b = np.asarray([r["r152_sd_nm"] for r in chosen])
        summary["calibration_period_sensitivity"][label] = {
            "n_scans": len(chosen), "improved_scans": int((a > b).sum()),
            "raw_pooled_sd_nm": float(np.sqrt(np.mean(a ** 2))),
            "r152_pooled_sd_nm": float(np.sqrt(np.mean(b ** 2))),
            "pooled_gain_percent": float(100 * (1 - np.sqrt(np.mean(b ** 2)) / np.sqrt(np.mean(a ** 2)))),
        }

    lines = [
        "# 30 趟重拍的單趟 30 步位移波動",
        "",
        "日期：2026-09-30。對象：R152 與同一批 RAW、R140v2、R148v2 實拍。",
        "",
        "## 要量的是什麼",
        "",
        "每一趟有 31 張影像，產生 30 個相鄰步距。先在**同一趟內**對這 30 個影像量得的步距計算樣本標準差；30 次重拍因此得到 30 個單趟標準差。30 趟的資料用來看逐趟改善是否一致、實際出現的改善範圍，以及整體平均改善的估計範圍。",
        "",
        "每一步的位移由同一張影像中九顆圓的圓心差取中位，再依固定方向與 `0.1725 μm/px` 轉成物體空間距離。**主要數字使用影像量得的實際步距**。另列扣除每一步 PI 回授後的版本作控制；兩者不能與「固定某一步在30趟之間的波動」混用。",
        "",
        "## 結果摘要（單位：nm）",
        "",
        "| 方法 | 30 趟的單趟標準差平均 | 30 趟合併後的單趟標準差 | 各趟標準差最小～最大 | 30 個單趟標準差之間的標準差 |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, (short, _) in MODELS.items():
        row = summary["model"][name]
        lines.append(f"| {short} | {row['mean_of_scan_sds_nm']:.3f} | **{row['pooled_within_scan_sd_nm']:.3f}** | {row['scan_sd_min_nm']:.3f}～{row['scan_sd_max_nm']:.3f} | {row['between_scan_sd_of_scan_sds_nm']:.3f} |")
    result = summary["r152_vs_raw"]
    lines.extend([
        "",
        f"**30 趟合併方式：**先扣掉每趟自身的平均步距，再將30趟的剩餘波動合併；由於每趟都有30步，結果等於 `sqrt(30 個單趟標準差平方的平均)`。RAW 為 `{pooled_checks['Raw']:.3f} nm`、R152 為 `{pooled_checks['R152-R148v2-SafeAdaptivePSF']:.3f} nm`，降低 `{result['pooled_gain_nm']:.3f} nm`，約 **{result['pooled_gain_percent']:.1f}%**。這不是把900個未分趟步距直接混算，也不是把標準差除以 `√30`。",
        "",
        "**實際30趟的改善範圍：**R152 每趟都比 RAW 低（30/30）。逐趟降低 `3.309～8.157 nm`，相當於 `36.9%～64.6%`；逐趟百分比的中間90%為 `42.2%～63.3%`。30趟百分比改善平均 `52.6%`。",
        "",
        f"**平均改善的估計範圍：**以完整掃描趟次為單位配對重抽樣20,000次，合併後的改善為 `{result['pooled_gain_percent']:.1f}%`，95%區間 `{result['pooled_gain_percent_bootstrap_ci95'][0]:.1f}%～{result['pooled_gain_percent_bootstrap_ci95'][1]:.1f}%`；這是平均改善估計的不確定範圍，並非另一批單趟一定落入的範圍。",
        "",
        "**與舊模型：**R148v2 的合併標準差 `4.865 nm`，與 R152 幾乎相同。R140v2 為 `4.321 nm`，在 24/30 趟低於 R152；不能因 R152 有新增 PSF 模組就稱它在單趟波動上最佳。",
        "",
        "## 每一趟的實際數值",
        "",
        "標準差與改善量均為 nm；改善百分比按同一趟 `100 × (RAW − R152) / RAW` 計算。",
        "",
        "| 趟次 | RAW | R140v2 | R148v2 | R152 | R152 比 RAW 降低 | 降低比例 |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in per_scan:
        lines.append(
            f"| {row['run_index']} | {row['raw_sd_nm']:.3f} | {row['r140_sd_nm']:.3f} | "
            f"{row['r148_sd_nm']:.3f} | {row['r152_sd_nm']:.3f} | "
            f"{row['gain_raw_minus_r152_nm']:.3f} | {row['gain_raw_minus_r152_percent']:.1f}% |"
        )
    lines.extend([
        "",
        "## PI 回授控制與拍攝時段",
        "",
        "若每一步先扣該趟的 PI 回授再計算單趟波動，合併標準差 RAW 為 `10.194 nm`、R152 為 `4.879 nm`；與直接使用影像步距的結論相近。這項控制包含 PI 讀值變化，不取代前面的主要定義。",
        "",
        "前六趟曾用於固定方向的 RAW 校準；後24趟提供較少校準重用的敏感度檢查。前六趟 R152 對 RAW 的合併波動降低 `56.2%`（6/6趟改善），後24趟降低 `51.7%`（24/24趟改善）。這些仍是同一顯微系統與同批樣品，不能稱為跨樣品獨立驗證。",
        "",
        "## 為何先前的 4.135 nm 不回答這個問題",
        "",
        "原正式表中的 R152 短步『重拍波動』`4.135 nm`，是固定第1步、第2步……各自比較30趟，再平均30個跨趟標準差。這和這裡『每一趟內的30個步距標準差』`4.754 nm`（逐趟平均）及`4.865 nm`（合併標準差）是不同統計問題。走完30步的終點跨趟標準差`14.049 nm`也不是單趟波動。",
        "",
        "本指標只表示步距在單趟內是否穩定，不等於每一步相對PI的準度或絕對長度準確度；相關誤差另見[完整模型與實驗紀錄](R152_COMPLETE_MODEL_AND_EXPERIMENT_RECORD_20260929.md)。",
        "",
        "## 來源與核對",
        "",
        "- [逐筆原始位移](../results/comparison/all_displacements.csv)：每個模型、每一趟、每一步的影像位移與PI回授。",
        "- [最後稽核](../results/final_audit.json)：930張、30趟與8,370顆圓通過身分核對。",
        "- [方向與像素比例](../evaluation/calibration.json)：固定方向及`0.1725 μm/px`；前六趟校準角色亦在此註明。",
        "- [完整精度的本次計算結果](../results/comparison/single_scan_step_sd_20260930.json)：30趟原始標準差、改善及重抽樣設定。",
        "",
        f"獨立從各趟圓心重算四個方法各900個相鄰步距，與原始位移表最大差 `{maximum_center_replay_difference_um:.2e} μm`。另一種直接扣除每趟平均、每個方法合併870個趟內自由度的計算，也與逐趟標準差平方合併的結果相同。",
    ])
    OUTPUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "report": str(OUTPUT_MD), "json": str(OUTPUT_JSON),
                      "raw_pooled_nm": pooled_checks["Raw"],
                      "r152_pooled_nm": pooled_checks["R152-R148v2-SafeAdaptivePSF"],
                      "improved_scans": int((gain > 0).sum()),
                      "pooled_gain_percent": result["pooled_gain_percent"],
                      "bootstrap_ci95_percent": result["pooled_gain_percent_bootstrap_ci95"],
                      "max_replay_difference_um": maximum_center_replay_difference_um},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
