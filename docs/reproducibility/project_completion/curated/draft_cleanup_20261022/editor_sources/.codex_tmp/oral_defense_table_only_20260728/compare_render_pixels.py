from pathlib import Path
import re
import numpy as np
from PIL import Image

root = Path(r"D:\GMM_2_Final\PSF_Fitting\.codex_tmp\oral_defense_table_only_20260728")
def ordered(folder):
    return sorted(folder.glob("*.PNG"), key=lambda p: int(re.search(r"\d+", p.stem).group()))

source = ordered(root / "render-source")
final = ordered(root / "render-final")
rows = []
for slide, (a_path, b_path) in enumerate(zip(source, final), 1):
    a = np.asarray(Image.open(a_path).convert("RGB"), dtype=np.int16)
    b = np.asarray(Image.open(b_path).convert("RGB"), dtype=np.int16)
    delta = np.abs(a - b)
    changed_pixels = int(np.any(delta != 0, axis=2).sum())
    rows.append((slide, changed_pixels, float(delta.mean()), int(delta.max())))

material = [row for row in rows if row[1] > 100 or row[2] > 0.001]
print("slide changed_pixels mean_abs_delta max_delta")
for row in material:
    print(f"{row[0]:02d} {row[1]} {row[2]:.6f} {row[3]}")
print(f"materially_different_slides={','.join(str(row[0]) for row in material)}")
