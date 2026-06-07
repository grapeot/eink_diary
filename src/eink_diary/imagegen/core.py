from __future__ import annotations

import argparse
import base64
import importlib
import mimetypes
import os
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol, TypedDict, Union, cast, overload

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is declared, kept for clearer import failures
    load_dotenv = None  # type: ignore[assignment]


MODEL_ALIASES = {
    "gemini-flash": "gemini-3.1-flash-image-preview",
    "gemini-3.1-flash-image-preview": "gemini-3.1-flash-image-preview",
    "gemini-pro": "gemini-3-pro-image-preview",
    "gemini-3-pro-image-preview": "gemini-3-pro-image-preview",
    "gpt-image-2": "gpt-image-2",
}

OPENAI_IMAGE_SIZE_MAP = {
    "1K": {
        "1:1": "1024x1024",
        "4:3": "1280x960",
        "16:9": "1536x864",
        "9:16": "864x1536",
        "3:4": "960x1280",
    },
    "2K": {
        "1:1": "2048x2048",
        "4:3": "2048x1536",
        "16:9": "2048x1152",
        "9:16": "1152x2048",
        "3:4": "1536x2048",
    },
    "4K": {
        "1:1": "3840x3840",
        "4:3": "3840x2880",
        "16:9": "3840x2160",
        "9:16": "2160x3840",
        "3:4": "2880x3840",
    },
}


class ImageGenerationError(RuntimeError):
    """Base exception for image generation failures."""


class ConfigurationError(ImageGenerationError):
    """Raised when local configuration is invalid."""


class MissingApiKeyError(ConfigurationError):
    """Raised when the selected provider has no usable API key."""


class DependencyError(ImageGenerationError):
    """Raised when an optional runtime dependency is unavailable."""


class InlineDataLike(Protocol):
    data: bytes
    mime_type: str | None


class GeminiPartLike(Protocol):
    text: str | None
    inline_data: InlineDataLike | None


class GeminiCandidateContentLike(Protocol):
    parts: Sequence[GeminiPartLike] | None


class GeminiCandidateLike(Protocol):
    content: GeminiCandidateContentLike | None


class GeminiChunkLike(Protocol):
    candidates: Sequence[GeminiCandidateLike] | None


class GeminiModelsLike(Protocol):
    def generate_content_stream(
        self,
        *,
        model: str,
        contents: GeminiContentDict,
        config: object,
    ) -> Iterable[GeminiChunkLike]: ...


class GeminiClientLike(Protocol):
    models: GeminiModelsLike


class GeminiClientFactory(Protocol):
    def __call__(self, *, api_key: str) -> GeminiClientLike: ...


class GeminiPartFactory(Protocol):
    def from_text(self, *, text: str) -> GeminiPartLike: ...

    def from_bytes(self, *, data: bytes, mime_type: str) -> GeminiPartLike: ...


class GeminiImageConfigFactory(Protocol):
    @overload
    def __call__(self, *, image_size: str) -> object: ...

    @overload
    def __call__(self, *, image_size: str, aspect_ratio: str) -> object: ...


class GeminiGenerateContentConfigFactory(Protocol):
    def __call__(self, *, response_modalities: list[str], image_config: object) -> object: ...


class GeminiModuleLike(Protocol):
    Client: GeminiClientFactory


class GeminiTypesLike(Protocol):
    Part: GeminiPartFactory
    ImageConfig: GeminiImageConfigFactory
    GenerateContentConfig: GeminiGenerateContentConfigFactory


class OpenAIImageItemLike(Protocol):
    b64_json: str | None


class OpenAIImageResultLike(Protocol):
    data: Sequence[OpenAIImageItemLike] | None


class OpenAIImagesLike(Protocol):
    def edit(
        self,
        *,
        model: str,
        image: BinaryIO,
        prompt: str,
        quality: str,
        output_format: str,
        extra_body: dict[str, str],
    ) -> OpenAIImageResultLike: ...

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        quality: str,
        output_format: str,
        extra_body: dict[str, str],
    ) -> OpenAIImageResultLike: ...


class OpenAIClientLike(Protocol):
    images: OpenAIImagesLike


class OpenAIClientFactory(Protocol):
    def __call__(self, *, api_key: str) -> OpenAIClientLike: ...


class TextPartDict(TypedDict):
    text: str


