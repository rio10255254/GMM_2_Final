"""
Data_Simulation.py
------------------
生成多階段乾淨幾何形狀影像，供後續 PSF 卷積 + 加雜訊訓練使用。
影像為 512x512 灰階 BMP，無任何雜訊，背景具隨機灰階變異性，
並使用 supersampling + anti-aliasing 降低形狀邊緣鋸齒。

輸出結構：
  Training_Data/generated/
    stage_01_triangles/     0001~0100  不規則三角形 + 尖刺三角形
    stage_02_circles/       0101~0200  填充圓形，大小差異大
    stage_03_rectangles/    0201~0300  矩形 + 細長條(thin_bar)
    stage_04_ellipses/      0301~0400  橢圓，軸比多樣
    stage_05_polygons/      0401~0500  不規則多邊形
    stage_06_mixed_simple/  0501~0600  基礎形狀 + 圓環混合
    stage_07_mixed_complex/ 0601~0700  全形狀高密度混合（含圓環）
    stage_08_annulus_focus/ 0701~0800  圓環主導 + 基礎形狀混合
"""

import os
import random
import numpy as np
import cv2
from dataclasses import dataclass
from typing import List, Tuple

# ─────────────────────────────────────────────
#  設定
# ─────────────────────────────────────────────
IMG_SIZE     = 512
OUTPUT_ROOT  = os.path.join(os.path.dirname(__file__), "generated")
FILE_FORMAT  = ".bmp"
SUPERSAMPLE_FACTOR = 8  # 高解析度繪製後下採樣，降低鋸齒

# 背景灰階範圍（純色，無雜訊）—— 涵蓋黑、暗灰、中灰、淺灰
BG_GRAY_RANGE  = (0, 180)

# 形狀灰階範圍（確保與背景有對比）
SHAPE_GRAY_MIN_CONTRAST = 45   # 形狀灰階與背景的最小差距


# ─────────────────────────────────────────────
#  StageConfig
# ─────────────────────────────────────────────
@dataclass
class StageConfig:
    stage_id:         int
    name:             str
    shape_types:      List[str]          # 'triangle','circle','annulus','rectangle','ellipse','polygon'
    start_idx:        int
    end_idx:          int
    num_shapes_range: Tuple[int, int] = (3, 8)
    size_range:       Tuple[int, int] = (20, 120)  # 形狀特徵尺寸範圍 (px)
    shape_gray_range: Tuple[int, int] = (100, 255)  # 形狀灰階範圍


# ─────────────────────────────────────────────
#  形狀繪製函式
# ─────────────────────────────────────────────

def _random_gray(shape_gray_range: Tuple[int, int], bg_val: int) -> int:
    """從 shape_gray_range 中隨機取一個與背景對比足夠的灰階值。"""
    lo, hi = shape_gray_range
    # 收集合格候選值（與背景差距足夠）
    candidates = [c for c in range(lo, hi + 1, 3)
                  if abs(c - bg_val) >= SHAPE_GRAY_MIN_CONTRAST]
    if candidates:
        return random.choice(candidates)
    # 找不到時強制偏移至對側
    return min(255, bg_val + SHAPE_GRAY_MIN_CONTRAST) if bg_val < 128 \
        else max(0, bg_val - SHAPE_GRAY_MIN_CONTRAST)


