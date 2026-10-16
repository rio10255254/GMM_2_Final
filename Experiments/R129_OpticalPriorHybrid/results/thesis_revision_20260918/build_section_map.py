"""Build a revision map from actual Word heading styles; leave source untouched."""
from pathlib import Path
import hashlib
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent
HEADINGS = json.loads((ROOT / "headings.json").read_text(encoding="utf-8-sig"))
RULES = {
    "1.1": ("保留", "研究背景維持量測用途。"),
    "1.2": ("局部改寫", "正常實拍、位移與輪廓／尺寸穩定性；不以勝過 V42 為門檻。"),
    "1.3": ("重寫", "改列 R129 實際方法、實拍效益及可追查性；移除舊排名。"),
    "1.4": ("局部改寫", "保留七章，更新章內重點。"),
    "2": ("保留並小補", "保留原光學、重建、量測文獻；補共享更新背景，不擴張為完整 XAI 論文。"),
    "3": ("保留", "光學與量測理論仍適用；不因換模型撤掉推導。"),
    "3.6": ("改寫", "改成神經重建與共享修正；U-Net 轉為背景。"),
    "3.9": ("局部改寫", "銜接 R129 方法，刪除把 U-Net 當現用架構的句子。"),
    "4.1": ("局部改寫", "明定實拍量測目的；設計意圖不當作幾何保證。"),
    "4.2": ("保留並補充", "舊 SEM、各倍率及新 PI 拍攝尺度分清，X/Y 尺度假設明列。"),
    "4.3": ("保留並標範圍", "屬光學校正；共用 SEM 參照不稱独立尺寸驗證。"),
    "4.4": ("重寫", "按實際 R129 光學輸入、四次共享、上取樣及原圖參照重畫。"),
    "4.4.1": ("重寫", "整體流程與共享四次修正；不是四個獨立模型。"),
    "4.4.2": ("重寫", "輸入端固定光學核與全局候選混合；不稱逐像素空間變異融合。"),
    "4.4.3": ("替換", "邊緣線索與抗混疊上取樣；移除不存在的獨立方向分支。"),
    "4.4.4": ("按實作改寫", "光學輸入和最終 Raw 參照分清，不保證圓心或真輪廓不變。"),
    "4.4.5": ("按實作改寫", "品質調幅與外框保留，不當已校準的可信機率。"),
    "4.5": ("重寫", "合成訓練來源、固定光學校正來源、開發與新實拍分開。"),
    "4.6": ("重寫", "真實三項訓練目標及接續訓練履歷；移除舊四組損失。"),
    "4.7": ("保留並補充", "統一讀法、浮點、資料群體；補 30 次尺寸與輪廓分析。"),
    "4.7.5": ("擴充", "同一物件同一位置重拍；成對掃描統計，保留時間與群體相關。"),
    "4.7.6": ("改寫界線", "單次波動、平均的不確定性與完整尺寸不確定度分開。"),
    "4.8": ("重寫", "依實際 R129 方法銜接實驗。"),
    "5.1": ("保留並補拍攝資料", "既有設備資料保留，補 R136 實際拍攝條件。"),
    "5.2": ("保留並補樣品來源", "新拍樣品身分據採集記錄，不由資料夾名推定。"),
    "5.3": ("核對後保留", "保留實際使用工具，區分 MATLAB 歷史流程與現用讀法。"),
    "5.4": ("重寫", "R129 固定版本、實際訓練、資料、比較方法及分析配置。"),
    "5.4.5": ("替換，舊內容附錄", "代表性方法來源；不新增七架構共同重訓。"),
    "5.4.6": ("替換，舊內容附錄", "既有連續影像與 30 次掃描配置。"),
    "5.4.7": ("替換，舊內容附錄", "過程與單項開關檢查；V42 配對重訓另標歷史。"),
    "5.5": ("重寫", "與更新後模型和採集配置一致。"),
    "6.1": ("保留並核對例圖", "校正結果保留；舊 MOSR 圖需標 V42 或以同來源 R129 替換。"),
    "6.2": ("按新證據重寫", "保留主要結構，分開輪廓、尺寸、位移與成本。"),
    "6.2.1": ("替換", "真實 R129 訓練與固定版本。"),
    "6.2.2": ("替換", "SEM 三曝光、201 舊影像與930新影像分列；120 對清單不可混用。"),
    "6.2.3": ("保留核對並整併", "讀法核對及 LSC／MZC 選擇；歷史版本清楚標示。"),
    "6.2.4": ("重寫並新增分析", "SEM 形狀與尺寸偏差；新增30次重拍尺寸、輪廓帶與位置依賴。"),
    "6.2.5": ("重寫並加入主實驗", "舊連續影像補充；R136 短步與距起點分列。"),
    "6.2.5.1": ("移動", "LSC／MZC 移至6.2.3或附錄；原位置改容納新位移小節。"),
    "6.2.6": ("替換，舊內容附錄", "R129 逐步行為與模組敏感度；不冒充匹配重訓。"),
    "6.2.7": ("替換，詳細歷史附錄", "重用 R135 代表對照，不把 V42 勝負當門檻。"),
    "6.2.8": ("替換", "現用配置時間與代價，不沿用 V42 速度。"),
    "6.2.9": ("重寫", "強項與不利尺寸、速度並列；正常條件、同次樣品及解釋範圍。"),
    "7": ("重寫", "依新證據回答問題；保留限制，未完成工作不寫成已達成。"),
}
chapters = {"緒論": "1", "文獻回顧": "2", "理論背景": "3", "研究方法": "4",
            "實驗系統與模型實作": "5", "實驗結果與分析": "6", "結論與未來工作": "7"}