class InlineDataPayloadDict(TypedDict):
    data: bytes
    mime_type: str | None


class InlineDataPartDict(TypedDict):
    inline_data: InlineDataPayloadDict


GeminiPartDict = Union[TextPartDict, InlineDataPartDict]


class GeminiContentDict(TypedDict):
    role: str
    parts: list[GeminiPartDict]


@dataclass(frozen=True)
class CliArgs:
    prompt: str | None
    input: list[str] | None
    output: str
    size: str
    aspect_ratio: str | None
    model: str | None
    upscale: bool
    quality: str


def load_env_file_if_present() -> None:
    """Load `.env` from the current project context without assuming a workspace root."""
    if load_dotenv is not None:
        _ = load_dotenv()


def _read_1password_reference(reference_env_var: str) -> str | None:
    reference = os.environ.get(reference_env_var)
    if not reference:
        return None
    try:
        result = subprocess.run(
            ["op", "read", reference],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _get_gemini_api_key() -> str:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        return api_key

    api_key = _read_1password_reference("GEMINI_API_KEY_1PASSWORD_REF") or _read_1password_reference(
        "GOOGLE_API_KEY_1PASSWORD_REF"
    )
    if api_key:
        return api_key

    raise MissingApiKeyError(
        "Gemini API key not found. Set GEMINI_API_KEY or GOOGLE_API_KEY, "
        + "or set GEMINI_API_KEY_1PASSWORD_REF to a generic op:// reference."
    )


def _get_openai_api_key() -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return api_key

    api_key = _read_1password_reference("OPENAI_API_KEY_1PASSWORD_REF")
    if api_key:
        return api_key

    raise MissingApiKeyError(
        "OpenAI API key not found. Set OPENAI_API_KEY or set "
        + "OPENAI_API_KEY_1PASSWORD_REF to a generic op:// reference."
    )


def _get_default_model_choice() -> str:
    configured = os.environ.get("IMAGE_GENERATION_MODEL", "gemini-flash")
    return _normalize_model_choice(configured)


def _normalize_model_choice(choice: str) -> str:
    normalized = MODEL_ALIASES.get(choice)
    if normalized is None:
        supported = ", ".join(sorted(MODEL_ALIASES))
        raise ValueError(f"Unsupported model '{choice}'. Supported values: {supported}")
    return normalized


def _resolve_generate_model(requested_model: str | None) -> tuple[str, str]:
    effective_choice = requested_model or _get_default_model_choice()
    normalized = _normalize_model_choice(effective_choice)

    if normalized == "gemini-3.1-flash-image-preview":
        return (
            "gemini",
            os.environ.get(
                "GEMINI_FLASH_IMAGE_MODEL",
                os.environ.get("GEMINI_IMAGE_GENERATION_MODEL", normalized),
            ),
        )
    if normalized == "gemini-3-pro-image-preview":
        return ("gemini", os.environ.get("GEMINI_PRO_IMAGE_MODEL", normalized))
    return ("openai", os.environ.get("OPENAI_IMAGE_MODEL", normalized))


def _resolve_upscale_model(requested_model: str | None) -> tuple[str, str]:
    effective_choice = requested_model or os.environ.get("IMAGE_UPSCALE_MODEL", "gemini-pro")
    normalized = _normalize_model_choice(effective_choice)
    if normalized == "gpt-image-2":
        raise ValueError("--upscale is not supported with gpt-image-2")
    if normalized == "gemini-3.1-flash-image-preview":
        return (
            "gemini",
            os.environ.get(
                "GEMINI_FLASH_IMAGE_MODEL",
                os.environ.get("GEMINI_IMAGE_GENERATION_MODEL", normalized),
            ),
        )
    return (
        "gemini",
        os.environ.get(
            "GEMINI_IMAGE_UPSCALE_MODEL",
            os.environ.get("GEMINI_PRO_IMAGE_MODEL", normalized),
        ),
    )


def _map_size_for_openai(image_size: str, aspect_ratio: str | None) -> str:
    aspect = aspect_ratio or "1:1"
    try:
        return OPENAI_IMAGE_SIZE_MAP[image_size][aspect]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported OpenAI size mapping for image_size={image_size}, aspect_ratio={aspect}"
        ) from exc


def _save_binary(path: str, data: bytes) -> None:
    _ = Path(path).write_bytes(data)
    print(f"Saved: {path}")


