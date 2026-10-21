from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat
from skimage.measure import find_contours, perimeter_crofton


ROOT = Path(__file__).resolve().parents[1]
MASK_PATH = ROOT / "results" / "masks" / "acm_qa_masks.mat"
FIGURE_DIR = ROOT / "results" / "figures"
FIGURE_PATH = FIGURE_DIR / "00_truth_acm_qa.png"


def circularity(mask: np.ndarray) -> float:
    perimeter = perimeter_crofton(mask, directions=4)
    return float(4 * np.pi * mask.sum() / perimeter**2)


def main() -> None:
    data = loadmat(MASK_PATH, squeeze_me=True)
    cells = data["truth_cells"]
    masks = data["truth_masks"].astype(bool)
    grid = data["global_index"].astype(int)
    height, width, _ = masks.shape
    yy, xx = np.indices((height, width))
    radius = np.hypot(xx - (width - 1) / 2, yy - (height - 1) / 2)
    support_radius = float(data["support_radius"])

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(6, 6, figsize=(13, 13), constrained_layout=True)
    for row in range(6):
        for col in range(6):
            pillar_id = int(grid[row, col])
            image = cells[:, :, pillar_id - 1]
            mask = masks[:, :, pillar_id - 1]
            ax = axes[row, col]
            ax.imshow(image, cmap="gray", vmin=0, vmax=255)
            for contour in find_contours(mask, 0.5):
                ax.plot(contour[:, 1], contour[:, 0], color="#111827", linewidth=1.6)
            theta = np.linspace(0, 2 * np.pi, 361)
            ax.plot(
                (width - 1) / 2 + support_radius * np.cos(theta),
                (height - 1) / 2 + support_radius * np.sin(theta),
                color="#DC2626",
                linewidth=0.65,
                linestyle=":",
            )
            touches = int(np.count_nonzero(mask & (radius >= support_radius - 0.5)))
            ax.set_title(
                f"ID {pillar_id}  C={circularity(mask):.3f}\ntouch={touches}",
                fontsize=8,
                color="#B91C1C" if touches else "#111827",
            )
            ax.set_xlim(5, width - 6)
            ax.set_ylim(height - 6, 5)
            ax.axis("off")

    fig.suptitle(
        "SEM ACM truth-contour audit — black: extracted boundary; red: ROI guard",
        fontsize=15,
        fontweight="bold",
    )
    fig.savefig(FIGURE_PATH, dpi=180, facecolor="white")
    plt.close(fig)
    print(FIGURE_PATH)


if __name__ == "__main__":
    main()
