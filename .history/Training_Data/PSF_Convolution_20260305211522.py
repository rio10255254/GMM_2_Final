"""
PSF_Convolution.py
------------------
將 generated/ 下各子資料夾的乾淨影像與 PSF 做卷積，
並在卷積後加入 Poisson-Gaussian 混合雜訊。

對應規則（一對一）：
  子資料夾中第 i 張影像（0-indexed）← PSF[i]
    PSF[i] = psf_grid[:, :, i//10, i%10]   (10×10 網格展開)

  同一個 PSF 在「所有」子資料夾各被使用一次，
  完成後每個 PSF 的使用次數 = 子資料夾數量。

輸入：
  Training_Data/generated/<stage_XX>/  (*.bmp, 512×512 灰階)
  D:/GMM_2_Final/PSF_Fitting/.../PSF_fitted_2D_FOVstack.mat
    └─ psf_grid: (101, 101, 10, 10)  float64

輸出：
  Training_Data/generated_convolved/<stage_XX>/  (*.bmp, 512×512 灰階)
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
BASE_DIR      = os.path.dirname(__file__)
INPUT_ROOT    = os.path.join(BASE_DIR, "generated")
OUTPUT_ROOT   = os.path.join(BASE_DIR, "generated_convolved")
PSF_MAT_PATH  = r"D:\GMM_2_Final\PSF_Fitting\Crop_circle_FreqFiltered\Fits\PSF_fitted_2D_FOVstack.mat"
FILE_FORMAT   = ".bmp"
PHOTON_SCALE_RANGE = (30.0, 150.0)   # alpha：光子縮放尺度
READ_NOISE_SIGMA_RANGE = (2.0, 8.0)  # sigma：讀取高斯底噪

# 執行控制（在程式內直接設定，不需要命令列）
# [] 代表執行 INPUT_ROOT 下全部 stage 子資料夾；例如 [9, 10] 代表只處理 stage_09 / stage_10
RUN_STAGE_IDS: List[int] = []
RUN_NOISE_SEED: Optional[int] = None

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


# ─────────────────────────────────────────────
#  卷積單張影像
# ─────────────────────────────────────────────

def convolve_image(img: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """
    將灰階影像與 PSF kernel 做 FFT 卷積（mode='same'）。
    輸入 img: uint8, kernel: float64 (sum=1)。
    輸出: uint8，值域 [0, 255]，形狀與輸入相同。
    """
    img_f = img.astype(np.float64)
    kh, kw = kernel.shape
    pad_h, pad_w = kh // 2, kw // 2

    # 以反射邊界 padding，避免零填充造成邊緣亮度不自然下降
    padded = np.pad(img_f, ((pad_h, pad_h), (pad_w, pad_w)), mode="reflect")
    conv_padded = fftconvolve(padded, kernel, mode="same")
    conv = conv_padded[pad_h:pad_h + img.shape[0], pad_w:pad_w + img.shape[1]]
    conv = np.clip(np.rint(conv), 0, 255)
    return conv.astype(np.uint8)


def add_random_noise(img: np.ndarray, rng: np.random.Generator,
                     photon_scale_range: tuple = PHOTON_SCALE_RANGE,
                     read_sigma_range: tuple = READ_NOISE_SIGMA_RANGE) -> np.ndarray:
    """
    Poisson-Gaussian 混合雜訊模型：
      I_noisy = P(I_clean * alpha) / alpha + N(0, sigma^2)
    """
    img_f = img.astype(np.float64)

    photon_scale = float(rng.uniform(photon_scale_range[0], photon_scale_range[1]))
    sigma = float(rng.uniform(read_sigma_range[0], read_sigma_range[1]))

    poisson_term = rng.poisson(lam=np.clip(img_f * photon_scale, 0.0, None)) / photon_scale
    gaussian_term = rng.normal(loc=0.0, scale=sigma, size=img.shape)
    noisy = poisson_term + gaussian_term

    noisy = np.clip(np.rint(noisy), 0, 255)
    return noisy.astype(np.uint8)


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
        img_paths = sorted(glob.glob(os.path.join(in_dir, f"*{FILE_FORMAT}")))
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

            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                print(f"    [跳過] 無法讀取：{img_path}")
                continue

            conv_img = convolve_image(img, kernel)
            conv_img = add_random_noise(conv_img, rng)

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
    psfs = load_psfs(PSF_MAT_PATH)
    print(f"Run config: RUN_STAGE_IDS={RUN_STAGE_IDS if RUN_STAGE_IDS else 'ALL'}, RUN_NOISE_SEED={RUN_NOISE_SEED}")
    run(INPUT_ROOT, OUTPUT_ROOT, psfs, noise_seed=RUN_NOISE_SEED, stage_ids=RUN_STAGE_IDS)
