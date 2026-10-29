"""
PSF_Convolution.py
------------------
將 generated/ 下各子資料夾的乾淨影像與 PSF 做卷積，
並在卷積後加入 Poisson-Gaussian 混合雜訊。

對應規則（一對一）：
  子資料夾中第 i 張影像（0-indexed）← PSF[i]
    PSF[i] = psf_grid[:, :, row, col]   (PSF 網格展開)

  同一個 PSF 在「所有」子資料夾各被使用一次，
  完成後每個 PSF 的使用次數 = 子資料夾數量。

輸入：
  Training_Data/generated/<stage_XX>/  (*.bmp/*.tif, 512×512 灰階)
  PSF_Fitting/.../PSF_fitted_2D_FOVstack.mat
    └─ psf_grid: (101, 101, rows, cols)  float64

輸出：
  Training_Data/generated_convolved/<stage_XX>/  (保留輸入副檔名；微位移 stage 為 uint16 .tif)
"""

import os
import glob
import re
import numpy as np
import cv2
import scipy.io as sio
from scipy.signal import fftconvolve
from typing import List, Optional

# ─────────────────────────────────────────────
#  路徑設定
# ─────────────────────────────────────────────
def _parse_stage_ids_env(value: str) -> List[int]:
    if value is None or str(value).strip() == "":
        return []
    out = []
    for part in str(value).replace(";", ",").split(","):
        part = part.strip()
        if part:
            out.append(int(part))
    return out


def _parse_optional_int_env(value: str) -> Optional[int]:
    if value is None or str(value).strip() == "":
        return None
    return int(str(value).strip())


def _parse_optional_float_env(value: str) -> Optional[float]:
    if value is None or str(value).strip() == "":
        return None
    return float(str(value).strip())


BASE_DIR      = os.path.dirname(__file__)
LABSYSTEM_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
INPUT_ROOT    = os.environ.get("LAB_CONV_INPUT_ROOT", os.path.join(BASE_DIR, "generated"))
OUTPUT_ROOT   = os.environ.get("LAB_CONV_OUTPUT_ROOT", os.path.join(BASE_DIR, "generated_convolved"))
PSF_MAT_PATH  = os.environ.get(
    "LAB_PSF_MAT_PATH",
    os.path.join(
        LABSYSTEM_ROOT,
        "psf_calibration",
        "results",
        "20250605_inner_circle_roi_fine_prealign_fit",
        "PSF_fitted_2D_FOVstack.mat",
    ),
)
IMAGE_EXTENSIONS = (".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff")
PHOTON_SCALE_RANGE = (45.0, 180.0)   # alpha：提高最低光子數，降低顆粒噪聲主導
READ_NOISE_SIGMA_RANGE = (0.7, 2.2)  # sigma：收斂讀噪幅度，保留真實感但減少斑點污染

# 執行控制（在程式內直接設定，不需要命令列）
# [] 代表執行 INPUT_ROOT 下全部 stage 子資料夾；例如 [9, 10] 代表只處理 stage_09 / stage_10
RUN_STAGE_IDS: List[int] = _parse_stage_ids_env(os.environ.get("LAB_RUN_STAGE_IDS"))
RUN_NOISE_SEED: Optional[int] = _parse_optional_int_env(os.environ.get("LAB_NOISE_SEED"))
GAUSSIAN_SIGMA_PX: Optional[float] = _parse_optional_float_env(os.environ.get("LAB_GAUSSIAN_SIGMA_PX"))
GAUSSIAN_PSF_COUNT: int = int(os.environ.get("LAB_GAUSSIAN_COUNT", "25"))
GAUSSIAN_KERNEL_SIZE: int = int(os.environ.get("LAB_GAUSSIAN_KERNEL_SIZE", "101"))

# ─────────────────────────────────────────────
#  載入並整理 PSF
# ─────────────────────────────────────────────

def load_psfs(mat_path: str) -> list:
    """
    從 .mat 載入 psf_grid (101,101,10,10)，
    展開為 100 個已正規化（sum=1）的 2D PSF。
    回傳 list[np.ndarray]，長度 100，每個 shape=(101,101)。
    """
    if not os.path.isfile(mat_path):
        raise FileNotFoundError(f"找不到 PSF 檔案：{mat_path}")

    mat = sio.loadmat(mat_path)
    if "psf_grid" not in mat:
        raise KeyError(f"{mat_path} 中缺少 'psf_grid' 變數")

    psf_grid = mat["psf_grid"]          # 預期 (101, 101, 10, 10)
    if psf_grid.ndim != 4:
        raise ValueError(f"psf_grid 維度錯誤：{psf_grid.shape}，預期 4 維")

    H, W, rows, cols = psf_grid.shape
    if rows <= 0 or cols <= 0:
        raise ValueError(f"psf_grid 網格尺寸無效：{psf_grid.shape}")

    psfs = []
    for r in range(rows):
        for c in range(cols):
            kernel = np.asarray(psf_grid[:, :, r, c], dtype=np.float64).copy()
            if not np.all(np.isfinite(kernel)):
                raise ValueError(f"PSF[{r},{c}] 含 NaN/Inf")

            total = kernel.sum()
            if total <= 0:
                raise ValueError(f"PSF[{r},{c}] 總和 <= 0，無法正規化")

            kernel /= total             # 正規化 sum=1，保持影像強度
            psfs.append(kernel)         # psfs[r*cols + c] = PSF 索引 r*10+c

    if len(psfs) == 0:
        raise ValueError("未載入任何 PSF")

    print(f"已載入 {len(psfs)} 個 PSF，每個尺寸 {H}x{W} px")
    return psfs


