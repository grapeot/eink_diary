"""eink-diary 命令行入口。

子命令：
- collect: 采集时间窗内的多源近况，合并成纯文本。
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from .collector import collect, format_text
from .config import Config
from .sources.ai_sessions import export_ai_sessions


def _add_collect_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("collect", help="采集时间窗内的近况并合并成纯文本")
    p.add_argument(
        "--minutes", type=int, default=None,
        help="时间窗长度（分钟），默认取配置值（DIARY_WINDOW_MINUTES 或 120）",
    )
    p.add_argument(
        "--end", type=str, default=None,
        help="时间窗右端 ISO8601（如 2026-06-06T10:00），默认 now。便于回放历史窗口",
    )
    p.add_argument(
        "--sources", type=str, default=None,
        help="逗号分隔，只采集这些源（在已启用源中筛）。默认全部已配置的源",
    )
    p.add_argument("--output", type=str, default=None, help="输出文件路径")
    p.add_argument("--stdout", action="store_true", help="直接打印到标准输出")


def _run_collect(args: argparse.Namespace) -> int:
    config = Config.from_env()

    end = None
    if args.end:
        try:
            end = datetime.fromisoformat(args.end)
        except ValueError:
            print(f"无法解析 --end: {args.end}", file=sys.stderr)
            return 2

    only = (
        [s.strip() for s in args.sources.split(",") if s.strip()]
        if args.sources
        else None
    )

    enabled = config.enabled_sources()
    if not enabled:
        print(
            "没有任何已配置的数据源。请在 .env 里配置至少一个："
            "DIARY_WECHAT_MSG_DIR / DIARY_AI_SESSIONS_REPO / "
            "DIARY_RESEND_SKILL_DIR(+RESEND_API_KEY)。",
            file=sys.stderr,
        )
        return 1

    try:
        export_ai_sessions(config.ai_sessions_repo)
    except Exception as exc:  # noqa: BLE001
        print(f"AI sessions 导出失败: {exc}", file=sys.stderr)
        return 1

    start, win_end, results = collect(config, end=end, minutes=args.minutes, only=only)
    minutes = int((win_end - start).total_seconds() // 60)
    text = format_text(start, win_end, results, minutes)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"已写入 {args.output}", file=sys.stderr)
    if args.stdout or not args.output:
        sys.stdout.write(text)
    return 0


def _add_synthesize_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("synthesize", help="素材文件 → 一段瞬间画面描述（image prompt）")
    p.add_argument("--input", type=str, default=None, help="素材文件路径；缺省读 stdin")
    p.add_argument("--output", type=str, default=None, help="画面描述写入路径")


def _run_synthesize(args: argparse.Namespace) -> int:
    from .synthesize import synthesize

    if args.input:
        with open(args.input, encoding="utf-8") as fh:
            context_text = fh.read()
    else:
        context_text = sys.stdin.read()
    if not context_text.strip():
        print("素材为空", file=sys.stderr)
        return 1

    prompt = synthesize(context_text)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(prompt + "\n")
        print(f"已写入 {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(prompt + "\n")
    return 0


def _add_run_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "run", help="one-shot：采集→挑瞬间→出图(带 moderation 重试)→推送 Pi（供 cron）"
    )
    p.add_argument("--minutes", type=int, default=None, help="时间窗长度，默认配置值")
    p.add_argument("--end", type=str, default=None, help="时间窗右端 ISO8601，默认 now")
    p.add_argument("--size", type=str, default="2K", help="图像尺寸，默认 2K")
    p.add_argument("--quality", type=str, default="medium", help="gpt-image-2 质量，默认 medium")
    p.add_argument("--output-prefix", type=str, default="eink_diary_out", help="图输出前缀")
    p.add_argument("--no-push", action="store_true", help="只出图不推送 Pi")


def _run_run(args: argparse.Namespace) -> int:
    from .pipeline import run_once

    end = None
    if args.end:
        try:
            end = datetime.fromisoformat(args.end)
        except ValueError:
            print(f"无法解析 --end: {args.end}", file=sys.stderr)
            return 2
    try:
        result = run_once(
            end=end,
            minutes=args.minutes,
            output_prefix=args.output_prefix,
            image_size=args.size,
            quality=args.quality,
            push=not args.no_push,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"run 失败: {exc}", file=sys.stderr)
        return 1
    print(f"窗口: {result['window']} | 素材 {result['context_chars']} 字", file=sys.stderr)
    print(f"图: {result['image_path']} | 推送: {result['pushed']}", file=sys.stderr)
    if result["note"]:
        print(f"note: {result['note']}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eink-diary", description="墨记 eink_diary")
    sub = parser.add_subparsers(dest="command", required=True)
    _add_collect_parser(sub)
    _add_synthesize_parser(sub)
    _add_run_parser(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "collect":
        return _run_collect(args)
    if args.command == "synthesize":
        return _run_synthesize(args)
    if args.command == "run":
        return _run_run(args)
    parser.error(f"未知命令: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