rows = []
for h in HEADINGS:
    title = h["text"]
    match = re.match(r"(\d+(?:\.\d+)*)", title)
    number = match.group(1) if match else chapters.get(title)
    if number:
        candidates = [k for k in RULES if number == k or number.startswith(k + ".")]
        if not candidates:  # Chapter headings without a chapter-level rule.
            action, detail = "保留章結構", "各節按下列明細改寫。"
        else:
            action, detail = RULES[max(candidates, key=len)]
    elif title in ("摘要", "Abstract"):
        action, detail = "最後重寫", "替換舊模型数字與貢獻；中英文一致。"
    elif title == "參考文獻":
        action, detail = "核對引用後保留", "保留實際使用文獻；增刪引用後更新編號。"
    else:
        raise ValueError(f"Unmapped heading: {title}")
    rows.append({**h, "action": action, "plan": detail})
(ROOT / "section_map.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
md = ["# 原稿逐節處理對照", "", "2026-09-18。依 Word 真實標題樣式建立；段落位置為從零起算的 XML 段落索引，不是頁碼。新增小節見主計畫。", "",
      "| 原稿標題 | 段落索引 | 決定 | 具體處理 |", "|---|---:|---|---|"]
md += [f"| {r['text']} | {r['paragraph_index']} | {r['action']} | {r['plan']} |" for r in rows]
(ROOT / "section_map.md").write_text("\n".join(md) + "\n", encoding="utf-8")

source = json.loads((ROOT / "source.json").read_text(encoding="utf-8-sig"))
actual = hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest()
assert actual == source["sha256"], "Source Word changed"
report = ROOT.parents[1] / "reports/R129_THESIS_REVISION_PLAN.md"
body = report.read_text(encoding="utf-8")
links = []
for dest in re.findall(r"\]\(([^)]+)\)", body):
    if dest.startswith("https://"):
        continue
    target = (report.parent / dest).resolve()
    links.append({"target": str(target), "exists": target.exists()})
assert all(x["exists"] for x in links), [x for x in links if not x["exists"]]
inventory = json.loads((ROOT / "repeatability_data_inventory.json").read_text(encoding="utf-8"))
for model in inventory["rows"]:
    assert (model["circle_rows"], model["groups"], model["min_repeats"], model["max_repeats"], model["point_files"]) == (8370, 279, 30, 30, 30)
    assert model["all_points_finite"]
validation = {"status": "planning_artifacts_checked_not_experiments_completed", "source_word_unchanged": actual == source["sha256"],
              "source_sha256": actual, "heading_count": len(HEADINGS), "mapped_heading_count": len(rows),
              "local_evidence_links": links, "repeatability_data_complete_for_three_methods": True,
              "new_repeatability_statistics_executed": False, "new_training_executed": False,
              "E0_version_bridge_completed": False, "E5_process_check_completed": False,
              "word_revision_completed": False}
(ROOT / "plan_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in validation.items() if k != "local_evidence_links"}, ensure_ascii=False, indent=2))
print(f"Checked {len(links)} local evidence links.")
