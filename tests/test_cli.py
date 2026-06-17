"""CLI 冒烟测试：子命令注册、parser 不崩、--help 可用。"""

from __future__ import annotations

from datetime import datetime

import pytest

from eink_diary.cli import build_parser, main, resolve_full_day_window


def test_subcommands_registered():
    parser = build_parser()
    # 解析各子命令不报错（拿到 namespace 即可）
    for sub in ("collect", "synthesize", "run"):
        ns = parser.parse_args([sub])
        assert ns.command == sub
    ns = parser.parse_args(["display", "out.png"])
    assert ns.command == "display"
    assert ns.image == "out.png"


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


def test_full_day_before_two_am_means_yesterday():
    end, minutes = resolve_full_day_window(datetime(2026, 6, 8, 0, 7))
    assert end == datetime(2026, 6, 8, 0, 0)
    assert minutes == 24 * 60


def test_full_day_after_two_am_means_today_so_far():
    end, minutes = resolve_full_day_window(datetime(2026, 6, 8, 9, 30))
    assert end == datetime(2026, 6, 8, 9, 30)
    assert minutes == 9 * 60 + 30


def test_full_day_rejects_manual_window(capsys):
    code = main(["run", "--full-day", "--minutes", "120"])
    assert code == 2
    err = capsys.readouterr().err
    assert "--full-day" in err


def test_display_uses_explicit_server_url(monkeypatch, tmp_path, capsys):
    img = tmp_path / "frame.png"
    img.write_bytes(b"not inspected by cli")

    calls = []

    def fake_push(path, server_url, timeout=120):
        calls.append((path, server_url, timeout))
        return {"status": 200, "body": "ok"}

    import eink_diary.pipeline as pipeline

    monkeypatch.setattr(pipeline, "push_to_server", fake_push)
    code = main(["display", str(img), "--server-url", "http://pi.test:8080"])
    assert code == 0
    assert calls == [(str(img), "http://pi.test:8080", 120)]
    assert "/api/display" in capsys.readouterr().err


def test_display_requires_server_url(monkeypatch, tmp_path, capsys):
    img = tmp_path / "frame.png"
    img.write_bytes(b"x")
    monkeypatch.delenv("EINK_SERVER_URL", raising=False)

    code = main(["display", str(img)])
    assert code == 2
    assert "EINK_SERVER_URL" in capsys.readouterr().err


def test_display_rejects_missing_image(capsys):
    code = main(["display", "/tmp/does-not-exist.png", "--server-url", "http://pi.test:8080"])
    assert code == 2
    assert "图片不存在" in capsys.readouterr().err
