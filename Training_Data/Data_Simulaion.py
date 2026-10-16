"""
Data_Simulation.py
------------------
生成多階段乾淨幾何形狀影像，供後續 PSF 卷積 + 加雜訊訓練使用。
影像為 512x512 灰階，無任何雜訊，背景具隨機灰階變異性，
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
    stage_09_annulus_non_overlap/ 0801~0900  純圓環，外接圓彼此不重疊
    stage_10_annulus_overlap/     0901~1000  純圓環，允許互相重疊
    stage_11_surface_defect_non_overlap/ 1001~1100  純背景裂紋/缺口瑕疵，不重疊
    stage_12_surface_defect_overlap/     1101~1200  純背景裂紋/缺口瑕疵，可重疊
    stage_13_curve_clean_general/        1201~1300  曲邊主導、較乾淨背景，保留泛化
    stage_14_annulus_edge_defect_focus/  1301~1400  圓環邊緣缺口/崩邊主導
    stage_15_annulus_sparse_clean/       1401~1500  稀疏大型曲邊，貼近單圓環樣本
    stage_16_annulus_sparse_defect_clean/1501~1600  稀疏大型缺口曲邊，保留真實邊界瑕疵
    stage_17_annulus_microstep_clean/    1601~1650  高 supersample 微位移曲邊，對齊 0.08px
    stage_18_annulus_microstep_defect/   1651~1700  高 supersample 微位移缺口曲邊，保留真實感
    stage_19_annulus_microstep_sequence_clean/   1701~1775  同場景微位移序列，對齊 0.08px
    stage_20_annulus_microstep_sequence_defect/  1776~1850  同場景微位移缺口序列
    stage_21_annulus_gmf_sequence_clean/         1851~1925  大型單圓環微位移序列，對齊 GMF 全環模型
    stage_22_annulus_gmf_sequence_defect/        1926~2000  大型單圓環缺口微位移序列，保留真實瑕疵
    stage_23_annulus_gmf_sequence_mid_clean/     2001~2075  大型單圓環 0.8px 位移序列
    stage_24_annulus_gmf_sequence_mid_defect/    2076~2150  大型單圓環 0.8px 缺口位移序列
    stage_25_annulus_gmf_sequence_macro_clean/   2151~2225  大型單圓環 8px 位移序列
    stage_26_annulus_gmf_sequence_macro_defect/  2226~2300  大型單圓環 8px 缺口位移序列
"""

import os
import random
import numpy as np
import cv2
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

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
ENV_DEFECT_RENDER_SIZE = IMG_SIZE  # 背景瑕疵以輸出解析度渲染，再上採樣以加速

# 執行控制（在程式內直接設定，不需要命令列）
# [] 代表執行全部 stage；例如 [11, 12] 只跑純背景裂紋/缺口瑕疵
RUN_STAGE_IDS: List[int] = []
RUN_BASE_SEED: int = 42


# ─────────────────────────────────────────────
#  StageConfig
# ─────────────────────────────────────────────
@dataclass
class StageConfig:
    stage_id:         int
    name:             str
    shape_types:      List[str]          # 'triangle','circle','annulus','rectangle','ellipse','polygon','micro_defect','annulus_edge_defect'
    start_idx:        int
    end_idx:          int
    num_shapes_range: Tuple[int, int] = (3, 8)
    size_range:       Tuple[int, int] = (20, 120)  # 形狀特徵尺寸範圍 (px)
    shape_gray_range: Tuple[int, int] = (100, 255)  # 形狀灰階範圍
    annulus_no_overlap: bool = False
    micro_no_overlap: bool = False
    edge_annulus_no_overlap: bool = False
    edge_notch_allow_overlap: bool = False
    render_scale: int = SUPERSAMPLE_FACTOR
    background_mode: str = "full"  # 'full' | 'mild' | 'flat'
    bg_gray_range: Optional[Tuple[int, int]] = None
    max_place_attempts_per_shape: int = 80
    output_ext: str = FILE_FORMAT
    save_bit_depth: int = 8
    sequence_length: int = 1
    sequence_step_px: float = 0.0
    sequence_axis: str = "y"


def _normalize_output_ext(ext: str) -> str:
    ext = str(ext).strip().lower()
    if not ext:
        ext = FILE_FORMAT
    if not ext.startswith("."):
        ext = "." + ext
    if ext not in {".bmp", ".png", ".tif", ".tiff"}:
        raise ValueError(f"Unsupported output extension: {ext}")
    return ext


def _quantize_output_image(img: np.ndarray, bit_depth: int) -> np.ndarray:
    img_f = np.asarray(img, dtype=np.float32)
    img_f = np.clip(img_f, 0.0, 255.0)
    if int(bit_depth) >= 16:
        return np.clip(np.rint(img_f * (65535.0 / 255.0)), 0, 65535).astype(np.uint16)
    return np.clip(np.rint(img_f), 0, 255).astype(np.uint8)


def _render_stage_canvas(cfg: StageConfig, rng_seed: int) -> tuple[np.ndarray, int, int]:
    random.seed(rng_seed)
    np.random.seed(rng_seed)

    bg_range = cfg.bg_gray_range if cfg.bg_gray_range is not None else BG_GRAY_RANGE
    bg_val = random.randint(int(bg_range[0]), int(bg_range[1]))
    annulus_only = set(cfg.shape_types) == {"annulus"}
    micro_only = set(cfg.shape_types) == {"micro_defect"}
    edge_annulus_only = set(cfg.shape_types) == {"annulus_edge_defect"}

    ss = max(1, int(getattr(cfg, "render_scale", SUPERSAMPLE_FACTOR)))
    work_size = IMG_SIZE * ss
    work_size_range = (cfg.size_range[0] * ss, cfg.size_range[1] * ss)
    canvas = np.full((work_size, work_size), bg_val, dtype=np.uint8)
    bg_mode = str(getattr(cfg, "background_mode", "full")).lower()
    if bg_mode == "mild":
        canvas = _render_mild_background(bg_val, work_size)
    elif bg_mode == "flat":
        pass
    else:
        canvas = _render_environment_defects(canvas, work_size)

    n_shapes = random.randint(*cfg.num_shapes_range)
    if annulus_only and bool(cfg.annulus_no_overlap):
        _draw_annulus_non_overlap(
            canvas=canvas,
            n_shapes=n_shapes,
            size_range=work_size_range,
            gray_range=cfg.shape_gray_range,
            bg_val=bg_val,
            img_size=work_size,
            max_attempts_per_shape=cfg.max_place_attempts_per_shape,
        )
    elif micro_only:
        _draw_micro_defects(
            canvas=canvas,
            n_shapes=n_shapes,
            size_range=work_size_range,
            gray_range=cfg.shape_gray_range,
            bg_val=bg_val,
            img_size=work_size,
            no_overlap=bool(cfg.micro_no_overlap),
            max_attempts_per_shape=cfg.max_place_attempts_per_shape,
        )
    elif edge_annulus_only:
        _draw_annulus_edge_defects(
            canvas=canvas,
            n_shapes=n_shapes,
            size_range=work_size_range,
            gray_range=cfg.shape_gray_range,
            bg_val=bg_val,
            img_size=work_size,
            no_overlap=bool(cfg.edge_annulus_no_overlap),
            notch_allow_overlap=bool(cfg.edge_notch_allow_overlap),
            max_attempts_per_shape=cfg.max_place_attempts_per_shape,
        )
    else:
        for _ in range(n_shapes):
            shape = random.choice(cfg.shape_types)
            DRAW_FUNC_MAP[shape](canvas, work_size_range, cfg.shape_gray_range, bg_val, work_size)
    return canvas, int(bg_val), int(ss)


