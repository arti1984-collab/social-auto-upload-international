"""Arguments and execution for the facebook-page command."""
from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uploader.meta_uploader.facebook_page_uploader.main import (
    FACEBOOK_PAGE_PROXY,
    MetaBusinessUploader,
    meta_cookie_auth,
    meta_setup,
)
from uploader.meta_uploader.facebook_page_uploader.posts import meta_post_action
from sau_commands.caption import add_caption_flags, apply_caption
from sau_commands.arguments import (
    SCHEDULE_FORMAT,
    account_argument,
    add_runtime_flags,
    existing_file_path,
    parse_image_files,
    parse_tags,
    resolve_account_file,
    schedule_value,
)


def register(platform_parsers):
    """Declare this platform's commands, arguments and accepted options."""
    schedule_help = SCHEDULE_FORMAT.replace("%", "%%")
    for meta_platform, meta_help in (
        ("facebook-page", "Facebook Page Business Suite operations"),
    ):
        meta_parser = platform_parsers.add_parser(meta_platform, help=meta_help)
        meta_actions = meta_parser.add_subparsers(dest="action", required=True)
        if meta_platform == "facebook-page":
            for action in ("verify", "delete"):
                post_parser = meta_actions.add_parser(action, help="Verify the original post by id" if action == "verify" else "Verify by id, then delete: scheduled posts are removed permanently, published posts go to the trash")
                account_argument(post_parser)
                post_parser.add_argument("--page-id", required=True)
                post_parser.add_argument("--page", required=True)
                post_parser.add_argument("--content-id", required=True)
                post_parser.add_argument("--expected-text", required=True)
                post_parser.add_argument("--scheduled", action="store_true", help="Look up or cancel the post in the scheduled list")
                post_parser.add_argument("--result", type=Path)
                post_parser.add_argument("--proxy", default=FACEBOOK_PAGE_PROXY, help="Proxy address; direct connection when omitted")
                add_runtime_flags(post_parser)
                post_parser.set_defaults(headless=False)
        for action_name in ("login", "check"):
            action_parser = meta_actions.add_parser(action_name, help=f"{meta_platform} {action_name}")
            account_argument(action_parser, "Meta account name")
            action_parser.add_argument("--proxy", default=FACEBOOK_PAGE_PROXY, help="Proxy address; direct connection when omitted")
            add_runtime_flags(action_parser)
            if action_name == "login":
                action_parser.set_defaults(headless=False)

        upload_video_parser = meta_actions.add_parser("upload-video", help=f"Upload a video to {meta_platform}")
        account_argument(upload_video_parser)
        upload_video_parser.add_argument("--file", required=True, type=existing_file_path)
        upload_video_parser.add_argument("--title", required=True)
        upload_video_parser.add_argument("--desc", default="")
        upload_video_parser.add_argument("--tags", default="")
        add_caption_flags(upload_video_parser)
        upload_video_parser.add_argument("--page", default=None, help="Business Suite publisher name; the current one is used when omitted")
        upload_video_parser.add_argument("--schedule", type=schedule_value, help=f"Scheduled publish time, format {schedule_help}")
        upload_video_parser.add_argument("--proxy", default=FACEBOOK_PAGE_PROXY, help="Proxy address; direct connection when omitted")
        upload_video_parser.add_argument("--result", type=Path, help="Write the content id and publish result JSON")
        add_runtime_flags(upload_video_parser)
        upload_video_parser.set_defaults(headless=False)

        upload_note_parser = meta_actions.add_parser("upload-note", help=f"Upload images to {meta_platform}")
        account_argument(upload_note_parser)
        upload_note_parser.add_argument("--images", required=True, nargs="+", type=existing_file_path)
        upload_note_parser.add_argument("--title", required=True)
        upload_note_parser.add_argument("--note", default="")
        upload_note_parser.add_argument("--tags", default="")
        add_caption_flags(upload_note_parser)
        upload_note_parser.add_argument("--page", default=None, help="Business Suite publisher name; the current one is used when omitted")
        upload_note_parser.add_argument("--schedule", type=schedule_value, help=f"Scheduled publish time, format {schedule_help}")
        upload_note_parser.add_argument("--proxy", default=FACEBOOK_PAGE_PROXY, help="Proxy address; direct connection when omitted")
        upload_note_parser.add_argument("--result", type=Path, help="Write the content id and publish result JSON")
        add_runtime_flags(upload_note_parser)
        upload_note_parser.set_defaults(headless=False)


