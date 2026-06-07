from __future__ import annotations

import sys

from .core import ImageGenerationError, build_parser, generate, upscale, validate_args


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    namespace = parser.parse_args(argv)
    args = validate_args(parser, namespace)

    try:
        if args.upscale:
            if args.input is None:
                parser.error("--upscale requires exactly one --input image")
            _ = upscale(
                image_path=args.input[0],
                output_path=args.output,
                aspect_ratio=args.aspect_ratio or "16:9",
                model=args.model,
            )
        else:
            if args.prompt is None:
                parser.error("--prompt is required in generate mode")
            _ = generate(
                prompt=args.prompt,
                image_paths=args.input,
                output_prefix=args.output,
                image_size=args.size,
                aspect_ratio=args.aspect_ratio,
                model=args.model,
                quality=args.quality,
            )
    except (FileNotFoundError, ImageGenerationError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
