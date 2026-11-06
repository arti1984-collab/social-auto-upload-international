---
name: meta-upload
description: Log in to a Facebook Page and publish or schedule video and image posts, then verify or delete them with the `sau facebook-page` CLI. Use for Facebook Pages, not personal profiles.
license: MIT-0
---

# Facebook Page — publish, schedule, manage

Wraps the existing `sau facebook-page` CLI; do not reimplement browser logic. Instagram is
handled by the separate `instagram-upload` skill (standalone web session, not Business Suite).

No proxy by default; pass `--proxy` or set `SAU_FACEBOOK_PAGE_PROXY`. `--proxy ""` connects
directly.

```powershell
sau facebook-page login --account creator
sau facebook-page check --account creator
sau facebook-page upload-note --account creator --page "My Page" --images images/1.jpg --title "Title" --note "Text" --result .local/page-result.json
sau facebook-page upload-video --account creator --page "My Page" --file videos/demo.mp4 --title "Title" --desc "Text" --schedule "2026-10-21 10:30" --result .local/reel-result.json
```

- `--page` must be the exact Page name; `--tags` is a comma-separated list.
- Video and image posts accept `--schedule "YYYY-MM-DD HH:MM"`: the browser's **local time**, at least
  2 hours in the future. Omit it to publish
  immediately. The browser's own timezone applies, so convert other zones.
- Results default to `.local/meta-results/`; always pass `--result` so ids do not have to be
  copied by hand.
- Status values: `scheduled` (platform confirmed the schedule and the record was re-read),
  `published` (image post live), `processing` (video accepted and still being processed —
  not proof of a public, playable video; `content_id` may be missing yet),
  `submission_unknown` (not enough evidence — query the record, never re-submit).

Verify and delete by Page ID, Page name, content id and caption:

```powershell
sau facebook-page verify --account creator --page "My Page" --page-id "PAGE_ID" --content-id "CONTENT_ID" --expected-text "exact caption" --scheduled
sau facebook-page delete --account creator --page "My Page" --page-id "PAGE_ID" --content-id "CONTENT_ID" --expected-text "exact caption" --scheduled --result .local/delete-result.json
```

`--scheduled` selects the scheduled list; deleting there cancels the schedule and removes the
post permanently (`deleted`). For published posts omit the flag — the platform moves them to the
trash (`trashed`, removed after 30 days); early permanent deletion from the Page trash is not
implemented. Content ids can change once a scheduled post actually publishes, so manage published
posts with ids from the published list.

Only recently loaded lists are covered, so do not claim a full history search. Refuse to delete
when the Page, id or caption does not match exactly. After a timeout or disconnect, re-query
before retrying. Local media is never deleted.

Copy-ready examples: `scripts/examples/meta_commands.ps1`, `.sh`, `meta_cli_template.py`.
