"""Arguments and execution for the facebook command."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from uploader.base_video import BaseVideoUploader
from uploader.meta_uploader.facebook_uploader.main import (
    FACEBOOK_PROXY,
    FacebookVideo,
    FacebookPost,
    facebook_cookie_auth,
    facebook_setup,
)
from uploader.meta_uploader.facebook_uploader.posts import facebook_post_action
from utils.browser import session_available
from sau_commands.caption import add_caption_flags, apply_caption
from sau_commands.arguments import (
    SCHEDULE_FORMAT,
    account_argument,
    add_runtime_flags,
    existing_file_path,
    parse_tags,
    resolve_account_file,
)


def register(platform_parsers):
    """Declare this platform's commands, arguments and accepted options."""
    schedule_help = SCHEDULE_FORMAT.replace("%", "%%")
    facebook_parser = platform_parsers.add_parser("facebook", help="Facebook personal post operations")
    facebook_actions = facebook_parser.add_subparsers(dest="action", required=True)

    for action in ("verify", "delete"):
        post_parser = facebook_actions.add_parser(action, help="Verify the original post" if action == "verify" else "Verify the original post and move it to the trash (platform deletes it after 30 days)")
        account_argument(post_parser)
        post_parser.add_argument("--post-url", required=True, help="Facebook link of the original post")
        post_parser.add_argument("--owner-id", required=True, help="Numeric ID of the profile that owns the post")
        post_parser.add_argument("--expected-text", required=True, help="Caption of the original post used for cross-checking")
        post_parser.add_argument("--result", type=Path, help="Write the verify or delete result JSON")
        post_parser.add_argument("--from-trash", action="store_true", help="The post is already in the trash; verify it from there")
        if action == "delete":
            post_parser.add_argument("--permanent", action="store_true", help="Permanently delete the verified post from the trash (cannot be undone)")
        else:
            post_parser.add_argument("--deleted", action="store_true", help="Only check the trash for the original ID id; deletes nothing")
        post_parser.add_argument("--proxy", default=FACEBOOK_PROXY, help="Proxy address; direct connection when omitted")
        add_runtime_flags(post_parser)
        post_parser.set_defaults(headless=False)

    for action_name in ("login", "check"):
        action_parser = facebook_actions.add_parser(action_name, help=f"Facebook {action_name}")
        account_argument(action_parser, "Facebook user-defined account_name")
        action_parser.add_argument(
            "--proxy",
            default=FACEBOOK_PROXY,
            help="Browser proxy address; direct connection when omitted; an empty string overrides the environment variable and forces a direct connection",
        )
        add_runtime_flags(action_parser)
        if action_name == "login":
            # Facebook login must happen in a visible Chrome window, otherwise headless users never see the login challenge.
            action_parser.set_defaults(headless=False)

    facebook_upload_video_parser = facebook_actions.add_parser(
        "upload-video", help="Upload one video to a Facebook personal post"
    )
    account_argument(facebook_upload_video_parser, "Facebook user-defined account_name")
    facebook_upload_video_parser.add_argument("--file", required=True, type=existing_file_path, help="Video file path")
    facebook_upload_video_parser.add_argument("--title", required=True, help="Post title, merged into Facebook caption")
    facebook_upload_video_parser.add_argument("--desc", default="", help="Optional post description")
    facebook_upload_video_parser.add_argument("--tags", default="", help="Comma-separated tags, such as tag1,tag2")
    add_caption_flags(facebook_upload_video_parser)
    facebook_upload_video_parser.add_argument(
        "--proxy",
        default=FACEBOOK_PROXY,
        help="Browser proxy address; direct connection when omitted; an empty string overrides the environment variable and forces a direct connection",
    )
    add_runtime_flags(facebook_upload_video_parser)

    facebook_note = facebook_actions.add_parser("upload-note", help="Publish images and text to the profile")
    account_argument(facebook_note)
    facebook_note.add_argument("--images", required=True, nargs="+", type=existing_file_path)
    facebook_note.add_argument("--title", required=True)
    facebook_note.add_argument("--note", default="")
    facebook_note.add_argument("--tags", default="")
    add_caption_flags(facebook_note)
    facebook_note.add_argument("--proxy", default=FACEBOOK_PROXY, help="Proxy address; direct connection when omitted")
    add_runtime_flags(facebook_note)
    facebook_note.set_defaults(headless=False)