@dataclass(slots=True)
class MetaUploadRequest:
    platform: str
    account_name: str
    title: str
    description: str
    tags: list[str]
    video_file: Path | None = None
    image_files: list[Path] | None = None
    schedule: datetime | int = 0
    page_name: str | None = None
    proxy: str | None = FACEBOOK_PAGE_PROXY
    debug: bool = True
    headless: bool = False
    result_file: Path | None = None


async def login_meta_account(platform: str, account_name: str, *, headless: bool = False, proxy: str | None = FACEBOOK_PAGE_PROXY) -> dict:
    account_file = resolve_account_file(platform, account_name)
    return await meta_setup(
        account_file,
        handle=True,
        return_detail=True,
        headless=headless,
        proxy=proxy,
    )


async def check_meta_account(platform: str, account_name: str, *, proxy: str | None = FACEBOOK_PAGE_PROXY) -> bool:
    account_file = resolve_account_file(platform, account_name)
    return await meta_cookie_auth(account_file, proxy=proxy)


async def upload_meta_content(request: MetaUploadRequest) -> dict:
    account_file = resolve_account_file(request.platform, request.account_name)
    if not await meta_cookie_auth(account_file, proxy=request.proxy):
        raise RuntimeError(
            f"{request.platform} Business Suite session is missing or expired: {account_file}. "
            f"Run `sau {request.platform} login --account {request.account_name}` first."
        )
    app = MetaBusinessUploader(
        request.platform,
        account_file,
        title=request.title,
        description=request.description,
        tags=request.tags,
        video_file=request.video_file,
        image_files=request.image_files,
        schedule=request.schedule,
        page_name=request.page_name,
        proxy=request.proxy,
        headless=request.headless,
        result_file=request.result_file,
    )
    return await app.upload()


async def run(args):
    """Run this platform's command; the platform implementation verifies publishing."""
    if args.platform == "facebook-page" and args.action in {"verify", "delete"}:
        result = await meta_post_action(
            resolve_account_file(args.platform, args.account), page_id=args.page_id, page_name=args.page,
            content_id=args.content_id, expected_text=args.expected_text, scheduled=args.scheduled,
            delete=args.action == "delete", proxy=args.proxy, headless=args.headless,
        )
        if args.result:
            args.result.parent.mkdir(parents=True, exist_ok=True)
            args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.action == "login":
        result = await login_meta_account(args.platform, args.account, headless=args.headless, proxy=args.proxy)
        if not result["success"]:
            raise RuntimeError(result.get("message", f"{args.platform} login failed"))
        print(f"{args.platform} login flow completed: {result['account_file']}")
        return 0

    if args.action == "check":
        is_valid = await check_meta_account(args.platform, args.account, proxy=args.proxy)
        print("valid" if is_valid else "invalid")
        return 0 if is_valid else 1

    if args.action in {"upload-video", "upload-note"}:
        description, tags = apply_caption(
            "facebook-page", args.title, args.desc if args.action == "upload-video" else args.note,
            parse_tags(args.tags), auto_desc=args.auto_desc, auto_tags=args.auto_tags,
            lang=args.caption_lang,
        )
        request = MetaUploadRequest(
            platform=args.platform,
            account_name=args.account,
            title=args.title,
            description=description,
            tags=tags,
            video_file=args.file if args.action == "upload-video" else None,
            image_files=parse_image_files(args.images) if args.action == "upload-note" else None,
            schedule=args.schedule or 0,
            page_name=args.page,
            result_file=args.result,
            proxy=args.proxy,
            debug=args.debug,
            headless=args.headless,
        )
        result = await upload_meta_content(request)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    raise RuntimeError(f"Unsupported {args.platform} action: {args.action}")
