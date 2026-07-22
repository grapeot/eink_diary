from PIL import Image, ImageFont

from eink_diary import markdown_page
from eink_diary.markdown_page import HEIGHT, WIDTH, render_first_page


def test_render_first_page_is_portrait_rgb(monkeypatch) -> None:
    monkeypatch.setattr(markdown_page, "_font", lambda _path, size: ImageFont.load_default(size=size))
    image = render_first_page("# Title\n\n" + "A readable paragraph. " * 200, "Title", "unused.ttf")
    assert image.mode == "RGB"
    assert image.size == (WIDTH, HEIGHT)
    assert image.getpixel((0, 0)) == (255, 255, 255)
