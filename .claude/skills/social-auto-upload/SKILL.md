---
name: social-auto-upload
description: Entry point for social-auto-upload. Use when the user wants to publish, schedule or verify video and image posts on TikTok, YouTube, a Facebook profile, a Facebook Page or Instagram and the platform-specific workflow must be chosen first.
license: MIT-0
---

# social-auto-upload — entry point

This checkout is scoped to **TikTok, YouTube, Facebook profile, Facebook Page and Instagram**.
Other platforms (Douyin, Kuaishou, Xiaohongshu, WeChat Channels, Bilibili, Baijiahao, Dayu,
Alipay, Weibo, Hupu, Xueqiu, Zhihu) are deliberately not part of the tool: do not offer them, do
not add their skills, do not run their CLI subcommands.

## Pick the platform

| Platform | Skill | CLI entry |
| --- | --- | --- |
| TikTok | `tiktok-upload` | none — Python uploader only |
| YouTube | `youtube-upload` | `sau youtube` |
| Facebook profile | `facebook-upload` | `sau facebook` |
| Facebook Page | `meta-upload` | `sau facebook-page` |
| Instagram | `instagram-upload` | `sau instagram` |

## Workflow

1. Read the platform skill first: `.claude/skills/<skill-name>/SKILL.md`.
2. Establish platform, content type (video vs image post), account alias and publish intent
   (now vs scheduled) from the user. Never choose a platform on your own.
3. Check that `sau` is installed (`sau --help`). If it is missing, stop and report that the
   environment is not set up instead of installing anything unasked.
4. Run `sau <platform> --help` before using any flag. Do not invent flags and never claim
   TikTok has a CLI.
5. Login is always performed by the human in the visible browser window. Never ask for
   passwords, never read, print or commit cookie files under `cookies/`.
6. Read back account, file, title, caption, tags, visibility and time before submitting.
   Publish only what the user explicitly requested, one platform at a time.
7. Report "published" only when the CLI or the platform confirmed this submission. On timeout
   or an unknown status, check the account's existing posts before doing anything else —
   never blindly re-upload.
8. Some older helper scripts print Chinese. Translate errors and status messages for the user instead
   of pasting them raw.
