from pathlib import Path
from docx import Document

path = Path(r"C:\Users\Rio\OneDrive\學業\碩班\論文\可用\論文完整版_20260716_v18_圖表整理版.docx")
document = Document(path)
paragraphs = [p.text.strip() for p in document.paragraphs]
for index, text in enumerate(paragraphs):
    if ("EDSR" in text or "NAFNet" in text) and ("位移" in text or "圖 6-" in text or "表 6-" in text):
        print(f"[{index}] {text}")
