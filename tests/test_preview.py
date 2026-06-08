from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_preview_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_preview.py"
    spec = importlib.util.spec_from_file_location("build_preview", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_slot(root: Path, day: str, slot: str, prompt: str = "prompt") -> Path:
    d = root / day / slot
    d.mkdir(parents=True)
    (d / "image.jpg").write_bytes(f"image-{day}-{slot}".encode())
    (d / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")
    (d / "context_private.md").write_text("private context", encoding="utf-8")
    (d / "manifest.json").write_text(
        json.dumps(
            {
                "window": {
                    "start": f"{day}T00:00:00",
                    "end": f"{day}T{slot[:2]}:{slot[2:]}:00",
                    "minutes": 120,
                },
                "sources": [{"name": "wechat", "available": True, "count": 2, "error": ""}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return d


def test_build_preview_writes_diary_index_with_day_cards(tmp_path):
    mod = _load_preview_module()
    diary = tmp_path / "diary"
    _write_slot(diary, "2026-06-06", "0800")
    _write_slot(diary, "2026-06-06", "1000")
    _write_slot(diary, "2026-06-07", "0800")

    index = mod.build_preview(diary, diary / "index.html")
    html = index.read_text(encoding="utf-8")

    assert index == diary / "index.html"
    assert "2026-06-06" in html
    assert "2026-06-07" in html
    assert html.count('class="day-card"') == 2
    assert html.count('class="slot-card"') == 3
    assert "0800–1000" in html


def test_preview_uses_relative_archive_image_paths(tmp_path):
    mod = _load_preview_module()
    diary = tmp_path / "diary"
    _write_slot(diary, "2026-06-06", "0800")

    index = mod.build_preview(diary, diary / "index.html")
    html = index.read_text(encoding="utf-8")

    assert 'src="2026-06-06/0800/image.jpg"' in html
    assert "assets/" not in html


def test_preview_keeps_prompt_collapsed_and_context_private_out_of_html(tmp_path):
    mod = _load_preview_module()
    diary = tmp_path / "diary"
    _write_slot(diary, "2026-06-06", "0800", prompt="draw a duck")

    index = mod.build_preview(diary, diary / "index.html")
    html = index.read_text(encoding="utf-8")

    assert "<summary>Prompt</summary>" in html
    assert "draw a duck" in html
    assert "private context" not in html
    assert "context: 15 chars" in html


def test_empty_preview_has_empty_state(tmp_path):
    mod = _load_preview_module()
    diary = tmp_path / "diary"
    diary.mkdir()

    index = mod.build_preview(diary, diary / "index.html")
    html = index.read_text(encoding="utf-8")

    assert "0 days" in html
    assert "0 frames" in html
    assert "还没有归档图" in html
