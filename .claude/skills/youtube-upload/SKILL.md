---
name: youtube-upload
description: Log in to YouTube and publish, schedule or set the visibility of a video with the `sau youtube` CLI of social-auto-upload. Use when the user wants a video on YouTube or wants the Google/YouTube session checked.
license: MIT-0
---

# YouTube — video upload

Wraps the existing `sau youtube` CLI. Login happens in the browser through a normal Google
sign-in (no QR code); `--account` is only a local session alias.

```powershell
sau youtube login --account creator
sau youtube check --account creator
sau youtube upload-video --account creator --file videos/demo.mp4 --title "Title" --desc "Description" --tags tag1,tag2 --visibility public
sau youtube upload-video --account creator --file videos/demo.mp4 --title "Scheduled video" --schedule "2026-10-21 10:30"
```

- Title: at most 100 characters.
- `--visibility`: `public` (default), `unlisted` or `private`.
- `--thumbnail` sets a custom cover, `--playlist` targets an existing playlist by name.
- Pass `--schedule "YYYY-MM-DD HH:MM"` only when the user gave an explicit time. It uses the
  YouTube Studio "Schedule" state — verify the date and time fields on the page afterwards.
- Without `--schedule` the video is published immediately with the chosen visibility.

Why a browser instead of the official API: videos uploaded by API projects that did not pass
Google's compliance review are locked to private, so this project drives YouTube Studio with a
saved session. Mention this if the user asks why no OAuth/API key is involved.

Before submitting, re-check account, file, title, description, tags, visibility and whether the
user wants immediate or scheduled publishing. On timeout check YouTube Studio for the upload
before retrying. A successful upload is not the same as a finished review or a playable public
video.
