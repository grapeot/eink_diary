from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import NoReturn, Protocol, cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


class ParsedCliArgs(Protocol):
    prompt: str | None
    model: str | None
    size: str
    upscale: bool

class CoreModule(Protocol):
    MissingApiKeyError: type[Exception]

    def build_parser(self) -> argparse.ArgumentParser: ...

    def resolve_generate_model(self, requested_model: str | None) -> tuple[str, str]: ...

    def resolve_upscale_model(self, requested_model: str | None) -> tuple[str, str]: ...

    def map_size_for_openai(self, image_size: str, aspect_ratio: str | None) -> str: ...

    def build_output_path(self, output_spec: str, index: int) -> str: ...

    def get_gemini_api_key(self) -> str: ...

    def get_openai_api_key(self) -> str: ...

    def coerce_cli_args(self, args: argparse.Namespace) -> ParsedCliArgs: ...

    def validate_args(self, parser: argparse.ArgumentParser, args: argparse.Namespace) -> ParsedCliArgs: ...


class CliModule(Protocol):
    def main(self, argv: list[str] | None = None) -> int: ...


def _import_module(name: str) -> ModuleType:
    return importlib.import_module(name)


core = cast(CoreModule, cast(object, _import_module("eink_diary.imagegen.core")))
cli = cast(CliModule, cast(object, _import_module("eink_diary.imagegen.cli")))
MissingApiKeyError = core.MissingApiKeyError


def _build_parser() -> argparse.ArgumentParser:
    return core.build_parser()


def test_parser_defaults() -> None:
    parser = _build_parser()
    args = parser.parse_args(["-p", "a cat"])

    parsed = core.coerce_cli_args(args)

    assert parsed.prompt == "a cat"
    assert parsed.model is None
    assert parsed.size == "1K"
    assert parsed.upscale is False


def test_resolve_generate_model_defaults_to_gemini_flash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IMAGE_GENERATION_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_FLASH_IMAGE_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_IMAGE_GENERATION_MODEL", raising=False)

    provider, model_id = core.resolve_generate_model(None)

    assert provider == "gemini"
    assert model_id == "gemini-3.1-flash-image-preview"


def test_env_can_override_model_to_gpt(monkeypatch: pytest.MonkeyPatch) -> None:
    # 本项目通过 .env 的 IMAGE_GENERATION_MODEL=gpt-image-2 把默认设为 gpt。
    monkeypatch.setenv("IMAGE_GENERATION_MODEL", "gpt-image-2")
    provider, model_id = core.resolve_generate_model(None)
    assert provider == "openai"
    assert model_id == "gpt-image-2"


def test_resolve_generate_model_supports_exact_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IMAGE_GENERATION_MODEL", raising=False)

    provider, model_id = core.resolve_generate_model("gemini-3-pro-image-preview")

    assert provider == "gemini"
    assert model_id == "gemini-3-pro-image-preview"


def test_resolve_generate_model_supports_gpt_image_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IMAGE_GENERATION_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_IMAGE_MODEL", raising=False)

    provider, model_id = core.resolve_generate_model("gpt-image-2")

    assert provider == "openai"
    assert model_id == "gpt-image-2"


def test_image_generation_model_env_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_GENERATION_MODEL", "gpt-image-2")

    provider, model_id = core.resolve_generate_model(None)

    assert provider == "openai"
    assert model_id == "gpt-image-2"


def test_resolve_upscale_model_rejects_gpt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IMAGE_UPSCALE_MODEL", raising=False)

    with pytest.raises(ValueError, match="not supported"):
        _ = core.resolve_upscale_model("gpt-image-2")


@pytest.mark.parametrize(
    ("image_size", "aspect_ratio", "expected"),
    [
        ("1K", None, "1024x1024"),
        ("1K", "16:9", "1536x864"),
        ("2K", "4:3", "2048x1536"),
        ("4K", "16:9", "3840x2160"),
        ("4K", "9:16", "2160x3840"),
    ],
)
def test_map_size_for_openai(image_size: str, aspect_ratio: str | None, expected: str) -> None:
    assert core.map_size_for_openai(image_size, aspect_ratio) == expected


def test_map_size_for_openai_rejects_unknown_aspect_ratio() -> None:
    with pytest.raises(ValueError, match="Unsupported OpenAI size mapping"):
        _ = core.map_size_for_openai("1K", "2:1")


def test_build_output_path_with_jpg_suffix() -> None:
    assert core.build_output_path("cat.jpg", 0) == "cat.jpg"
    assert core.build_output_path("cat.jpg", 1) == "cat_1.jpg"


def test_build_output_path_with_png_suffix() -> None:
    assert core.build_output_path("cat.png", 0) == "cat.png"
    assert core.build_output_path("cat.png", 1) == "cat_1.png"


def test_build_output_path_without_suffix() -> None:
    assert core.build_output_path("cat", 0) == "cat_0.jpg"


def test_validate_args_requires_prompt_in_generate_mode() -> None:
    parser = _build_parser()
    args = parser.parse_args([])

    with pytest.raises(SystemExit):
        _ = core.validate_args(parser, args)


def test_validate_args_rejects_upscale_with_prompt() -> None:
    parser = _build_parser()
    args = parser.parse_args(["--upscale", "-i", "input.jpg", "-p", "test"])

    with pytest.raises(SystemExit):
        _ = core.validate_args(parser, args)


def test_validate_args_rejects_upscale_with_gpt() -> None:
    parser = _build_parser()
    args = parser.parse_args(["--upscale", "-i", "input.jpg", "-m", "gpt-image-2"])

    with pytest.raises(SystemExit):
        _ = core.validate_args(parser, args)


def test_validate_args_accepts_exact_model_id() -> None:
    parser = _build_parser()
    args = parser.parse_args(["-p", "test", "-m", "gemini-3.1-flash-image-preview"])

    _ = core.validate_args(parser, args)


def test_validate_args_rejects_unknown_model() -> None:
    parser = _build_parser()
    args = parser.parse_args(["-p", "test", "-m", "unknown-model"])

    with pytest.raises(SystemExit):
        _ = core.validate_args(parser, args)


def test_missing_gemini_key_raises_exception_not_sys_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY_1PASSWORD_REF", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY_1PASSWORD_REF", raising=False)

    with pytest.raises(MissingApiKeyError, match="Gemini API key not found"):
        _ = core.get_gemini_api_key()


def test_missing_openai_key_raises_exception_not_sys_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY_1PASSWORD_REF", raising=False)

    with pytest.raises(MissingApiKeyError, match="OpenAI API key not found"):
        _ = core.get_openai_api_key()


def test_cli_returns_nonzero_for_library_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def fail_generate(**_kwargs: object) -> NoReturn:
        raise MissingApiKeyError("missing fake key")

    patched_generate: Callable[..., NoReturn] = fail_generate
    monkeypatch.setattr("eink_diary.imagegen.cli.generate", patched_generate)

    exit_code = cli.main(["-p", "a cat"])

    assert exit_code == 1
    assert "missing fake key" in capsys.readouterr().err
