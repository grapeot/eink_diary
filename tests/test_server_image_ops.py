"""image_ops 纯函数 offline 测试。"""

from __future__ import annotations

from PIL import Image

from server.image_ops import (
    DISPLAY_HEIGHT,
    DISPLAY_WIDTH,
    apply_spectra6_dithering,
    prepare_for_display,
    process_for_eink,
    rotate_if_needed,
)


def test_prepare_outputs_exact_panel_size():
    # 任意尺寸输入 → 正好 1200x1600
    for size in [(800, 600), (1000, 2000), (1200, 1600), (3000, 3000)]:
        out = prepare_for_display(Image.new("RGB", size, "white"))
        assert out.size == (DISPLAY_WIDTH, DISPLAY_HEIGHT)


def test_rotate_landscape_to_portrait():
    # 横图（宽>高）目标是竖屏 → 应旋转
    landscape = Image.new("RGB", (1600, 1200), "white")
    target_ratio = DISPLAY_WIDTH / DISPLAY_HEIGHT  # <1（竖）
    rotated = rotate_if_needed(landscape, target_ratio)
    assert rotated.height > rotated.width  # 转成竖了


def test_portrait_not_rotated():
    portrait = Image.new("RGB", (1200, 1600), "white")
    target_ratio = DISPLAY_WIDTH / DISPLAY_HEIGHT
    out = rotate_if_needed(portrait, target_ratio)
    assert out.size == (1200, 1600)


def test_dithering_limits_to_7_colors():
    # 渐变图抖动后，颜色数应 <= 7（Spectra6 调色板）
    grad = Image.new("RGB", (100, 100))
    grad.putdata([(i % 256, (i * 2) % 256, (i * 3) % 256) for i in range(100 * 100)])
    out = apply_spectra6_dithering(grad)
    colors = out.convert("RGB").getcolors(maxcolors=100000)
    assert colors is not None
    assert len({c[1] for c in colors}) <= 7


def test_process_for_eink_full_chain():
    out = process_for_eink(Image.new("RGB", (900, 700), "red"))
    assert out.size == (DISPLAY_WIDTH, DISPLAY_HEIGHT)
    assert out.mode == "RGB"