def make_gaussian_kernel(size: int, sigma_px: float) -> np.ndarray:
    size = int(size)
    if size % 2 == 0:
        raise ValueError(f"Gaussian kernel size must be odd, got {size}")
    if float(sigma_px) <= 0:
        raise ValueError(f"Gaussian sigma must be > 0, got {sigma_px}")
    half = size // 2
    yy, xx = np.mgrid[-half:half + 1, -half:half + 1]
    kernel = np.exp(-(xx * xx + yy * yy) / (2.0 * float(sigma_px) ** 2))
    kernel = kernel.astype(np.float64)
    kernel /= kernel.sum()
    return kernel


def make_gaussian_psfs(sigma_px: float, count: int, size: int = 101) -> list:
    if int(count) <= 0:
        raise ValueError(f"Gaussian PSF count must be > 0, got {count}")
    kernel = make_gaussian_kernel(size=size, sigma_px=sigma_px)
    psfs = [kernel.copy() for _ in range(int(count))]
    print(f"已建立 Gaussian control PSF：sigma={float(sigma_px):.4f} px，count={len(psfs)}，尺寸 {size}x{size} px")
    return psfs


# ─────────────────────────────────────────────
#  卷積單張影像
# ─────────────────────────────────────────────

def _imread_gray_preserve(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"無法讀取影像：{path}")
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if img.dtype not in (np.uint8, np.uint16):
        raise RuntimeError(f"不支援的影像 dtype: {img.dtype} @ {path}")
    return img


def _to_unit_float(img: np.ndarray) -> np.ndarray:
    if img.dtype == np.uint16:
        return img.astype(np.float64) / 65535.0
    return img.astype(np.float64) / 255.0


def _quantize_unit_image(img01: np.ndarray, out_dtype: np.dtype) -> np.ndarray:
    img01 = np.clip(img01, 0.0, 1.0)
    if out_dtype == np.uint16:
        return np.clip(np.rint(img01 * 65535.0), 0, 65535).astype(np.uint16)
    return np.clip(np.rint(img01 * 255.0), 0, 255).astype(np.uint8)


def _collect_image_paths(folder: str) -> List[str]:
    paths: List[str] = []
    for ext in IMAGE_EXTENSIONS:
        paths.extend(glob.glob(os.path.join(folder, f"*{ext}")))
    return sorted(paths)


