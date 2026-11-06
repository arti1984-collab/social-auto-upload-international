"""Arguments and execution for the status command.

One line per platform and account, merged from the cookie files and the stored
profiles: what exists, when it was last used and which profile is the default.
With ``--verify`` the platform's own session check confirms each login.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

from utils.browser import (
    browser_spec,
    default_profile,
    list_profiles,
    set_profile_mode,
)

KNOWN_PLATFORMS = ("youtube", "facebook", "facebook-page", "instagram")


def cookie_directory() -> Path:
    """Directory holding the exported cookie files."""
    from conf import BASE_DIR

    return Path(BASE_DIR) / "cookies"


def register(platform_parsers) -> None:
    """Declare the status command; without --verify it only reads the file system."""
    parser = platform_parsers.add_parser(
        "status", help="Show cookie files, stored profiles and the default profile"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Check every session in a browser and report valid, invalid or the error",
    )
    parser.add_argument(
        "--verify-jobs",
        type=_job_count,
        default=2,
        metavar="N",
        help="How many session checks may run at once (default: 2)",
    )


def _job_count(value: str) -> int:
    """Bound the parallel browser starts; more only piles up memory and CPU."""
    try:
        jobs = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a number, got {value!r}")
    if not 1 <= jobs <= 16:
        raise argparse.ArgumentTypeError("must be between 1 and 16")
    return jobs


def _split_platform(stem: str) -> tuple[str, str]:
    """Split ``<platform>_<account>``; '' keeps unknown files under 'other'."""
    for name in sorted(KNOWN_PLATFORMS, key=len, reverse=True):
        prefix = f"{name}_"
        if stem.startswith(prefix):
            return name, stem[len(prefix):]
    return "other", stem


def _entry(platform: str, account: str) -> dict:
    return {
        "platform": platform,
        "account": account,
        "cookie": None,
        "profiles": {},
        "last_used": None,
    }


def collect_accounts() -> list[dict]:
    """Merge cookie files and profiles into one row per platform and account."""
    rows: dict[tuple[str, str], dict] = {}
    cookies = cookie_directory()
    if cookies.is_dir():
        for path in sorted(cookies.glob("*.json")):
            if path.stem.endswith(".pending"):
                continue
            platform, account = _split_platform(path.stem)
            row = rows.setdefault((platform, account), _entry(platform, account))
            row["cookie"] = path
    for profile in list_profiles():
        platform, account = _split_platform(profile["account"])
        row = rows.setdefault((platform, account), _entry(platform, account))
        row["profiles"][profile["browser"]] = profile
    for row in rows.values():
        stamps: list[float] = []
        if row["cookie"]:
            try:
                stamps.append(row["cookie"].stat().st_mtime)
            except OSError:
                pass
        stamps.extend(
            profile["last_used"].timestamp()
            for profile in row["profiles"].values()
            if profile["last_used"]
        )
        row["last_used"] = datetime.fromtimestamp(max(stamps)) if stamps else None
    order = {name: index for index, name in enumerate(KNOWN_PLATFORMS)}
    return sorted(
        rows.values(),
        key=lambda row: (order.get(row["platform"], len(order)), row["platform"], row["account"]),
    )


def checker(platform: str) -> Callable[[str], Awaitable[bool]] | None:
    """The platform's own session check, so status never reimplements one."""
    if platform == "youtube":
        from sau_commands.youtube import check_youtube_account

        return check_youtube_account
    if platform == "facebook":
        from sau_commands.facebook import check_facebook_account

        return check_facebook_account
    if platform == "facebook-page":
        from sau_commands.facebook_page import check_meta_account

        return lambda account: check_meta_account("facebook-page", account)
    if platform == "instagram":
        from sau_commands.instagram import check_instagram_account

        return check_instagram_account
    return None


async def verify_accounts(accounts: list[dict], jobs: int = 2) -> list[tuple[str, str]]:
    """Check the sessions with at most ``jobs`` browsers at once, in row order."""
    semaphore = asyncio.Semaphore(max(1, jobs))

    async def check_one(row: dict) -> tuple[str, str]:
        async with semaphore:
            return await verify_account(row)

    return list(await asyncio.gather(*(check_one(row) for row in accounts)))


async def verify_account(row: dict) -> tuple[str, str]:
    """Return the session state and, on failure, the reason printed below the table."""
    if not row["cookie"] and not row["profiles"]:
        return "missing", ""
    check = checker(row["platform"])
    if check is None:
        return "-", ""
    try:
        valid = await check(row["account"])
    except Exception as exc:
        # Expired Instagram/Meta sessions raise instead of returning False.
        reason = str(exc).strip().splitlines()
        return "error", reason[0] if reason else exc.__class__.__name__
    return ("valid" if valid else "invalid"), ""


def _session_column(row: dict, sessions: dict[tuple[str, str], str]) -> str:
    return sessions.get((row["platform"], row["account"]), "-")


async def run(args) -> int:
    """Print the overview; only --verify starts a browser, and nothing is stored."""
    accounts = collect_accounts()
    if not accounts:
        print("No accounts yet: run `sau <platform> login --account NAME` once.")
        return 0
    stored = default_profile()
    # The default is a pair: the configured browser and the stored profile.
    configured = browser_spec(None).name if stored else ""
    verify = bool(getattr(args, "verify", False))
    sessions: dict[tuple[str, str], str] = {}
    details: list[str] = []
    if verify:
        # A session may live in a profile, so profiles count while checking.
        set_profile_mode(True)
        try:
            results = await verify_accounts(accounts, getattr(args, "verify_jobs", 2))
        finally:
            set_profile_mode(None)
        for row, (state, detail) in zip(accounts, results):
            sessions[(row["platform"], row["account"])] = state
            if detail:
                details.append(f"{row['platform']} {row['account']}: {detail}")

    header = f"{'PLATFORM':14} {'ACCOUNT':22} {'COOKIE':7} {'PROFILES':24} {'LAST USED':16}  {'DEFAULT':20}"
    if verify:
        header += "SESSION"
    print(header)
    for row in accounts:
        def is_default(browser: str, profile: dict) -> bool:
            return profile["account"] == stored and browser == configured

        browsers = ", ".join(
            f"{browser}*" if is_default(browser, profile) else browser
            for browser, profile in sorted(row["profiles"].items())
        )
        is_default_row = any(
            is_default(browser, profile) for browser, profile in row["profiles"].items()
        )
        last_used = row["last_used"].strftime("%Y-%m-%d %H:%M") if row["last_used"] else "-"
        line = (
            f"{row['platform']:14} {row['account']:22} {'yes' if row['cookie'] else '-':7} "
            f"{browsers or '-':24} {last_used:16}  "
            f"{f'{configured}/{stored}' if is_default_row else '-':20}"
        )
        if verify:
            line += _session_column(row, sessions)
        print(line)
    print("\n* marks the stored default profile; `-` means the state is missing.")
    if verify:
        print(f"Sessions were checked with the configured browser ({configured or 'unknown'}).")
        for detail in details:
            print(f"  {detail}")
    return 0
