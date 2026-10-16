from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
FIGURES = ROOT / "figures"
FIGURES.mkdir(exist_ok=True)

CONFIGS = [
    ("R140v2 full", "r140_full_frame*.json", "R140v2 整張"),
    ("R140v2 tiled 992/128", "r140_tiled_c992_h128_frame*.json", "R140v2 平衡分塊"),
    ("R140v2 tiled 720/128", "r140_tiled_c720_h128_frame*.json", "R140v2 低記憶體"),
    ("R148v2 full", "r148_full_frame*.json", "R148v2 整張"),
    ("R148v2 tiled 512/24", "r148_tiled_c512_h24_frame*.json", "R148v2 正式分塊"),
]


def q90(values):
    return float(np.percentile(np.asarray(values, dtype=np.float64), 90))


def aggregate(label, pattern, display):
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RUNS.glob(pattern))]
    if len(records) != 3:
        raise RuntimeError(f"Expected three frames for {label}, found {len(records)}")
    times = [v for r in records for v in r["wall_seconds"]]
    diffs = [r["difference_from_full"] for r in records if "difference_from_full" in r]
    row = {
        "configuration": label,
        "display": display,
        "frames": len(records),
        "timed_calls": len(times),
        "median_seconds": statistics.median(times),
        "p90_seconds": q90(times),
        "peak_allocated_gib": max(r["peak_allocated_bytes"] for r in records) / 2**30,
        "peak_reserved_gib": max(r["peak_reserved_bytes"] for r in records) / 2**30,
        "checkpoint_sha256": records[0]["checkpoint_sha256"],
        "device": records[0]["device"],
        "shape": records[0]["shape"],
    }
    if diffs:
        row.update({
            "worst_mean_difference_gray_levels": max(d["mae_gray_levels"] for d in diffs),
            "worst_max_difference_gray_levels": max(d["max_gray_levels"] for d in diffs),
            "worst_changed_u8_percent": 100 * max(d["changed_after_u8_fraction"] for d in diffs),
            "minimum_seam_to_interior_ratio": min(d["seam_to_interior_ratio"] for d in diffs),
            "maximum_seam_to_interior_ratio": max(d["seam_to_interior_ratio"] for d in diffs),
        })
    return row


