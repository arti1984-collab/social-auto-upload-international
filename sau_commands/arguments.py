"""Shared path, tag and time argument rules for the CLI."""
from __future__ import annotations
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable
from conf import BASE_DIR
from utils.conf_settings import set_conf_values
from utils.browser import (
    available_browsers,
    default_profile,
    find_profile,
    set_default_browser,
    set_profile_mode,
)

SCHEDULE_FORMAT = "%Y-%m-%d %H:%M"

def has_interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def resolve_account_file(platform: str, account_name: str) -> Path:
    account_file = Path(BASE_DIR) / "cookies" / f"{platform}_{account_name}.json"
    account_file.parent.mkdir(exist_ok=True)
    return account_file


def parse_tags(raw_tags: str | None) -> list[str]:
    if not raw_tags:
        return []

    tags: list[str] = []
    for item in raw_tags.split(","):
        cleaned = item.strip().lstrip("#")
        if cleaned:
            tags.append(cleaned)
    return tags


def parse_image_files(raw_files: Iterable[Path]) -> list[Path]:
    return [Path(file) for file in raw_files]


def parse_schedule(raw_schedule: str | None) -> datetime | int:
    if not raw_schedule:
        return 0
    return datetime.strptime(raw_schedule, SCHEDULE_FORMAT)


def existing_file_path(value: str) -> Path:
    path = Path(value)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"File not found: {value}")
    return path


def schedule_value(value: str):
    try:
        return parse_schedule(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid schedule '{value}'. Expected format: {SCHEDULE_FORMAT}"
        ) from exc


def account_argument(parser: argparse.ArgumentParser, help: str = "Account name") -> None:
    """Account name; optional because --use-profile can name the profile instead."""
    parser.add_argument("--account", required=False, help=help)


def apply_use_profile(args: argparse.Namespace) -> None:
    """Take browser, profile mode and account from one stored profile.

    Without --use-profile the profile stored by `sau profile use` is used, as long
    as it belongs to this platform and no account was named explicitly.
    """
    selection = getattr(args, "use_profile", None)
    if not selection:
        _apply_stored_profile(args)
        return
    found = find_profile(selection)
    key = found["account"]
    platform_key = str(getattr(args, "platform", "") or "")
    account = getattr(args, "account", None)
    if not account:
        prefix = f"{platform_key}_"
        account = key[len(prefix):] if platform_key and key.startswith(prefix) else key
        expected = f"{platform_key}_{account}" if platform_key else account
        if expected != key:
            raise ValueError(
                f"Profile '{key}' is not named after {platform_key} and its account. "
                f"Rename it to '{expected}' or pass --account explicitly."
            )
    set_profile_mode(True)
    set_default_browser(found["browser"])
    args.account = account


def _apply_stored_profile(args: argparse.Namespace) -> None:
    """Fill the account from conf.DEFAULT_PROFILE when it belongs to this platform."""
    if getattr(args, "account", None):
        return
    platform_key = str(getattr(args, "platform", "") or "")
    stored = default_profile()
    prefix = f"{platform_key}_"
    if not platform_key or not stored.startswith(prefix) or stored == prefix:
        return
    set_profile_mode(True)
    args.account = stored[len(prefix):]


def remember_default_profile(browser: str, key: str) -> Path:
    """Store browser and profile as the default in conf.py and return that file."""
    return set_conf_values(
        {
            "LOCAL_BROWSER": f'"{browser}"',
            "LOCAL_BROWSER_PROFILE": "True",
            "DEFAULT_PROFILE": f'"{key}"',
        }
    )


def add_runtime_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument(
        "--browser",
        choices=available_browsers(),
        help="Browser to drive; defaults to LOCAL_BROWSER in conf.py, then chrome",
    )
    parser.add_argument(
        "--browser-path",
        dest="browser_path",
        help="Path to the browser program, for example an Opera GX install outside the default location",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Keep a persistent browser profile instead of writing a cookie file",
    )
    parser.add_argument(
        "--profile-dir",
        dest="profile_dir",
        help="Directory for that profile (default: profiles/<browser>/<account>)",
    )
    parser.add_argument(
        "--use-profile",
        dest="use_profile",
        help="Use a stored profile, as browser/account or a unique account name; replaces --browser and --account",
    )
    headless_group = parser.add_mutually_exclusive_group()
    headless_group.add_argument("--headed", dest="headless", action="store_false", help="Run with browser UI")
    headless_group.add_argument("--headless", dest="headless", action="store_true", help="Run in headless mode")
    parser.set_defaults(headless=True)
