---
name: tiktok-upload
description: Publish a TikTok video with the repository's Patchright/Playwright uploader. Use when the user wants a video on TikTok; note that TikTok has no `sau` CLI command.
license: MIT-0
---

# TikTok — video upload (no CLI)

TikTok has **no** `sau tiktok` command. Use `uploader/tk_uploader/main_chrome.py`; do not invent
CLI flags. Before running, confirm the repository dependencies, the browser configuration in
`conf.py` and the video path supplied by the user.

The account session lives in `cookies/tk_uploader/account.json`. A relative name is resolved
there by `account_path()`; an absolute path is used unchanged. Never read, copy or commit that
cookie file.

Login is interactive and works without the Playwright inspector: the browser opens, the user signs
in, and the session is saved as soon as TikTok sets its `sessionid` cookie (10 minute timeout).

```python
import asyncio
from pathlib import Path
from conf import BASE_DIR
from uploader.tk_uploader.main_chrome import TiktokVideo, tiktok_setup

account_file = Path(BASE_DIR) / "cookies" / "tk_uploader" / "account.json"
video_file = Path(BASE_DIR) / "videos" / "demo.mp4"
if not asyncio.run(tiktok_setup(str(account_file), handle=True)):
    raise SystemExit("No TikTok session; sign-in did not complete")
app = TiktokVideo("Title", str(video_file), ["tag"], 0, str(account_file), visibility="private")
asyncio.run(app.main())
```

The browser is chosen by `--browser` (CLI only), then the `SAU_BROWSER` environment variable, then
`LOCAL_BROWSER` in `conf.py` — for Opera GX, set `SAU_BROWSER=opera-gx` before the Python call.
`tiktok_setup(..., handle=False)` returns `False` without starting a browser when no session
exists.

- `TiktokVideo` has no separate description parameter — only title and tags.
- `visibility="public" | "friends" | "private"` (default `public`). The composer's audience is a
  combobox (`[data-e2e="video_visibility_container"]`), labelled in the session's language:
  "Alle" / "Nur du" or "Everyone" / "Only me". The uploader picks the option by label, reads the
  trigger back, and raises **before** clicking Post if the label is missing or not confirmed — an
  unconfirmed private upload aborts instead of publishing publicly.
- Photo posts (carousel) use the same class with a list of 1–35 images (`jpg/jpeg/png/webp/heic`):
  `TiktokVideo("Titel", ["videos/a.png", "videos/b.png"], [], 0, str(account_file), visibility="private")`.
  Photos are attached straight through the upload input (`input[type=file]`), because the
  "Select video" button only exists for videos; `validate_photo_files()` checks count and formats,
  and the same visibility verification runs before Post.
- For scheduled publishing pass an explicit `datetime` as `publish_date`; never compute a time
  on your own.
- `examples/upload_video_to_tiktok.py` is a batch script: it takes every MP4 in a folder,
  derives title and tags from the filename and schedules everything for 16:00 the next day.
  Do not run it unless the user explicitly wants exactly that.

Have the user confirm account, single video, title, tags and immediate-vs-scheduled before each
publish. If the page layout or the session does not look as expected, stop and report. Report
success only after the TikTok page confirmed the submission; for unknown results check TikTok
Studio first and do not simply re-upload.