def convolve_image(img01: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """
    將灰階影像與 PSF kernel 做 FFT 卷積（mode='same'）。
    輸入 img01: float64, 值域 [0, 1]，kernel: float64 (sum=1)。
    輸出: float64, 值域 [0, 1]，形狀與輸入相同。
    """
    kh, kw = kernel.shape
    pad_h, pad_w = kh // 2, kw // 2

    # 以反射邊界 padding，避免零填充造成邊緣亮度不自然下降
    padded = np.pad(img01, ((pad_h, pad_h), (pad_w, pad_w)), mode="reflect")
    conv_padded = fftconvolve(padded, kernel, mode="same")
    conv = conv_padded[pad_h:pad_h + img01.shape[0], pad_w:pad_w + img01.shape[1]]
    return np.clip(conv, 0.0, 1.0)


def add_random_noise(img01: np.ndarray, rng: np.random.Generator,
                     photon_scale_range: tuple = PHOTON_SCALE_RANGE,
                     read_sigma_range: tuple = READ_NOISE_SIGMA_RANGE) -> np.ndarray:
    """
    Poisson-Gaussian 混合雜訊模型：
      I_noisy = P(I_clean * alpha) / alpha + N(0, sigma^2)
    """
    img_255 = np.clip(img01, 0.0, 1.0) * 255.0

    photon_scale = float(rng.uniform(photon_scale_range[0], photon_scale_range[1]))
    sigma = float(rng.uniform(read_sigma_range[0], read_sigma_range[1]))

    poisson_term = rng.poisson(lam=np.clip(img_255 * photon_scale, 0.0, None)) / photon_scale
    gaussian_term = rng.normal(loc=0.0, scale=sigma, size=img01.shape)
    noisy = poisson_term + gaussian_term

    noisy = np.clip(noisy, 0.0, 255.0)
    return noisy / 255.0


# ─────────────────────────────────────────────
#  主流程
# ─────────────────────────────────────────────

def _extract_stage_id(folder_name: str) -> Optional[int]:
    """
    從資料夾名抓 stage_id（例如 stage_09_xxx -> 9）。
    不符合命名規則則回傳 None。
    """
    m = re.match(r"^stage_(\d+)(?:_|$)", folder_name)
    if m is None:
        return None
    return int(m.group(1))


def select_subdirs(subdirs: List[str], stage_ids: List[int]) -> List[str]:
    """依 stage_id 篩選子資料夾；空清單表示不篩選（全跑）。"""
    if not stage_ids:
        return subdirs

    req_ids = set(int(x) for x in stage_ids)
    available_ids = set()
    selected = []
    found_ids = set()
    for d in subdirs:
        sid = _extract_stage_id(d)
        if sid is None:
            continue
        available_ids.add(sid)
        if sid in req_ids:
            selected.append(d)
            found_ids.add(sid)

    missing = sorted(req_ids - found_ids)
    if missing:
        raise ValueError(
            f"RUN_STAGE_IDS 包含不存在於輸入資料夾的 stage_id: {missing}；"
            f"可用 stage_id={sorted(available_ids)}"
        )
    return selected


def run(input_root: str, output_root: str, psfs: list, noise_seed: int = None,
        stage_ids: Optional[List[int]] = None) -> None:
    n_psf = len(psfs)   # 100
    if n_psf == 0:
        raise ValueError("PSF 清單為空，無法執行卷積")

    if not os.path.isdir(input_root):
        raise FileNotFoundError(f"輸入資料夾不存在：{input_root}")

    rng = np.random.default_rng(noise_seed)

    # 取得所有子資料夾（排序確保一致性）
    subdirs = sorted([
        d for d in os.listdir(input_root)
        if os.path.isdir(os.path.join(input_root, d))
    ])

    if not subdirs:
        print(f"[警告] 找不到子資料夾：{input_root}")
        return

    subdirs = select_subdirs(subdirs, [] if stage_ids is None else stage_ids)
    if not subdirs:
        print(f"[警告] 套用 RUN_STAGE_IDS 後沒有可處理的子資料夾")
        return

    print(f"\n子資料夾數量：{len(subdirs)}")
    print(f"PSF 數量：{n_psf}")
    print(f"每個 PSF 預計使用次數：{len(subdirs)}\n")
    print(f"Poisson alpha 範圍：{PHOTON_SCALE_RANGE}")
    print(f"Gaussian sigma 範圍：{READ_NOISE_SIGMA_RANGE}\n")
    os.makedirs(output_root, exist_ok=True)

    for folder_name in subdirs:
        in_dir  = os.path.join(input_root,  folder_name)
        out_dir = os.path.join(output_root, folder_name)
        os.makedirs(out_dir, exist_ok=True)

        # 取得該資料夾內所有影像，依檔名排序
        img_paths = _collect_image_paths(in_dir)
        n_imgs = len(img_paths)

        if n_imgs == 0:
            print(f"  [跳過] {folder_name}：無影像")
            continue

        if n_imgs > n_psf:
            print(f"  [警告] {folder_name}：影像數 {n_imgs} > PSF 數 {n_psf}，超出部分循環使用 PSF")

        print(f"[stage] {folder_name}  ({n_imgs} 張)")

        for i, img_path in enumerate(img_paths):
            psf_idx = i % n_psf
            kernel  = psfs[psf_idx]

            try:
                img = _imread_gray_preserve(img_path)
            except RuntimeError as exc:
                print(f"    [跳過] {exc}")
                continue

            out_dtype = img.dtype
            img01 = _to_unit_float(img)
            conv01 = convolve_image(img01, kernel)
            noisy01 = add_random_noise(conv01, rng)
            conv_img = _quantize_unit_image(noisy01, out_dtype)

            fname    = os.path.basename(img_path)
            out_path = os.path.join(out_dir, fname)
            ok = cv2.imwrite(out_path, conv_img)
            if not ok:
                print(f"    [警告] 寫檔失敗：{out_path}")

        print(f"   完成，PSF 索引 0~{min(n_imgs, n_psf) - 1} 各使用一次")

    print("\n全部完成。")
    print(f"輸出目錄：{output_root}")


# ─────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if GAUSSIAN_SIGMA_PX is None:
        psfs = load_psfs(PSF_MAT_PATH)
        psf_mode = f"BADS:{PSF_MAT_PATH}"
    else:
        psfs = make_gaussian_psfs(
            sigma_px=GAUSSIAN_SIGMA_PX,
            count=GAUSSIAN_PSF_COUNT,
            size=GAUSSIAN_KERNEL_SIZE,
        )
        psf_mode = f"Gaussian:sigma={GAUSSIAN_SIGMA_PX}"
    print(f"Run config: mode={psf_mode}, INPUT_ROOT={INPUT_ROOT}, OUTPUT_ROOT={OUTPUT_ROOT}")
    print(f"Run config: RUN_STAGE_IDS={RUN_STAGE_IDS if RUN_STAGE_IDS else 'ALL'}, RUN_NOISE_SEED={RUN_NOISE_SEED}")
    run(INPUT_ROOT, OUTPUT_ROOT, psfs, noise_seed=RUN_NOISE_SEED, stage_ids=RUN_STAGE_IDS)
