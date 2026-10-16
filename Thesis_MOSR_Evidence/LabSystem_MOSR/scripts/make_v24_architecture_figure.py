from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle
from PIL import Image, ImageFilter


ROOT = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence")
OUT_DIR = ROOT / "LabSystem_MOSR" / "Figures" / "network_architecture_20260707"
RAW_EXAMPLE = (
    ROOT
    / "External_GMF_Packages"
    / "best_displacement_models_20260706"
    / "trusted_full_sequences"
    / "100MG_x_1um_full_raw"
    / "bmp"
    / "frame_0000.bmp"
)


COLORS = {
    "green": "#75B84A",
    "blue": "#0D73B7",
    "cyan": "#20C5B5",
    "yellow": "#FFE066",
    "yellow_edge": "#D9B433",
    "pink": "#FF58D2",
    "gray": "#A9B0B8",
    "line": "#1F1F1F",
    "lightcyan": "#C7F1F2",
    "cream": "#FFF6D8",
    "raw": "#EEF1F5",
}


def add_box(ax, xy, wh, label, color, fontsize=10, edge="#FFFFFF", lw=1.2, text_color="white"):
    x, y = xy
    w, h = wh
    rect = Rectangle((x, y), w, h, facecolor=color, edgecolor=edge, linewidth=lw)
    ax.add_patch(rect)
    ax.text(
        x + w / 2,
        y + h / 2,
        label,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=text_color,
        family="DejaVu Sans",
        linespacing=1.05,
    )
    return rect


def arrow(ax, p0, p1, lw=1.7, color=None, mutation_scale=12, style="-|>"):
    if color is None:
        color = COLORS["line"]
    arr = FancyArrowPatch(
        p0,
        p1,
        arrowstyle=style,
        mutation_scale=mutation_scale,
        linewidth=lw,
        color=color,
        shrinkA=0,
        shrinkB=0,
        connectionstyle="arc3,rad=0.0",
    )
    ax.add_patch(arr)
    return arr


