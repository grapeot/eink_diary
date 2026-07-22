from PIL import Image

from eink_diary.markdown_page import HEIGHT, WIDTH, render_first_page


def test_render_first_page_is_portrait_rgb() -> None:
    image = render_first_page("# Title\n\n" + "A readable paragraph. " * 200, "Title", "/System/Library/Fonts/Helvetica.ttc")
    assert image.mode == "RGB"
    assert image.size == (WIDTH, HEIGHT)
    assert image.getpixel((0, 0)) == (255, 255, 255)
