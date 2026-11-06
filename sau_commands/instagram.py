"""Arguments and execution for the instagram command."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from uploader.meta_uploader.insgraph_uploader.main import (
    INSTAGRAM_PROXY,
    InstagramUploader,
    instagram_cookie_auth,
    instagram_setup,
)
from uploader.meta_uploader.insgraph_uploader.posts import instagram_post_action
from sau_commands.arguments import (
    SCHEDULE_FORMAT,
    account_argument,
    add_runtime_flags,
    existing_file_path,
    parse_image_files,
    parse_tags,
    resolve_account_file,
)


def register(platform_parsers):
    """Declare this platform's commands, arguments and accepted options."""
    schedule_help = SCHEDULE_FORMAT.replace("%", "%%")
    instagram_parser = platform_parsers.add_parser("instagram", help="Instagram independent web operations")
    instagram_actions = instagram_parser.add_subparsers(dest="action", required=True)
    for action_name in ("login", "check"):
        action_parser = instagram_actions.add_parser(action_name, help=f"Instagram {action_name}")
        account_argument(action_parser)
        action_parser.add_argument("--proxy", default=INSTAGRAM_PROXY, help="Proxy address; direct connection when omitted")
        add_runtime_flags(action_parser)
        if action_name == "login":
            action_parser.set_defaults(headless=False)
    instagram_video = instagram_actions.add_parser("upload-video", help="Publish a video/Reel to Instagram")
    account_argument(instagram_video)
    instagram_video.add_argument("--file", required=True, type=existing_file_path)
    instagram_video.add_argument("--thumbnail", type=existing_file_path, help="Custom Reel cover (JPG/JPEG/PNG)")
    instagram_video.add_argument("--title", required=True)
    instagram_video.add_argument("--desc", default="")
    instagram_video.add_argument("--tags", default="")
    instagram_video.add_argument("--proxy", default=INSTAGRAM_PROXY, help="Proxy address; direct connection when omitted")
    instagram_video.add_argument("--result", type=Path)
    add_runtime_flags(instagram_video)
    instagram_video.set_defaults(headless=False)
    instagram_note = instagram_actions.add_parser("upload-note", help="Publish images or a carousel to Instagram")
    account_argument(instagram_note)
    instagram_note.add_argument("--images", required=True, nargs="+", type=existing_file_path)
    instagram_note.add_argument("--title", required=True)
    instagram_note.add_argument("--note", default="")
    instagram_note.add_argument("--tags", default="")
    instagram_note.add_argument("--proxy", default=INSTAGRAM_PROXY, help="Proxy address; direct connection when omitted")
    instagram_note.add_argument("--result", type=Path)
    add_runtime_flags(instagram_note)
    instagram_note.set_defaults(headless=False)
    for action_name in ("verify", "delete"):
        action_parser = instagram_actions.add_parser(action_name, help="Verify the Instagram original post" if action_name == "verify" else "Verify the Instagram post, then move it to Recently deleted")
        account_argument(action_parser)
        action_parser.add_argument("--post-url", required=True)
        action_parser.add_argument("--expected-text", required=True)
        action_parser.add_argument("--proxy", default=INSTAGRAM_PROXY, help="Proxy address; direct connection when omitted")
        action_parser.add_argument("--result", type=Path)
        add_runtime_flags(action_parser)
        action_parser.set_defaults(headless=False)


@dataclass(slots=True)
class InstagramUploadRequest:
    account_name: str
    title: str
    description: str
    tags: list[str]
    video_file: Path | None = None
    image_files: list[Path] | None = None
    thumbnail: Path | None = None
    proxy: str | None = INSTAGRAM_PROXY
    headless: bool = False
    result_file: Path | None = None


async def login_instagram_account(account_name: str, *, headless: bool = False, proxy: str | None = INSTAGRAM_PROXY) -> dict:
    account_file = resolve_account_file("instagram", account_name)
    return await instagram_setup(account_file, handle=True, return_detail=True, headless=headless, proxy=proxy)


async def check_instagram_account(account_name: str, *, proxy: str | None = INSTAGRAM_PROXY) -> bool:
    account_file = resolve_account_file("instagram", account_name)
    return await instagram_cookie_auth(account_file, proxy=proxy)


async def upload_instagram_content(request: InstagramUploadRequest) -> dict:
    account_file = resolve_account_file("instagram", request.account_name)
    app = InstagramUploader(
        account_file,
        title=request.title,
        description=request.description,
        tags=request.tags,
        video_file=request.video_file,
        image_files=request.image_files,
        thumbnail=request.thumbnail,
        proxy=request.proxy,
        headless=request.headless,
        result_file=request.result_file,
    )
    return await app.upload()


async def run(args):
    """Run this platform's command; the platform implementation verifies publishing."""
    if args.action == "login":
        result = await login_instagram_account(args.account, headless=args.headless, proxy=args.proxy)
        if not result["success"]:
            raise RuntimeError(result.get("message", "Instagram login failed"))
        print(f"Instagram login flow completed: {result['account_file']}")
        return 0
    if args.action == "check":
        is_valid = await check_instagram_account(args.account, proxy=args.proxy)
        print("valid" if is_valid else "invalid")
        return 0 if is_valid else 1
    if args.action in {"upload-video", "upload-note"}:
        request = InstagramUploadRequest(
            account_name=args.account,
            title=args.title,
            description=args.desc if args.action == "upload-video" else args.note,
            tags=parse_tags(args.tags),
            video_file=args.file if args.action == "upload-video" else None,
            image_files=parse_image_files(args.images) if args.action == "upload-note" else None,
            thumbnail=args.thumbnail if args.action == "upload-video" else None,
            proxy=args.proxy,
            headless=args.headless,
            result_file=args.result,
        )
        result = await upload_instagram_content(request)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.action in {"verify", "delete"}:
        result = await instagram_post_action(
            resolve_account_file("instagram", args.account),
            post_url=args.post_url,
            expected_text=args.expected_text,
            delete=args.action == "delete",
            proxy=args.proxy,
            headless=args.headless,
            result_file=args.result,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    raise RuntimeError(f"Unsupported Instagram action: {args.action}")
