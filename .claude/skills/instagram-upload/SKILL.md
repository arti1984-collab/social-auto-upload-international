---
name: instagram-upload
description: Log in to Instagram on the standalone web session and publish Reels, single images or carousels, then verify or delete them with the `sau instagram` CLI. Use when the user wants an Instagram post.
license: MIT-0
---

# Instagram — Reels and image posts

Uses the project's Patchright Chrome with an independent Instagram session; no Facebook Page or
Business Suite binding. Visible browser by default; no proxy unless `--proxy` or
`SAU_INSTAGRAM_PROXY` is set (`--proxy ""` forces a direct connection).

```powershell
sau instagram login --account creator
sau instagram check --account creator
sau instagram upload-video --account creator --file videos/demo.mp4 --thumbnail covers/demo.png --title "Title" --desc "Text" --tags life,sharing --result .local/instagram-video.json
sau instagram upload-note --account creator --images images/1.jpg images/2.jpg --title "Carousel title" --note "Text" --result .local/instagram-images.json
```

- `--thumbnail` (JPG/PNG) applies to Reels only and is checked against the preview before
  submitting; the cover is centre-cropped to the video aspect ratio, so keep important text away
  from the edges. Image posts reject this flag.
- Session file: `cookies/instagram_creator.json`. Passwords and verification are entered by the
  user in the project browser; `--headless` switches to headless mode, but login needs the
  visible window.
- Video: MP4/MOV. Photos: JPG/JPEG/PNG/AVIF/HEIC/HEIF (actual support depends on the platform).
  Multiple images become a carousel in the given order; single images and two-image carousels
  are the tested cases.
- Title, caption and tags are merged into one caption: 2200 characters total.
- **No scheduling**: the standalone web composer has no scheduling entry, so this CLI only
  publishes immediately. Do not silently turn a scheduled request into an immediate post.
- Place, collaborators, AI labels, alt text, filters, crop, audio and comment/like settings are
  not implemented and stay at page defaults.

Result values: `published` (platform confirmed creation, includes `content_id`, `post_id`,
`post_url`, `media_count`), `processing` (accepted, still processing), `submission_unknown`
(submitted but unconfirmed — not a publication, never re-upload). Default output goes to
`.local/instagram-results/`; prefer `--result`.

```powershell
sau instagram verify --account creator --post-url "https://www.instagram.com/p/POST_ID/" --expected-text "exact caption" --result .local/instagram-verify.json
sau instagram delete --account creator --post-url "https://www.instagram.com/reel/POST_ID/" --expected-text "exact caption" --result .local/instagram-delete.json
```

Without a link, look the post up on the same account's profile by media, caption and time; not
finding it does not prove the upload failed. Check the signed-in user, author, post id and
caption before deleting. `delete` moves the post to "Recently deleted" (`deleted`); bulk deletes
and early permanent deletion are out of scope. On `deletion_unknown`, re-check the post and the
recently-deleted folder instead of deleting again. Failure artifacts contain account state and
screenshots — keep them out of Git and out of the chat.

Copy-ready examples: `scripts/examples/instagram_commands.ps1`, `.sh`,
`instagram_cli_template.py`.
