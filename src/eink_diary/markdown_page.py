"""Render a readable first Markdown page for the portrait Raspberry Pi display."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1200
HEIGHT = 1600
MARGIN_X = 84
MARGIN_Y = 80
FOOTER_HEIGHT = 72


@dataclass(frozen=True)
class Line:
    text: str
    size: int
    bold: bool = False
    indent: int = 0


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size, index=0)


def _lines(markdown: str, title: str) -> list[Line]:
    lines = [Line(title, 56, bold=True), Line("", 14)]
    first_heading = True
    for raw in markdown.splitlines():
        text = raw.strip()
        if not text:
            lines.append(Line("", 14))
            continue
        heading = re.match(r"^(#{1,3})\s+(.+)$", text)
        if heading:
            value = heading.group(2)
            if first_heading and value == title:
                first_heading = False
                continue
            first_heading = False
            lines.append(Line(value, {1: 56, 2: 46, 3: 38}[len(heading.group(1))], bold=True))
            continue
        bullet = re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)(.+)$", text)
        lines.append(Line(("• " + bullet.group(1)) if bullet else text, 34, indent=18 if bullet else 0))
    return lines


def _wrap(draw: ImageDraw.ImageDraw, line: Line, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    parts = re.findall(r"[A-Za-z0-9][A-Za-z0-9._:/?&=#%+~-]*|.", re.sub(r"\s+", " ", line.text))
    rows: list[str] = []
    current = ""
    for part in parts:
        candidate = current + part
        if current and draw.textlength(candidate, font=font) > width:
            rows.append(current)
            current = part.lstrip()
        else:
            current = candidate
    rows.append(current)
    return rows


def render_first_page(markdown: str, title: str, font_path: str) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    pages: list[Image.Image] = []
    y = MARGIN_Y

    def new_page() -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
        page = Image.new("RGB", (WIDTH, HEIGHT), "white")
        return page, ImageDraw.Draw(page), MARGIN_Y

    for line in _lines(markdown, title):
        font = _font(font_path, line.size)
        rows = _wrap(draw, line, font, WIDTH - MARGIN_X * 2 - line.indent)
        height = line.size + 14
        for row in rows:
            if y + height > HEIGHT - MARGIN_Y - FOOTER_HEIGHT and y > MARGIN_Y:
                pages.append(image)
                image, draw, y = new_page()
            x = MARGIN_X + line.indent
            draw.text((x, y), row, font=font, fill="black")
            if line.bold:
                draw.text((x + 1, y), row, font=font, fill="black")
            y += height
    pages.append(image)
    footer = _font(font_path, 24)
    for number, page in enumerate(pages, start=1):
        ImageDraw.Draw(page).text((MARGIN_X, HEIGHT - MARGIN_Y), f"{number}/{len(pages)}", font=footer, fill="black")
    return pages[0]


def render_file(path: Path, title: str | None, font_path: str) -> Image.Image:
    return render_first_page(path.read_text(encoding="utf-8"), title or path.stem, font_path)
