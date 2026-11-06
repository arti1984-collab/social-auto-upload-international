"""Browser selection for every uploader.

patchright drives Chromium based browsers, so Chrome, Microsoft Edge, plain
Chromium and Opera GX all use its chromium engine. Firefox uses the firefox
engine of the same driver, which ships its own Firefox build
(install it once with ``patchright install firefox``).

The browser is chosen, in this order, by the ``--browser`` flag, the
``SAU_BROWSER`` environment variable, ``LOCAL_BROWSER`` in conf.py, and
finally Google Chrome.
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class BrowserSpec:
    """One selectable browser and how the driver has to launch it."""

    name: str
    engine: str
    channel: str | None = None
    needs_executable: bool = False
    summary: str = ""


BROWSERS: dict[str, BrowserSpec] = {
    "chrome": BrowserSpec(
        "chrome", "chromium", channel="chrome", summary="Google Chrome (installed)"
    ),
    "edge": BrowserSpec(
        "edge", "chromium", channel="msedge", summary="Microsoft Edge (installed)"
    ),
    "chromium": BrowserSpec(
        "chromium", "chromium", summary="the Chromium build managed by patchright"
    ),
    "opera-gx": BrowserSpec(
        "opera-gx", "chromium", needs_executable=True, summary="Opera GX (installed)"
    ),
    "firefox": BrowserSpec(
        "firefox", "firefox", summary="the Firefox build managed by patchright"
    ),
}

ALIASES = {
    "opera": "opera-gx",
    "operagx": "opera-gx",
    "opera-gx": "opera-gx",
    "msedge": "edge",
    "microsoft-edge": "edge",
    "google-chrome": "chrome",
}

# Opera GX has no driver channel, so its executable has to be found by path.
OPERA_GX_CANDIDATES: dict[str, tuple[str, ...]] = {
    "win32": (
        r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe",
        r"%PROGRAMFILES%\Opera GX\opera.exe",
        r"%PROGRAMFILES(X86)%\Opera GX\opera.exe",
    ),
    "darwin": ("/Applications/Opera GX.app/Contents/MacOS/Opera GX",),
    "linux": ("/usr/bin/opera-gx", "/usr/lib/x86_64-linux-gnu/opera-gx/opera"),
}

# Chromium throttles background tabs and occluded windows: timers drop to one
# tick per minute, the renderer stops painting and the page reports itself as
# hidden, so video players and streaming previews stall as soon as the window
# loses focus. Logins and uploads of this project run headed next to the user's
# own work, so the launched browser keeps running while it is in the background.
# Firefox rejects unknown switches, so it never sees these.
ANTI_THROTTLE_ARGS: tuple[str, ...] = (
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-features=CalculateNativeWinOcclusion",
)


def launch_args(args: Iterable[str] | None = None) -> list[str]:
    """Anti-throttling switches first, then the caller's own, without duplicates."""
    merged: list[str] = []
    for flag in (*ANTI_THROTTLE_ARGS, *(args or ())):
        if flag not in merged:
            merged.append(flag)
    return merged


_selected: str | None = None
_executable: str | None = None
_default_profile: str | None = None
_profile_mode: bool | None = None
_profile_root: Path | None = None


def available_browsers() -> list[str]:
    """Browser names the CLI accepts."""
    return list(BROWSERS)


def set_default_browser(name: str | None) -> None:
    """Remember the browser this process asked for; validates the name early."""
    global _selected
    if name:
        browser_spec(name)
        _selected = name.strip().lower().replace("_", "-").replace(" ", "-")
    else:
        _selected = None


def set_default_executable(path: str | None) -> None:
    """Remember an explicit browser program path, e.g. an unusual Opera GX install."""
    global _executable
    _executable = path or None


def default_executable() -> str | None:
    """Path given by --browser-path or an earlier set_default_executable call."""
    return _executable


def default_browser() -> str:
    """Explicit selection first, then the environment, then conf.py, then Chrome."""
    if _selected:
        return _selected
    from_env = os.environ.get("SAU_BROWSER", "").strip()
    if from_env:
        return from_env
    try:
        import conf
    except ImportError:
        return "chrome"
    configured = str(getattr(conf, "LOCAL_BROWSER", "") or "").strip()
    return configured or "chrome"


def browser_spec(name: str | None = None) -> BrowserSpec:
    """Resolve a browser name (or the configured default) into its launch spec."""
    key = (name or default_browser()).strip().lower().replace("_", "-").replace(" ", "-")
    key = ALIASES.get(key, key)
    try:
        return BROWSERS[key]
    except KeyError:
        raise ValueError(
            f"Unknown browser '{name}'. Available: {', '.join(available_browsers())}"
        ) from None


