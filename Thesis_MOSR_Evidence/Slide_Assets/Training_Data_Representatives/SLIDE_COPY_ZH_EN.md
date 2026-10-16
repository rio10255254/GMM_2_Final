# Training-data slide copy

## Slide 1 — Foundation training data

**Chinese title**  
階段一：以大規模多樣化資料建立基礎重建能力

**English title**  
Stage I: Building foundational reconstruction capability with diverse large-scale training data

**Chinese speaking notes**  
本階段以多樣化的合成影像建立模型的基本辨識與重建能力。混合邊界資料提供不同方向、對比與模糊程度的邊緣；多形狀資料避免模型只記住單一圓形結構；含紋理的位移資料則讓模型學習在雜訊與非均勻背景下，仍維持結構輪廓與相對位置。

**English speaking notes**  
This stage establishes the model's basic recognition and reconstruction ability using diverse synthetic examples. Mixed boundary fields provide edges with different orientations, contrasts, and blur levels. Multi-shape fields prevent over-specialization to a single circular pattern. Textured motion examples teach the model to preserve contours and relative positions under noise and non-uniform backgrounds.

| Panel caption | Chinese explanation | English explanation |
|---|---|---|
| Mixed boundary fields | 複雜邊界與多方向模糊 | Complex boundaries under multi-directional blur |
| Multi-shape fields | 圓形、環形、線條與多邊形的組合 | Mixed circles, annuli, lines, and polygons |
| Textured motion | 含背景紋理與雜訊的受控位移 | Controlled motion with texture and noise |

## Slide 2 — Precision refinement data

**Chinese title**  
階段二：以受控位移、SEM 參考與連續影像進行精密修正

**English title**  
Stage II: Precision refinement with controlled motion, SEM references, and image sequences

**Chinese speaking notes**  
在基礎能力建立後，後期資料將重點轉為量測相關的限制。步進位移資料以已知移動關係約束模型，降低重建後的位置漂移；SEM 參考資料把實際顯微影像的邊界拉回獨立幾何參考；連續影像資料則抑制逐張重建時不必要的形貌波動。

**English speaking notes**  
After the foundational stage, later data emphasize measurement-relevant constraints. Step-motion examples use known displacement relationships to reduce positional drift. SEM-referenced samples anchor microscopic boundaries to an independent geometric reference. Sequence examples suppress unnecessary frame-to-frame shape fluctuation.

| Panel caption | Chinese explanation | English explanation |
|---|---|---|
| Step-motion guard | 已知步進關係下的位置保持 | Position preservation under known stepwise motion |
| SEM-referenced patches | 真實顯微影像與 SEM 幾何參考 | Real microscope patches anchored to SEM geometry |
| Sequence consistency | 連續影像中的形貌與位置穩定性 | Shape and position consistency across image sequences |

## Figure-use note

The two PNG files in `slide_panels` are ready to place directly on two 16:9 slides. Each individual source/label pair is also stored under `selected` for cases where a larger single example is preferred.
