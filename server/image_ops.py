"""图像预处理：把任意输入图转成 1200x1600、Spectra-6 7 色的可刷屏图。

纯函数，不碰硬件、不碰网络，可离线单测。
逻辑复用自原 Pi 控制端（见 adhoc_jobs/archived/pi_eink_control_original）。
"""

from __future__ import annotations

from PIL import Image, ImageEnhance


DISPLAY_WIDTH = 1200
DISPLAY_HEIGHT = 1600

# Spectra 6 (E6) 7 色调色板：黑白黄红蓝绿橙
_SPECTRA6 = [
    (0, 0, 0),
    (255, 255, 255),
    (255, 255, 0),
    (255, 0, 0),
    (0, 0, 255),
    (0, 255, 0),
    (255, 128, 0),
]


def boost_saturation(image: Image.Image, factor: float = 1.2) -> Image.Image:
    return ImageEnhance.Color(image).enhance(factor)


def rotate_if_needed(image: Image.Image, target_ratio: float) -> Image.Image:
    """输入图朝向和目标不一致时旋转 90°，避免横图被压扁。"""
    img_ratio = image.width / float(image.height)
    mismatch = (img_ratio >= 1 and target_ratio < 1) or (
        img_ratio < 1 and target_ratio >= 1
    )
    return image.transpose(Image.ROTATE_90) if mismatch else image


def get_center_crop_box(
    img_w: int, img_h: int, target_w: int, target_h: int
) -> tuple[int, int, int, int]:
    img_ratio = img_w / float(img_h)
    target_ratio = target_w / float(target_h)
    if target_ratio > img_ratio:
        new_w, new_h = img_w, int(img_w / target_ratio)
        off_x, off_y = 0, (img_h - new_h) // 2
    else:
        new_h, new_w = img_h, int(img_h * target_ratio)
        off_x, off_y = (img_w - new_w) // 2, 0
    return (off_x, off_y, off_x + new_w, off_y + new_h)


def prepare_for_display(image: Image.Image) -> Image.Image:
    """旋转对齐 → 居中裁剪到 3:4 → resize 到 1200x1600。"""
    target_ratio = DISPLAY_WIDTH / float(DISPLAY_HEIGHT)
    aligned = rotate_if_needed(image, target_ratio)
    box = get_center_crop_box(
        aligned.width, aligned.height, DISPLAY_WIDTH, DISPLAY_HEIGHT
    )
    return aligned.crop(box).resize((DISPLAY_WIDTH, DISPLAY_HEIGHT), Image.LANCZOS)


def apply_spectra6_dithering(image: Image.Image) -> Image.Image:
    """Floyd-Steinberg 抖动到 7 色（适合插画/照片）。"""
    flat = []
    for r, g, b in _SPECTRA6:
        flat.extend([r, g, b])
    while len(flat) < 768:
        flat.extend([0, 0, 0])
    pal = Image.new("P", (1, 1))
    pal.putpalette(flat)
    return image.quantize(palette=pal, dither=Image.FLOYDSTEINBERG).convert("RGB")


def process_for_eink(image: Image.Image, saturation: float = 1.2) -> Image.Image:
    """完整链：RGB → 提饱和 → 裁剪缩放 → 7 色抖动。返回可刷屏的 1200x1600 图。"""
    rgb = image.convert("RGB")
    if saturation and saturation != 1.0:
        rgb = boost_saturation(rgb, saturation)
    prepared = prepare_for_display(rgb)
    return apply_spectra6_dithering(prepared)