def _canvas_scale(img_size: int) -> int:
    """工作畫布相對於輸出解析度的整數倍率。"""
    return max(1, img_size // IMG_SIZE)


def _render_environment_defects(canvas: np.ndarray, img_size: int) -> np.ndarray:
    """
    在繪製幾何前，先渲染背景環境瑕疵：
    1) 機率性低頻光照漸層
    2) 光學微塵深色斑塊 + 強高斯模糊
    """
    scale = _canvas_scale(img_size)
    work = canvas.astype(np.float32)

    # 機率性低頻光照漸層（線性矩陣擴展）
    if random.random() < 0.7:
        x = np.linspace(-1.0, 1.0, img_size, dtype=np.float32)
        y = np.linspace(-1.0, 1.0, img_size, dtype=np.float32)
        xv, yv = np.meshgrid(x, y)
        gx = random.uniform(-1.0, 1.0)
        gy = random.uniform(-1.0, 1.0)
        amp = random.uniform(8.0, 28.0)
        bias = random.uniform(-6.0, 6.0)
        gradient = amp * (gx * xv + gy * yv) + bias
        work += gradient

    # 鏡頭微塵斑塊：1~5 個深色區域，半徑 10~80，並施加顯著模糊
    dust = np.zeros_like(work, dtype=np.float32)
    n_spots = random.randint(1, 5)
    for _ in range(n_spots):
        r = random.randint(10 * scale, 80 * scale)
        cx = random.randint(0, img_size - 1)
        cy = random.randint(0, img_size - 1)
        darkness = random.uniform(10.0, 45.0)
        cv2.circle(dust, (cx, cy), r, -darkness, thickness=-1, lineType=cv2.LINE_AA)

    sigma = random.uniform(3.0 * scale, 15.0 * scale)
    dust = cv2.GaussianBlur(dust, (0, 0), sigmaX=sigma, sigmaY=sigma)
    work += dust

    return np.clip(np.rint(work), 0, 255).astype(np.uint8)


# ── 三角形：不規則隨機頂點（確保最小面積避免退化）──────────────
def draw_triangle(canvas: np.ndarray, size_range: Tuple[int, int],
                  gray_range: Tuple[int, int], bg_val: int,
                  img_size: int) -> None:
    """不規則三角形：3 個隨機頂點，角度不均勻，形狀多樣。"""
    s = random.randint(*size_range)
    cx = random.randint(s, img_size - s)
    cy = random.randint(s, img_size - s)
    # 不等分角度產生不規則形狀
    base_angle = random.uniform(0, 360)
    spread1 = random.uniform(60, 150)
    spread2 = random.uniform(60, 150)
    angles = [base_angle, base_angle + spread1, base_angle + spread1 + spread2]
    # 各頂點半徑也不同（產生非等腰三角形）
    radii  = [random.uniform(s * 0.4, s),
              random.uniform(s * 0.4, s),
              random.uniform(s * 0.4, s)]
    pts = [[int(cx + radii[i] * np.cos(np.radians(angles[i]))),
            int(cy + radii[i] * np.sin(np.radians(angles[i])))]
           for i in range(3)]
    pts = np.array(pts, dtype=np.int32)
    color = _random_gray(gray_range, bg_val)
    cv2.fillPoly(canvas, [pts], color, lineType=cv2.LINE_AA)


# ── 尖刺三角形：極細長，像指針或碎片 ──────────────────────────
def draw_spike_triangle(canvas: np.ndarray, size_range: Tuple[int, int],
                        gray_range: Tuple[int, int], bg_val: int,
                        img_size: int) -> None:
    """細長尖銳三角形：底邊窄（5~18px）、長度長（size 的 1.5~3 倍）。"""
    scale = _canvas_scale(img_size)
    length = random.randint(size_range[0], size_range[1]) * random.uniform(1.8, 3.6)
    half_base = random.randint(2 * scale, 12 * scale)
    margin = 10 * scale
    cx = random.randint(margin, img_size - margin)
    cy = random.randint(margin, img_size - margin)
    tip_angle = random.uniform(0, 360)
    tip_rad = np.radians(tip_angle)
    perp_rad = tip_rad + np.pi / 2

    tip  = [cx + length * np.cos(tip_rad),   cy + length * np.sin(tip_rad)]
    base1 = [cx + half_base * np.cos(perp_rad), cy + half_base * np.sin(perp_rad)]
    base2 = [cx - half_base * np.cos(perp_rad), cy - half_base * np.sin(perp_rad)]
    pts = np.array([tip, base1, base2], dtype=np.int32)
    color = _random_gray(gray_range, bg_val)
    cv2.fillPoly(canvas, [pts], color, lineType=cv2.LINE_AA)


# ── 細長條：極窄旋轉矩形，像針、棍棒 ─────────────────────────
def draw_thin_bar(canvas: np.ndarray, size_range: Tuple[int, int],
                  gray_range: Tuple[int, int], bg_val: int,
                  img_size: int) -> None:
    """極細長矩形（長寬比 8:1 ~ 25:1），任意角度旋轉。"""
    scale = _canvas_scale(img_size)
    length = random.randint(size_range[0], size_range[1]) * random.uniform(2.5, 5.0)
    thickness = random.randint(2 * scale, 12 * scale)
    margin = 20 * scale
    cx = random.randint(margin, img_size - margin)
    cy = random.randint(margin, img_size - margin)
    angle = random.uniform(0, 360)
    color = _random_gray(gray_range, bg_val)
    half_l, half_t = length / 2, thickness / 2
    corners = np.array([[-half_l, -half_t], [half_l, -half_t],
                         [half_l,  half_t], [-half_l,  half_t]], dtype=np.float32)
    rot = cv2.getRotationMatrix2D((0, 0), angle, 1.0)[:, :2]
    rotated = (corners @ rot.T).astype(np.int32) + np.array([cx, cy])
    cv2.fillPoly(canvas, [rotated], color, lineType=cv2.LINE_AA)


# ── 圓形：全填充，尺寸差異大 ─────────────────────────────────
def draw_circle(canvas: np.ndarray, size_range: Tuple[int, int],
                gray_range: Tuple[int, int], bg_val: int,
                img_size: int) -> None:
    r = random.randint(max(5, size_range[0] // 2), size_range[1] // 2)
    cx = random.randint(r, img_size - r)
    cy = random.randint(r, img_size - r)
    color = _random_gray(gray_range, bg_val)
    cv2.circle(canvas, (cx, cy), r, color, thickness=-1, lineType=cv2.LINE_AA)


# ── 空心圓環：使用 thickness 控制內外雙邊緣 ───────────────────
def draw_annulus(canvas: np.ndarray, size_range: Tuple[int, int],
                 gray_range: Tuple[int, int], bg_val: int,
                 img_size: int) -> None:
    """空心圓環：外半徑 + 隨機 thickness，模擬失焦後內外邊緣干涉特性。"""
    scale = _canvas_scale(img_size)
    r_out = random.randint(max(6 * scale, size_range[0] // 2), max(7 * scale, size_range[1] // 2))
    min_t = 3 * scale
    max_t = max(4 * scale, int(r_out * 0.4))
    max_t = min(max_t, max(1, r_out - 1))
    thickness = random.randint(min_t, max(min_t, max_t))

    cx = random.randint(r_out, img_size - r_out)
    cy = random.randint(r_out, img_size - r_out)
    color = _random_gray(gray_range, bg_val)
    cv2.circle(canvas, (cx, cy), r_out, color, thickness=thickness, lineType=cv2.LINE_AA)


# ── 矩形：旋轉，允許長寬比差異大 ────────────────────────────
def draw_rectangle(canvas: np.ndarray, size_range: Tuple[int, int],
                   gray_range: Tuple[int, int], bg_val: int,
                   img_size: int) -> None:
    # 長寬可獨立隨機，允許長方形
    w = random.randint(size_range[0], size_range[1])
    h = random.randint(size_range[0] // 2, size_range[1] // 2)
    if random.random() < 0.5:
        w, h = h, w   # 隨機交換長短邊
    cx = random.randint(max(w, h), img_size - max(w, h))
    cy = random.randint(max(w, h), img_size - max(w, h))
    angle = random.uniform(0, 360)
    color = _random_gray(gray_range, bg_val)
    corners = np.array([[-w/2, -h/2], [w/2, -h/2],
                         [w/2,  h/2], [-w/2,  h/2]], dtype=np.float32)
    rot = cv2.getRotationMatrix2D((0, 0), angle, 1.0)[:, :2]
    rotated = (corners @ rot.T).astype(np.int32) + np.array([cx, cy])
    cv2.fillPoly(canvas, [rotated], color, lineType=cv2.LINE_AA)


# ── 橢圓：軸比差異大 ─────────────────────────────────────────
def draw_ellipse(canvas: np.ndarray, size_range: Tuple[int, int],
                 gray_range: Tuple[int, int], bg_val: int,
                 img_size: int) -> None:
    long_ax  = random.randint(size_range[0] // 2, size_range[1] // 2)
    short_ax = random.randint(max(3, long_ax // 6), max(6, long_ax * 5 // 6))
    cx = random.randint(long_ax, img_size - long_ax)
    cy = random.randint(long_ax, img_size - long_ax)
    angle = random.randint(0, 180)
    color = _random_gray(gray_range, bg_val)
    cv2.ellipse(canvas, (cx, cy), (long_ax, short_ax), angle, 0, 360,
                color, thickness=-1, lineType=cv2.LINE_AA)


# ── 不規則多邊形 ──────────────────────────────────────────────
def draw_polygon(canvas: np.ndarray, size_range: Tuple[int, int],
                 gray_range: Tuple[int, int], bg_val: int,
                 img_size: int) -> None:
    n_sides = random.randint(5, 10)
    s = random.randint(*size_range)
    cx = random.randint(s, img_size - s)
    cy = random.randint(s, img_size - s)
    angle_offset = random.uniform(0, 360)
    pts = []
    for k in range(n_sides):
        a = np.radians(angle_offset + k * (360 / n_sides) + random.uniform(-30, 30))
        r = random.uniform(s * 0.3, s)
        pts.append([int(cx + r * np.cos(a)), int(cy + r * np.sin(a))])
    pts = np.array(pts, dtype=np.int32)
    color = _random_gray(gray_range, bg_val)
    cv2.fillPoly(canvas, [pts], color, lineType=cv2.LINE_AA)


DRAW_FUNC_MAP = {
    "triangle":       draw_triangle,
    "spike_triangle": draw_spike_triangle,
    "thin_bar":       draw_thin_bar,
    "circle":         draw_circle,
    "annulus":        draw_annulus,
    "rectangle":      draw_rectangle,
    "ellipse":        draw_ellipse,
    "polygon":        draw_polygon,
}


# ─────────────────────────────────────────────
#  影像生成
# ─────────────────────────────────────────────

def generate_image(cfg: StageConfig, rng_seed: int) -> np.ndarray:
    """生成一張乾淨 512x512 灰階影像。"""
    random.seed(rng_seed)
    np.random.seed(rng_seed)

    # 純色背景（無雜訊）
    bg_val = random.randint(*BG_GRAY_RANGE)
    ss = max(1, int(SUPERSAMPLE_FACTOR))
    work_size = IMG_SIZE * ss
    work_size_range = (cfg.size_range[0] * ss, cfg.size_range[1] * ss)
    canvas = np.full((work_size, work_size), bg_val, dtype=np.uint8)
    canvas = _render_environment_defects(canvas, work_size)

    n_shapes = random.randint(*cfg.num_shapes_range)
    for _ in range(n_shapes):
        shape = random.choice(cfg.shape_types)
        DRAW_FUNC_MAP[shape](canvas, work_size_range, cfg.shape_gray_range, bg_val, work_size)

    if ss > 1:
        canvas = cv2.resize(canvas, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_AREA)
    return canvas


# ─────────────────────────────────────────────
#  批次生成與儲存
# ─────────────────────────────────────────────

def run_stage(cfg: StageConfig, base_seed: int = 0) -> None:
    out_dir = os.path.join(OUTPUT_ROOT, cfg.name)
    os.makedirs(out_dir, exist_ok=True)

    total = cfg.end_idx - cfg.start_idx + 1
    for i, idx in enumerate(range(cfg.start_idx, cfg.end_idx + 1)):
        seed = base_seed + idx
        img = generate_image(cfg, seed)
        filename = f"{idx:04d}{FILE_FORMAT}"
        filepath = os.path.join(out_dir, filename)
        cv2.imwrite(filepath, img)

        if (i + 1) % 10 == 0 or (i + 1) == total:
            print(f"  [{cfg.name}] {i+1}/{total} → {filename}")


def run_pipeline(stages: List[StageConfig], base_seed: int = 42) -> None:
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    print(f"輸出根目錄：{OUTPUT_ROOT}\n")
    for cfg in stages:
        print(f"▶ Stage {cfg.stage_id:02d}：{cfg.name}  ({cfg.start_idx:04d}~{cfg.end_idx:04d})")
        run_stage(cfg, base_seed)
    print("\n全部完成。")


# ─────────────────────────────────────────────
#  階段定義
# ─────────────────────────────────────────────
STAGES: List[StageConfig] = [
    # ── 純三角形：不規則 + 尖刺混合 ────────────────────────────
    StageConfig(
        stage_id=1, name="stage_01_triangles",
        shape_types=["triangle", "triangle", "spike_triangle", "spike_triangle"],  # spike 機率提高
        start_idx=1, end_idx=100,
        num_shapes_range=(10, 20), size_range=(20, 150),
        shape_gray_range=(50, 255),
    ),
    # ── 純圓形：全填充，大小差異大 ─────────────────────────────
    StageConfig(
        stage_id=2, name="stage_02_circles",
        shape_types=["circle"],
        start_idx=101, end_idx=200,
        num_shapes_range=(12, 24), size_range=(12, 145),
        shape_gray_range=(50, 255),
    ),
    # ── 矩形 + 細長條 ───────────────────────────────────────────
    StageConfig(
        stage_id=3, name="stage_03_rectangles",
        shape_types=["rectangle", "rectangle", "thin_bar", "thin_bar"],
        start_idx=201, end_idx=300,
        num_shapes_range=(10, 20), size_range=(18, 150),
        shape_gray_range=(50, 255),
    ),
    # ── 橢圓：軸比差異大 ────────────────────────────────────────
    StageConfig(
        stage_id=4, name="stage_04_ellipses",
        shape_types=["ellipse"],
        start_idx=301, end_idx=400,
        num_shapes_range=(10, 19), size_range=(12, 150),
        shape_gray_range=(50, 255),
    ),
    # ── 不規則多邊形 ────────────────────────────────────────────
    StageConfig(
        stage_id=5, name="stage_05_polygons",
        shape_types=["polygon"],
        start_idx=401, end_idx=500,
        num_shapes_range=(9, 18), size_range=(20, 150),
        shape_gray_range=(50, 255),
    ),
    # ── 混合（不含 spike/thin_bar）：中複雜度 + 圓環 ───────────
    StageConfig(
        stage_id=6, name="stage_06_mixed_simple",
        shape_types=["triangle", "circle", "annulus", "rectangle", "ellipse", "polygon", "polygon"],
        start_idx=501, end_idx=600,
        num_shapes_range=(14, 28), size_range=(12, 145),
        shape_gray_range=(40, 255),
    ),
    # ── 混合（含全部形狀）：高複雜度、高密度（含圓環） ─────────
    StageConfig(
        stage_id=7, name="stage_07_mixed_complex",
        shape_types=["triangle", "triangle", "spike_triangle", "spike_triangle", "spike_triangle",
                     "circle", "rectangle", "rectangle", "thin_bar", "thin_bar", "thin_bar",
                     "ellipse", "polygon", "polygon", "annulus", "annulus"],
        start_idx=601, end_idx=700,
        num_shapes_range=(20, 36), size_range=(8, 165),
        shape_gray_range=(30, 255),
    ),
    # ── 圓環主導 + 基礎形狀混合 ─────────────────────────────────
    StageConfig(
        stage_id=8, name="stage_08_annulus_focus",
        shape_types=["annulus", "annulus", "annulus", "circle", "ellipse", "triangle", "rectangle", "polygon"],
        start_idx=701, end_idx=800,
        num_shapes_range=(16, 30), size_range=(10, 160),
        shape_gray_range=(30, 255),
    ),
]


# ─────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    run_pipeline(STAGES, base_seed=42)
