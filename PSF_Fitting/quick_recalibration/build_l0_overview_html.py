"""build_l0_overview_html.py
生成 self-contained HTML 綜述,給別的 AI 或新進讀者快速建立 L0 系列實驗的全貌。

包含:
  - 整個 quick_recalibration 子專案的設計脈絡
  - L0 實驗的設計與配置
  - 4 組 setA-D 的結果
  - 10 個深度分析的發現
  - 對 DESIGN §9 的影響與下一步

兩張嵌入圖(base64):
  - 4 組視野在 10x10 格上的分佈
  - 4 組共 60 次擬合在(失焦, 球差)平面的散點

執行(在 d:/GMM_2_Final/ 或任意位置):
  python PSF_Fitting/quick_recalibration/build_l0_overview_html.py
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


SCRIPT_DIR = Path(__file__).resolve().parent
VEXP_DIR = SCRIPT_DIR / "validation_experiments"
OUT_HTML = SCRIPT_DIR / "L0_OVERVIEW.html"

SETS = [
    {"name": "setA", "indices": [1, 5, 10, 41, 45, 50, 91, 95, 100],
     "color": "#1f77b4", "rows": "1,5,10", "cols": "1,5,10",
     "date": "2026-05-06", "minutes": "~110",
     "raw_probs": "73.3% / 26.7%", "main_prob": 73.3, "noise_floor": 0.02863},
    {"name": "setB", "indices": [12, 16, 19, 52, 56, 59, 82, 86, 89],
     "color": "#ff7f0e", "rows": "2,6,9", "cols": "2,6,9",
     "date": "2026-05-14", "minutes": "80.3",
     "raw_probs": "33.3% / 66.7%", "main_prob": 66.7, "noise_floor": 0.02732},
    {"name": "setC", "indices": [30, 33, 37, 60, 63, 67, 80, 83, 87],
     "color": "#2ca02c", "rows": "3,6,8", "cols": "3,7,10",
     "date": "2026-05-15", "minutes": "88.0",
     "raw_probs": "80.0% / 20.0%", "main_prob": 80.0, "noise_floor": 0.02247},
    {"name": "setD", "indices": [13, 14, 17, 73, 74, 77, 93, 94, 97],
     "color": "#d62728", "rows": "2,7,10", "cols": "3,4,7",
     "date": "2026-05-15", "minutes": "91.5",
     "raw_probs": "20.0% / 80.0%", "main_prob": 80.0, "noise_floor": 0.02302},
]


# ============================================================================
# 視野位置圖
# ============================================================================

def make_fov_layout_fig_b64() -> str:
    fig, ax = plt.subplots(figsize=(8, 8))

    used_indices = set()
    for s in SETS:
        for idx in s["indices"]:
            used_indices.add(idx)

    # 背景:所有 100 個視野點(灰色)
    for idx in range(1, 101):
        r = (idx - 1) // 10 + 1
        c = (idx - 1) % 10 + 1
        if idx not in used_indices:
            ax.plot(c, 11 - r, "o", color="lightgray", markersize=14, zorder=1)

    # 標 4 組
    for s in SETS:
        for idx in s["indices"]:
            r = (idx - 1) // 10 + 1
            c = (idx - 1) % 10 + 1
            ax.plot(c, 11 - r, "o", color=s["color"], markersize=20,
                    markeredgecolor="black", zorder=2)
            ax.text(c, 11 - r, s["name"][-1],
                    ha="center", va="center",
                    fontsize=10, fontweight="bold", color="white", zorder=3)

    ax.set_xlim(0.5, 10.5)
    ax.set_ylim(0.5, 10.5)
    ax.set_xticks(range(1, 11))
    ax.set_yticks(range(1, 11))
    ax.set_yticklabels(range(10, 0, -1))
    ax.set_xlabel("col", fontsize=12)
    ax.set_ylabel("row", fontsize=12)
    ax.set_title("4 組視野位置在 10×10 格點上的分佈\n"
                 "灰色 = 未用(64 個);彩色 = 各組用的(共 36 個,互不重疊)",
                 fontsize=13)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)

    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=s["color"],
               markeredgecolor="black", markersize=14, label=s["name"])
        for s in SETS
    ]
    ax.legend(handles=legend_elements, loc="upper right", framealpha=0.95)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def load_existing_png_b64(path: Path) -> str:
    if not path.is_file():
        return ""
    return base64.b64encode(path.read_bytes()).decode("utf-8")


# ============================================================================
# HTML 模板(用字串 concatenation 避開 f-string 跟 CSS 大括號衝突)
# ============================================================================

CSS = """
  body {
    font-family: "Microsoft JhengHei", "PingFang TC", "Hiragino Sans", Arial, sans-serif;
    max-width: 1100px; margin: auto; padding: 30px;
    line-height: 1.75; color: #222; background: #fafafa;
  }
  h1 { color: #1a3a5c; border-bottom: 3px solid #1a3a5c; padding-bottom: 0.3em; }
  h2 { color: #1a3a5c; border-left: 5px solid #1a3a5c; padding-left: 0.6em;
       margin-top: 2.2em; padding-top: 0.2em; padding-bottom: 0.2em;
       background: linear-gradient(to right, #eef3f8, transparent); }
  h3 { color: #2a5582; margin-top: 1.5em; }
  table { border-collapse: collapse; margin: 1em 0; width: 100%; background: white; font-size: 0.95em; }
  th, td { border: 1px solid #ccc; padding: 0.5em 0.8em; text-align: left; vertical-align: top; }
  th { background: #e8eef5; }
  tr:nth-child(even) td { background: #fafbfd; }
  code { background: #f0f0f0; padding: 2px 5px; border-radius: 3px; font-size: 0.9em;
         font-family: Consolas, Monaco, monospace; }
  pre { background: #f4f4f4; padding: 1em; border-radius: 5px; overflow-x: auto;
        font-size: 0.9em; line-height: 1.5; }
  .takeaway { background: #e7f5e7; padding: 1em 1.5em; border-left: 5px solid #2ca02c;
              margin: 1.5em 0; border-radius: 5px; }
  .caveat { background: #fff5d8; padding: 1em 1.5em; border-left: 5px solid #f0ad4e;
            margin: 1em 0; border-radius: 5px; }
  .info { background: #e7f3ff; padding: 1em 1.5em; border-left: 5px solid #2980b9;
          margin: 1em 0; border-radius: 5px; }
  .big-finding { background: #fff0f0; padding: 1em 1.5em; border-left: 5px solid #d62728;
                 margin: 1.5em 0; border-radius: 5px; }
  .figure { margin: 1.5em 0; text-align: center; }
  .figure img { max-width: 100%; border: 1px solid #ddd; border-radius: 4px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
  .caption { font-size: 0.9em; color: #666; margin-top: 0.5em; font-style: italic; }
  .meta { color: #777; font-size: 0.88em; }
  .formula { background: #fafafa; padding: 0.8em 1em; border-left: 3px solid #888;
             margin: 0.8em 0; font-family: Consolas, monospace; }
  .toc { background: white; padding: 1em 1.5em; border: 1px solid #ddd; border-radius: 5px; }
  .toc a { color: #1a3a5c; text-decoration: none; }
  .toc a:hover { text-decoration: underline; }
  strong.hl { color: #d62728; }
  ol li, ul li { margin: 0.3em 0; }
"""


def build_html() -> str:
    fov_b64 = make_fov_layout_fig_b64()
    scatter_b64 = load_existing_png_b64(VEXP_DIR / "fig_4sets_basin_scatter.png")

    parts = []
    parts.append('<!DOCTYPE html>')
    parts.append('<html lang="zh-Hant">')
    parts.append('<head>')
    parts.append('<meta charset="UTF-8">')
    parts.append('<title>L0 同型號 PSF 快速校正 — 算法驗證實驗綜述</title>')
    parts.append('<style>' + CSS + '</style>')
    parts.append('</head>')
    parts.append('<body>')

    # === 標題 + 摘要 ===
    parts.append('<h1>L0 同型號 PSF 快速校正 — 算法驗證實驗綜述</h1>')
    parts.append('<p class="meta">本份文件給其他 AI 或新進讀者快速建立全貌。'
                 '對應子專案位置:<code>PSF_Fitting/quick_recalibration/</code>。'
                 '產出於 2026-05-18,涵蓋 4 組共 60 次 BADS 擬合 + 10 個深度分析。</p>')

    parts.append('<div class="takeaway">')
    parts.append('<strong>三句話結論:</strong>')
    parts.append('<ol>')
    parts.append('<li><strong>BADS 對這類擬合會分裂成兩個收斂域</strong>(主 75% / 次 25%),不是預期的單一解</li>')
    parts.append('<li><strong>兩個解的擬合誤差幾乎等高</strong>(差 &lt; 1 / 基準 1400+),是「等高的兩個局部最低點」,不是「對 vs 錯」</li>')
    parts.append('<li><strong>物理上兩個解差在「失焦量 + 球差」的權衡</strong>:主解 = 對焦準 + 球差大;次解 = 對焦不準 + 球差小</li>')
    parts.append('</ol>')
    parts.append('</div>')

    # === 目錄 ===
    parts.append('<div class="toc"><strong>目錄</strong><ol>')
    for title in [
        ("子專案脈絡:同型號 PSF 快速校正方法", "sec1"),
        ("L0 在 A 階段算法驗證裡的位置", "sec2"),
        ("實驗設計:BADS 在擬合什麼", "sec3"),
        ("4 組視野配置", "sec4"),
        ("雜訊下限的定義跟計算", "sec5"),
        ("結果概覽(4 組基本統計)", "sec6"),
        ("兩個解的物理意義", "sec7"),
        ("10 條深度分析發現", "sec8"),
        ("對歸因設計(DESIGN §9)的影響", "sec9"),
        ("還沒答的問題 + 下一步", "sec10"),
    ]:
        parts.append('<li><a href="#{}">{}</a></li>'.format(title[1], title[0]))
    parts.append('</ol></div>')

    # === Section 1: 子專案脈絡 ===
    parts.append('<h2 id="sec1">1. 子專案脈絡:同型號 PSF 快速校正方法</h2>')
    parts.append('<p>整個 <code>PSF_Fitting/quick_recalibration/</code> 子專案的目標是把現行的 PSF 校正流程(每台機 1.5–2 小時)在「同型號量產校正」場景下壓到 5–15 分鐘。</p>')

    parts.append('<h3>現行流程瓶頸</h3>')
    parts.append('<p>現行 <code>HDR_fitting_2D_WholeFOV.m</code> 對 100 張 FOV 影像從零像差初始值開始 BADS 擬合,完整跑一輪 1.5–2 小時。適合「研究階段」(同一台種子機從無到有建立 PSF),但<strong>不適合</strong>下列場景:</p>')
    parts.append('<ul>')
    parts.append('<li>同一台機台拆裝/重對焦後的快速重校</li>')
    parts.append('<li>同型號的不同機台間的校正轉移(本子專案主要場景)</li>')
    parts.append('</ul>')

    parts.append('<h3>願景:兩個獨立 artifact + 階梯式校正</h3>')
    parts.append('<table>')
    parts.append('<tr><th>Artifact</th><th>內容</th></tr>')
    parts.append('<tr><td><strong>機型模板</strong>(Machine-Type Template)</td>'
                 '<td>記錄該機型的中位 Zernike 係數、合理變動範圍(std)、品質基準;'
                 '是同型號量產校正的「先驗」</td></tr>')
    parts.append('<tr><td><strong>L0–L4 階梯式校正</strong></td>'
                 '<td>L0 sanity check(不擬合)→ L1 9 點熱擬合 → L2 全 FOV 窄搜尋 → '
                 'L3 模態降維 → L4 兜底(現行完整流程);根據漂移大小決定爬到哪一級</td></tr>')
    parts.append('</table>')

    parts.append('<p>整套方法在 <code>quick_recalibration/DESIGN_TW.md</code> 有完整 brainstorming 設計,主流程尚未實作,目前在 A 階段算法驗證。</p>')

    parts.append('<h3>三層誤差歸因(DESIGN §9)</h3>')
    parts.append('<p>判斷新機台跟模板的差異是不是真實的,要拆成三來源:</p>')
    parts.append('<ol>')
    parts.append('<li><strong>Test 1</strong>:擬合誤差下限測試(差異是不是只是 BADS 收斂隨機性)</li>')
    parts.append('<li><strong>Test 2</strong>:空間結構測試(差異有沒有跨 FOV 的 systematic pattern)</li>')
    parts.append('<li><strong>Test 3</strong>:模態定位測試(差異集中在「物理上會變」的模態嗎)</li>')
    parts.append('</ol>')
    parts.append('<p>Test 1 的<strong>分母就是「雜訊下限」</strong>,L0 的核心任務是把這個下限量出來。</p>')

    # === Section 2: L0 在哪裡 ===
    parts.append('<h2 id="sec2">2. L0 在 A 階段算法驗證裡的位置</h2>')
    parts.append('<p>A 階段是新方法上線前的算法驗證,設計成四層實驗,從「完全不動」一路加重到「真的拆」:</p>')
    parts.append('<table>')
    parts.append('<tr><th>層</th><th>動作</th><th>回答的問題</th><th>狀態</th></tr>')
    parts.append('<tr><td><strong>L0</strong></td><td>同一張影像,BADS 跑 N 次</td><td>BADS 本身的隨機性下限</td><td><strong>已完成</strong>(本文件主題)</td></tr>')
    parts.append('<tr><td>L1</td><td>同機台不動,重新拍 100 張 × 3 次</td><td>拍攝噪聲 + 擬合噪聲</td><td>未開始;前置驗證計畫已寫</td></tr>')
    parts.append('<tr><td>L2</td><td>假介入(關機重開、輕碰外殼)</td><td>歸因不該誤判升級(偽陽性)</td><td>未開始</td></tr>')
    parts.append('<tr><td>L3</td><td>真介入(拆裝物鏡)</td><td>歸因應正確識別(真陽性)+ 模態歸因正確性</td><td>未開始</td></tr>')
    parts.append('</table>')

    # === Section 3: 實驗設計 ===
    parts.append('<h2 id="sec3">3. 實驗設計:BADS 在擬合什麼</h2>')
    parts.append('<p><strong>BADS</strong>(Bayesian Adaptive Direct Search)在每張 FOV 影像上找 15 個參數,讓「模擬影像」跟「實際影像」最像。15 個參數是:</p>')
    parts.append('<ul>')
    parts.append('<li><strong>14 個 Zernike 像差係數</strong>(程式內部編號 Z2 到 Z15,對應 OSA 標準 Z1 到 Z14)</li>')
    parts.append('<li><strong>1 個振幅縮放係數</strong>(AC)</li>')
    parts.append('</ul>')

    parts.append('<h3>3.1 影像來源</h3>')
    parts.append('<ul>')
    parts.append('<li>同一台種子機(R26NewPSF 那條線)在 2025-09-03 拍的 100 張 BMP</li>')
    parts.append('<li>檔案路徑:<code>PSF_Fitting/Crop_circle_FreqFiltered/VisionTop_*.bmp</code></li>')
    parts.append('<li>對應 10×10 視野格點,第 N 張 → 位置 row = ⌈N/10⌉, col = ((N−1) mod 10) + 1</li>')
    parts.append('<li>真值樣本:<code>Crop_circle_FreqFiltered/GT/GT_901_with_Block_proc.bmp</code>(共用)</li>')
    parts.append('<li>理論 PSF 基底:<code>SimulatePSF/psf_multi.mat</code></li>')
    parts.append('</ul>')

    parts.append('<h3>3.2 BADS 搜尋邊界(4 組固定不變)</h3>')
    parts.append('<table>')
    parts.append('<tr><th>內部編號</th><th>OSA 編號</th><th>物理意義</th><th>下界</th><th>上界</th></tr>')
    bounds = [
        ("Z2", "Z1", "Y 傾斜(鎖死=0)", -0.3, 0.3),
        ("Z3", "Z2", "X 傾斜(鎖死=0)", -0.3, 0.3),
        ("Z4", "Z3", "散光 45°", -0.1, 0.1),
        ("Z5", "Z4", "失焦", 0.0, 1.0),
        ("Z6", "Z5", "散光 0°", -0.1, 0.1),
        ("Z7", "Z6", "三葉(sin)", -0.05, 0.05),
        ("Z8", "Z7", "慧差 Y", -0.05, 0.05),
        ("Z9", "Z8", "慧差 X", -0.05, 0.05),
        ("Z10", "Z9", "三葉(cos)", -0.05, 0.05),
        ("Z11", "Z10", "四葉(sin)", -0.01, 0.01),
        ("Z12", "Z11", "二級散光(sin)", -0.01, 0.01),
        ("Z13", "Z12", "球差", 0.0, 0.3),
        ("Z14", "Z13", "二級散光(cos)", -0.01, 0.01),
        ("Z15", "Z14", "四葉(cos)", -0.01, 0.01),
        ("AC", "—", "振幅縮放", 0.8, 1.25),
    ]
    for row in bounds:
        parts.append('<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(*row))
    parts.append('</table>')

    parts.append('<h3>3.3 預對齊 + lock_tilt 雙通道設計</h3>')
    parts.append('<p>擬合前先做「預對齊」:在 ±2 像素範圍以 0.25 像素步距找最佳影像平移,讓實際影像跟真值對齊。然後 BADS 擬合時把 Z2/Z3 傾斜<strong>強制鎖死為 0</strong>。</p>')
    parts.append('<div class="info"><strong>為什麼這樣設計</strong>:Zernike 傾斜的物理效果就是讓整張 PSF 在影像平面平移幾個像素——這跟「整張影像偏移」是同一件事。讓預對齊跟 BADS 各自獨立處理會兼併(BADS 可能把部分平移歸因到慧差),所以分階段解耦——預對齊處理影像平移、BADS 處理「不造成平移的高階像差」。</div>')
    parts.append('<p><strong>注意</strong>:預對齊找到的 (dy, dx) 寫進 <code>batch_results.csv</code> 的 <code>prealign_shift_y/x</code> 欄位,不是丟掉。要看「機台是否有 systematic 偏移」要看那邊,<strong>不能看 Z2/Z3</strong>(永遠是 0)。</p>')

    parts.append('<h3>3.4 擬合誤差函數</h3>')
    parts.append('<div class="formula">擬合誤差 = 1 × MSE(頻率域) + 8×10⁴ × MSE(梯度域,正規化)</div>')
    parts.append('<p><strong>權重 8×10⁴ 沒有實證根據,純經驗值</strong>(來自 Tutorial README 的設計說明:「讓兩個 loss 在數值上量級接近」)。Git 歷史顯示這個值從 repo 初始化以來沒改過。這是 L0 結論的一個潛在不確定性源頭——換 weight 兩個收斂域可能變一個或變三個,但目前沒掃描分析。</p>')

    # === Section 4: 4 組視野配置 ===
    parts.append('<h2 id="sec4">4. 4 組視野配置</h2>')
    parts.append('<p>從 100 張影像挑 4 組各 9 張,4 組之間完全不重疊(共 36 個視野,佔 100 張的 36%)。同一組跑 15 次 BADS(隨機種子從 <code>rng(1)</code> 到 <code>rng(15)</code>),每次從預設起點 <code>[0,...,0,1]</code> 開始。</p>')

    parts.append('<table>')
    parts.append('<tr><th>Set</th><th>視野編號</th><th>10×10 格點上的位置</th><th>跑的日期</th><th>BADS 跑時間</th></tr>')
    for s in SETS:
        parts.append('<tr><td><strong>{}</strong></td><td><code>{}</code></td><td>row {{{}}} × col {{{}}}</td><td>{}</td><td>{} 分</td></tr>'.format(
            s["name"], s["indices"], s["rows"], s["cols"], s["date"], s["minutes"]))
    parts.append('</table>')

    parts.append('<div class="figure">')
    parts.append('<img src="data:image/png;base64,{}">'.format(fov_b64))
    parts.append('<div class="caption">圖 1:4 組視野位置在 10×10 格點上的分佈。灰色點 = 未用,彩色 = 各組所選。</div>')
    parts.append('</div>')

    # === Section 5: 雜訊下限 ===
    parts.append('<h2 id="sec5">5. 雜訊下限的定義跟計算</h2>')
    parts.append('<h3>5.1 一句話定義</h3>')
    parts.append('<p>BADS 跑同一張影像 N 次,每次得到不同的擬合係數值,<strong>「不同次之間的標準差」就是雜訊下限</strong>。也就是「不動任何東西、只重複跑擬合」的可重現性下限。</p>')

    parts.append('<h3>5.2 為什麼重要</h3>')
    parts.append('<p>後續歸因設計 Test 1 算 z 分數時:</p>')
    parts.append('<div class="formula">z = |新機係數 − 模板係數| / 雜訊下限</div>')
    parts.append('<p>雜訊下限就是這個 z 分數的<strong>分母</strong>。估太小 → 隨便都過門檻 → 誤報;估太大 → 真的變了也說沒變 → 漏報。所以這個量必須穩、必須說得清楚怎麼算。</p>')

    parts.append('<h3>5.3 計算步驟</h3>')
    parts.append('<ol>')
    parts.append('<li>每組跑完得到擬合結果張量 <code>X[t, z, f]</code>,shape = (15 跑次, 15 係數, 9 視野)</li>')
    parts.append('<li>對每個 (係數, 視野) 算跨 15 跑次的<strong>樣本標準差</strong>(<code>ddof=1</code>),得到 15 × 9 = 135 個 std 值</li>')
    parts.append('<li>篩出 7 個可信係數(下一節說明),其餘 8 個係數的 std 是擬合產物,排除</li>')
    parts.append('<li>對剩下 7 × 9 = 63 個 std 取<strong>中位數</strong>,就是該組的「乾淨雜訊下限中位 std」</li>')
    parts.append('</ol>')

    parts.append('<h3>5.4 三個設計選擇</h3>')
    parts.append('<table>')
    parts.append('<tr><th>選擇</th><th>替代</th><th>為什麼選現在這個</th></tr>')
    parts.append('<tr><td>用 std</td><td>MAD / range</td><td>std 是歸因 Test 1 z 分數的天然分母,直接相容</td></tr>')
    parts.append('<tr><td>取中位數</td><td>平均</td><td>不同視野的 std 量級差大(setC 從 0.004 到 0.033),中位數抗 outlier</td></tr>')
    parts.append('<tr><td>篩 7 個可信係數</td><td>用全 15 個</td><td>鎖死/撞邊/死的 std 是擬合產物,混進來會把數字撐大(全係數版 0.04 vs 乾淨版 0.029,差 38%)</td></tr>')
    parts.append('</table>')

    parts.append('<h3>5.5 15 個係數的可信度四分類(跨 4 組完全一致)</h3>')
    parts.append('<table>')
    parts.append('<tr><th>分類</th><th>哪幾個</th><th>為什麼</th></tr>')
    parts.append('<tr><td><strong>可信</strong>(7 個)</td><td>Z4, Z5, Z8, Z9, Z11, Z12, Z13(程式內部編號)</td><td>跨 trial std 穩定,真的量到 BADS 隨機抖動</td></tr>')
    parts.append('<tr><td>被鎖死(2 個)</td><td>Z2, Z3 傾斜</td><td><code>lock_tilt = true</code> 強制歸零,BADS 隨便擲值對擬合誤差無影響</td></tr>')
    parts.append('<tr><td>撞搜尋邊界(5 個)</td><td>Z6, Z7, Z10, Z14, Z15</td><td>80% 以上撞 lb 或 ub,「隨機選撞哪邊」不是真擬合</td></tr>')
    parts.append('<tr><td>死掉(1 個)</td><td>AC 振幅</td><td>永遠停在下界 0.8,BADS 判斷「越小越好」被擋住</td></tr>')
    parts.append('</table>')
    parts.append('<p>分類在 4 組 setA-D 完全一致,代表這是<strong>底層擬合工具的設計決定</strong>,不是視野偶然。</p>')

    # === Section 6: 結果概覽 ===
    parts.append('<h2 id="sec6">6. 結果概覽(4 組基本統計)</h2>')
    parts.append('<table>')
    parts.append('<tr><th>Set</th><th>跑次</th><th>偵測到的解數</th><th>原始機率分佈</th><th>對齊後主解機率</th><th>乾淨雜訊下限</th></tr>')
    for s in SETS:
        parts.append('<tr><td><strong>{}</strong></td><td>15</td><td><strong>2</strong></td><td>{}</td><td>{:.1f}%</td><td>{:.5f}</td></tr>'.format(
            s["name"], s["raw_probs"], s["main_prob"], s["noise_floor"]))
    parts.append('</table>')

    parts.append('<div class="info">')
    parts.append('<strong>觀察:</strong>')
    parts.append('<ol>')
    parts.append('<li>四組全部偵測到 <strong>2 個收斂域</strong>(階層分群自動選 k=2)</li>')
    parts.append('<li>原始機率乍看差很多(73/27、33/67、80/20、20/80),但<strong>群組編號 1/2 是隨機分配</strong>——對齊後其實穩定(75% ± 6.4%,範圍 13 個百分點)</li>')
    parts.append('<li>乾淨雜訊下限四組量級接近 0.022–0.029,跨組差 21.5%,比預期大</li>')
    parts.append('</ol>')
    parts.append('</div>')

    parts.append('<h3>6.1 跨組對齊(以 setA 為基準)</h3>')
    parts.append('<p>對齊方法:把每組兩個解的中心點(15 維 Zernike 係數跨 9 視野平均)算出來,用最近距離配對。對齊結果:</p>')
    parts.append('<table>')
    parts.append('<tr><th>對齊組合</th><th>centroid 距離</th></tr>')
    pairs = [
        ("setA mode 1 ↔ setB mode 2", "0.0648"),
        ("setA mode 2 ↔ setB mode 1", "0.1964"),
        ("setA mode 1 ↔ setC mode 1", "0.1745"),
        ("setA mode 2 ↔ setC mode 2", "0.2290"),
        ("setA mode 1 ↔ setD mode 2", "0.0634"),
        ("setA mode 2 ↔ setD mode 1", "0.2299"),
    ]
    for label, dist in pairs:
        parts.append('<tr><td>{}</td><td>{}</td></tr>'.format(label, dist))
    parts.append('</table>')
    parts.append('<p><strong>對齊距離 0.06–0.23,遠小於組內兩解距離(2.4–2.7)</strong>。四組看到的確實是同一對解,不是各自獨立的局部最低點。setB 跟 setD 的 raw label 是翻轉的(setA mode 1 對應 setB/setD mode 2)。</p>')

    # === Section 7: 兩個解的物理意義 ===
    parts.append('<h2 id="sec7">7. 兩個解的物理意義</h2>')

    parts.append('<h3>7.1 主/次解的中心(用 setA)</h3>')
    parts.append('<p>對 15 個係數,主/次解的中心值:</p>')
    parts.append('<table>')
    parts.append('<tr><th>係數(OSA)</th><th>分類</th><th>主解中心</th><th>次解中心</th><th>主 − 次</th></tr>')
    centroids = [
        ("Z1 Y 傾斜", "鎖死", "+0.024", "−0.030", "+0.054"),
        ("Z2 X 傾斜", "鎖死", "+0.025", "+0.041", "−0.016"),
        ("Z3 散光 45°", "可信", "−0.040", "+0.008", "−0.048"),
        ("<strong>Z4 失焦</strong>", "<strong>可信</strong>", "<strong>+0.142</strong>", "<strong>+0.696</strong>", "<strong>−0.554</strong>"),
        ("Z5 散光 0°", "撞邊", "+0.027", "−0.017", "+0.044"),
        ("Z6 三葉 sin", "撞邊", "−0.005", "+0.009", "−0.014"),
        ("Z7 慧差 Y", "可信", "0.000", "+0.009", "−0.009"),
        ("Z8 慧差 X", "可信", "−0.041", "−0.041", "≈0"),
        ("Z9 三葉 cos", "撞邊", "+0.018", "+0.014", "+0.004"),
        ("Z10 四葉 sin", "可信", "0.000", "0.000", "≈0"),
        ("Z11 二級散光 sin", "可信", "0.000", "−0.001", "≈0"),
        ("<strong>Z12 球差</strong>", "<strong>可信</strong>", "<strong>+0.277</strong>", "<strong>+0.069</strong>", "<strong>+0.207</strong>"),
        ("Z13 二級散光 cos", "撞邊", "−0.003", "+0.002", "−0.004"),
        ("Z14 四葉 cos", "撞邊", "+0.010", "−0.005", "+0.015"),
        ("AC 振幅", "死", "+0.800", "+0.800", "0"),
    ]
    for row in centroids:
        parts.append('<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(*row))
    parts.append('</table>')

    parts.append('<div class="big-finding">')
    parts.append('<strong>核心物理理解</strong>:可信係數裡只有 <strong>Z4 失焦(差 0.554)</strong> 跟 <strong>Z12 球差(差 0.207)</strong> 有實質差別。兩個解差在:')
    parts.append('<ul>')
    parts.append('<li><strong>主解</strong>:失焦小(0.142,接近正焦)+ 球差大(0.277)</li>')
    parts.append('<li><strong>次解</strong>:失焦大(0.696,離焦明顯)+ 球差小(0.069)</li>')
    parts.append('</ul>')
    parts.append('光學上熟知的權衡:一張模糊影像可以解讀成「對焦準但球差大」或「對焦不準但光學乾淨」。兩種解讀產生幾乎一樣的影像,所以擬合誤差沒辦法區分,BADS 隨機落到其中一個。')
    parts.append('</div>')

    if scatter_b64:
        parts.append('<div class="figure">')
        parts.append('<img src="data:image/png;base64,{}">'.format(scatter_b64))
        parts.append('<div class="caption">圖 2:4 組共 60 次擬合(每組 15 跑次,跨 9 視野平均)在(失焦, 球差)平面的分佈。藍 = 主解,紅 = 次解,形狀區分組(○ setA、△ setB、□ setC、◇ setD)。星號是解的中心。注意次解其實分成兩個子群(setA/setC 偏中間、setB/setD 偏右下),反映次解的物理位置 set 之間有些微變動。</div>')
        parts.append('</div>')

    # === Section 8: 10 條深度分析 ===
    parts.append('<h2 id="sec8">8. 10 條深度分析發現</h2>')
    parts.append('<p>從 60 次擬合的原始資料 + per-trial CSV,做了 10 個深度分析,分四大類。完整數字在 <code>validation_experiments/all_sets_comparison.md</code>。</p>')

    parts.append('<h3>8.1 §6 為什麼雜訊下限跨組差 21.5%</h3>')
    parts.append('<table>')
    parts.append('<tr><th>分析</th><th>發現</th></tr>')
    parts.append('<tr><td>6.1 主解佔比 vs 雜訊下限</td><td>皮爾森相關係數 <strong>−0.814</strong>(N=4)。主解佔比越高,雜訊越低</td></tr>')
    parts.append('<tr><td>6.2 fval / 迭代次數跨組</td><td>setC fval 中位 1401 &lt; setA 1453 ——<strong>setC 影像本來就比較好擬合</strong>,雜訊低是結果不是原因</td></tr>')
    parts.append('<tr><td>6.3 按視野的主解內 std 貢獻</td><td>setC 有三個視野(#30, #67, #80)內部 std 在 0.004–0.007,比其他組任一視野低 3–5 倍,把組平均拉低</td></tr>')
    parts.append('</table>')

    parts.append('<h3>8.2 §7 兩個解的物理意義 + 結構穩定性</h3>')
    parts.append('<table>')
    parts.append('<tr><th>分析</th><th>發現</th></tr>')
    parts.append('<tr><td>7.1 主/次解的 Zernike 中心</td><td>主要差在 Z4 失焦(差 0.554)跟 Z12 球差(差 0.207),其他可信係數幾乎相同(見上節)</td></tr>')
    parts.append('<tr><td>7.2 兩解距離跨組變動</td><td>1.89(setA)到 2.67(setC),變動 <strong>40.8%</strong>(比雜訊下限的 21.5% 還大)</td></tr>')
    parts.append('<tr><td><strong>7.3 主 vs 次解的擬合誤差</strong></td><td><strong>差不到 1(基準 1400+)——兩個解是等高的局部最低點,不是「對 vs 錯」</strong>。這是整份分析最關鍵發現</td></tr>')
    parts.append('</table>')

    parts.append('<h3>8.3 §8 BADS 內部隨機性</h3>')
    parts.append('<table>')
    parts.append('<tr><th>分析</th><th>發現</th></tr>')
    parts.append('<tr><td>8.1 隨機種子 → 落點對應</td><td>跨 4 組同 <code>rng</code> 落到同解只有 <strong>26.7%</strong>(15 個種子裡 4 個一致),跟純隨機 25% 幾乎一樣。MATLAB rng 不控制 BADS 內部隨機性</td></tr>')
    parts.append('<tr><td>8.2 一次擬合內 9 視野的一致性</td><td>setB/C/D 100% 的跑次「9 視野全部落到同一解」,setA 87%(15 跑次裡 2 個是混合)。<strong>解的選擇是跑次層級決策,不是視野層級</strong></td></tr>')
    parts.append('</table>')

    parts.append('<h3>8.4 §9 撞邊飽和細節</h3>')
    parts.append('<table>')
    parts.append('<tr><th>係數</th><th>setA 撞下/上</th><th>setB</th><th>setC</th><th>setD</th></tr>')
    bound_split = [
        ("Z5 散光 0°", "42/58", "60/40", "<strong>93/7</strong>", "51/49"),
        ("Z6 三葉 sin", "46/44", "56/39", "<strong>93/6</strong>", "61/35"),
        ("Z9 三葉 cos", "33/66", "26/73", "<strong>87/10</strong>", "47/51"),
        ("Z13 二級散光 cos", "58/42", "40/60", "<strong>7/93</strong>", "49/51"),
        ("Z14 四葉 cos", "20/74", "32/57", "20/70", "19/72"),
        ("AC 振幅", "100/0", "100/0", "100/0", "100/0"),
    ]
    for row in bound_split:
        parts.append('<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(*row))
    parts.append('</table>')
    parts.append('<p><strong>setC 特別極端</strong>(Z5/Z6/Z9 撞下界 93%、Z13 撞上界 93%),其他組撞兩邊較均勻。代表 setC 影像結構讓 BADS 對這些係數有強烈方向偏好。<strong>這是底層擬合工具搜尋邊界可能設太窄的疑點,跟 L0 結論獨立</strong>。</p>')

    # === Section 9: 對 DESIGN §9 的影響 ===
    parts.append('<h2 id="sec9">9. 對歸因設計(DESIGN §9)的影響</h2>')
    parts.append('<p>L0 結論翻譯到 DESIGN §9 設計上,要改三個地方:</p>')

    parts.append('<h3>9.1 Test 1 從單層改成兩層</h3>')
    parts.append('<p><strong>原設計</strong>:對單一雜訊下限算 z 分數,大於 2 就判「有差異」。</p>')
    parts.append('<p><strong>新設計</strong>(三層):</p>')
    parts.append('<ol>')
    parts.append('<li><strong>第一層(判落點)</strong>:用 4 組蒸餾出來的主/次解中心點當參考,看新機這次擬合的 15 維係數向量比較靠近哪個</li>')
    parts.append('<li><strong>第二層(算偏差)</strong>:在判定的解內,算實際係數跟解中心的偏差,用解內 std 當分母算 z 分數</li>')
    parts.append('<li><strong>第三層機率核對(advisory)</strong>:同一台機台多次擬合,主/次解出現比例如果接近 75/25 就正常;偏離很大才 flag</li>')
    parts.append('</ol>')

    parts.append('<h3>9.2 雜訊下限要用保守版</h3>')
    parts.append('<p>跨組差 21.5% 代表雜訊下限不是固定數字。建議用 4 組最大值(setA 0.0286)當分母,寧可漏報也不要誤報。</p>')

    parts.append('<h3>9.3 解的機率不是「BADS 偏見」</h3>')
    parts.append('<p>原本可能想把 75/25 解釋為「BADS 對主解有偏好」,改成「兩個合理解的物理權重」。兩個解擬合誤差等高,不存在「正解 vs 錯解」。新機跑出來如果機率分佈嚴重偏離 75/25,代表這台機的「兩解權重」跟參考機不一樣,可能機台真的變了。</p>')

    parts.append('<h3>9.4 改寫提案的位置</h3>')
    parts.append('<p>改寫建議草稿:<code>quick_recalibration/DESIGN_SECTION9_REVISION_PROPOSAL_TW.md</code>。等使用者(設計作者)review 採納後 copy 進主 DESIGN 並刪掉提案。</p>')

    # === Section 10: 還沒答 + 下一步 ===
    parts.append('<h2 id="sec10">10. 還沒答的問題 + 下一步</h2>')

    parts.append('<h3>10.1 L0 答不了的關鍵問題</h3>')
    parts.append('<div class="caveat">')
    parts.append('<p><strong>主/次解機率(75/25)是「跨視野穩定」沒錯,但「跨拍攝穩不穩」?</strong></p>')
    parts.append('<p>目前測的全是「同一次拍攝、不同視野」。L1 前置驗證要答:同機重拍 2–3 次,看落點機率還會不會在 75/25 範圍。穩定 → 設計可以直接往下;不穩 → 第一層判斷邏輯要重想。</p>')
    parts.append('<p>L1 前置驗證計畫:<code>validation_experiments/L1_PRECHECK_PLAN_TW.md</code>(要進實驗室重拍照才能執行)。</p>')
    parts.append('</div>')

    parts.append('<h3>10.2 跟 L0 結論獨立、但相關的待辦</h3>')
    parts.append('<ol>')
    parts.append('<li><strong>擬合誤差函數權重 8×10⁴ 沒有實證根據,純經驗值</strong>。可能要做 weight sweep 驗證兩個解的存在不是 loss 形狀產物</li>')
    parts.append('<li><strong>5 個撞邊飽和係數的搜尋範圍可能太窄</strong>。尤其 setC 的極端方向偏好暗示真實答案可能超出邊界</li>')
    parts.append('<li><strong>傾斜訊號(預對齊 (dy, dx))沒分析過</strong>。如果未來機台診斷要含對齊偏差,要把這條納入歸因設計(目前 DESIGN §9 沒涵蓋)</li>')
    parts.append('</ol>')

    parts.append('<h3>10.3 整套狀態總結</h3>')
    parts.append('<table>')
    parts.append('<tr><th>階段</th><th>狀態</th></tr>')
    parts.append('<tr><td>L0 setA + setB + setC + setD + 4 組對比 + 10 個深度分析</td><td>✓ 完成 2026-05-15</td></tr>')
    parts.append('<tr><td>DESIGN §9 改寫提案草稿</td><td>✓ 寫完,等使用者 review</td></tr>')
    parts.append('<tr><td>L1 前置驗證計畫</td><td>✓ 寫完,等使用者進實驗室執行</td></tr>')
    parts.append('<tr><td>L1 完整版 / L2 / L3</td><td>待開始</td></tr>')
    parts.append('</table>')

    # === 結語 ===
    parts.append('<hr style="margin-top: 3em;">')
    parts.append('<p class="meta">本綜述產出腳本:<code>PSF_Fitting/quick_recalibration/build_l0_overview_html.py</code>。重新生成時跑該腳本即可。')
    parts.append('主要資料來源:'
                 '<code>validation_experiments/L0_repeat_fit*/outputs/deep_analysis.json</code>(各組),'
                 '<code>validation_experiments/all_sets_comparison.md</code>(跨組對比),'
                 '<code>quick_recalibration/DESIGN_TW.md</code>(設計主文件)。</p>')

    parts.append('</body></html>')

    return '\n'.join(parts)


def main() -> None:
    print("生成 HTML...")
    html = build_html()
    OUT_HTML.write_text(html, encoding="utf-8")
    size_kb = OUT_HTML.stat().st_size / 1024
    print(f"已輸出:{OUT_HTML}({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