def _shift_highres_canvas(canvas: np.ndarray, dx_px: float, dy_px: float, bg_val: int) -> np.ndarray:
    h, w = canvas.shape
    M = np.array([[1.0, 0.0, float(dx_px)], [0.0, 1.0, float(dy_px)]], dtype=np.float32)
    shifted = cv2.warpAffine(
        canvas.astype(np.float32),
        M,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=float(bg_val),
    )
    return shifted


def _finalize_canvas_image(canvas: np.ndarray, cfg: StageConfig) -> np.ndarray:
    bit_depth = int(getattr(cfg, "save_bit_depth", 8))
    ss = max(1, int(getattr(cfg, "render_scale", SUPERSAMPLE_FACTOR)))
    if ss > 1:
        resize_src = canvas.astype(np.float32) if bit_depth >= 16 else canvas
        canvas = cv2.resize(resize_src, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_AREA)
    elif bit_depth >= 16:
        canvas = canvas.astype(np.float32)
    return _quantize_output_image(canvas, bit_depth)


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


def _sample_center_with_margin(img_size: int, margin: int) -> Tuple[int, int]:
    """依外接 margin 在畫布內隨機取中心。"""
    m = int(max(1, min(margin, (img_size // 2) - 1)))
    cx = random.randint(m, img_size - m)
    cy = random.randint(m, img_size - m)
    return cx, cy


_NORM_AXIS_CACHE = {}


def _get_norm_axis(size: int) -> np.ndarray:
    """快取正規化座標軸，避免每張圖重建。"""
    axis = _NORM_AXIS_CACHE.get(size)
    if axis is None:
        axis = np.linspace(-1.0, 1.0, size, dtype=np.float32)
        _NORM_AXIS_CACHE[size] = axis
    return axis


def _render_environment_defects(canvas: np.ndarray, img_size: int) -> np.ndarray:
    """
    在繪製幾何前，先渲染背景環境瑕疵：
    1) 機率性低頻光照漸層
    2) 光學微塵深色斑塊 + 強高斯模糊
    """
    # 低頻背景瑕疵不需要在 supersample 畫布渲染；先在較小尺寸生成再上採樣即可
    defect_size = min(img_size, ENV_DEFECT_RENDER_SIZE)
    bg_val = float(canvas[0, 0])
    defect = np.full((defect_size, defect_size), bg_val, dtype=np.float32)

    # 機率性低頻光照漸層（線性矩陣擴展）
    if random.random() < 0.7:
        axis = _get_norm_axis(defect_size)
        gx = random.uniform(-1.0, 1.0)
        gy = random.uniform(-1.0, 1.0)
        amp = random.uniform(8.0, 28.0)
        bias = random.uniform(-6.0, 6.0)
        gradient = amp * (gx * axis[None, :] + gy * axis[:, None]) + bias
        defect += gradient

    # 鏡頭微塵斑塊：1~5 個深色區域，半徑 10~80，並施加顯著模糊
    dust = np.zeros((defect_size, defect_size), dtype=np.float32)
    n_spots = random.randint(1, 5)
    for _ in range(n_spots):
        r = random.randint(10, 80)
        cx = random.randint(0, defect_size - 1)
        cy = random.randint(0, defect_size - 1)
        darkness = random.uniform(10.0, 45.0)
        cv2.circle(dust, (cx, cy), r, -darkness, thickness=-1, lineType=cv2.LINE_AA)

    sigma = random.uniform(3.0, 15.0)
    dust = cv2.GaussianBlur(dust, (0, 0), sigmaX=sigma, sigmaY=sigma)
    defect += dust

    if defect_size != img_size:
        defect = cv2.resize(defect, (img_size, img_size), interpolation=cv2.INTER_CUBIC)

    return np.clip(np.rint(defect), 0, 255).astype(np.uint8)


def _render_mild_background(bg_val: int, img_size: int) -> np.ndarray:
    """
    較平滑的背景（給 annulus_edge_defect 用），
    保留弱漸層與低幅度模糊起伏，避免大型黑斑。
    """
    canvas = np.full((img_size, img_size), float(bg_val), dtype=np.float32)

    if random.random() < 0.9:
        axis = _get_norm_axis(img_size)
        gx = random.uniform(-0.8, 0.8)
        gy = random.uniform(-0.8, 0.8)
        amp = random.uniform(3.0, 12.0)
        bias = random.uniform(-3.0, 3.0)
        grad = amp * (gx * axis[None, :] + gy * axis[:, None]) + bias
        canvas += grad

    # 低對比、低頻紋理
    tex = np.random.normal(0.0, 2.0, size=(img_size, img_size)).astype(np.float32)
    tex = cv2.GaussianBlur(tex, (0, 0), sigmaX=img_size / 140.0, sigmaY=img_size / 140.0)
    canvas += tex

    return np.clip(np.rint(canvas), 0, 255).astype(np.uint8)


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
    cx, cy, r_out, thickness = _sample_annulus_params(size_range, img_size)
    color = _random_gray(gray_range, bg_val)
    cv2.circle(canvas, (cx, cy), r_out, color, thickness=thickness, lineType=cv2.LINE_AA)


def _sample_annulus_params(size_range: Tuple[int, int], img_size: int) -> Tuple[int, int, int, int]:
    """抽樣圓環參數，供一般與不重疊模式共用。"""
    scale = _canvas_scale(img_size)
    r_out = random.randint(max(6 * scale, size_range[0] // 2), max(7 * scale, size_range[1] // 2))
    min_t = 3 * scale
    max_t = max(4 * scale, int(r_out * 0.4))
    max_t = min(max_t, max(1, r_out - 1))
    thickness = random.randint(min_t, max(min_t, max_t))

    cx = random.randint(r_out, img_size - r_out)
    cy = random.randint(r_out, img_size - r_out)
    return cx, cy, r_out, thickness


def _draw_annulus_non_overlap(canvas: np.ndarray, n_shapes: int,
                              size_range: Tuple[int, int], gray_range: Tuple[int, int],
                              bg_val: int, img_size: int,
                              max_attempts_per_shape: int = 80) -> None:
    """
    繪製互不重疊圓環（以外接圓不相交為準）。
    若密度過高無法放滿，會在嘗試上限後提前結束。
    """
    placed: List[Tuple[int, int, int]] = []
    scale = _canvas_scale(img_size)
    gap = max(1, 2 * scale)  # 額外安全間隔，避免 AA 邊界視覺上黏連
    max_tries = max(1, int(max_attempts_per_shape)) * max(1, n_shapes)
    tries = 0

    while len(placed) < n_shapes and tries < max_tries:
        tries += 1
        cx, cy, r_out, thickness = _sample_annulus_params(size_range, img_size)
        ok = True
        for px, py, pr in placed:
            min_dist = r_out + pr + gap
            if (cx - px) * (cx - px) + (cy - py) * (cy - py) < min_dist * min_dist:
                ok = False
                break
        if not ok:
            continue

        color = _random_gray(gray_range, bg_val)
        cv2.circle(canvas, (cx, cy), r_out, color, thickness=thickness, lineType=cv2.LINE_AA)
        placed.append((cx, cy, r_out))


def _sample_annulus_edge_defect_spec(size_range: Tuple[int, int], img_size: int) -> Dict[str, float]:
    """
    抽樣「圓環邊緣缺口」瑕疵規格。
    size_range 以「直徑」語意解讀，內部轉為半徑。
    """
    scale = _canvas_scale(img_size)
    margin = 12 * scale
    r_min_cfg = max(12 * scale, size_range[0] // 2)
    r_max_cfg = max(r_min_cfg + 1, size_range[1] // 2)
    r_cap = max(r_min_cfg + 1, (img_size // 2) - margin)
    r_min = min(r_min_cfg, r_cap - 1)
    r_max = max(r_min + 1, min(r_max_cfg, r_cap))

    r_out = random.randint(r_min, r_max)
    t_min = max(6 * scale, int(r_out * 0.08))
    t_max = max(t_min, min(int(r_out * 0.24), r_out - 3 * scale))
    thickness = random.randint(t_min, t_max)
    r_in = max(2 * scale, r_out - thickness)

    safe_r = r_out + int(thickness * 0.9) + 4 * scale
    cx, cy = _sample_center_with_margin(img_size, safe_r)
    n_notches = random.randint(8, 18)
    n_inner_spots = random.randint(2, 8)

    return {
        "cx": cx, "cy": cy, "r_out": r_out, "r_in": r_in, "thickness": thickness,
        "n_notches": n_notches, "n_inner_spots": n_inner_spots, "safe_r": safe_r
    }


def _draw_annulus_edge_defect_from_spec(canvas: np.ndarray, spec: Dict[str, float],
                                        gray_range: Tuple[int, int], bg_val: int,
                                        img_size: int,
                                        notch_allow_overlap: bool = False) -> None:
    """
    繪製亮圓環，並在內外邊緣加入缺口/崩邊/短裂紋，使外觀接近顯微缺陷樣貌。
    """
    scale = _canvas_scale(img_size)
    cx = int(spec["cx"])
    cy = int(spec["cy"])
    r_out = int(spec["r_out"])
    r_in = int(spec["r_in"])
    thickness = int(spec["thickness"])
    n_notches = int(spec["n_notches"])
    n_inner_spots = int(spec["n_inner_spots"])
    lo, hi = gray_range

    # 先把物件周邊抬到中灰，再疊亮環與圓盤，避免出現過黑背景。
    local_bg = int(np.clip(max(int(bg_val), 95) + random.randint(-6, 12), lo, hi))
    cv2.circle(canvas, (cx, cy), int(r_out * 1.36), local_bg, thickness=-1, lineType=cv2.LINE_AA)
    core_color = int(np.clip(local_bg + random.randint(6, 20), lo, hi))
    ring_color = int(np.clip(core_color + random.randint(55, 95), lo, hi))
    if ring_color - core_color < 18:
        ring_color = int(np.clip(core_color + random.randint(18, 45), lo, hi))
    cv2.circle(canvas, (cx, cy), r_in, core_color, thickness=-1, lineType=cv2.LINE_AA)
    cv2.circle(canvas, (cx, cy), r_out, ring_color, thickness=thickness, lineType=cv2.LINE_AA)

    # 缺口角度採「群聚 + 少量均勻」混合，避免過度規則。
    hotspots = [random.uniform(0.0, 2.0 * np.pi) for _ in range(random.randint(1, 3))]
    placed_notches: List[Tuple[int, int, int]] = []
    tries = 0
    max_tries = max(40, n_notches * 20)

    while len(placed_notches) < n_notches and tries < max_tries:
        tries += 1
        if random.random() < 0.74:
            h = random.choice(hotspots)
            ang = (h + random.gauss(0.0, 0.22)) % (2.0 * np.pi)
        else:
            ang = random.uniform(0.0, 2.0 * np.pi)

        on_outer = (random.random() < 0.78)
        notch_r_min = max(1 * scale, int(thickness * 0.05))
        notch_r_max = max(notch_r_min + 1, min(7 * scale, int(thickness * 0.18)))
        notch_r = random.randint(notch_r_min, notch_r_max)
        if on_outer:
            radial = r_out + random.uniform(-0.05 * thickness, 0.18 * thickness)
        else:
            radial = r_in + random.uniform(-0.18 * thickness, 0.05 * thickness)
        x = int(cx + radial * np.cos(ang))
        y = int(cy + radial * np.sin(ang))

        if (x < 1) or (x >= img_size - 1) or (y < 1) or (y >= img_size - 1):
            continue

        if not notch_allow_overlap:
            ok = True
            for px, py, pr in placed_notches:
                min_dist = notch_r + pr + max(1, scale)
                if (x - px) * (x - px) + (y - py) * (y - py) < min_dist * min_dist:
                    ok = False
                    break
            if not ok:
                continue

        notch_color = int(np.clip(int(0.65 * core_color + 0.35 * local_bg) + random.randint(-12, 4), lo, hi))
        cv2.circle(canvas, (x, y), notch_r, notch_color, thickness=-1, lineType=cv2.LINE_AA)

        # 部分缺口拉長成崩邊形狀。
        if random.random() < 0.28:
            major = max(notch_r + 1, int(notch_r * random.uniform(1.2, 1.8)))
            minor = max(1, int(notch_r * random.uniform(0.55, 0.95)))
            deg = float(np.degrees(ang + random.uniform(-0.6, 0.6)))
            cv2.ellipse(canvas, (x, y), (major, minor), deg, 0, 360, notch_color, thickness=-1, lineType=cv2.LINE_AA)

        # 少量短裂紋由缺口延伸。
        if random.random() < 0.22:
            line_len = random.randint(max(1 * scale, int(notch_r * 1.4)),
                                      max(2 * scale, int(notch_r * 3.2)))
            dir_ang = ang + random.choice([-1.0, 1.0]) * random.uniform(0.6, 1.4)
            x2 = int(x + line_len * np.cos(dir_ang))
            y2 = int(y + line_len * np.sin(dir_ang))
            cv2.line(canvas, (x, y), (x2, y2), notch_color, thickness=max(1, scale // 2), lineType=cv2.LINE_AA)

        # 少量亮色邊緣堆積（類似崩邊凸起）。
        if random.random() < 0.16:
            burr_r = max(1, int(notch_r * random.uniform(0.8, 1.6)))
            b_ang = ang + random.uniform(-0.28, 0.28)
            b_rad = r_out + random.uniform(-0.08 * thickness, 0.22 * thickness)
            bx = int(cx + b_rad * np.cos(b_ang))
            by = int(cy + b_rad * np.sin(b_ang))
            burr_color = int(np.clip(ring_color + random.randint(6, 20), lo, hi))
            cv2.circle(canvas, (bx, by), burr_r, burr_color, thickness=-1, lineType=cv2.LINE_AA)

        placed_notches.append((x, y, notch_r))

    # 圓盤內部加入少量弱對比斑點，貼近顯微影像質感。
    for _ in range(n_inner_spots):
        a = random.uniform(0.0, 2.0 * np.pi)
        d = random.uniform(0.0, max(3.0, r_in * 0.86))
        rr = random.randint(max(1, scale // 2), max(1, min(3 * scale, int(thickness * 0.10))))
        x = int(cx + d * np.cos(a))
        y = int(cy + d * np.sin(a))
        if x - rr < 0 or y - rr < 0 or x + rr >= img_size or y + rr >= img_size:
            continue
        c = int(np.clip(core_color + random.randint(-8, 8), lo, hi))
        cv2.circle(canvas, (x, y), rr, c, thickness=-1, lineType=cv2.LINE_AA)

    # 輕度局部模糊，讓邊緣更接近實拍柔化效果。
    pad = int(thickness * 1.1 + 6 * scale)
    x0 = max(0, cx - r_out - pad)
    x1 = min(img_size, cx + r_out + pad)
    y0 = max(0, cy - r_out - pad)
    y1 = min(img_size, cy + r_out + pad)
    if (x1 - x0) > 4 and (y1 - y0) > 4:
        patch = canvas[y0:y1, x0:x1].astype(np.float32)
        sigma = max(0.6 * scale, thickness * 0.028)
        blur = cv2.GaussianBlur(patch, (0, 0), sigmaX=sigma, sigmaY=sigma)
        blend = random.uniform(0.10, 0.22)
        patch = np.clip((1.0 - blend) * patch + blend * blur, 0, 255).astype(np.uint8)
        canvas[y0:y1, x0:x1] = patch


def draw_annulus_edge_defect(canvas: np.ndarray, size_range: Tuple[int, int],
                             gray_range: Tuple[int, int], bg_val: int,
                             img_size: int) -> None:
    """單一圓環邊緣缺口瑕疵。"""
    spec = _sample_annulus_edge_defect_spec(size_range, img_size)
    _draw_annulus_edge_defect_from_spec(
        canvas=canvas,
        spec=spec,
        gray_range=gray_range,
        bg_val=bg_val,
        img_size=img_size,
        notch_allow_overlap=False,
    )


def _draw_annulus_edge_defects(canvas: np.ndarray, n_shapes: int,
                               size_range: Tuple[int, int], gray_range: Tuple[int, int],
                               bg_val: int, img_size: int,
                               no_overlap: bool = False,
                               notch_allow_overlap: bool = False,
                               max_attempts_per_shape: int = 80) -> None:
    """批次繪製 annulus edge defect，可控制圓環間與缺口間重疊策略。"""
    placed: List[Tuple[int, int, int]] = []
    scale = _canvas_scale(img_size)
    gap = max(1, 3 * scale)
    max_tries = max(1, int(max_attempts_per_shape)) * max(1, n_shapes) if no_overlap else max(1, n_shapes)
    tries = 0
    drawn = 0

    while drawn < n_shapes and tries < max_tries:
        tries += 1
        spec = _sample_annulus_edge_defect_spec(size_range, img_size)
        cx = int(spec["cx"])
        cy = int(spec["cy"])
        safe_r = int(spec["safe_r"])

        if no_overlap:
            ok = True
            for px, py, pr in placed:
                min_dist = safe_r + pr + gap
                if (cx - px) * (cx - px) + (cy - py) * (cy - py) < min_dist * min_dist:
                    ok = False
                    break
            if not ok:
                continue

        _draw_annulus_edge_defect_from_spec(
            canvas=canvas,
            spec=spec,
            gray_range=gray_range,
            bg_val=bg_val,
            img_size=img_size,
            notch_allow_overlap=bool(notch_allow_overlap),
        )
        drawn += 1
        if no_overlap:
            placed.append((cx, cy, safe_r))


def _random_micro_gray(gray_range: Tuple[int, int], bg_val: int) -> int:
    """細微瑕疵灰階：偏低對比，模擬顯微缺陷不明顯的亮暗變化。"""
    lo, hi = gray_range
    delta = random.randint(10, 55)
    sign = -1 if random.random() < 0.7 else 1  # 多數瑕疵偏暗
    val = int(np.clip(int(bg_val) + sign * delta, lo, hi))
    if abs(val - int(bg_val)) < 8:
        if bg_val >= 128:
            val = int(np.clip(int(bg_val) - 8, lo, hi))
        else:
            val = int(np.clip(int(bg_val) + 8, lo, hi))
    return val


def _sample_micro_defect_spec(size_range: Tuple[int, int], img_size: int) -> Dict[str, float]:
    """
    抽樣一個細微瑕疵規格，並給出 safe_r（外接安全半徑）供不重疊檢查。
    種類包含：crack / notch / pit（裂紋與缺口為主）。
    """
    scale = _canvas_scale(img_size)
    kind = random.choices(
        ["crack", "notch", "pit"],
        weights=[0.58, 0.34, 0.08],
        k=1,
    )[0]

    min_s = max(2 * scale, size_range[0] // 6)
    max_s = max(min_s + 1, size_range[1] // 4)

    if kind == "crack":
        length = random.randint(max(12 * scale, size_range[0]), max(16 * scale, int(size_range[1] * 2.2)))
        thickness = random.randint(max(1, scale), max(1, int(2.0 * scale)))
        angle = random.uniform(0.0, np.pi)
        jitter = random.uniform(0.18, 0.55)
        n_segments = random.randint(4, 7)
        branch_prob = random.uniform(0.25, 0.65)
        safe_r = int(length * 0.70 + 4 * scale)
        cx, cy = _sample_center_with_margin(img_size, safe_r)
        return {
            "kind": kind, "cx": cx, "cy": cy, "length": length,
            "thickness": thickness, "angle": angle, "jitter": jitter,
            "n_segments": n_segments, "branch_prob": branch_prob, "safe_r": safe_r
        }

    if kind == "notch":
        body_r = random.randint(max(5 * scale, min_s), max(7 * scale, int(size_range[1] * 0.45)))
        cut_r = random.randint(max(2 * scale, int(body_r * 0.35)), max(3 * scale, int(body_r * 0.75)))
        cut_angle = random.uniform(0.0, 2.0 * np.pi)
        cut_shift = random.uniform(body_r * 0.45, body_r * 0.9)
        safe_r = int(body_r + cut_r + 3 * scale)
        cx, cy = _sample_center_with_margin(img_size, safe_r)
        return {
            "kind": "notch", "cx": cx, "cy": cy, "body_r": body_r,
            "cut_r": cut_r, "cut_angle": cut_angle, "cut_shift": cut_shift, "safe_r": safe_r
        }

    radius = random.randint(min_s, max_s)
    safe_r = radius + 2 * scale
    cx, cy = _sample_center_with_margin(img_size, safe_r)
    return {
        "kind": "pit", "cx": cx, "cy": cy, "radius": radius, "safe_r": safe_r
    }


def _draw_micro_defect_from_spec(canvas: np.ndarray, spec: Dict[str, float],
                                 gray_range: Tuple[int, int], bg_val: int,
                                 img_size: int) -> None:
    """依 spec 在畫布上繪製單一細微瑕疵。"""
    kind = str(spec["kind"])
    cx = int(spec["cx"])
    cy = int(spec["cy"])
    color = _random_micro_gray(gray_range, bg_val)
    scale = _canvas_scale(img_size)

    if kind == "pit":
        cv2.circle(canvas, (cx, cy), int(spec["radius"]), color, thickness=-1, lineType=cv2.LINE_AA)
        return

    if kind == "crack":
        length = float(spec["length"])
        angle = float(spec["angle"])
        thickness = int(spec["thickness"])
        jitter = float(spec["jitter"])
        n_segments = int(spec["n_segments"])
        branch_prob = float(spec["branch_prob"])

        # 主裂紋：多段折線，角度逐步抖動。
        seg_len = length / max(1, n_segments - 1)
        x = cx - 0.5 * length * np.cos(angle)
        y = cy - 0.5 * length * np.sin(angle)
        pts = [[x, y]]
        cur_angle = angle
        for _ in range(max(1, n_segments - 1)):
            cur_angle += random.uniform(-jitter, jitter)
            x += seg_len * np.cos(cur_angle)
            y += seg_len * np.sin(cur_angle)
            pts.append([x, y])
        pts_arr = np.array(pts, dtype=np.float32).reshape(-1, 1, 2).astype(np.int32)
        cv2.polylines(canvas, [pts_arr], isClosed=False, color=color, thickness=thickness, lineType=cv2.LINE_AA)

        # 次分支裂紋：從主裂紋中段長出短分支。
        if len(pts) >= 3 and random.random() < branch_prob:
            pivot = random.randint(1, len(pts) - 2)
            bx, by = pts[pivot]
            b_len = length * random.uniform(0.18, 0.42)
            b_ang = cur_angle + random.choice([-1.0, 1.0]) * random.uniform(0.6, 1.3)
            b_x = bx + b_len * np.cos(b_ang)
            b_y = by + b_len * np.sin(b_ang)
            b_pts = np.array([[bx, by], [b_x, b_y]], dtype=np.float32).reshape(-1, 1, 2).astype(np.int32)
            cv2.polylines(canvas, [b_pts], isClosed=False, color=color, thickness=max(1, thickness - 1), lineType=cv2.LINE_AA)
        return

    if kind == "notch":
        body_r = int(spec["body_r"])
        cut_r = int(spec["cut_r"])
        cut_angle = float(spec["cut_angle"])
        cut_shift = float(spec["cut_shift"])

        # 先畫實心微結構，再用背景色切掉一塊，形成「缺口」。
        cv2.circle(canvas, (cx, cy), body_r, color, thickness=-1, lineType=cv2.LINE_AA)
        cut_x = int(cx + cut_shift * np.cos(cut_angle))
        cut_y = int(cy + cut_shift * np.sin(cut_angle))
        cut_color = int(np.clip(int(bg_val) + random.randint(-8 * scale, 8 * scale), 0, 255))
        cv2.circle(canvas, (cut_x, cut_y), cut_r, cut_color, thickness=-1, lineType=cv2.LINE_AA)

        # 少量加入 V 型切角，讓缺口邊緣更尖銳。
        if random.random() < 0.45:
            tip = np.array([cut_x, cut_y], dtype=np.float32)
            base_dir = np.array([np.cos(cut_angle), np.sin(cut_angle)], dtype=np.float32)
            perp = np.array([-base_dir[1], base_dir[0]], dtype=np.float32)
            p1 = tip + base_dir * cut_r * 0.9 + perp * cut_r * 0.45
            p2 = tip + base_dir * cut_r * 0.9 - perp * cut_r * 0.45
            tri = np.array([tip, p1, p2], dtype=np.int32)
            cv2.fillPoly(canvas, [tri], cut_color, lineType=cv2.LINE_AA)
        return


def draw_micro_defect(canvas: np.ndarray, size_range: Tuple[int, int],
                      gray_range: Tuple[int, int], bg_val: int,
                      img_size: int) -> None:
    """單一細微瑕疵（可重疊模式使用）。"""
    spec = _sample_micro_defect_spec(size_range, img_size)
    _draw_micro_defect_from_spec(canvas, spec, gray_range, bg_val, img_size)


def _draw_micro_defects(canvas: np.ndarray, n_shapes: int,
                        size_range: Tuple[int, int], gray_range: Tuple[int, int],
                        bg_val: int, img_size: int,
                        no_overlap: bool = False,
                        max_attempts_per_shape: int = 80) -> None:
    """批次繪製細微瑕疵；可切換不重疊模式。"""
    placed: List[Tuple[int, int, int]] = []
    scale = _canvas_scale(img_size)
    gap = max(1, int(1.5 * scale))
    max_tries = max(1, int(max_attempts_per_shape)) * max(1, n_shapes) if no_overlap else max(1, n_shapes)
    tries = 0
    drawn = 0

    while drawn < n_shapes and tries < max_tries:
        tries += 1
        spec = _sample_micro_defect_spec(size_range, img_size)
        cx = int(spec["cx"])
        cy = int(spec["cy"])
        safe_r = int(spec["safe_r"])

        if no_overlap:
            ok = True
            for px, py, pr in placed:
                min_dist = safe_r + pr + gap
                if (cx - px) * (cx - px) + (cy - py) * (cy - py) < min_dist * min_dist:
                    ok = False
                    break
            if not ok:
                continue

        _draw_micro_defect_from_spec(canvas, spec, gray_range, bg_val, img_size)
        drawn += 1
        if no_overlap:
            placed.append((cx, cy, safe_r))


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
    "micro_defect":   draw_micro_defect,
    "annulus_edge_defect": draw_annulus_edge_defect,
    "rectangle":      draw_rectangle,
    "ellipse":        draw_ellipse,
    "polygon":        draw_polygon,
}


# ─────────────────────────────────────────────
#  影像生成
# ─────────────────────────────────────────────

def generate_image(cfg: StageConfig, rng_seed: int) -> np.ndarray:
    """生成一張乾淨 512x512 灰階影像。"""
    canvas, _, _ = _render_stage_canvas(cfg, rng_seed)
    return _finalize_canvas_image(canvas, cfg)


def generate_sequence_images(cfg: StageConfig, rng_seed: int) -> List[np.ndarray]:
    seq_len = max(2, int(getattr(cfg, "sequence_length", 1)))
    step_px = float(getattr(cfg, "sequence_step_px", 0.0))
    axis = str(getattr(cfg, "sequence_axis", "y")).lower()
    if step_px <= 0.0:
        raise ValueError(f"sequence_step_px must be > 0 for sequence stage: {cfg.name}")

    base_canvas, bg_val, ss = _render_stage_canvas(cfg, rng_seed)
    center = 0.5 * (seq_len - 1)
    frames: List[np.ndarray] = []
    for frame_idx in range(seq_len):
        offset_px = (float(frame_idx) - center) * step_px * float(ss)
        dx = offset_px if axis == "x" else 0.0
        dy = offset_px if axis != "x" else 0.0
        shifted = _shift_highres_canvas(base_canvas, dx, dy, bg_val=bg_val)
        frames.append(_finalize_canvas_image(shifted, cfg))
    return frames


# ─────────────────────────────────────────────
#  批次生成與儲存
# ─────────────────────────────────────────────

def run_stage(cfg: StageConfig, base_seed: int = 0) -> None:
    out_dir = os.path.join(OUTPUT_ROOT, cfg.name)
    os.makedirs(out_dir, exist_ok=True)
    output_ext = _normalize_output_ext(getattr(cfg, "output_ext", FILE_FORMAT))

    total = cfg.end_idx - cfg.start_idx + 1
    seq_len = max(1, int(getattr(cfg, "sequence_length", 1)))
    if seq_len > 1:
        if total % seq_len != 0:
            raise ValueError(f"{cfg.name}: total frames {total} is not divisible by sequence_length={seq_len}")
        total_seqs = total // seq_len
        idx = int(cfg.start_idx)
        for seq_i in range(total_seqs):
            seed = base_seed + idx
            frames = generate_sequence_images(cfg, seed)
            for frame_i, img in enumerate(frames):
                filename = f"{idx:04d}_seq{seq_i:03d}_f{frame_i:02d}{output_ext}"
                filepath = os.path.join(out_dir, filename)
                cv2.imwrite(filepath, img)
                idx += 1
            if (seq_i + 1) % 5 == 0 or (seq_i + 1) == total_seqs:
                print(f"  [{cfg.name}] seq {seq_i + 1}/{total_seqs} -> {filename}")
        return

    for i, idx in enumerate(range(cfg.start_idx, cfg.end_idx + 1)):
        seed = base_seed + idx
        img = generate_image(cfg, seed)
        filename = f"{idx:04d}{output_ext}"
        filepath = os.path.join(out_dir, filename)
        cv2.imwrite(filepath, img)

        if (i + 1) % 10 == 0 or (i + 1) == total:
            print(f"  [{cfg.name}] {i+1}/{total} -> {filename}")


def run_pipeline(stages: List[StageConfig], base_seed: int = 42) -> None:
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    print(f"Output root: {OUTPUT_ROOT}\n")
    for cfg in stages:
        print(f"[Stage {cfg.stage_id:02d}] {cfg.name} ({cfg.start_idx:04d}~{cfg.end_idx:04d})")
        run_stage(cfg, base_seed)
    print("\nDone.")


def select_stages(stages: List[StageConfig], stage_ids: List[int]) -> List[StageConfig]:
    """依 stage_id 篩選要執行的 stages；空清單表示全部。"""
    if not stage_ids:
        return stages

    all_ids = {cfg.stage_id for cfg in stages}
    req_ids = set(int(x) for x in stage_ids)
    missing = sorted(req_ids - all_ids)
    if missing:
        raise ValueError(f"Unknown stage_id in RUN_STAGE_IDS: {missing}; valid ids={sorted(all_ids)}")

    selected = [cfg for cfg in stages if cfg.stage_id in req_ids]
    if not selected:
        raise ValueError("RUN_STAGE_IDS is set but no stages were selected.")
    return selected


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
        num_shapes_range=(14, 26), size_range=(12, 156),
        shape_gray_range=(30, 255),
        render_scale=10,
        background_mode="mild",
        bg_gray_range=(75, 150),
    ),
    # ── 純圓環（不重疊）────────────────────────────────────────
    StageConfig(
        stage_id=9, name="stage_09_annulus_non_overlap",
        shape_types=["annulus"],
        start_idx=801, end_idx=900,
        num_shapes_range=(8, 15), size_range=(18, 132),
        shape_gray_range=(30, 255),
        annulus_no_overlap=True,
        render_scale=12,
        background_mode="mild",
        bg_gray_range=(80, 155),
        max_place_attempts_per_shape=120,
    ),
    # ── 純圓環（可重疊）────────────────────────────────────────
    StageConfig(
        stage_id=10, name="stage_10_annulus_overlap",
        shape_types=["annulus"],
        start_idx=901, end_idx=1000,
        num_shapes_range=(12, 22), size_range=(16, 150),
        shape_gray_range=(30, 255),
        annulus_no_overlap=False,
        render_scale=10,
        background_mode="mild",
        bg_gray_range=(80, 155),
    ),
    # ── 純背景裂紋/缺口瑕疵（不重疊）───────────────────────────
    StageConfig(
        stage_id=11, name="stage_11_surface_defect_non_overlap",
        shape_types=["micro_defect"],
        start_idx=1001, end_idx=1100,
        num_shapes_range=(12, 24), size_range=(3, 20),
        shape_gray_range=(0, 255),
        micro_no_overlap=True,
        render_scale=1,
        background_mode="mild",
        bg_gray_range=(95, 150),
        max_place_attempts_per_shape=40,
    ),
    # ── 純背景裂紋/缺口瑕疵（可重疊）───────────────────────────
    StageConfig(
        stage_id=12, name="stage_12_surface_defect_overlap",
        shape_types=["micro_defect"],
        start_idx=1101, end_idx=1200,
        num_shapes_range=(18, 36), size_range=(3, 22),
        shape_gray_range=(0, 255),
        micro_no_overlap=False,
        render_scale=1,
        background_mode="mild",
        bg_gray_range=(95, 150),
        max_place_attempts_per_shape=30,
    ),
    # ── 曲邊主導、較乾淨背景：幫助模型學到更清楚的曲邊位置與厚度 ──
    StageConfig(
        stage_id=13, name="stage_13_curve_clean_general",
        shape_types=["circle", "ellipse", "annulus", "annulus"],
        start_idx=1201, end_idx=1300,
        num_shapes_range=(9, 16), size_range=(18, 150),
        shape_gray_range=(40, 255),
        render_scale=12,
        background_mode="mild",
        bg_gray_range=(85, 160),
        max_place_attempts_per_shape=100,
    ),
    # ── 圓環邊緣缺口/崩邊：強化邊界位置與局部紋理辨識 ────────────
    StageConfig(
        stage_id=14, name="stage_14_annulus_edge_defect_focus",
        shape_types=["annulus_edge_defect"],
        start_idx=1301, end_idx=1400,
        num_shapes_range=(6, 12), size_range=(28, 170),
        shape_gray_range=(55, 255),
        edge_annulus_no_overlap=False,
        edge_notch_allow_overlap=False,
        render_scale=10,
        background_mode="mild",
        bg_gray_range=(88, 155),
        max_place_attempts_per_shape=80,
    ),
    # ── 稀疏大型曲邊：貼近單圓環/少量曲邊樣本，避免被高密度場景稀釋 ───
    StageConfig(
        stage_id=15, name="stage_15_annulus_sparse_clean",
        shape_types=["annulus", "annulus", "circle", "ellipse"],
        start_idx=1401, end_idx=1500,
        num_shapes_range=(2, 6), size_range=(36, 190),
        shape_gray_range=(55, 255),
        render_scale=14,
        background_mode="mild",
        bg_gray_range=(92, 160),
        max_place_attempts_per_shape=120,
    ),
    # ── 稀疏大型缺口曲邊：更直接對齊邊界位置、厚度與局部崩邊真實感 ───
    StageConfig(
        stage_id=16, name="stage_16_annulus_sparse_defect_clean",
        shape_types=["annulus_edge_defect"],
        start_idx=1501, end_idx=1600,
        num_shapes_range=(2, 5), size_range=(44, 196),
        shape_gray_range=(70, 255),
        edge_annulus_no_overlap=True,
        edge_notch_allow_overlap=False,
        render_scale=12,
        background_mode="mild",
        bg_gray_range=(96, 160),
        max_place_attempts_per_shape=120,
    ),
    # ── 高 supersample 微位移曲邊：專門給 0.08px 級別訓練使用 ─────
    StageConfig(
        stage_id=17, name="stage_17_annulus_microstep_clean",
        shape_types=["annulus", "annulus", "circle", "ellipse"],
        start_idx=1601, end_idx=1650,
        num_shapes_range=(1, 4), size_range=(48, 210),
        shape_gray_range=(60, 255),
        render_scale=16,
        background_mode="mild",
        bg_gray_range=(96, 160),
        max_place_attempts_per_shape=160,
        output_ext=".tif",
        save_bit_depth=16,
    ),
    # ── 高 supersample 微位移缺口曲邊：保留真實感，避免微位移只學乾淨邊 ──
    StageConfig(
        stage_id=18, name="stage_18_annulus_microstep_defect",
        shape_types=["annulus_edge_defect"],
        start_idx=1651, end_idx=1700,
        num_shapes_range=(1, 3), size_range=(54, 216),
        shape_gray_range=(72, 255),
        edge_annulus_no_overlap=True,
        edge_notch_allow_overlap=False,
        render_scale=16,
        background_mode="mild",
        bg_gray_range=(100, 162),
        max_place_attempts_per_shape=180,
        output_ext=".tif",
        save_bit_depth=16,
    ),
    # ── 同場景微位移序列：讓訓練可直接看到相鄰 frame 的細微位移差 ─────
    StageConfig(
        stage_id=19, name="stage_19_annulus_microstep_sequence_clean",
        shape_types=["annulus", "annulus", "circle", "ellipse"],
        start_idx=1701, end_idx=1775,
        num_shapes_range=(1, 4), size_range=(48, 210),
        shape_gray_range=(60, 255),
        render_scale=16,
        background_mode="mild",
        bg_gray_range=(96, 160),
        max_place_attempts_per_shape=160,
        output_ext=".tif",
        save_bit_depth=16,
        sequence_length=5,
        sequence_step_px=0.08,
        sequence_axis="y",
    ),
    StageConfig(
        stage_id=20, name="stage_20_annulus_microstep_sequence_defect",
        shape_types=["annulus_edge_defect"],
        start_idx=1776, end_idx=1850,
        num_shapes_range=(1, 3), size_range=(54, 216),
        shape_gray_range=(72, 255),
        edge_annulus_no_overlap=True,
        edge_notch_allow_overlap=False,
        render_scale=16,
        background_mode="mild",
        bg_gray_range=(100, 162),
        max_place_attempts_per_shape=180,
        output_ext=".tif",
        save_bit_depth=16,
        sequence_length=5,
        sequence_step_px=0.08,
        sequence_axis="y",
    ),
    StageConfig(
        stage_id=21, name="stage_21_annulus_gmf_sequence_clean",
        shape_types=["annulus"],
        start_idx=1851, end_idx=1925,
        num_shapes_range=(1, 1), size_range=(120, 220),
        shape_gray_range=(72, 255),
        annulus_no_overlap=True,
        render_scale=16,
        background_mode="mild",
        bg_gray_range=(100, 160),
        max_place_attempts_per_shape=180,
        output_ext=".tif",
        save_bit_depth=16,
        sequence_length=5,
        sequence_step_px=0.08,
        sequence_axis="y",
    ),
    StageConfig(
        stage_id=22, name="stage_22_annulus_gmf_sequence_defect",
        shape_types=["annulus_edge_defect"],
        start_idx=1926, end_idx=2000,
        num_shapes_range=(1, 1), size_range=(124, 224),
        shape_gray_range=(76, 255),
        edge_annulus_no_overlap=True,
        edge_notch_allow_overlap=False,
        render_scale=16,
        background_mode="mild",
        bg_gray_range=(102, 162),
        max_place_attempts_per_shape=200,
        output_ext=".tif",
        save_bit_depth=16,
        sequence_length=5,
        sequence_step_px=0.08,
        sequence_axis="y",
    ),
    StageConfig(
        stage_id=23, name="stage_23_annulus_gmf_sequence_mid_clean",
        shape_types=["annulus"],
        start_idx=2001, end_idx=2075,
        num_shapes_range=(1, 1), size_range=(120, 220),
        shape_gray_range=(72, 255),
        annulus_no_overlap=True,
        render_scale=16,
        background_mode="mild",
        bg_gray_range=(100, 160),
        max_place_attempts_per_shape=180,
        output_ext=".tif",
        save_bit_depth=16,
        sequence_length=5,
        sequence_step_px=0.8,
        sequence_axis="y",
    ),
    StageConfig(
        stage_id=24, name="stage_24_annulus_gmf_sequence_mid_defect",
        shape_types=["annulus_edge_defect"],
        start_idx=2076, end_idx=2150,
        num_shapes_range=(1, 1), size_range=(124, 224),
        shape_gray_range=(76, 255),
        edge_annulus_no_overlap=True,
        edge_notch_allow_overlap=False,
        render_scale=16,
        background_mode="mild",
        bg_gray_range=(102, 162),
        max_place_attempts_per_shape=200,
        output_ext=".tif",
        save_bit_depth=16,
        sequence_length=5,
        sequence_step_px=0.8,
        sequence_axis="y",
    ),
    StageConfig(
        stage_id=25, name="stage_25_annulus_gmf_sequence_macro_clean",
        shape_types=["annulus"],
        start_idx=2151, end_idx=2225,
        num_shapes_range=(1, 1), size_range=(120, 220),
        shape_gray_range=(72, 255),
        annulus_no_overlap=True,
        render_scale=12,
        background_mode="mild",
        bg_gray_range=(100, 160),
        max_place_attempts_per_shape=180,
        output_ext=".tif",
        save_bit_depth=16,
        sequence_length=5,
        sequence_step_px=8.0,
        sequence_axis="y",
    ),
    StageConfig(
        stage_id=26, name="stage_26_annulus_gmf_sequence_macro_defect",
        shape_types=["annulus_edge_defect"],
        start_idx=2226, end_idx=2300,
        num_shapes_range=(1, 1), size_range=(124, 224),
        shape_gray_range=(76, 255),
        edge_annulus_no_overlap=True,
        edge_notch_allow_overlap=False,
        render_scale=12,
        background_mode="mild",
        bg_gray_range=(102, 162),
        max_place_attempts_per_shape=200,
        output_ext=".tif",
        save_bit_depth=16,
        sequence_length=5,
        sequence_step_px=8.0,
        sequence_axis="y",
    ),
    StageConfig(
        stage_id=27, name="stage_27_annulus_gmf_sequence_midwide_clean",
        shape_types=["annulus"],
        start_idx=2301, end_idx=2384,
        num_shapes_range=(1, 1), size_range=(116, 228),
        shape_gray_range=(74, 255),
        annulus_no_overlap=True,
        render_scale=18,
        background_mode="mild",
        bg_gray_range=(100, 160),
        max_place_attempts_per_shape=220,
        output_ext=".tif",
        save_bit_depth=16,
        sequence_length=7,
        sequence_step_px=0.8,
        sequence_axis="y",
    ),
    StageConfig(
        stage_id=28, name="stage_28_annulus_gmf_sequence_midwide_defect",
        shape_types=["annulus_edge_defect"],
        start_idx=2385, end_idx=2468,
        num_shapes_range=(1, 1), size_range=(120, 232),
        shape_gray_range=(78, 255),
        edge_annulus_no_overlap=True,
        edge_notch_allow_overlap=False,
        render_scale=18,
        background_mode="mild",
        bg_gray_range=(102, 162),
        max_place_attempts_per_shape=240,
        output_ext=".tif",
        save_bit_depth=16,
        sequence_length=7,
        sequence_step_px=0.8,
        sequence_axis="y",
    ),
]


# ─────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    stages_to_run = select_stages(STAGES, RUN_STAGE_IDS)
    print(f"Run config: RUN_STAGE_IDS={RUN_STAGE_IDS if RUN_STAGE_IDS else 'ALL'}, RUN_BASE_SEED={RUN_BASE_SEED}")
    run_pipeline(stages_to_run, base_seed=RUN_BASE_SEED)
