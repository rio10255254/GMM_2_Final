from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DIAG = ROOT / "results" / "diagnosis_near_identity_behavior"
OUT = ROOT / "reports" / "R88_NEAR_IDENTITY_DIAGNOSIS.artifact.json"


def read_csv(name: str) -> list[dict[str, str]]:
    with (DIAG / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: str, digits: int = 4) -> float:
    return round(float(value), digits)


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def values_query(dataset_name: str, rows: list[dict], columns: list[str], order_by: str) -> str:
    values = ",\n    ".join(
        "(" + ", ".join(sql_literal(row.get(column)) for column in columns) + ")" for row in rows
    )
    names = ", ".join(columns)
    selected = ", ".join(columns)
    return f"WITH {dataset_name}({names}) AS (\n  VALUES\n    {values}\n)\nSELECT {selected}\nFROM {dataset_name}\nORDER BY {order_by}"


def source(
    source_id: str,
    label: str,
    path: Path,
    description: str,
    definitions: dict[str, str],
    sql: str | None = None,
) -> dict:
    query = {
        "engine": "sqlite" if sql else "file",
        "description": description,
        "metric_definitions": definitions,
    }
    if sql:
        query.update({"sql": sql, "language": "sql"})
    return {
        "id": source_id,
        "label": label,
        "path": str(path),
        "query": query,
    }


