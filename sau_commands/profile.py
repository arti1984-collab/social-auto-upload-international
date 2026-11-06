"""Arguments and execution for the profile command.

Profiles are the persistent browser directories that ``--profile`` uses. This
command only inspects and removes them; cookie files are never touched.
"""
from __future__ import annotations

from utils.browser import (
    available_browsers,
    default_profile,
    find_profile,
    list_profiles,
    profile_root,
    remove_profile,
)
from utils.conf_settings import set_conf_values


def _human_size(size: int) -> str:
    """Readable size for the listing."""
    value = float(size)
    for unit in ("B", "KB", "MB"):
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def register(platform_parsers) -> None:
    """Declare the profile command, its actions and options."""
    parser = platform_parsers.add_parser(
        "profile", help="List and remove persistent browser profiles"
    )
    actions = parser.add_subparsers(dest="action", required=True)

    listing = actions.add_parser("list", help="Show every stored profile")
    listing.add_argument("--browser", choices=available_browsers(), help="Only this browser")

    use = actions.add_parser("use", help="Store a profile as the default for its platform")
    use.add_argument("key", nargs="?", help="Profile key, for example firefox/youtube_main")
    use.add_argument("--clear", action="store_true", help="Remove the stored default profile")

    removal = actions.add_parser("remove", help="Delete one stored profile")
    removal.add_argument("--account", required=True, help="Profile key, for example youtube_main")
    removal.add_argument(
        "--browser",
        choices=available_browsers(),
        help="Browser holding that profile; defaults to the configured browser",
    )
    removal.add_argument(
        "--platform",
        dest="platform_prefix",
        help="Optional prefix, so --platform youtube --account main targets youtube_main",
    )


def _profile_key(account: str, platform: str | None) -> str:
    return f"{platform}_{account}" if platform else account


async def run(args) -> int:
    """List profiles or remove one; a missing profile is reported, never ignored."""
    if args.action == "list":
        profiles = list_profiles(getattr(args, "browser", None))
        if not profiles:
            print(f"No stored profiles under {profile_root()}.")
            return 0
        stored = default_profile()
        print(
            f"{'BROWSER':9} {'ACCOUNT':24} {'SIZE':>9}  {'LAST USED':16}  {'DEFAULT':8}  PATH"
        )
        for entry in profiles:
            last_used = (
                entry["last_used"].strftime("%Y-%m-%d %H:%M") if entry["last_used"] else "-"
            )
            marker = "yes" if entry["account"] == stored else ""
            print(
                f"{entry['browser']:9} {entry['account']:24} {_human_size(entry['bytes']):>9}  "
                f"{last_used:16}  {marker:8}  {entry['path']}"
            )
        return 0

    if args.action == "use":
        if getattr(args, "clear", False):
            set_conf_values({"DEFAULT_PROFILE": '""'})
            print("Default profile cleared; stored profiles and the browser choice stay.")
            return 0
        if not args.key:
            raise RuntimeError(
                "Missing profile: pass `sau profile use BROWSER/ACCOUNT` (see `sau profile list`)."
            )
        found = find_profile(args.key)
        path = set_conf_values(
            {
                "LOCAL_BROWSER": f'"{found["browser"]}"',
                "LOCAL_BROWSER_PROFILE": "True",
                "DEFAULT_PROFILE": f'"{found["account"]}"',
            }
        )
        print(
            f"Stored {found['account']} in {found['browser']} as the default in {path}."
        )
        print(
            "Later runs of that platform use it without --account, --browser or --profile."
        )
        return 0

    if args.action == "remove":
        result = remove_profile(
            _profile_key(args.account, getattr(args, "platform_prefix", None)),
            browser=getattr(args, "browser", None),
        )
        print(
            f"Removed {result['path']} "
            f"({_human_size(result['bytes'])}, {result['files']} files)."
        )
        return 0

    raise RuntimeError(f"Unsupported profile action: {args.action}")
