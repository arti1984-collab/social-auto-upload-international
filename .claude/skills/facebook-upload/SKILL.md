---
name: facebook-upload
description: Log in to a Facebook profile and publish video or image posts immediately, then verify, trash or permanently delete the resulting post with the `sau facebook` CLI. Use for personal Facebook profiles (not Pages).
license: MIT-0
---

# Facebook profile — publish and manage

Uses the existing CLI. No proxy is configured by default (the browser uses the system network);
pass `--proxy "http://host:port"` or set `SAU_FACEBOOK_PROXY` when one is needed. `--proxy ""`
ignores the environment variable and connects directly.

```powershell
sau facebook login --account creator
sau facebook check --account creator
sau facebook upload-video --account creator --file videos/demo.mp4 --title "Title" --desc "Text" --tags life,sharing
sau facebook upload-note --account creator --images images/1.jpg images/2.jpg --title "Image title" --note "Text"
```

- Login happens in a visible Chrome; the session is stored as `cookies/facebook_creator.json`.
- `check` validates the profile session only — it says nothing about Page permissions or about
  whether a post was published.
- Title, description and tags are merged into one caption.
- Immediate publishing only: profile scheduling is not implemented. Scheduled posts must go
  through `facebook-page` (see the `meta-upload` skill).

Managing a post, once the original URL is known:

```powershell
sau facebook verify --account creator --post-url "URL" --owner-id "numeric author id" --expected-text "exact caption"
sau facebook delete --account creator --post-url "URL" --owner-id "numeric author id" --expected-text "exact caption" --result .local/trash-result.json
sau facebook delete --account creator --post-url "URL" --owner-id "numeric author id" --expected-text "exact caption" --from-trash --permanent --result .local/delete-result.json
```

Verify the signed-in user, the author, the post id and the caption before deleting. Deletion
moves the post to the trash (returned as `trashed`, removed by the platform after 30 days);
`--permanent` deletes immediately, and a post already in the trash additionally needs
`--from-trash`. Permanent deletion cannot be undone.

`verify --from-trash` searches the trash; `verify --deleted` only reports that the id is absent
from the trash (`absent_from_trash`) and is not proof of an earlier permanent deletion. Only
recently loaded posts are searched; if nothing matches or the caption is ambiguous, fail
explicitly instead of guessing.

Treat "success" as confirmed only when the platform showed the confirmation for this submission.
After a timeout or browser disconnect the result is unknown: check the profile or the trash first,
do not re-upload or re-delete. Deleting a remote post never deletes local media.

Copy-ready examples live in `scripts/examples/` (`facebook_commands.ps1`, `.sh`,
`facebook_cli_template.py`); they are not runtime dependencies and may create real posts.