def main() -> None:
    generated_at = datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds")
    real_raw = read_csv("real_50x_output_trend.csv")
    gate_raw = read_csv("synthetic_validation_gate_trend.csv")
    degradation_raw = read_csv("degradation_vs_output_bound.csv")
    summary = json.loads((DIAG / "diagnostic_summary.json").read_text(encoding="utf-8"))

    real_rows: list[dict] = []
    series_name = {"current": "當輪權重", "ema": "平均權重"}
    for row in real_raw:
        real_rows.append(
            {
                "epoch": int(row["epoch"]),
                "series": series_name[row["weight_source"]],
                "output_change_gray_mean": number(row["output_change_gray_mean"], 3),
                "candidate_change_gray_mean": number(row["candidate_change_gray_mean"], 3),
                "confidence_percent": number(str(float(row["confidence_mean"]) * 100), 1),
                "gate_pass_percent": number(str(float(row["gate_pass_fraction"]) * 100), 1),
            }
        )

    domain_rows: list[dict] = []
    gate_rows: list[dict] = []
    metrics = (
        ("輪廓", "boundary_ratio_to_raw"),
        ("紋理", "texture_ratio_to_raw"),
        ("亮度", "photometry_ratio_to_raw"),
    )
    for row in gate_raw:
        epoch = int(row["epoch"])
        for label, field in metrics:
            domain_rows.append(
                {
                    "epoch": epoch,
                    "metric": label,
                    "improvement_vs_raw_percent": number(str((1.0 - float(row[field])) * 100), 2),
                }
            )
        gate_rows.append(
            {
                "epoch": epoch,
                "qualified": "是" if row["eligible"].lower() == "true" else "否",
                "boundary_improvement_percent": number(str((1.0 - float(row["boundary_ratio_to_raw"])) * 100), 2),
                "texture_improvement_percent": number(str((1.0 - float(row["texture_ratio_to_raw"])) * 100), 2),
                "photometry_improvement_percent": number(str((1.0 - float(row["photometry_ratio_to_raw"])) * 100), 2),
                "motion_error_over_limit": number(row["motion_error_over_limit"], 2),
                "topology_mismatch_count": int(row["topology_mismatch_count"]),
                "identity_change_gray": number(row["identity_change_gray"], 2),
            }
        )

    family_labels = {
        "compound_severe_but_recoverable": "複合重度退化",
        "low_contrast_and_uneven_illumination": "低對比與不均勻照明",
        "halo_ghost_and_banding": "光暈、鬼影與條帶",
        "local_boundary_fade": "局部邊界淡化",
        "defocus_and_motion_blur": "失焦與運動模糊",
        "standard_blur_and_noise": "一般模糊與雜訊",
        "identity_and_near_identity": "原圖與近原圖",
    }
    degradation_rows = [
        {
            "family": family_labels[row["degradation_family"]],
            "observation_count": int(row["observation_count"]),
            "mean_target_gap_gray": number(row["mean_target_gap_gray"], 1),
            "pixels_beyond_model_bound_percent": number(
                str(float(row["fraction_pixels_beyond_51_gray_bound"]) * 100), 1
            ),
        }
        for row in degradation_raw
    ]

    real_source_sql = values_query(
        "real_output_trend",
        real_rows,
        [
            "epoch",
            "series",
            "output_change_gray_mean",
            "candidate_change_gray_mean",
            "confidence_percent",
            "gate_pass_percent",
        ],
        "epoch, series",
    )
    gate_source_sql = values_query(
        "gate_summary",
        gate_rows,
        [
            "epoch",
            "qualified",
            "boundary_improvement_percent",
            "texture_improvement_percent",
            "photometry_improvement_percent",
            "motion_error_over_limit",
            "topology_mismatch_count",
            "identity_change_gray",
        ],
        "epoch",
    )
    degradation_source_sql = values_query(
        "degradation_limits",
        degradation_rows,
        [
            "family",
            "observation_count",
            "mean_target_gap_gray",
            "pixels_beyond_model_bound_percent",
        ],
        "pixels_beyond_model_bound_percent DESC",
    )
    with sqlite3.connect(":memory:") as connection:
        for query, expected_rows in (
            (real_source_sql, len(real_rows)),
            (gate_source_sql, len(gate_rows)),
            (degradation_source_sql, len(degradation_rows)),
        ):
            actual_rows = len(connection.execute(query).fetchall())
            if actual_rows != expected_rows:
                raise RuntimeError(f"source SQL returned {actual_rows} rows; expected {expected_rows}")

    sources = [
        source(
            "src_real_trend",
            "真實 50 倍影像逐輪輸出診斷",
            DIAG / "real_50x_output_trend.csv",
            "固定使用同一張真實 50 倍影像的同一個 256x256 區域，逐一載入已保存權重並量測輸出相對原圖的平均改動。",
            {
                "output_change_gray_mean": "輸出與原圖逐像素絕對差的平均值，單位為 8 位元灰階。",
                "candidate_change_gray_mean": "尚未經過信心限制前，候選修正的逐像素絕對差平均值。",
                "confidence_percent": "模型願意採用候選修正的平均程度。",
            },
            real_source_sql,
        ),
        source(
            "src_gate_trend",
            "合成驗證與合格條件逐輪結果",
            DIAG / "synthetic_validation_gate_trend.csv",
            "從正式訓練紀錄抽出每次驗證的輪廓、紋理、亮度、位移、形狀一致性與原圖保護結果。",
            {
                "improvement_vs_raw_percent": "以原圖為 0；正值代表比原圖好，負值代表比原圖差。",
                "motion_error_over_limit": "位移誤差除以預定上限；小於或等於 1 才符合要求。",
                "topology_mismatch_count": "984 個驗證視圖中，形狀連通或孔洞狀態不一致的數量。",
            },
            gate_source_sql,
        ),
        source(
            "src_degradation",
            "驗證資料與模型輸出範圍比對",
            DIAG / "degradation_vs_output_bound.csv",
            "按退化類型統計輸入與答案的灰階差距，並檢查差距是否超過模型最多可修正的 51 灰階。",
            {
                "mean_target_gap_gray": "輸入與答案逐像素絕對差的平均值，單位為灰階。",
                "pixels_beyond_model_bound_percent": "需要超過 51 灰階修正的像素比例。",
            },
            degradation_source_sql,
        ),
        source(
            "src_summary",
            "R88 近原圖行為診斷摘要",
            DIAG / "diagnostic_summary.json",
            "彙整診斷時的訓練進度、輸出限制、資料來源與位移裁切品質。",
            {
                "best_eligible_epoch": "截至診斷時，通過全部預定條件的最佳輪次；0 表示沒有任何權重合格。"
            },
        ),
        source(
            "src_model",
            "R88 的輸出設計",
            ROOT / "model" / "r88_model.py",
            "核對原圖直通、候選修正上限與信心限制的實際設計。",
            {},
        ),
        source(
            "src_generator",
            "R88 訓練資料產生方式",
            ROOT / "scripts" / "generate_dataset.py",
            "核對訓練資料是否讀取真實顯微影像、量測光學資訊或匿名真實光學統計。",
            {},
        ),
    ]

    title = "R88 為何幾乎沒有重建"
    manifest = {
        "version": 1,
        "surface": "report",
        "title": title,
        "generatedAt": generated_at,
        "description": "以真實 50 倍影像、正式訓練紀錄與資料設計，診斷 R88 為何輸出接近原圖。",
        "sources": sources,
        "charts": [
            {
                "id": "real_output_change_trend",
                "title": "真實 50 倍影像的平均改動幅度",
                "subtitle": "即使到第 70 至 80 輪，平均權重也只改動約 2 至 2.5 灰階，肉眼看起來自然接近原圖。",
                "type": "line",
                "dataset": "real_output_trend",
                "sourceId": "src_real_trend",
                "encodings": {
                    "x": {"field": "epoch", "type": "quantitative", "label": "訓練輪次"},
                    "y": {
                        "field": "output_change_gray_mean",
                        "type": "quantitative",
                        "label": "平均改動",
                        "format": "number",
                        "unit": "灰階",
                    },
                    "color": {"field": "series", "type": "nominal", "label": "權重版本"},
                    "tooltip": [
                        {"field": "candidate_change_gray_mean", "type": "quantitative", "label": "限制前候選改動", "format": "number", "unit": "灰階"},
                        {"field": "confidence_percent", "type": "quantitative", "label": "平均採用程度", "format": "number", "unit": "%"},
                    ],
                },
            },
            {
                "id": "synthetic_domain_trend",
                "title": "合成驗證相對原圖的變化",
                "subtitle": "輪廓與亮度逐漸改善，但紋理從第 45 輪起持續倒退，代表不是所有能力一起變好。",
                "type": "line",
                "dataset": "domain_ratio_trend",
                "sourceId": "src_gate_trend",
                "encodings": {
                    "x": {"field": "epoch", "type": "quantitative", "label": "訓練輪次"},
                    "y": {
                        "field": "improvement_vs_raw_percent",
                        "type": "quantitative",
                        "label": "相對原圖改善",
                        "format": "number",
                        "unit": "%",
                    },
                    "color": {"field": "metric", "type": "nominal", "label": "檢查項目"},
                },
            },
        ],
        "tables": [
            {
                "id": "qualification_table",
                "title": "各輪權重的合格檢查",
                "description": "正的改善百分比代表優於原圖；位移倍數必須不超過 1，且預定形狀不一致數必須為 0。",
                "dataset": "gate_summary",
                "sourceId": "src_gate_trend",
                "columns": [
                    {"field": "epoch", "label": "輪次", "format": "number"},
                    {"field": "qualified", "label": "全部合格"},
                    {"field": "boundary_improvement_percent", "label": "輪廓改善", "format": "number", "unit": "%"},
                    {"field": "texture_improvement_percent", "label": "紋理改善", "format": "number", "unit": "%"},
                    {"field": "motion_error_over_limit", "label": "位移超標倍數", "format": "number"},
                    {"field": "topology_mismatch_count", "label": "形狀不一致數", "format": "number"},
                ],
                "defaultSort": {"field": "epoch", "direction": "desc"},
            },
            {
                "id": "degradation_bound_table",
                "title": "不同退化資料需要的修正幅度",
                "description": "越多像素超過 51 灰階，代表標準答案越有一部分超出模型現有輸出能力。",
                "dataset": "degradation_limits",
                "sourceId": "src_degradation",
                "columns": [
                    {"field": "family", "label": "退化類型"},
                    {"field": "observation_count", "label": "影像數", "format": "number"},
                    {"field": "mean_target_gap_gray", "label": "平均答案差距", "format": "number", "unit": "灰階"},
                    {"field": "pixels_beyond_model_bound_percent", "label": "超過模型上限的像素", "format": "number", "unit": "%"},
                ],
                "defaultSort": {"field": "pixels_beyond_model_bound_percent", "direction": "desc"},
            },
        ],
        "blocks": [
            {"id": "title", "type": "markdown", "body": f"# {title}"},
            {
                "id": "executive_summary",
                "type": "markdown",
                "body": "## Executive Summary\n\nR88 不是完全沒有學習，但對真實 50 倍影像，目前可視為接近原圖直通。第 70 輪的平均權重只改動 2.45 灰階，而且主要是整體變亮，不是清楚補回細節。診斷時已完成第 84 輪，最佳合格輪次仍是 0。主因不是單一設定，而是模型被設計得過度保守、合成資料沒有用真實光學統計校準、部分答案超出模型能修正的範圍，以及位移裁切包含大量空白區域。",
            },
            {
                "id": "real_image_finding",
                "type": "markdown",
                "body": "## 真實 50 倍影像：確實只做了很小修正\n\n固定同一張影像、同一個位置逐輪重跑後，第 50 輪平均只改 0.56 灰階，第 70 輪為 2.45 灰階，第 80 輪為 2.24 灰階。這已確認不是顯示縮放造成的錯覺。",
            },
            {"id": "real_output_chart", "type": "chart", "chartId": "real_output_change_trend"},
            {
                "id": "synthetic_finding",
                "type": "markdown",
                "body": "## 合成資料上有小幅學習，但能力互相交換\n\n第 70 輪的輪廓比原圖改善 13.5%，亮度改善 7.3%，但紋理反而退化 3.2%。第 80 輪輪廓改善擴大到 21.5%，紋理退化也擴大到 7.6%。因此模型不是完全沒動，而是只學到部分合成規則，且犧牲了另一部分能力。",
            },
            {"id": "synthetic_chart", "type": "chart", "chartId": "synthetic_domain_trend"},
            {
                "id": "qualification_finding",
                "type": "markdown",
                "body": "## 沒有任何權重達到原先的合格條件\n\n截至這次診斷，所有已驗證輪次都不合格。第 70 輪位移誤差是上限的 4.73 倍，984 個視圖中仍有 561 個形狀不一致；第 80 輪也沒有翻轉這個結論。",
            },
            {"id": "qualification_table_block", "type": "table", "tableId": "qualification_table"},
            {
                "id": "causes",
                "type": "markdown",
                "body": "## 為何訓練會走向保守答案\n\n1. 輸出天生從原圖開始，只有模型有把握時才允許加入有限修正；初始狀態幾乎就是完全不動。\n2. 未經信心限制的候選修正本身也被要求不能比原圖差，讓模型連嘗試較大修正都要付出代價。\n3. 20% 訓練觀察是原圖或近原圖，同時還要兼顧輪廓、紋理、位移、形狀、拼接與亮度，最安全的共同答案就是少改。\n4. 訓練資料完全由程序產生，沒有真正導入允許使用的匿名顯微光學統計，因此在真實影像上沒有足夠依據判斷何時該修、該修多少。",
            },
            {
                "id": "data_limit_finding",
                "type": "markdown",
                "body": "## 資料要求與模型能力不一致\n\n模型最多只能修正 51 灰階，但整個驗證集中有 8.55% 像素需要更大幅度的修正。重度複合退化甚至有 21.4% 像素超出上限；這部分答案在目前設計下無法完整做到。",
            },
            {"id": "degradation_table_block", "type": "table", "tableId": "degradation_bound_table"},
            {
                "id": "motion_crop_finding",
                "type": "markdown",
                "body": "## 位移資料也在提供錯誤壓力\n\n40 個位移驗證視圖中，有 8 個完全沒有可量測結構，12 個的前景低於 1%。模型卻仍被要求從這些空白或極稀疏區域計算位置，導致位移項目劇烈波動。這不是模型能靠多跑幾輪自行修好的問題。",
            },
            {
                "id": "decision",
                "type": "markdown",
                "body": "## 判定與下一步\n\n這一輪可以繼續跑完，保留完整失敗證據，但 R88 目前不能列為穩定模型，更不能交付。下一輪應保留原圖安全通道，但先讓重建能力學起來，再校準是否採用修正；原圖保護只套在真正接近原圖的資料；位移裁切必須保證有結構；合成退化則要用不含樣品形狀的真實光學統計校準。",
            },
            {
                "id": "open_questions",
                "type": "markdown",
                "body": "## 尚待確認\n\n目前正式訓練仍在進行，這份報告只納入已保存到第 80 輪的權重。第 100 輪完成後仍需重跑同一套檢查，但除非後段出現非常大的轉折，現有的資料與驗證問題不會因訓練自然結束而消失。",
            },
            {
                "id": "limitations",
                "type": "markdown",
                "body": "## 限制與假設\n\n真實影像診斷固定使用同一個 256x256 區域，用來判斷模型到底改了多少，不代表所有顯微場景的完整泛化結論。合成驗證則沿用本輪已鎖定的 492 個案例與 984 個視圖；這些數字可用來判斷本輪是否過關，但不能取代外部真實影像、SEM 輪廓與位移工具的最終驗證。",
            },
        ],
    }

    snapshot = {
        "version": 1,
        "generatedAt": generated_at,
        "status": "ready",
        "datasets": {
            "real_output_trend": real_rows,
            "domain_ratio_trend": domain_rows,
            "gate_summary": gate_rows,
            "degradation_limits": degradation_rows,
        },
    }
    artifact = {"surface": "report", "sources": sources, "manifest": manifest, "snapshot": snapshot}
    OUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(OUT), "training_snapshot": summary["training"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
