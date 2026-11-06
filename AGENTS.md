# Agent instructions — social-auto-upload (international platforms only)

An international fork of [dreammis/social-auto-upload](https://github.com/dreammis/social-auto-upload)
(MIT). It publishes video and image posts by driving Chrome, Edge, Opera GX, Chromium or Firefox through `patchright`
(Playwright fork) with a saved session — a cookie file or a persistent profile, not official APIs.

## Scope: only these platforms

| Platform | Skill | CLI | Video | Image post | Scheduling |
| --- | --- | --- | --- | --- | --- |
| TikTok | `.claude/skills/tiktok-upload` | none (Python uploader) | yes | no | via `publish_date` |
| YouTube | `.claude/skills/youtube-upload` | `sau youtube` | yes | no | via YouTube Studio |
| Facebook profile | `.claude/skills/facebook-upload` | `sau facebook` | yes | yes | no |
| Facebook Page | `.claude/skills/meta-upload` | `sau facebook-page` | yes | yes | yes (local time) |
| Instagram | `.claude/skills/instagram-upload` | `sau instagram` | Reels | single / carousel | no |

The upstream Chinese platforms (Douyin, Kuaishou, Xiaohongshu, WeChat Channels, Bilibili,
Baijiahao, Dayu, Alipay, Weibo, Hupu, Xueqiu, Zhihu) were deliberately removed. Their skills are
gone; do not offer them, do not restore the skill folders, do not run `sau douyin` & co.

Their code is removed as well: the 12 `sau_commands/*.py` modules, their `uploader/*_uploader/`
packages, the matching `examples/` scripts and `tests/`, plus the legacy web stack
(`sau_backend.py`, `sau_backend/`, `sau_frontend/`, `myUtils/`). `sau` now knows exactly five
subcommands: `article`, `facebook`, `facebook-page`, `instagram`, `youtube`. `sau article` only
renders local Markdown/HTML and needs Node.js 22+ for themes.

Do not re-add any of it, and do not "restore upstream" with `git checkout` — that brings the
Chinese platforms back.

## Layout

- `sau_cli.py` — CLI entry point, builds the argparse tree; `sau_commands/<platform>.py` —
  one module per platform; `uploader/` — the actual browser flows.
- `.claude/skills/` — English skills, read by Claude Code and opencode (`.claude/skills` is also
  a documented opencode search path). Read the platform skill before touching a platform.
- `docs/` and `README.md` — documentation in **German and English**: `docs/CLI.md` is the flag
  reference, `docs/install.md` and `docs/update.md` cover setup and upgrades.
- `conf.example.py` — config template (`LOCAL_CHROME_PATH`, `LOCAL_CHROME_HEADLESS`,
  `DEBUG_MODE`).
- `examples/` — upstream sample and debugging scripts, partly Chinese and partly outdated.

## Environment

A fresh clone has no virtualenv, no `sau` on `PATH`, no browser and no `conf.py`, so `sau …`
commands fail until the setup ran. Do not install anything on your own initiative; if a task needs
the CLI, say what is missing and offer the setup:

```powershell
winget install --id=astral-sh.uv -e      # once, if uv is missing
uv venv
.venv\Scripts\Activate.ps1               # PowerShell; Linux/macOS: source .venv/bin/activate
uv pip install -e .                      # registers the `sau` command
patchright install chromium
Copy-Item conf.example.py conf.py        # then set LOCAL_CHROME_PATH etc.
sau youtube --help                       # smoke test
```

The upstream docs add `PLAYWRIGHT_DOWNLOAD_HOST="https://npmmirror.com/mirrors/playwright"`
(Chinese mirror). Skip that unless the default download fails.

## Hard rules

1. Never publish, schedule or delete anything without an explicit instruction naming platform,
   asset and account. Uploading creates real public content.
2. Read back account alias, file path, title, caption, tags, visibility and time before
   submitting; ask if any of it is missing.
3. Login and any platform verification are done by the human in the visible browser. Never ask
   for passwords, never type credentials, never read, print, copy or commit files under
   `cookies/` or `.local/`.
4. Report "published" only on positive evidence from the CLI result or the platform page. After a
   timeout or `submission_unknown`, inspect the account/post list first — never re-upload "just to
   be sure".
5. Verify current flags with `sau <platform> --help` (or `upload-video --help`,
   `upload-note --help`). Do not invent flags and never claim TikTok has a CLI.
6. The CLI speaks German and English; pass its errors and statuses on unchanged.
7. Selectors break when a platform redesigns its composer. If the page does not look like the
   flow expects, stop and report instead of guessing.
8. Timezones: every `--schedule` means the browser's local time, for YouTube Studio as well as the
   Meta composer. Convert other timezones explicitly and confirm.
9. This repository is public. Before **every** commit and push, check that no personal data of
   the owner goes along, and report the result. Never commit `profiles/` (live browser session),
   `logs/`, `cookies/`, `conf.py`, session JSON files or media from real uploads. On any hit,
   stop and report instead of committing.

## Risk

Cookie-based browser automation against these platforms violates their terms of service and can
trigger risk-control or account blocks. Mention this when a user plans to use it on an important
account.