@dataclass(slots=True)
class FacebookVideoUploadRequest:
    account_name: str
    video_file: Path
    title: str
    description: str
    tags: list[str]
    proxy: str | None = FACEBOOK_PROXY
    debug: bool = True
    headless: bool = True


async def login_facebook_account(
    account_name: str, *, headless: bool = False, proxy: str | None = FACEBOOK_PROXY
) -> dict:
    account_file = resolve_account_file("facebook", account_name)
    return await facebook_setup(
        account_file,
        handle=True,
        return_detail=True,
        headless=headless,
        proxy=proxy,
    )


async def check_facebook_account(
    account_name: str, *, proxy: str | None = FACEBOOK_PROXY
) -> bool:
    account_file = resolve_account_file("facebook", account_name)
    if not session_available(account_file):
        return False
    return await facebook_cookie_auth(account_file, proxy=proxy)


async def upload_facebook_video(request: FacebookVideoUploadRequest) -> Path:
    account_file = resolve_account_file("facebook", request.account_name)
    is_ready = await facebook_setup(
        account_file,
        handle=False,
        proxy=request.proxy,
    )
    if not is_ready:
        raise RuntimeError(
            f"Facebook session is missing or expired: {account_file}. "
            f"Run `sau facebook login --account {request.account_name}` first."
        )

    app = FacebookVideo(
        title=request.title,
        file_path=request.video_file,
        description=request.description,
        tags=request.tags,
        account_file=account_file,
        proxy=request.proxy,
        headless=request.headless,
    )
    await app.main()
    return account_file


async def run(args):
    """Run this platform's command; the platform implementation verifies publishing."""
    if args.action == "upload-note":
        for image in args.images:
            BaseVideoUploader.validate_image_file(image)
        description, tags = apply_caption(
            "facebook", args.title, args.note, parse_tags(args.tags),
            auto_desc=args.auto_desc, auto_tags=args.auto_tags, lang=args.caption_lang,
        )
        app = FacebookPost(args.title, args.images, description, tags,
                           resolve_account_file("facebook", args.account), proxy=args.proxy, headless=args.headless)
        await app.main()
        print("Facebook image post submitted")
        return 0
    if args.action in {"verify", "delete"}:
        result = await facebook_post_action(
            resolve_account_file("facebook", args.account), post_url=args.post_url,
            owner_id=args.owner_id, expected_text=args.expected_text,
            delete=args.action == "delete", proxy=args.proxy, headless=args.headless,
            permanent=getattr(args, "permanent", False), from_trash=args.from_trash,
            deleted=getattr(args, "deleted", False),
        )
        if args.result:
            args.result.parent.mkdir(parents=True, exist_ok=True)
            args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.action == "login":
        result = await login_facebook_account(
            args.account, headless=args.headless, proxy=args.proxy
        )
        if not result["success"]:
            raise RuntimeError(result["message"])
        print(f"Facebook login flow completed: {result['account_file']}")
        return 0

    if args.action == "check":
        is_valid = await check_facebook_account(args.account, proxy=args.proxy)
        print("valid" if is_valid else "invalid")
        return 0 if is_valid else 1

    if args.action == "upload-video":
        description, tags = apply_caption(
            "facebook", args.title, args.desc, parse_tags(args.tags),
            auto_desc=args.auto_desc, auto_tags=args.auto_tags, lang=args.caption_lang,
        )
        request = FacebookVideoUploadRequest(
            account_name=args.account,
            video_file=args.file,
            title=args.title,
            description=description,
            tags=tags,
            proxy=args.proxy,
            debug=args.debug,
            headless=args.headless,
        )
        await upload_facebook_video(request)
        print(f"Facebook video upload submitted: {request.video_file}")
        return 0

    raise RuntimeError(f"Unsupported Facebook action: {args.action}")
