"""Arguments and execution for the article command."""
from __future__ import annotations
import json
from pathlib import Path
from utils.article_render import ARTICLE_THEMES, render_article_file, setup_article_renderer
from sau_commands.arguments import SCHEDULE_FORMAT, existing_file_path


def register(platform_parsers):
    """Declare this platform's commands, arguments and accepted options."""
    schedule_help = SCHEDULE_FORMAT.replace("%", "%%")
    article_parser = platform_parsers.add_parser("article", help="Local article conversion and theme preview; no login, no publishing")
    article_actions = article_parser.add_subparsers(dest="action", required=True)
    article_actions.add_parser("themes", help="List the built-in themes")
    article_actions.add_parser("setup", help="Install the pinned Markdown renderer dependencies (requires Node.js 22+)")
    article_render = article_actions.add_parser("render", help="Convert a content file into previewable HTML")
    article_render.add_argument("--content-file", required=True, type=existing_file_path, help="UTF-8 Markdown, HTML or TXT file")
    article_render.add_argument("--theme", choices=ARTICLE_THEMES, help="Markdown theme (default: default); HTML/TXT does not use themes")
    article_render.add_argument("--output", required=True, type=Path, help="Output .html file path")
    article_render.add_argument("--overwrite", action="store_true", help="Overwrite an existing output file; the source file is never overwritten")


async def run(args):
    """Run this platform's command; the platform implementation verifies publishing."""
    if args.action == "setup":
        setup_article_renderer()
        print("Article renderer dependencies are installed")
    elif args.action == "themes":
        for name, description in ARTICLE_THEMES.items():
            print(f"{name}\t{description}")
    else:
        print(json.dumps(render_article_file(args.content_file, args.output, args.theme, args.overwrite), ensure_ascii=False))
    return 0