def font(size, bold=False):
    names = ["msjhbd.ttc" if bold else "msjh.ttc", "arialbd.ttf" if bold else "arial.ttf"]
    for name in names:
        path = Path(r"C:\Windows\Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def hatch(draw, box, index):
    x0, y0, x1, y1 = box
    if index in (0, 1, 2):
        draw.rectangle(box, fill=242, outline=0, width=2)
        step = 18 if index == 0 else 14 if index == 1 else 10
        for yy in range(y0 + 8, y1, step):
            for xx in range(x0 + 8, x1, step):
                r = 2 if index == 0 else 3
                draw.ellipse((xx-r, yy-r, xx+r, yy+r), fill=0)
    elif index == 3:
        draw.rectangle(box, fill=170, outline=0, width=2)
        height = y1 - y0
        for start in range(x0-height, x1+1, 20):
            xa=max(x0,start); ya=y1-(xa-start); xb=min(x1,start+height); yb=y1-(xb-start)
            if xa <= xb: draw.line((xa,ya,xb,yb), fill=50, width=3)
    else:
        draw.rectangle(box, fill=30, outline=0, width=2)


def draw_panel(draw, box, rows, key, ymax, tick, title, unit):
    x0,y0,x1,y1=box; left=x0+95; right=x1-25; top=y0+65; base=y1-100
    f18=font(18); f20=font(20); fb=font(22,True)
    for value in np.arange(0,ymax+0.001,tick):
        yy=base-int((base-top)*value/ymax);draw.line((left,yy,right,yy),fill=218,width=2)
        text=f"{value:g}";bb=draw.textbbox((0,0),text,font=f18);draw.text((left-14-(bb[2]-bb[0]),yy-(bb[3]-bb[1])/2),text,font=f18,fill=0)
    draw.line((left,top,left,base),fill=0,width=3);draw.line((left,base,right,base),fill=0,width=3)
    width=(right-left)/len(rows); bar=min(105,int(width*.44))
    for i,row in enumerate(rows):
        cx=left+(i+.5)*width;value=row[key];by=base-int((base-top)*value/ymax);bx=int(cx-bar/2)
        hatch(draw,(bx,by,bx+bar,base),i)
        text=f"{value:.2f}";bb=draw.textbbox((0,0),text,font=f18);draw.text((cx-(bb[2]-bb[0])/2,by-(bb[3]-bb[1])-7),text,font=f18,fill=0)
        label=row["display"].replace(" ","\n",1); bb=draw.multiline_textbbox((0,0),label,font=f18,align="center",spacing=2);draw.multiline_text((cx-(bb[2]-bb[0])/2,base+10),label,font=f18,fill=0,align="center",spacing=2)
    bb=draw.textbbox((0,0),title,font=fb);draw.text(((x0+x1-(bb[2]-bb[0]))/2,y0+5),title,font=fb,fill=0)
    draw.text((x0+8,top-32),unit,font=f20,fill=0)


def make_figure(rows):
    image=Image.new("L",(2200,980),255);draw=ImageDraw.Draw(image)
    draw_panel(draw,(25,20,1080,950),rows,"median_seconds",3.0,.5,"(a) 重建時間","秒")
    draw_panel(draw,(1120,20,2175,950),rows,"peak_allocated_gib",5.0,1.0,"(b) 顯示卡記憶體峰值","GiB")
    path=FIGURES/"efficiency_time_memory.png";image.save(path,dpi=(200,200));return path


def percent(delta, base):
    return 100.0 * (delta / base - 1.0)


def main():
    rows=[aggregate(*cfg) for cfg in CONFIGS]
    with (ROOT/"benchmark_summary.csv").open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0].keys())+[
            "worst_mean_difference_gray_levels","worst_max_difference_gray_levels","worst_changed_u8_percent",
            "minimum_seam_to_interior_ratio","maximum_seam_to_interior_ratio"])
        writer.writeheader()
        for row in rows:writer.writerow(row)
    (ROOT/"benchmark_summary.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
    make_figure(rows)
    by={r["configuration"]:r for r in rows};r140=by["R140v2 full"];r148=by["R148v2 full"];r140b=by["R140v2 tiled 992/128"];r140l=by["R140v2 tiled 720/128"];r148t=by["R148v2 tiled 512/24"]
    lines=[
        "# R140v2 與 R148v2 重建效率及分塊驗證",
        "",
        "日期：2026-09-28",
        "",
        "## 結論",
        "",
        f"- 若顯示卡記憶體足夠，R140v2 整張重建最快：中位 {r140['median_seconds']:.2f} 秒，模型本身峰值 {r140['peak_allocated_gib']:.2f} GiB。",
        f"- R148v2 的正式 512/24 分塊是最可靠的節省記憶體方案：中位 {r148t['median_seconds']:.2f} 秒、峰值 {r148t['peak_allocated_gib']:.2f} GiB，三張實拍與整張輸出的最壞平均差只有 {r148t['worst_mean_difference_gray_levels']:.2e} 灰階。",
        f"- R140v2 可用 992/128 分塊把峰值降到 {r140b['peak_allocated_gib']:.2f} GiB，但時間增加至 {r140b['median_seconds']:.2f} 秒。三張實拍未見接縫加重；由於其內部處理會受整張尺寸影響，只能稱為實測近似一致。",
        f"- 若記憶體更緊，R140v2 的 720/128 分塊可降到 {r140l['peak_allocated_gib']:.2f} GiB，中位 {r140l['median_seconds']:.2f} 秒。",
        "",
        "## 同條件結果",
        "",
        "| 方案 | 中位時間（秒） | P90（秒） | 模型峰值（GiB） | 暫存保留峰值（GiB） | 與整張輸出差異 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        diff="基準"
        if "worst_mean_difference_gray_levels" in row:
            diff=f"平均最壞 {row['worst_mean_difference_gray_levels']:.2e} 灰階；最大 {row['worst_max_difference_gray_levels']:.3f} 灰階"
        lines.append(f"| {row['display']} | {row['median_seconds']:.2f} | {row['p90_seconds']:.2f} | {row['peak_allocated_gib']:.2f} | {row['peak_reserved_gib']:.2f} | {diff} |")
    lines += [
        "",
        "![時間與記憶體比較](figures/efficiency_time_memory.png)",
        "",
        "## 相對差異",
        "",
        f"- 整張對整張：R140v2 比 R148v2 快 {-percent(r140['median_seconds'],r148['median_seconds']):.1f}%，模型峰值少 {-percent(r140['peak_allocated_gib'],r148['peak_allocated_gib']):.1f}%。",
        f"- R148v2 正式分塊相對自身整張：時間增加 {percent(r148t['median_seconds'],r148['median_seconds']):.1f}%，模型峰值降低 {-percent(r148t['peak_allocated_gib'],r148['peak_allocated_gib']):.1f}%。",
        f"- R140v2 992/128 相對自身整張：時間增加 {percent(r140b['median_seconds'],r140['median_seconds']):.1f}%，模型峰值降低 {-percent(r140b['peak_allocated_gib'],r140['peak_allocated_gib']):.1f}%。",
        f"- 兩者都分塊時，R148v2 512/24 比 R140v2 992/128 快 {-percent(r148t['median_seconds'],r140b['median_seconds']):.1f}%；R140v2 則少用 {-percent(r140b['peak_allocated_gib'],r148t['peak_allocated_gib']):.1f}% 模型記憶體。",
        "",
        "## 分塊策略驗證",
        "",
        "### R148v2",
        "",
        "先以整張影像計算光學提示與全域脈絡，再只把三段原尺寸修正切成 512 像素核心；每塊周圍多讀 24 像素，最後只保留核心。實測 256、512、768、1024 四種核心大小，記憶體都停在約 2.46 GiB，表示主要下限來自仍需整張計算的前半部。512/24 最快，也與模型原設定一致。",
        "",
        "### R140v2",
        "",
        "整個四輪模型連同周圍影像一起分塊，每塊只留下中央核心。核心與周圍範圍都對齊八像素，避免縮放階段錯位。掃描結果顯示 992/128 是速度與記憶體的平衡點，720/128 適合更低記憶體。三張影像的接縫區差異沒有高於一般區域；但這版含整體頻率處理，分塊不具理論上的完全等價。",
        "",
        "## 實驗條件與限制",
        "",
        "- 同一張 NVIDIA RTX A6000、FP32、相同 1544×2064 實拍尺寸、固定最終權重。",
        "- 使用最早、中段與最後三張實拍；整張模式共計時 10 次，主要分塊模式各計時 9 至 10 次，計時前均先預跑。",
        "- 顯示卡記憶體採每個測試程序本身的實際張量峰值；暫存保留峰值另列，方便估計部署餘裕。",
        "- 測試期間 R61 訓練仍在同張顯示卡上執行，使用率約 64% 至 68%。因此相對排序與記憶體結論可用，絕對秒數仍應在訓練結束後再跑一次作正式論文數值。",
        "- 先前 930 張紀錄的 R140v2 1.454 秒與 R148v2 3.075 秒來自不同執行時段，不能直接當成純模型速度差。本次同條件整張比較為 1.32 秒與 1.42 秒。",
        "",
        "## 建議",
        "",
        "1. 現有 RTX A6000 或至少約 5 GiB 可用記憶體：R140v2 直接整張重建。",
        "2. R148v2 正式部署：保留 512/24 分塊，輸出可靠且記憶體較低。",
        "3. R140v2 若必須分塊：一般使用 992/128；記憶體優先使用 720/128。論文中應寫成三張實拍驗證近似一致，不寫成與整張完全相同。",
    ]
    (ROOT/"EFFICIENCY_VALIDATION_REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps(rows,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
