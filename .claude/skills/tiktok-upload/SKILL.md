---
name: tiktok-upload
description: Publish a TikTok video with the repository's Patchright/Playwright Chrome uploader. Use when the user wants a video on TikTok; note that TikTok has no `sau` CLI command.
license: MIT-0
---

# TikTok — video upload (no CLI)

TikTok has **no** `sau tiktok` command. Use `uploader/tk_uploader/main_chrome.py`; do not invent
CLI flags. Before running, confirm the repository dependencies, the Chrome settings in `conf.py`
and the video path supplied by the user.

The account session lives in `cookies/tk_uploader/account.json`. First login can be done with
`examples/get_tk_cookie.py`, where the user signs in themselves on the TikTok page. Never read,
copy or commit that cookie file.

For a single video use the repository API directly, with `publish_date=0` for "publish now":

```python
import asyncio
from pathlib import Path
from conf import BASE_DIR
from uploader.tk_uploader.main_chrome import TiktokVideo, tiktok_setup

account_file = Path(BASE_DIR) / "cookies" / "tk_uploader" / "account.json"
video_file = Path(BASE_DIR) / "videos" / "demo.mp4"
asyncio.run(tiktok_setup(str(account_file), handle=True))
app = TiktokVideo("Title", str(video_file), ["tag"], 0, str(account_file))
asyncio.run(app.main())
```

- `TiktokVideo` has no separate description parameter — only title and tags.
- For scheduled publishing pass an explicit `datetime` as `publish_date`; never compute a time
  on your own.
- `examples/upload_video_to_tiktok.py` is a batch script: it takes every MP4 in a folder,
  derives title and tags from the filename and schedules everything for 16:00 the next day.
  Do not run it unless the user explicitly wants exactly that.

Have the user confirm account, single video, title, tags and immediate-vs-scheduled before each
publish. If the page layout or the session does not look as expected, stop and report. Report
success only after the TikTok page confirmed the submission; for unknown results check TikTok
Studio first and do not simply re-upload.
