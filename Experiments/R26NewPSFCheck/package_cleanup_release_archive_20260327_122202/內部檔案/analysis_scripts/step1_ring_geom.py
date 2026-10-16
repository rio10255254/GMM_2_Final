"""step1_ring_geom.py — 對 10 張 input BMP 偵測環形幾何，輸出 ring_geometry_per_image.json"""
import cv2, math, json
import numpy as np
from pathlib import Path

PKG    = Path(r"D:\GMM_2_Final\_deployment_package\GeoEdge_R26_使用包")
IN_DIR = PKG / "輸出結果" / "驗證分析" / "R26_external_batch_bundle" / "input_subset"
DEST   = PKG / "輸出結果" / "驗證分析" / "R26_validation_complete"
NAMES  = sorted([f.name for f in IN_DIR.glob("*.bmp")])

def imread_gray(p):
    arr = np.fromfile(str(p), dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(p)
    return img

def detect_ring(img):
    blur = cv2.GaussianBlur(img, (0, 0), 3.0)
    otsu, _ = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    pct = np.percentile(blur, 85)
    mask = (blur >= int(max(otsu, pct))).astype(np.uint8) * 255
    k = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(cv2.morphologyEx(mask, cv2.MORPH_OPEN, k), cv2.MORPH_CLOSE, k)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
    best, best_s = None, -1.0
    for lb in range(1, n):
        a = int(stats[lb, cv2.CC_STAT_AREA])
        if a < 4000:
            continue
        comp = (labels == lb).astype(np.uint8)
        cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        p_len = cv2.arcLength(cnts[0], True)
        if p_len <= 0:
            continue
        circ = 4.0 * math.pi * a / (p_len * p_len)
        cx, cy = cents[lb]
        bm = min(cx, cy, img.shape[1] - cx, img.shape[0] - cy)
        s = a * max(circ, 0.05) * max(bm, 1.0)
        if s > best_s:
            best_s, best = s, lb
    if best is None:
        return {"cx": img.shape[1] / 2.0, "cy": img.shape[0] / 2.0, "peak_r": 500.0, "profile": np.zeros(1)}
    cx, cy = float(cents[best][0]), float(cents[best][1])
    yy, xx = np.indices(img.shape)
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    ridx = np.floor(rr).astype(np.int32)
    rsum = np.bincount(ridx.ravel(), weights=img.ravel().astype(np.float64))
    rcnt = np.bincount(ridx.ravel())
    profile = rsum / np.maximum(rcnt, 1)
    start = min(10, len(profile) - 1)
    peak = int(np.argmax(profile[start:])) + start
    return {"cx": cx, "cy": cy, "peak_r": float(peak), "profile": profile}

results = {}
for name in NAMES:
    img = imread_gray(IN_DIR / name)
    ring = detect_ring(img)
    prof = ring["profile"]
    peak_r = int(ring["peak_r"])
    peak_v = prof[peak_r]
    # Estimate background: median of profile well below ring peak
    bg_start = max(0, peak_r - 400)
    bg_end   = max(1, peak_r - 200)
    bg_val   = float(np.median(prof[bg_start:bg_end])) if bg_end > bg_start else float(np.median(prof[:50]))
    # Background-subtracted half-maximum
    half_v = (peak_v - bg_val) / 2.0 + bg_val
    left = peak_r
    while left > 0 and prof[left] > half_v:
        left -= 1
    right = peak_r
    while right < len(prof) - 1 and prof[right] > half_v:
        right += 1
    fwhm = float(right - left)
    results[name] = {
        "cx": ring["cx"],
        "cy": ring["cy"],
        "peak_r": ring["peak_r"],
        "fwhm": fwhm,
    }
    print(f"{name}: cx={ring['cx']:.1f}, cy={ring['cy']:.1f}, r={ring['peak_r']:.1f}, fwhm={fwhm:.1f}")

with open(DEST / "data" / "ring_geometry_per_image.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\nTask 1 完成 — {len(results)} 張圖的幾何已寫入 ring_geometry_per_image.json")