def _convert_to_jpeg(source: str, target: str) -> bool:
    try:
        result = subprocess.run(
            ["sips", "-s", "format", "jpeg", source, "--out", target],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise DependencyError("JPEG conversion requires the macOS `sips` command.") from exc
    if result.returncode != 0:
        raise ImageGenerationError(f"JPEG conversion failed: {result.stderr.strip()}")
    return True


def _save_image_part(inline_data: InlineDataLike | None, output_path: str) -> bool:
    if inline_data is None or not inline_data.data:
        return False

    image_bytes = inline_data.data
    ext = mimetypes.guess_extension(inline_data.mime_type or "image/png") or ".png"
    output_suffix = Path(output_path).suffix.lower()

    if ext in {".jpg", ".jpeg"} or output_suffix == ".png":
        _save_binary(output_path, image_bytes)
        return True

    temp_path = f"{output_path}{ext}"
    _save_binary(temp_path, image_bytes)
    success = _convert_to_jpeg(temp_path, output_path)
    if success:
        Path(temp_path).unlink(missing_ok=True)
    return success


def _save_openai_b64_image(image_base64: str, output_path: str) -> bool:
    image_bytes = base64.b64decode(image_base64)
    output_suffix = Path(output_path).suffix.lower()
    if output_suffix == ".png":
        _save_binary(output_path, image_bytes)
        return True

    temp_path = f"{output_path}.png"
    _ = Path(temp_path).write_bytes(image_bytes)
    success = _convert_to_jpeg(temp_path, output_path)
    if success:
        Path(temp_path).unlink(missing_ok=True)
        print(f"Saved: {output_path}")
    return success


def _build_output_path(output_spec: str, index: int) -> str:
    path = Path(output_spec)
    if path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
        if index == 0:
            return str(path)
        return str(path.with_name(f"{path.stem}_{index}{path.suffix}"))
    return f"{output_spec}_{index}.jpg"


def _require_existing_files(image_paths: list[str]) -> None:
    for image_path in image_paths:
        if not Path(image_path).expanduser().exists():
            raise FileNotFoundError(f"file not found: {image_path}")


def _import_gemini_sdk() -> tuple[GeminiModuleLike, GeminiTypesLike]:
    try:
        genai_module = importlib.import_module("google.genai")
        types_module = importlib.import_module("google.genai.types")
    except ImportError as exc:
        raise DependencyError("Gemini support requires `google-genai`. Install the package extras first.") from exc
    return cast(GeminiModuleLike, cast(object, genai_module)), cast(GeminiTypesLike, cast(object, types_module))


def _import_openai_sdk() -> OpenAIClientFactory:
    try:
        openai_module = importlib.import_module("openai")
    except ImportError as exc:
        raise DependencyError("OpenAI support requires `openai`. Install the package extras first.") from exc
    return cast(OpenAIClientFactory, openai_module.__dict__["OpenAI"])


def _part_to_dict(part: GeminiPartLike) -> GeminiPartDict:
    if part.text is not None:
        return {"text": part.text}
    if part.inline_data is not None:
        return {
            "inline_data": {
                "data": part.inline_data.data,
                "mime_type": part.inline_data.mime_type,
            }
        }
    raise ValueError("Unsupported Gemini part shape for this CLI")


def _generate_gemini(
    model: str,
    prompt: str,
    image_paths: list[str] | None = None,
    output_prefix: str = "output",
    image_size: str = "1K",
    aspect_ratio: str | None = None,
) -> str | None:
    genai, types = _import_gemini_sdk()
    client = genai.Client(api_key=_get_gemini_api_key())
    print(f"Model: {model} | Size: {image_size}")

    parts = [types.Part.from_text(text=prompt)]
    if image_paths:
        _require_existing_files(image_paths)
        for image_path in image_paths:
            expanded_path = Path(image_path).expanduser()
            data = expanded_path.read_bytes()
            mime, _encoding = mimetypes.guess_type(str(expanded_path))
            parts.append(types.Part.from_bytes(data=data, mime_type=mime or "image/png"))

    if aspect_ratio:
        image_config = types.ImageConfig(image_size=image_size, aspect_ratio=aspect_ratio)
    else:
        image_config = types.ImageConfig(image_size=image_size)

    config = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"], image_config=image_config)
    contents: GeminiContentDict = {"role": "user", "parts": [_part_to_dict(part) for part in parts]}

    first_saved: str | None = None
    file_index = 0
    for chunk in client.models.generate_content_stream(model=model, contents=contents, config=config):
        candidates = chunk.candidates or ()
        candidate = candidates[0] if candidates else None
        content = candidate.content if candidate else None
        parts_out: Sequence[GeminiPartLike] = content.parts if content and content.parts else ()

        for part in parts_out:
            if part.text:
                print(part.text, end="", flush=True)
                continue

            out_path = _build_output_path(output_prefix, file_index)
            if _save_image_part(part.inline_data, out_path):
                if first_saved is None:
                    first_saved = out_path
                file_index += 1

    return first_saved


def _generate_openai(
    model: str,
    prompt: str,
    image_paths: list[str] | None = None,
    output_prefix: str = "output",
    image_size: str = "1K",
    aspect_ratio: str | None = None,
    quality: str = "high",
) -> str | None:
    openai_client = _import_openai_sdk()
    client = openai_client(api_key=_get_openai_api_key())
    size = _map_size_for_openai(image_size, aspect_ratio)
    print(f"Model: {model} | Size: {size} | Quality: {quality}")

    if image_paths:
        _require_existing_files(image_paths)
        if len(image_paths) != 1:
            raise ValueError("gpt-image-2 currently supports at most one --input image in this CLI.")
        with Path(image_paths[0]).expanduser().open("rb") as image_file:
            result = client.images.edit(
                model=model,
                image=image_file,
                prompt=prompt,
                quality=quality,
                output_format="png",
                extra_body={"size": size},
            )
    else:
        result = client.images.generate(
            model=model,
            prompt=prompt,
            quality=quality,
            output_format="png",
            extra_body={"size": size},
        )

    first_saved: str | None = None
    items: Sequence[OpenAIImageItemLike] = result.data if result.data is not None else ()
    for index, item in enumerate(items):
        if not item.b64_json:
            continue
        out_path = _build_output_path(output_prefix, index)
        if _save_openai_b64_image(item.b64_json, out_path) and first_saved is None:
            first_saved = out_path

    return first_saved


def generate(
    prompt: str,
    image_paths: list[str] | None = None,
    output_prefix: str = "output",
    image_size: str = "1K",
    aspect_ratio: str | None = None,
    model: str | None = None,
    quality: str = "high",
) -> str | None:
    load_env_file_if_present()
    provider, model_id = _resolve_generate_model(model)
    if provider == "gemini":
        if quality != "high":
            print(
                f"Note: --quality {quality} is ignored for Gemini models "
                + "because only gpt-image-2 supports quality tiers."
            )
        return _generate_gemini(
            model=model_id,
            prompt=prompt,
            image_paths=image_paths,
            output_prefix=output_prefix,
            image_size=image_size,
            aspect_ratio=aspect_ratio,
        )
    return _generate_openai(
        model=model_id,
        prompt=prompt,
        image_paths=image_paths,
        output_prefix=output_prefix,
        image_size=image_size,
        aspect_ratio=aspect_ratio,
        quality=quality,
    )


def upscale(
    image_path: str,
    output_path: str,
    aspect_ratio: str = "16:9",
    model: str | None = None,
) -> str | None:
    load_env_file_if_present()
    _require_existing_files([image_path])
    provider, model_id = _resolve_upscale_model(model)
    if provider != "gemini":
        raise ValueError("upscale currently requires a Gemini image model")

    genai, types = _import_gemini_sdk()
    client = genai.Client(api_key=_get_gemini_api_key())
    print(f"Upscale model: {model_id} | {image_path} -> {output_path}")

    expanded_path = Path(image_path).expanduser()
    image_bytes = expanded_path.read_bytes()
    mime, _encoding = mimetypes.guess_type(str(expanded_path))
    prompt = (
        "Upscale this image to 4K resolution. Maintain all details, text, "
        "and structure exactly. Do not add or remove elements. "
        "Only increase the resolution and sharpness."
    )
    contents: GeminiContentDict = {
        "role": "user",
        "parts": [
            _part_to_dict(types.Part.from_text(text=prompt)),
            _part_to_dict(types.Part.from_bytes(data=image_bytes, mime_type=mime or "image/jpeg")),
        ],
    }
    config = types.GenerateContentConfig(
        response_modalities=["IMAGE", "TEXT"],
        image_config=types.ImageConfig(aspect_ratio=aspect_ratio, image_size="4K"),
    )

    for chunk in client.models.generate_content_stream(model=model_id, contents=contents, config=config):
        candidates = chunk.candidates or ()
        candidate = candidates[0] if candidates else None
        content = candidate.content if candidate else None
        parts_out: Sequence[GeminiPartLike] = content.parts if content and content.parts else ()

        for part in parts_out:
            if _save_image_part(part.inline_data, output_path):
                return output_path

    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate or upscale images using Gemini or OpenAI image models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  generate-image -p "A serene mountain lake" -o lake.jpg
  generate-image -p "A cinematic mountain lake" -o lake.jpg -m gemini-pro
  generate-image -p "A product photo on a white background" -o product.png -m gpt-image-2
  generate-image -p "Remove the background" -i photo.jpg -o clean.png
  generate-image -p "Wide banner" -o banner.jpg --size 4K --aspect-ratio 16:9
  generate-image --upscale -i small.jpg -o big.jpg
""",
    )
    _ = parser.add_argument("--prompt", "-p", help="Text prompt, required for generate mode")
    _ = parser.add_argument(
        "--input",
        "-i",
        action="append",
        help="Input image path, repeatable for Gemini image editing",
    )
    _ = parser.add_argument("--output", "-o", default="output", help="Output file path or prefix")
    _ = parser.add_argument("--size", "-s", default="1K", choices=["1K", "2K", "4K"], help="Image size")
    _ = parser.add_argument(
        "--aspect-ratio",
        "-a",
        choices=["1:1", "4:3", "16:9", "9:16", "3:4"],
        help="Aspect ratio, defaults to provider behavior for generation and 16:9 for upscale",
    )
    _ = parser.add_argument(
        "--model",
        "-m",
        help=(
            "Model alias or exact id: gemini-flash, gemini-pro, gpt-image-2, "
            "gemini-3.1-flash-image-preview, gemini-3-pro-image-preview"
        ),
    )
    _ = parser.add_argument("--upscale", action="store_true", help="Upscale one input image to 4K with Gemini")
    _ = parser.add_argument(
        "--quality",
        "-q",
        default="high",
        choices=["low", "medium", "high"],
        help="Quality tier for gpt-image-2; ignored for Gemini models",
    )
    return parser


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _required_str(value: object, default: str) -> str:
    return value if isinstance(value, str) else default


def _optional_str_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = cast(list[object], value)
    return [item for item in items if isinstance(item, str)]


def _bool_value(value: object) -> bool:
    return bool(value) if isinstance(value, bool) else False


def coerce_cli_args(args: argparse.Namespace) -> CliArgs:
    raw_args: dict[str, object] = args.__dict__
    return CliArgs(
        prompt=_optional_str(raw_args.get("prompt")),
        input=_optional_str_list(raw_args.get("input")),
        output=_required_str(raw_args.get("output"), "output"),
        size=_required_str(raw_args.get("size"), "1K"),
        aspect_ratio=_optional_str(raw_args.get("aspect_ratio")),
        model=_optional_str(raw_args.get("model")),
        upscale=_bool_value(raw_args.get("upscale")),
        quality=_required_str(raw_args.get("quality"), "high"),
    )


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> CliArgs:
    parsed = coerce_cli_args(args)
    if parsed.model is not None:
        try:
            _ = _normalize_model_choice(parsed.model)
        except ValueError as exc:
            parser.error(str(exc))
    if parsed.upscale and parsed.prompt:
        parser.error("--prompt cannot be used with --upscale")
    if parsed.upscale and (not parsed.input or len(parsed.input) != 1):
        parser.error("--upscale requires exactly one --input image")
    if not parsed.upscale and not parsed.prompt:
        parser.error("--prompt is required in generate mode")
    if parsed.upscale:
        try:
            _ = _resolve_upscale_model(parsed.model)
        except ValueError as exc:
            parser.error(str(exc))
    return parsed


resolve_generate_model = _resolve_generate_model
resolve_upscale_model = _resolve_upscale_model
map_size_for_openai = _map_size_for_openai
build_output_path = _build_output_path
get_gemini_api_key = _get_gemini_api_key
get_openai_api_key = _get_openai_api_key
_validate_args = validate_args
