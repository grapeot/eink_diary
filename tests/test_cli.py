"""CLI 冒烟测试：子命令注册、parser 不崩、--help 可用。"""

from __future__ import annotations

import pytest

from eink_diary.cli import build_parser, main


def test_subcommands_registered():
    parser = build_parser()
    # 解析各子命令不报错（拿到 namespace 即可）
    for sub in ("collect", "synthesize", "run"):
        ns = parser.parse_args([sub])
        assert ns.command == sub


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "eink-diary" in out


def test_unknown_command_errors():
    with pytest.raises(SystemExit) as exc:
        main(["nope"])
    assert exc.value.code != 0


def test_run_flags_parse():
    parser = build_parser()
    ns = parser.parse_args(
        ["run", "--end", "2026-06-06T10:00", "--size", "2K", "--no-push"]
    )
    assert ns.command == "run"
    assert ns.end == "2026-06-06T10:00"
    assert ns.size == "2K"
    assert ns.no_push is True
