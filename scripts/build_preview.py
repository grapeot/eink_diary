#!/usr/bin/env python3
"""Build a local static diary preview at diary/index.html."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path


IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")


@dataclass(frozen=True)
class Slot:
    day: str
    slot: str
    slot_dir: Path
    image_path: str
    prompt: str
    prompt_chars: int
    context_chars: int
    manifest: dict


@dataclass(frozen=True)
class DayGroup:
    day: str
    slots: list[Slot]


def _find_image(slot_dir: Path) -> Path | None:
    for suffix in IMAGE_SUFFIXES:
        candidate = slot_dir / f"image{suffix}"
        if candidate.exists():
            return candidate
    return None


def _rel(path: Path, base_file: Path) -> str:
    return str(path.relative_to(base_file.parent))


def _source_counts(manifest: dict) -> str:
    parts = []
    for source in manifest.get("sources") or []:
        name = source.get("name", "unknown")
        count = source.get("count", 0)
        available = source.get("available", False)
        label = f"{name}:{count}"
        if not available:
            label += " unavailable"
        parts.append(label)
    return " · ".join(parts) if parts else "sources: n/a"


def load_days(diary_dir: Path, output_file: Path) -> list[DayGroup]:
    by_day: dict[str, list[Slot]] = {}
    for manifest_path in sorted(diary_dir.glob("20??-??-??/*/manifest.json")):
        slot_dir = manifest_path.parent
        day = slot_dir.parent.name
        slot = slot_dir.name
        image = _find_image(slot_dir)
        if image is None:
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        prompt_path = slot_dir / "prompt.txt"
        prompt = prompt_path.read_text(encoding="utf-8").strip() if prompt_path.exists() else ""
        context_path = slot_dir / "context_private.md"
        context_chars = len(context_path.read_text(encoding="utf-8")) if context_path.exists() else 0
        by_day.setdefault(day, []).append(
            Slot(
                day=day,
                slot=slot,
                slot_dir=slot_dir,
                image_path=_rel(image, output_file),
                prompt=prompt,
                prompt_chars=len(prompt),
                context_chars=context_chars,
                manifest=manifest,
            )
        )
    return [DayGroup(day, sorted(slots, key=lambda s: s.slot)) for day, slots in sorted(by_day.items())]


def _cover_html(slots: list[Slot]) -> str:
    cover_slots = slots[:4]
    if not cover_slots:
        return '<div class="cover empty-cover">No image</div>'
    imgs = "".join(
        f'<img src="{escape(slot.image_path)}" alt="{escape(slot.day + " " + slot.slot)}" loading="lazy">'
        for slot in cover_slots
    )
    klass = "cover mosaic" if len(cover_slots) >= 4 else "cover single-cover"
    return f'<div class="{klass}">{imgs}</div>'


def _slot_card(slot: Slot) -> str:
    window = slot.manifest.get("window", {})
    start = escape(str(window.get("start", "")))
    end = escape(str(window.get("end", "")))
    source_counts = escape(_source_counts(slot.manifest))
    prompt_kind = escape(str((slot.manifest.get("backfill") or {}).get("prompt_kind", "final")))
    prompt = escape(slot.prompt)
    return f"""
      <article class="slot-card">
        <img src="{escape(slot.image_path)}" alt="{escape(slot.day)} {escape(slot.slot)}" loading="lazy">
        <div class="slot-meta">
          <div class="slot-title">{escape(slot.slot)}</div>
          <div>{start} → {end}</div>
          <div>{source_counts}</div>
          <div>prompt: {slot.prompt_chars} chars · context: {slot.context_chars} chars · kind: {prompt_kind}</div>
        </div>
        <details>
          <summary>Prompt</summary>
          <pre>{prompt}</pre>
        </details>
      </article>
    """


def _day_section(day: DayGroup) -> str:
    slots = day.slots
    slot_count = len(slots)
    slot_range = f"{slots[0].slot}–{slots[-1].slot}" if slots else ""
    slot_cards = "\n".join(_slot_card(slot) for slot in slots)
    return f"""
    <section class="day-card" data-day="{escape(day.day)}">
      <button class="day-summary" type="button" aria-expanded="false">
        {_cover_html(slots)}
        <div class="day-info">
          <div class="date">{escape(day.day)}</div>
          <div class="day-subtitle">{slot_count} frames · {escape(slot_range)}</div>
        </div>
        <div class="open-hint">Open day</div>
      </button>
      <div class="day-detail">
        <div class="detail-header">
          <div>
            <h2>{escape(day.day)}</h2>
            <p>{slot_count} frames in chronological order</p>
          </div>
          <button class="close-day" type="button">Close</button>
        </div>
        <div class="slots-grid">{slot_cards}</div>
      </div>
    </section>
    """


def render_html(days: list[DayGroup]) -> str:
    total_frames = sum(len(day.slots) for day in days)
    sections = "\n".join(_day_section(day) for day in days)
    empty = "" if days else "<div class='empty'>还没有归档图。先运行 eink-diary run 或 backfill。</div>"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>墨记 Preview</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #15100c;
      --bg-2: #2a1a10;
      --paper: #f6ead7;
      --paper-2: #fff8ec;
      --paper-3: #ead8bd;
      --ink: #24180f;
      --muted: #806d58;
      --line: rgba(76, 49, 24, 0.18);
      --shadow: rgba(0, 0, 0, 0.30);
      --amber: #b6662d;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; min-height: 100vh; background: radial-gradient(circle at 12% 0%, #49301e 0, var(--bg-2) 26%, var(--bg) 62%); color: var(--paper); font: 15px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body::before {{ content: ""; position: fixed; inset: 0; pointer-events: none; opacity: 0.28; background-image: linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px); background-size: 38px 38px, 38px 38px; mask-image: radial-gradient(circle at 50% 15%, #000, transparent 74%); }}
    header {{ padding: 40px clamp(16px, 4vw, 56px) 24px; }}
    h1 {{ margin: 0; font-size: clamp(38px, 7vw, 92px); letter-spacing: -0.075em; line-height: 0.88; font-weight: 850; }}
    .lede {{ margin: 14px 0 0; color: rgba(245, 234, 216, 0.72); max-width: 760px; font-size: 16px; }}
    .stats {{ margin-top: 20px; display: flex; gap: 12px; flex-wrap: wrap; }}
    .pill {{ border: 1px solid rgba(245, 234, 216, 0.24); border-radius: 999px; padding: 8px 13px; color: rgba(245, 234, 216, 0.82); background: rgba(255, 247, 234, 0.05); }}
    main {{ padding: 10px clamp(14px, 4vw, 56px) 64px; }}
    .calendar {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(310px, 1fr)); gap: 26px; align-items: start; }}
    .day-card {{ background: linear-gradient(145deg, var(--paper-2), var(--paper)); color: var(--ink); border: 1px solid rgba(255,255,255,0.34); border-radius: 32px; box-shadow: 0 26px 80px var(--shadow), inset 0 1px 0 rgba(255,255,255,0.65); overflow: hidden; transition: grid-column 420ms ease, transform 260ms ease, box-shadow 260ms ease; }}
    .day-card:hover {{ transform: translateY(-4px) rotate(-0.15deg); box-shadow: 0 34px 100px rgba(0,0,0,0.38), inset 0 1px 0 rgba(255,255,255,0.72); }}
    .day-card.open {{ grid-column: 1 / -1; transform: none; }}
    .day-summary {{ width: 100%; border: 0; background: transparent; color: inherit; padding: 0; text-align: left; cursor: pointer; display: block; }}
    .cover {{ height: 350px; background: var(--paper-3); overflow: hidden; }}
    .single-cover img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
    .mosaic {{ display: grid; grid-template-columns: repeat(2, 1fr); grid-template-rows: repeat(2, 1fr); gap: 5px; padding: 6px; }}
    .mosaic img {{ width: 100%; height: 100%; object-fit: cover; display: block; border-radius: 14px; box-shadow: 0 2px 8px rgba(45,28,12,0.16); }}
    .day-info {{ padding: 20px 22px 8px; }}
    .date {{ font-size: 36px; font-weight: 820; letter-spacing: -0.055em; }}
    .day-subtitle {{ color: var(--muted); margin-top: 4px; }}
    .open-hint {{ padding: 0 22px 22px; color: var(--amber); font-weight: 760; }}
    .day-detail {{ max-height: 0; opacity: 0; overflow: hidden; transform: translateY(-8px); transition: max-height 520ms ease, opacity 300ms ease, transform 420ms ease; }}
    .day-card.open .day-detail {{ max-height: 5000px; opacity: 1; transform: translateY(0); }}
    .detail-header {{ display: flex; justify-content: space-between; gap: 20px; align-items: start; padding: 28px 30px 12px; border-top: 1px solid var(--line); background: linear-gradient(180deg, rgba(255,255,255,0.22), transparent); }}
    .detail-header h2 {{ margin: 0; font-size: 32px; letter-spacing: -0.045em; }}
    .detail-header p {{ margin: 4px 0 0; color: var(--muted); }}
    .close-day {{ border: 1px solid var(--line); background: var(--paper-2); border-radius: 999px; padding: 9px 15px; cursor: pointer; box-shadow: 0 4px 12px rgba(55,32,10,0.08); }}
    .slots-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 18px; padding: 18px 24px 30px; }}
    .slot-card {{ background: rgba(255, 248, 236, 0.9); border: 1px solid var(--line); border-radius: 22px; overflow: hidden; box-shadow: 0 10px 28px rgba(73, 42, 12, 0.10); }}
    .slot-card > img {{ width: 100%; aspect-ratio: 3 / 4; object-fit: cover; display: block; background: #e2d0b6; }}
    .slot-meta {{ padding: 12px 13px; color: var(--muted); font-size: 11px; }}
    .slot-title {{ color: var(--ink); font-size: 22px; font-weight: 820; margin-bottom: 4px; letter-spacing: -0.035em; }}
    details {{ padding: 0 12px 12px; color: var(--muted); }}
    summary {{ cursor: pointer; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #efe0c9; color: var(--ink); padding: 10px; border-radius: 10px; font-size: 12px; }}
    .empty {{ padding: 28px; border: 1px solid rgba(245, 234, 216, 0.24); border-radius: 24px; color: rgba(245, 234, 216, 0.8); }}
    @media (max-width: 1100px) {{ .slots-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
    @media (max-width: 700px) {{ .cover {{ height: 260px; }} .date {{ font-size: 28px; }} .detail-header {{ flex-direction: column; }} .slots-grid {{ grid-template-columns: 1fr; padding: 14px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>墨记 Preview</h1>
    <p class="lede">本地视觉日记浏览器。按天打开，看这一天被画成了什么样。</p>
    <div class="stats"><span class="pill">{len(days)} days</span><span class="pill">{total_frames} frames</span><span class="pill">local only</span></div>
  </header>
  <main><div class="calendar">{sections}</div>{empty}</main>
  <script>
    document.addEventListener('click', (event) => {{
      const close = event.target.closest('.close-day');
      if (close) {{ close.closest('.day-card').classList.remove('open'); return; }}
      const summary = event.target.closest('.day-summary');
      if (!summary) return;
      const card = summary.closest('.day-card');
      const willOpen = !card.classList.contains('open');
      document.querySelectorAll('.day-card.open').forEach((el) => {{ if (el !== card) el.classList.remove('open'); }});
      card.classList.toggle('open', willOpen);
      summary.setAttribute('aria-expanded', String(willOpen));
      if (willOpen) setTimeout(() => card.scrollIntoView({{ behavior: 'smooth', block: 'start' }}), 80);
    }});
  </script>
</body>
</html>
"""


def build_preview(diary_dir: Path, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    days = load_days(diary_dir, output)
    output.write_text(render_html(days), encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local static preview from eink diary archive")
    parser.add_argument("--diary-dir", default="diary", type=Path)
    parser.add_argument("--output", default=None, type=Path, help="HTML output path, default: <diary-dir>/index.html")
    parser.add_argument("--output-dir", default=None, type=Path, help="Deprecated compatibility: writes index.html inside this directory")
    args = parser.parse_args()
    if args.output is not None:
        output = args.output
    elif args.output_dir is not None:
        output = args.output_dir / "index.html"
    else:
        output = args.diary_dir / "index.html"
    index = build_preview(args.diary_dir, output)
    print(index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
