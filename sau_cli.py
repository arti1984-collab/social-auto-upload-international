"""SAU command entry point; platform arguments and execution live in sau_commands."""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Sequence

from sau_commands import (
    article,
    caption,
    facebook,
    facebook_page,
    instagram,
    profile,
    status,
    youtube,
)
from sau_commands.arguments import (
    apply_use_profile,
    remember_default_profile,
    resolve_account_file,
)
from utils.browser import (
    default_browser,
    set_default_browser,
    set_default_executable,
    set_profile_mode,
    set_profile_root,
)


PLATFORMS = {
    "article": article,
    "caption": caption,
    "facebook": facebook,
    "facebook-page": facebook_page,
    "instagram": instagram,
    "youtube": youtube,
    "profile": profile,
    "status": status,
}


def build_parser() -> argparse.ArgumentParser:
    """Build the platform commands; each platform owns its arguments and action."""
    parser = argparse.ArgumentParser(prog="sau", description="CLI for social-auto-upload.")
    platform_parsers = parser.add_subparsers(dest="platform", required=True)
    for platform in PLATFORMS.values():
        platform.register(platform_parsers)
    return parser


async def dispatch(args: argparse.Namespace) -> int:
    """Dispatch by platform only; no platform business logic in the entry point."""
    if args.platform not in PLATFORMS:
        raise RuntimeError(f"Unsupported platform: {args.platform}")
    # Browser choice is process-wide: the uploaders read it when they launch.
    set_default_browser(getattr(args, "browser", None))
    set_default_executable(getattr(args, "browser_path", None))
    set_profile_mode(True if getattr(args, "profile", False) else None)
    if getattr(args, "profile_dir", None):
        set_profile_root(args.profile_dir)
    # --use-profile takes browser and account from one stored profile.
    apply_use_profile(args)
    if hasattr(args, "account") and not args.account:
        raise RuntimeError(
            "Missing --account: pass --account NAME, or select a stored profile with "
            "--use-profile BROWSER/ACCOUNT (see `sau profile list`)."
        )
    login = getattr(args, "action", None) == "login"
    if login:
        # A login always writes into a persistent profile, so the session is reusable
        # without a cookie file.
        set_profile_mode(True)
    code = await PLATFORMS[args.platform].run(args)
    if login and code == 0:
        key = f"{args.platform}_{args.account}"
        try:
            path = remember_default_profile(default_browser(), key)
        except Exception as exc:
            print(f"Login succeeded, but the default profile was not stored: {exc}", file=sys.stderr)
        else:
            print(f"Default profile {key} in {default_browser()} stored in {path}.")
    return code


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return asyncio.run(dispatch(args))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
