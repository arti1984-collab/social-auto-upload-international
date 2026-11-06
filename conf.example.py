from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOCAL_CHROME_PATH = ""  # optional, e.g. C:/Program Files/Google/Chrome/Application/chrome.exe
LOCAL_CHROME_HEADLESS = True  # default headless behavior for uploader/examples
# Browser the uploaders drive: chrome | edge | chromium | opera-gx | firefox.
# Override per run with `--browser` or the SAU_BROWSER environment variable.
# Firefox needs Playwright's build once: python -m playwright install firefox
LOCAL_BROWSER = "chrome"
# Keep a persistent browser profile (profiles/<browser>/<account>) instead of exporting cookie
# files. `--profile` turns it on for a single run; logins then stay inside the profile.
LOCAL_BROWSER_PROFILE = False
# Profile stored by `sau profile use`; it supplies the browser and the account of its platform.
DEFAULT_PROFILE = ""
DEBUG_MODE = True  # default debug behavior
# Optional proxy for the YouTube uploader. Where youtube.com is blocked, direct
# connections time out and the (patchright) chromium does NOT use the system proxy.
# Point this at your local proxy port, e.g. "http://127.0.0.1:7890". None = no proxy.
YT_PROXY = None
