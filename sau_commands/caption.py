"""Arguments and execution for the caption command.

The command builds a description and hashtags from a title and your notes
without any AI service; the upload commands reuse the same builder through
``--auto-desc`` and ``--auto-tags``.
"""
from __future__ import annotations

import json
from pathlib import Path

from utils.caption import PLATFORM_LIMITS, apply_caption, build


def add_caption_flags(parser) -> None:
    """Let an upload command fill description and tags on its own."""
    parser.add_argument(
        "--auto-desc",
        dest="auto_desc",
        action="store_true",
        help="Fill an empty description from title and notes; your own --desc/--note always wins",
    )
    parser.add_argument(
        "--auto-tags",
        dest="auto_tags",
        action="store_true",
        help="Add suggested hashtags to --tags, without duplicates",
    )
    parser.add_argument(
        "--lang",
        dest="caption_lang",
        choices=["de", "en"],
        default="de",
        help="Language of the generated description and hashtags (default: de)",
    )


def register(platform_parsers) -> None:
    """Declare the caption command, its options and the platform filter."""
    parser = platform_parsers.add_parser(
        "caption", help="Build a description and hashtags from a title, without any AI service"
    )
    parser.add_argument("--title", required=True, help="Working title of the post")
    parser.add_argument("--notes", default="", help="Your own text; it becomes the first paragraph")
    parser.add_argument(
        "--for",
        dest="target",
        choices=["all", *PLATFORM_LIMITS],
        default="all",
        help="Platform whose limits and wording apply (default: all)",
    )
    parser.add_argument(
        "--lang",
        dest="caption_lang",
        choices=["de", "en", "both"],
        default="both",
        help="Language of the generated text (default: both)",
    )
    parser.add_argument("--json", type=Path, help="Write the result JSON to this file")


async def run(args) -> int:
    """Print one block per language and platform; the same input always gives the same text."""
    targets = list(PLATFORM_LIMITS) if args.target == "all" else [args.target]
    languages = ["de", "en"] if args.caption_lang == "both" else [args.caption_lang]
    results = {
        language: {
            platform: build(platform, args.title, args.notes, language) for platform in targets
        }
        for language in languages
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for language, per_platform in results.items():
        print(f"[{language}]")
        for platform, result in per_platform.items():
            print(f"  {platform}:")
            print(f"    description: {result['description']}")
            print(f"    tags: {', '.join(result['tags']) or '-'}")
            print(f"    caption ({len(result['caption'])} chars):")
            for line in result["caption"].splitlines():
                print(f"      {line}")
        print()
    return 0