def add_input_thumbnail(fig, left, bottom, width, height):
    ax_img = fig.add_axes([left, bottom, width, height])
    ax_img.axis("off")
    if RAW_EXAMPLE.exists():
        img = Image.open(RAW_EXAMPLE).convert("L")
        w, h = img.size
        crop = img.crop((max(0, w // 2 - 320), max(0, h // 2 - 240), min(w, w // 2 + 320), min(h, h // 2 + 240)))
        crop = crop.resize((260, 190), Image.Resampling.LANCZOS)
    else:
        yy, xx = np.indices((190, 260))
        crop_arr = np.full((190, 260), 210, dtype=np.float32)
        for cx, cy in [(75, 65), (185, 65), (75, 140), (185, 140)]:
            crop_arr -= 135 * np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * 20**2)))
        crop = Image.fromarray(np.clip(crop_arr, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
    ax_img.imshow(crop, cmap="gray", vmin=0, vmax=255)
    ax_img.set_title("Input\nimage", fontsize=10, family="DejaVu Sans", pad=4)


def add_psf_thumbnail(fig, left, bottom, width, height):
    ax_psf = fig.add_axes([left, bottom, width, height])
    ax_psf.axis("off")
    h, w = 180, 230
    yy, xx = np.indices((h, w))
    img = np.zeros((h, w, 3), dtype=np.float32)
    img[:, :, 2] = 0.35
    for r in np.linspace(28, h - 28, 5):
        for c in np.linspace(30, w - 30, 5):
            spot = np.exp(-(((xx - c) ** 2 + (yy - r) ** 2) / (2 * 2.2**2)))
            img[:, :, 0] += 0.08 * spot
            img[:, :, 1] += 1.10 * spot
            img[:, :, 2] += 0.95 * spot
    ax_psf.imshow(np.clip(img, 0, 1))
    ax_psf.set_title("PSF stack\n/ weak PSFs", fontsize=10, family="DejaVu Sans", pad=4)


def build_figure():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(7.2, 16), dpi=220)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 720)
    ax.set_ylim(0, 1600)
    ax.axis("off")

    ax.text(
        360,
        1565,
        "GeoEdgeAlignSR-v1  V24 / v7-anchor-blend10 built-in",
        ha="center",
        va="center",
        fontsize=15,
        weight="bold",
        family="DejaVu Sans",
    )

    add_psf_thumbnail(fig, 0.12, 0.865, 0.25, 0.095)
    add_input_thumbnail(fig, 0.50, 0.865, 0.25, 0.095)

    # Left conditioning rails, matching the reference figure style.
    ax.plot([115, 115], [255, 1302], color=COLORS["line"], lw=1.2)
    ax.plot([245, 245], [255, 1302], color=COLORS["line"], lw=1.2)
    add_box(ax, (48, 1308), (92, 42), "Raw\nanchor", COLORS["green"], fontsize=10)
    add_box(ax, (192, 1308), (108, 42), "PSF\nprior", COLORS["green"], fontsize=10)
    ax.plot([94, 115], [1308, 1302], color=COLORS["line"], lw=1.2)
    ax.plot([246, 245], [1308, 1302], color=COLORS["line"], lw=1.2)

    # Main stem.
    stem_x = 440
    input_y = 1370
    add_box(ax, (382, input_y), (116, 35), "Input image", COLORS["gray"], fontsize=9)
    arrow(ax, (440, 1358), (440, 1325))

    add_box(ax, (347, 1284), (186, 45), "PSF physics layer\nconservative deconv", COLORS["green"], fontsize=9)
    arrow(ax, (245, 1307), (347, 1307), lw=1.3)
    arrow(ax, (440, 1284), (440, 1258))

    # Encoder group.
    add_box(ax, (260, 1004), (360, 244), "", COLORS["yellow"], edge=COLORS["yellow_edge"], lw=1.0, text_color="black")
    ax.text(278, 1228, "Encoder", fontsize=12, weight="bold", family="DejaVu Sans", color="#4A3B00")
    e_boxes = [
        ((340, 1195), (200, 32), "Enc 1\nConvBlock + ResBlock"),
        ((340, 1143), (200, 32), "Down 1"),
        ((340, 1091), (200, 32), "Enc 2\nConvBlock + ResBlock"),
        ((340, 1039), (200, 32), "Down 2"),
    ]
    add_box(ax, e_boxes[0][0], e_boxes[0][1], e_boxes[0][2], COLORS["green"], fontsize=8.5)
    arrow(ax, (440, 1195), (440, 1175), mutation_scale=9)
    add_box(ax, e_boxes[1][0], e_boxes[1][1], e_boxes[1][2], COLORS["blue"], fontsize=9)
    arrow(ax, (440, 1143), (440, 1123), mutation_scale=9)
    add_box(ax, e_boxes[2][0], e_boxes[2][1], e_boxes[2][2], COLORS["green"], fontsize=8.5)
    arrow(ax, (440, 1091), (440, 1071), mutation_scale=9)
    add_box(ax, e_boxes[3][0], e_boxes[3][1], e_boxes[3][2], COLORS["blue"], fontsize=9)
    arrow(ax, (440, 1258), (440, 1227))
    arrow(ax, (440, 1039), (440, 1022))

    # Third encoder / bottleneck block.
    add_box(ax, (260, 768), (360, 230), "", COLORS["yellow"], edge=COLORS["yellow_edge"], lw=1.0, text_color="black")
    ax.text(278, 978, "Deep encoder + bottleneck", fontsize=12, weight="bold", family="DejaVu Sans", color="#4A3B00")
    add_box(ax, (340, 940), (200, 32), "Enc 3\nConvBlock + ResBlock", COLORS["green"], fontsize=8.5)
    arrow(ax, (440, 940), (440, 918), mutation_scale=9)
    add_box(ax, (340, 890), (200, 32), "Down 3", COLORS["blue"], fontsize=9)
    arrow(ax, (440, 890), (440, 868), mutation_scale=9)
    add_box(ax, (323, 828), (234, 45), "Bottleneck\nConvBlock + 2 ResBlocks", COLORS["cyan"], fontsize=9)
    add_box(ax, (573, 828), (82, 45), "SE\noptional", COLORS["gray"], fontsize=8)
    arrow(ax, (557, 850), (573, 850), mutation_scale=8)
    arrow(ax, (440, 828), (440, 790))

    # Decoder block.
    add_box(ax, (240, 418), (400, 330), "", COLORS["yellow"], edge=COLORS["yellow_edge"], lw=1.0, text_color="black")
    ax.text(258, 728, "Decoder with skip connections", fontsize=12, weight="bold", family="DejaVu Sans", color="#4A3B00")
    add_box(ax, (336, 688), (208, 32), "Up 3 + skip f3", COLORS["blue"], fontsize=9)
    arrow(ax, (440, 688), (440, 666), mutation_scale=9)
    add_box(ax, (336, 636), (208, 32), "Dec 3\nConvBlock + ResBlock", COLORS["green"], fontsize=8.5)
    arrow(ax, (440, 636), (440, 614), mutation_scale=9)
    add_box(ax, (336, 584), (208, 32), "Up 2 + skip f2", COLORS["blue"], fontsize=9)
    arrow(ax, (440, 584), (440, 562), mutation_scale=9)
    add_box(ax, (336, 532), (208, 32), "Dec 2\nConvBlock + ResBlock", COLORS["green"], fontsize=8.5)
    arrow(ax, (245, 548), (336, 548), lw=1.3)
    add_box(ax, (88, 526), (128, 44), "Weak PSF\ninjection", COLORS["pink"], fontsize=8.5)
    arrow(ax, (216, 548), (336, 548), lw=1.2)
    arrow(ax, (440, 532), (440, 510), mutation_scale=9)
    add_box(ax, (336, 480), (208, 32), "Up 1 + skip f1", COLORS["blue"], fontsize=9)
    arrow(ax, (440, 480), (440, 458), mutation_scale=9)
    add_box(ax, (336, 428), (208, 32), "Dec 1\nConvBlock + ResBlock", COLORS["green"], fontsize=8.5)
    # Skip connection rail, drawn as an outer bus to avoid visual clutter.
    ax.plot([668, 668], [1212, 496], color=COLORS["line"], lw=1.25)
    ax.plot([540, 668], [1212, 1212], color=COLORS["line"], lw=1.25)
    ax.plot([540, 668], [1107, 1107], color=COLORS["line"], lw=1.25)
    ax.plot([540, 668], [956, 956], color=COLORS["line"], lw=1.25)
    arrow(ax, (668, 704), (544, 704), lw=1.25, mutation_scale=9)
    arrow(ax, (668, 600), (544, 600), lw=1.25, mutation_scale=9)
    arrow(ax, (668, 496), (544, 496), lw=1.25, mutation_scale=9)
    ax.text(680, 850, "skip\nconnections", fontsize=8.2, rotation=90, ha="center", va="center", family="DejaVu Sans")
    arrow(ax, (440, 418), (440, 384))

    # Output head.
    add_box(ax, (255, 204), (370, 160), "", COLORS["lightcyan"], edge="#B7DEE0", lw=1.0, text_color="black")
    ax.text(273, 344, "Output head", fontsize=12, weight="bold", family="DejaVu Sans", color="#00545A")
    add_box(ax, (332, 312), (216, 30), "Output Conv + sigmoid", COLORS["green"], fontsize=8.8)
    arrow(ax, (440, 312), (440, 292), mutation_scale=9)
    add_box(ax, (315, 260), (250, 34), "Boundary residual adapter\noptional", COLORS["gray"], fontsize=8.4)
    arrow(ax, (440, 260), (440, 238), mutation_scale=9)
    add_box(ax, (302, 210), (276, 36), "Raw-anchor output\nV24: 90% Raw + 10% recon", COLORS["cyan"], fontsize=8.6)
    arrow(ax, (115, 228), (302, 228), lw=1.3)
    arrow(ax, (440, 204), (440, 168))
    add_box(ax, (340, 120), (200, 40), "Reconstructed\nimage", COLORS["green"], fontsize=9)

    # Extra explanatory notes, kept small.
    add_box(ax, (40, 82), (620, 28), "Single-image inference; sequence/motion data are used for training and validation, not as extra input.", COLORS["raw"], fontsize=8.2, text_color="#30343B", edge="#C8CCD2")

    # PSF rail feeds.
    arrow(ax, (245, 1307), (347, 1307), lw=1.25)
    arrow(ax, (245, 548), (88, 548), lw=1.2, style="-")

    fig.patch.set_facecolor("white")
    png = OUT_DIR / "geoedgealignsr_v24_architecture_thesis_style.png"
    svg = OUT_DIR / "geoedgealignsr_v24_architecture_thesis_style.svg"
    pdf = OUT_DIR / "geoedgealignsr_v24_architecture_thesis_style.pdf"
    fig.savefig(png, dpi=260, bbox_inches="tight", facecolor="white")
    fig.savefig(svg, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(png)
    print(svg)
    print(pdf)


def save_all_formats(fig, stem: str):
    png = OUT_DIR / f"{stem}.png"
    svg = OUT_DIR / f"{stem}.svg"
    pdf = OUT_DIR / f"{stem}.pdf"
    fig.savefig(png, dpi=260, bbox_inches="tight", facecolor="white")
    fig.savefig(svg, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(png)
    print(svg)
    print(pdf)


def add_plus(ax, center, radius=12):
    circ = Circle(center, radius, facecolor="white", edgecolor=COLORS["line"], linewidth=1.1)
    ax.add_patch(circ)
    ax.text(center[0], center[1] - 0.5, "+", ha="center", va="center", fontsize=10, weight="bold", family="DejaVu Sans")
    return circ


def draw_encoder_detail_stage(ax, x, y, w, h, stage: int):
    add_box(ax, (x, y), (w, h), "", COLORS["yellow"], edge=COLORS["yellow_edge"], lw=1.0, text_color="black")
    ax.text(x + 18, y + h - 24, f"EDB {stage}", fontsize=11.5, weight="bold", family="DejaVu Sans", color="#4A3B00")

    cx = x + 170
    bw = 190
    bx = cx - bw / 2
    add_box(ax, (bx, y + h - 74), (bw, 34), f"Conv_EDB {stage}-1\nConv 3x3 + GN + SiLU", COLORS["green"], fontsize=7.1)
    arrow(ax, (cx, y + h - 74), (cx, y + h - 94), mutation_scale=8)
    add_box(ax, (bx, y + h - 132), (bw, 42), f"Conv_EDB {stage}-2\nRelu_EDB {stage}-1", COLORS["green"], fontsize=7.3)

    plus = (cx, y + 64)
    arrow(ax, (cx, y + h - 132), (cx, plus[1] + 12), mutation_scale=8)
    rail_x = x + 328
    ax.plot([cx, rail_x], [y + h - 90, y + h - 90], color=COLORS["line"], lw=1.1)
    ax.plot([rail_x, rail_x], [y + h - 90, plus[1]], color=COLORS["line"], lw=1.1)
    arrow(ax, (rail_x, plus[1]), (plus[0] + 12, plus[1]), mutation_scale=8)
    add_box(ax, (rail_x - 45, y + h - 74), (90, 28), f"Conv_EDB {stage}-3\nRelu_EDB {stage}-2", COLORS["gray"], fontsize=6.5, text_color="white", edge="#C8CCD2")
    add_plus(ax, plus, radius=10)

    add_box(ax, (cx - 82, y + 20), (164, 28), f"Norm EDB {stage}", COLORS["cyan"], fontsize=7.8)
    arrow(ax, (plus[0], plus[1] - 10), (cx, y + 48), mutation_scale=8)
    add_box(ax, (x + w + 18, y + 19), (78, 30), f"skip f{stage}", COLORS["raw"], fontsize=7.8, text_color="#2A2F36", edge="#BFC5CC")
    arrow(ax, (cx + 82, y + 34), (x + w + 18, y + 34), lw=1.2, mutation_scale=8)


def draw_decoder_detail_stage(ax, x, y, w, h, stage: int, inject_psf=False):
    add_box(ax, (x, y), (w, h), "", COLORS["yellow"], edge=COLORS["yellow_edge"], lw=1.0, text_color="black")
    ax.text(x + 18, y + h - 24, f"DDB {stage}", fontsize=11.5, weight="bold", family="DejaVu Sans", color="#4A3B00")

    cx = x + 190
    bw = 210
    bx = cx - bw / 2
    add_box(ax, (bx, y + h - 64), (bw, 30), f"Up {stage}\nDeconv DDB {stage}", COLORS["blue"], fontsize=7.2)
    arrow(ax, (cx, y + h - 64), (cx, y + h - 84), mutation_scale=8)
    add_box(ax, (bx, y + h - 108), (bw, 30), f"Concat f{stage}", COLORS["cyan"], fontsize=7.8)
    arrow(ax, (cx, y + h - 108), (cx, y + h - 128), mutation_scale=8)
    add_box(ax, (bx, y + h - 152), (bw, 30), f"Conv_DDB {stage}-1\nConv 3x3 + GN + SiLU", COLORS["green"], fontsize=6.9)
    arrow(ax, (cx, y + h - 152), (cx, y + h - 172), mutation_scale=8)
    add_box(ax, (bx, y + h - 208), (bw, 42), f"Conv_DDB {stage}-2\nRelu_DDB {stage}-1", COLORS["green"], fontsize=7.3)

    plus = (cx, y + 48)
    arrow(ax, (cx, y + h - 208), (cx, plus[1] + 12), mutation_scale=8)
    rail_x = x + 330
    ax.plot([cx, rail_x], [y + h - 166, y + h - 166], color=COLORS["line"], lw=1.1)
    ax.plot([rail_x, rail_x], [y + h - 166, plus[1]], color=COLORS["line"], lw=1.1)
    arrow(ax, (rail_x, plus[1]), (plus[0] + 12, plus[1]), mutation_scale=8)
    add_box(ax, (rail_x - 44, y + h - 154), (88, 27), f"Conv_DDB {stage}-3\nRelu_DDB {stage}-2", COLORS["gray"], fontsize=6.3, text_color="white", edge="#C8CCD2")
    add_plus(ax, plus, radius=10)

    add_box(ax, (cx - 84, y + 8), (168, 28), f"Norm DDB {stage}", COLORS["cyan"], fontsize=7.8)
    arrow(ax, (plus[0], plus[1] - 10), (cx, y + 36), mutation_scale=8)

    add_box(ax, (x + w + 18, y + h - 106), (78, 30), f"skip f{stage}", COLORS["raw"], fontsize=7.8, text_color="#30343B", edge="#BFC5CC")
    arrow(ax, (x + w + 18, y + h - 91), (bx + bw, y + h - 93), lw=1.2, mutation_scale=8)


def build_encoder_figure():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(7.2, 15.8), dpi=220)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 720)
    ax.set_ylim(0, 1600)
    ax.axis("off")

    ax.text(
        360,
        1568,
        "GeoEdgeAlignSR-v1 V24 Encoder",
        ha="center",
        va="center",
        fontsize=15,
        weight="bold",
        family="DejaVu Sans",
    )
    ax.text(
        360,
        1538,
        "Input image, PSF-aware preprocessing, and multi-scale feature extraction",
        ha="center",
        va="center",
        fontsize=9,
        family="DejaVu Sans",
        color="#3C4048",
    )

    add_psf_thumbnail(fig, 0.10, 0.840, 0.25, 0.105)
    add_input_thumbnail(fig, 0.53, 0.840, 0.25, 0.105)

    add_box(ax, (56, 1248), (112, 42), "PSF\nprior", COLORS["green"], fontsize=10)
    ax.plot([112, 112], [252, 1248], color=COLORS["line"], lw=1.15)
    add_box(ax, (54, 210), (116, 38), "to decoder:\nweak PSF", COLORS["pink"], fontsize=8.2)

    add_box(ax, (405, 1250), (120, 34), "Conv_3", COLORS["green"], fontsize=9)
    arrow(ax, (465, 1238), (465, 1208), mutation_scale=10)
    add_box(ax, (350, 1158), (230, 48), "Deconv EDB input\nPSF physics layer", COLORS["pink"], fontsize=8.0)
    arrow(ax, (168, 1268), (350, 1182), lw=1.2)
    arrow(ax, (465, 1158), (465, 1128), mutation_scale=10)

    stage_x = 220
    stage_w = 390
    draw_encoder_detail_stage(ax, stage_x, 895, stage_w, 220, 1)
    arrow(ax, (465, 1128), (465, 1100), mutation_scale=10)
    arrow(ax, (465, 895), (465, 866), mutation_scale=10)
    add_box(ax, (338, 820), (254, 36), "Down 1\nConv_d1", COLORS["blue"], fontsize=8.6)
    arrow(ax, (465, 820), (465, 790), mutation_scale=10)

    draw_encoder_detail_stage(ax, stage_x, 570, stage_w, 220, 2)
    arrow(ax, (465, 570), (465, 540), mutation_scale=10)
    add_box(ax, (338, 494), (254, 36), "Down 2\nConv_d2", COLORS["blue"], fontsize=8.6)
    arrow(ax, (465, 494), (465, 465), mutation_scale=10)

    draw_encoder_detail_stage(ax, stage_x, 245, stage_w, 220, 3)
    arrow(ax, (465, 245), (465, 214), mutation_scale=10)
    add_box(ax, (338, 170), (254, 36), "Down 3\nConv_d3", COLORS["blue"], fontsize=8.6)
    arrow(ax, (465, 178), (465, 150), mutation_scale=10)

    add_box(ax, (220, 42), (390, 104), "", COLORS["yellow"], edge=COLORS["yellow_edge"], lw=1.0, text_color="black")
    ax.text(238, 124, "Bottleneck", fontsize=11.5, weight="bold", family="DejaVu Sans", color="#4A3B00")
    add_box(ax, (314, 92), (214, 30), "Conv_mid", COLORS["green"], fontsize=8.2)
    add_box(ax, (314, 54), (214, 30), "Relu_mid + Norm_mid", COLORS["cyan"], fontsize=8.0)
    arrow(ax, (465, 92), (465, 84), mutation_scale=8)

    add_box(ax, (38, 12), (640, 24), "Encoder side: the image is converted into three skip features and one bottleneck feature.", COLORS["raw"], fontsize=8.0, text_color="#30343B", edge="#C8CCD2")

    fig.patch.set_facecolor("white")
    save_all_formats(fig, "geoedgealignsr_v24_encoder_thesis_style")


