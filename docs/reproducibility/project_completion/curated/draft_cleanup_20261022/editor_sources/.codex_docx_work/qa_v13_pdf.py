from __future__ import annotations

import argparse
import re
from pathlib import Path

from pypdf import PdfReader


def norm(text: str) -> str:
    return re.sub(r"\s+", "", text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()

    reader = PdfReader(args.pdf)
    texts = [page.extract_text() or "" for page in reader.pages]
    print(f"PAGES={len(texts)}")
    terms = [
        "5.4.6 現代重建模型與跨形貌評估配置",
        "5.5 小結",
        "第 6 章 實驗結果與分析",
        "6.1 點擴散函數校正",
        "6.1.1 點擴散函數擬合結果",
        "6.1.2 點擴散函數驗證",
        "6.2 神經網路重建效果與位移量測結果",
        "6.2.1 MOSR 模型與訓練狀態",
        "6.2.2 評估資料與量測方法",
        "6.2.3 影像重建與邊緣響應",
        "6.2.4 SEM 對照之 CD 修正與門檻穩健度",
        "6.2.5 位移量測結果",
        "6.2.6 模組與損失函數消融實驗",
        "6.2.7 跨形貌、現代模型與計算效能補充驗證",
        "6.2.8 綜合討論",
        "結論與未來工作",
        "7.1 研究結論",
        "7.2 主要方法貢獻",
        "7.3 主要量化結果",
        "7.4 研究範圍與量測可信度",
        "7.5 未來工作",
        "7.6 小結",
        "圖 6-53 20× via apparent CD range under fixed local-contrast thresholds",
        "圖 6-54 Raw and MOSR edge-transition width on horizontal and vertical line patterns",
    ]
    normalized_pages = [norm(text) for text in texts]
    for term in terms:
        needle = norm(term)
        hits = [index + 1 for index, text in enumerate(normalized_pages) if needle in text]
        print(f"{term}\t{hits}")

    forbidden = ["Base U-Net", "base U-Net", "基礎U-Net", "基礎 U-Net"]
    hits = []
    for page_index, text in enumerate(texts, start=1):
        for term in forbidden:
            if term in text:
                hits.append((page_index, term))
    print(f"FORBIDDEN_HITS={hits}")


if __name__ == "__main__":
    main()