def _platform_key() -> str:
    if sys.platform.startswith("win"):
        return "win32"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def opera_gx_candidates() -> tuple[str, ...]:
    """Install locations checked for Opera GX on this platform."""
    return tuple(os.path.expandvars(path) for path in OPERA_GX_CANDIDATES[_platform_key()])


def installed_executable() -> str:
    """Path of a browser the driver cannot locate on its own, i.e. Opera GX."""
    for candidate in opera_gx_candidates():
        if os.path.isfile(candidate):
            return candidate
    raise RuntimeError(
        "Opera GX was not found. Install it or pass --browser-path with the path to "
        f"opera.exe. Looked in: {', '.join(opera_gx_candidates())}"
    )


def launch_options(
    *,
    browser: str | None = None,
    executable_path: str | None = None,
    headless: bool = True,
    proxy: dict[str, str] | None = None,
    args: Iterable[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return the engine name and the launch keyword arguments for that browser."""
    spec = browser_spec(browser)
    executable_path = executable_path or default_executable()
    options: dict[str, Any] = {"headless": headless}
    if spec.channel:
        options["channel"] = spec.channel
    if executable_path:
        options["executable_path"] = executable_path
    elif spec.needs_executable:
        options["executable_path"] = installed_executable()
    if proxy:
        options["proxy"] = proxy
    if spec.engine == "chromium":
        options["args"] = launch_args(args)
    elif args:
        options["args"] = list(args)
    return spec.engine, options


FIREFOX_DRIVER_HINT = "python -m playwright install firefox"


class _SessionBrowser:
    """Browser that also owns the driver session it was started with.

    patchright only patches Chromium, so its bundled Firefox cannot evaluate
    scripts. Firefox therefore runs on the regular Playwright driver, whose
    session has to be stopped together with the browser.
    """

    def __init__(self, target, playwright):
        self._target = target
        self._playwright = playwright

    def __getattr__(self, item):
        return getattr(self._target, item)

    async def close(self):
        try:
            await self._target.close()
        finally:
            await self._playwright.stop()


async def _launch_on_own_driver(persistent: bool, options: dict[str, Any]):
    from playwright.async_api import async_playwright as playwright_driver

    playwright = await playwright_driver().start()
    try:
        engine = playwright.firefox
        target = (
            await engine.launch_persistent_context(**options)
            if persistent
            else await engine.launch(**options)
        )
    except Exception as exc:
        await playwright.stop()
        raise RuntimeError(
            f"Firefox could not be started: {exc}\nInstall its build once: {FIREFOX_DRIVER_HINT}"
        ) from exc
    return _SessionBrowser(target, playwright)


async def launch(
    playwright,
    *,
    browser: str | None = None,
    executable_path: str | None = None,
    headless: bool = True,
    proxy: dict[str, str] | None = None,
    args: Iterable[str] | None = None,
):
    """Launch the selected browser; Chromium on the given session, Firefox on its own."""
    engine_name, options = launch_options(
        browser=browser,
        executable_path=executable_path,
        headless=headless,
        proxy=proxy,
        args=args,
    )
    if engine_name == "firefox":
        return await _launch_on_own_driver(False, options)
    return await getattr(playwright, engine_name).launch(**options)


def set_profile_mode(enabled: bool | None) -> None:
    """Keep a persistent browser profile instead of writing cookie files (None = use conf)."""
    global _profile_mode
    _profile_mode = enabled


def profile_mode() -> bool:
    """Persistent profiles only when asked for: the flag, then conf.LOCAL_BROWSER_PROFILE."""
    if _profile_mode is not None:
        return _profile_mode
    try:
        import conf
    except ImportError:
        return False
    return bool(getattr(conf, "LOCAL_BROWSER_PROFILE", False))


def set_default_profile(key: str | None) -> None:
    """Remember the profile chosen by `sau profile use` for this process."""
    global _default_profile
    _default_profile = None if key is None else str(key).strip()


def default_profile() -> str:
    """Profile stored by `sau profile use`, empty when none is configured."""
    if _default_profile is not None:
        return _default_profile
    try:
        import conf
    except ImportError:
        return ""
    return str(getattr(conf, "DEFAULT_PROFILE", "") or "").strip()


def set_profile_root(path: str | Path | None) -> None:
    """Directory holding every profile; default is profiles/ in the project."""
    global _profile_root
    _profile_root = Path(path) if path else None


def profile_root() -> Path:
    if _profile_root:
        return _profile_root
    try:
        import conf
    except ImportError:
        return Path("profiles")
    return Path(getattr(conf, "BASE_DIR", Path.cwd())) / "profiles"


def profile_directory(account_file=None, *, browser: str | None = None) -> Path:
    """Profiles are separated per browser and per account, like the cookie files."""
    key = Path(account_file).stem if account_file else "default"
    return profile_root() / browser_spec(browser).name / key


def session_available(account_file=None) -> bool:
    """A saved cookie file or an existing profile makes a session possible."""
    if account_file and Path(account_file).is_file():
        return True
    if not profile_mode():
        return False
    directory = profile_directory(account_file)
    return directory.is_dir() and any(directory.iterdir())


async def launch_persistent(
    playwright,
    *,
    browser: str | None = None,
    executable_path: str | None = None,
    headless: bool = True,
    proxy: dict[str, str] | None = None,
    args: Iterable[str] | None = None,
    profile: str | Path | None = None,
):
    """Open the selected browser with a persistent profile directory."""
    engine_name, options = launch_options(
        browser=browser,
        executable_path=executable_path,
        headless=headless,
        proxy=proxy,
        args=args,
    )
    directory = Path(profile) if profile else profile_directory(browser=browser)
    directory.mkdir(parents=True, exist_ok=True)
    options["user_data_dir"] = str(directory)
    if engine_name == "firefox":
        return await _launch_on_own_driver(True, options)
    return await getattr(playwright, engine_name).launch_persistent_context(**options)


def _directory_usage(directory: Path) -> tuple[int, int, float | None]:
    """Total bytes, file count and newest modification time of a profile directory."""
    total, files, newest = 0, 0, None
    for item in directory.rglob("*"):
        if not item.is_file():
            continue
        try:
            stat = item.stat()
        except OSError:
            continue
        total += stat.st_size
        files += 1
        newest = stat.st_mtime if newest is None else max(newest, stat.st_mtime)
    return total, files, newest


def list_profiles(browser: str | None = None) -> list[dict[str, Any]]:
    """Stored profiles with size and last use, optionally limited to one browser."""
    root = profile_root()
    if not root.is_dir():
        return []
    wanted = browser_spec(browser).name if browser else None
    entries: list[dict[str, Any]] = []
    for browser_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if wanted and browser_dir.name != wanted:
            continue
        for account_dir in sorted(path for path in browser_dir.iterdir() if path.is_dir()):
            size, files, newest = _directory_usage(account_dir)
            entries.append(
                {
                    "browser": browser_dir.name,
                    "account": account_dir.name,
                    "path": account_dir,
                    "bytes": size,
                    "files": files,
                    "last_used": datetime.fromtimestamp(newest) if newest else None,
                }
            )
    return entries


def remove_profile(account: str, *, browser: str | None = None) -> dict[str, Any]:
    """Delete one stored profile and report what it freed; cookie files stay untouched."""
    directory = profile_root() / browser_spec(browser).name / account
    if not directory.is_dir():
        raise FileNotFoundError(f"No stored profile at {directory}")
    size, files, _ = _directory_usage(directory)
    shutil.rmtree(directory)
    return {"path": directory, "bytes": size, "files": files}


def find_profile(selection: str) -> dict[str, Any]:
    """Resolve ``browser/account`` or a unique account name to one stored profile."""
    raw = str(selection or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("--use-profile needs a profile, for example firefox/youtube_main")
    profiles = list_profiles()
    if not profiles:
        raise FileNotFoundError(
            f"No stored profiles under {profile_root()}. Create one with --profile first."
        )
    if "/" in raw:
        browser_name, _, account = raw.partition("/")
        name = browser_spec(browser_name).name
        matches = [
            entry
            for entry in profiles
            if entry["browser"] == name and entry["account"] == account.strip("/ ").strip()
        ]
    else:
        matches = [entry for entry in profiles if entry["account"] == raw]
    if len(matches) == 1:
        return matches[0]
    available = ", ".join(f"{entry['browser']}/{entry['account']}" for entry in profiles)
    if not matches:
        raise FileNotFoundError(
            f"No stored profile matches '{selection}'. Available: {available}"
        )
    raise ValueError(
        f"'{selection}' exists in several browsers; name one of: "
        + ", ".join(f"{entry['browser']}/{entry['account']}" for entry in matches)
    )


async def open_session(
    playwright,
    account_file=None,
    *,
    headless: bool = True,
    proxy: dict[str, str] | None = None,
    args: Iterable[str] | None = None,
    browser: str | None = None,
    executable_path: str | None = None,
):
    """Return (browser, context) from a persistent profile or from a saved cookie state.

    A persistent context is also a browser, so both are the same object and the
    callers can keep closing ``browser`` as before.
    """
    if profile_mode():
        context = await launch_persistent(
            playwright,
            browser=browser,
            executable_path=executable_path,
            headless=headless,
            proxy=proxy,
            args=args,
            profile=profile_directory(account_file, browser=browser),
        )
        return context, context
    launched = await launch(
        playwright,
        browser=browser,
        executable_path=executable_path,
        headless=headless,
        proxy=proxy,
        args=args,
    )
    state = str(account_file) if account_file and Path(account_file).is_file() else None
    return launched, await launched.new_context(storage_state=state)