def build_decoder_figure():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(7.2, 14.5), dpi=220)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 720)
    ax.set_ylim(0, 1450)
    ax.axis("off")

    ax.text(
        360,
        1418,
        "GeoEdgeAlignSR-v1 V24 Decoder",
        ha="center",
        va="center",
        fontsize=15,
        weight="bold",
        family="DejaVu Sans",
    )
    ax.text(
        360,
        1388,
        "Feature recovery, skip fusion, weak PSF injection, and raw-anchored output",
        ha="center",
        va="center",
        fontsize=9,
        family="DejaVu Sans",
        color="#3C4048",
    )

    add_box(ax, (42, 1296), (104, 44), "Raw\nanchor", COLORS["green"], fontsize=10)
    ax.plot([94, 94], [107, 1296], color=COLORS["line"], lw=1.15)
    add_box(ax, (104, 1110), (92, 44), "PSF\nprior", COLORS["green"], fontsize=9.5)
    ax.plot([150, 150], [1110, 624], color=COLORS["line"], lw=1.15)

    add_box(ax, (310, 1300), (210, 44), "Norm_mid\nfrom encoder", COLORS["cyan"], fontsize=9)
    arrow(ax, (415, 1300), (415, 1270), mutation_scale=10)

    stage_x = 210
    stage_w = 392
    draw_decoder_detail_stage(ax, stage_x, 986, stage_w, 270, 3)
    arrow(ax, (415, 1270), (415, 1256), mutation_scale=10)
    arrow(ax, (415, 986), (415, 932), mutation_scale=10)

    draw_decoder_detail_stage(ax, stage_x, 662, stage_w, 270, 2)
    add_box(ax, (324, 606), (182, 36), "Deconv DDB 2\nweak PSF", COLORS["pink"], fontsize=7.8)
    arrow(ax, (150, 624), (324, 624), lw=1.1)
    arrow(ax, (415, 662), (415, 642), mutation_scale=9)
    arrow(ax, (415, 606), (415, 588), mutation_scale=9)

    draw_decoder_detail_stage(ax, stage_x, 318, stage_w, 270, 1)
    arrow(ax, (415, 318), (415, 292), mutation_scale=10)

    add_box(ax, (210, 70), (400, 222), "", COLORS["lightcyan"], edge="#B7DEE0", lw=1.0, text_color="black")
    ax.text(230, 268, "Output head", fontsize=12.5, weight="bold", family="DejaVu Sans", color="#00545A")
    add_box(ax, (308, 232), (230, 30), "Conv_out", COLORS["green"], fontsize=8.4)
    arrow(ax, (415, 232), (415, 214), mutation_scale=8)
    add_box(ax, (308, 190), (230, 30), "Relu_out / Sigmoid_out", COLORS["gray"], fontsize=7.8)
    arrow(ax, (415, 190), (415, 172), mutation_scale=8)
    add_box(ax, (276, 148), (294, 30), "Norm_out / Boundary adapter", COLORS["gray"], fontsize=7.8)
    arrow(ax, (415, 148), (415, 130), mutation_scale=8)
    add_box(ax, (260, 86), (326, 42), "RawAnchor_out\nV24 blend: 90% Raw + 10% recon", COLORS["cyan"], fontsize=8.0)
    arrow(ax, (94, 107), (260, 107), lw=1.3)

    arrow(ax, (415, 70), (415, 50), mutation_scale=9)
    add_box(ax, (314, 18), (202, 28), "Reconstructed image", COLORS["green"], fontsize=8.4)

    add_box(ax, (42, 0), (640, 14), "Decoder side: skip features rebuild detail; V24 anchors the final image to Raw.", COLORS["raw"], fontsize=6.8, text_color="#30343B", edge="#C8CCD2")

    fig.patch.set_facecolor("white")
    save_all_formats(fig, "geoedgealignsr_v24_decoder_thesis_style")


if __name__ == "__main__":
    build_figure()
    build_encoder_figure()
    build_decoder_figure()
