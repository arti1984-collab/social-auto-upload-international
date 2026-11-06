# CLI-Referenz / CLI reference

[Deutsch](#deutsch) · [English](#english)

## Deutsch

`sau` ist der einzige Einstiegspunkt. Subcommands: `youtube`, `facebook`, `facebook-page`,
`instagram`, `article`, `profile`, `status`. Für TikTok gibt es keinen CLI-Befehl (siehe
`.claude/skills/tiktok-upload/SKILL.md`).

Aktuelle Parameter immer selbst prüfen: `sau <plattform> --help`, `sau <plattform> upload-video --help`.
Zum Einstieg ins Projekt: [handbuch.md](./handbuch.md).

### Gemeinsame Konventionen

- `--account <name>` — lokaler Alias für eine gespeicherte Session (`cookies/…`); frei wählbar,
  ein Alias pro Account.
- `--result <pfad.json>` — wohin das Ergebnis-JSON geschrieben wird.
- `--proxy "http://host:port"` bzw. `--proxy ""` (Umgebungsvariable ignorieren, direkt verbinden).
  Umgebungsvariablen: `SAU_FACEBOOK_PROXY`, `SAU_FACEBOOK_PAGE_PROXY`, `SAU_INSTAGRAM_PROXY`.
- `--browser chrome|edge|chromium|opera-gx|firefox` — welcher Browser gesteuert wird. Ohne Angabe
  gilt `LOCAL_BROWSER` aus `conf.py`, dann `SAU_BROWSER`, sonst Chrome. Chrome, Edge, Chromium und
  Opera GX laufen über die Chromium-Engine (Opera GX wird automatisch in den üblichen
  Installationsordnern gesucht), Firefox über den Firefox-Build von Playwright; dafür einmalig
  `python -m playwright install firefox`. `--browser-path` zeigt auf die Programmmdatei, etwa bei einer
  Opera-GX-Installation an einem anderen Ort.
- `--profile` — statt einer Cookie-Datei ein persistentes Browserprofil führen
  (`profiles/<browser>/<account>`): der Login bleibt im Profil, es wird nichts exportiert. `--profile-dir`
  legt den Ort fest; `LOCAL_BROWSER_PROFILE = True` in `conf.py` macht es zum Standard.
- Videos: `--file`, `--title`, `--desc`, `--tags`. Bild-Posts: `--images`, `--title`, `--note`.
- Statuswerte im Ergebnis: `published` (bestätigt), `processing` (angenommen, in Arbeit),
  `scheduled` (Page-Vorplanung bestätigt), `submission_unknown` (unklar — am Account prüfen).

### YouTube

```bash
sau youtube login --account <name>
sau youtube check --account <name>
sau youtube upload-video --account <name> --file videos/demo.mp4 --title "Titel" --desc "Beschreibung" \
  --tags tag1,tag2 --playlist "Meine Serie" --visibility public
# YouTube-Scheduling ist im Browser-Flow nicht umgesetzt: --schedule wird abgelehnt,
# statt sofort zu veroeffentlichen. Termin im Studio selbst setzen.
```

Titel max. 100 Zeichen; `--visibility` = `public` | `unlisted` | `private`; `--thumbnail` setzt ein
Cover. Ein Upload veröffentlicht sofort; `--schedule` wird für YouTube mit einer Fehlermeldung
abgelehnt, weil der Studio-Dialog nicht automatisiert ist.

### Facebook-Profil

```bash
sau facebook login --account <name>
sau facebook check --account <name>
sau facebook upload-video --account <name> --file videos/demo.mp4 --title "Titel" --desc "Text" --tags a,b
sau facebook upload-note  --account <name> --images images/1.jpg images/2.jpg --title "Titel" --note "Text"
sau facebook verify --account <name> --post-url "<URL>" --owner-id "<ID>" --expected-text "Text"
sau facebook delete --account <name> --post-url "<URL>" --owner-id "<ID>" --expected-text "Text"
```

Titel, Beschreibung und Tags werden zu einer Bildunterschrift zusammengeführt. Kein Scheduling.
Löschen verschiebt in den Papierkorb (`trashed`, 30 Tage); `--permanent` löscht sofort,
`--from-trash` zusätzlich nötig, wenn das Werk schon im Papierkorb liegt.

### Facebook-Page

```bash
sau facebook-page login --account <name>
sau facebook-page check --account <name>
sau facebook-page upload-video --account <name> --page "Meine Page" --file videos/demo.mp4 \
  --title "Titel" --desc "Text" --schedule "2026-11-20 18:00" --result .local/page.json
sau facebook-page upload-note  --account <name> --page "Meine Page" --images images/1.jpg --title "Titel" --note "Text"
sau facebook-page verify --account <name> --page "Meine Page" --page-id "<ID>" --content-id "<ID>" --expected-text "Text" --scheduled
sau facebook-page delete --account <name> --page "Meine Page" --page-id "<ID>" --content-id "<ID>" --expected-text "Text" --scheduled
```

`--schedule` = **Peking-Zeit** (`Asia/Shanghai`), mindestens 2 Stunden in der Zukunft; der Browser
muss auf dieser Zeitzone laufen. Ergebnisse standardmäßig unter `.local/meta-results/`.

### Instagram

```bash
sau instagram login --account <name>
sau instagram check --account <name>
sau instagram upload-video --account <name> --file videos/demo.mp4 --thumbnail cover.png \
  --title "Titel" --desc "Text" --result .local/ig.json
sau instagram upload-note  --account <name> --images images/1.jpg images/2.jpg --title "Titel" --note "Text"
sau instagram verify --account <name> --post-url "<URL>" --expected-text "Text"
sau instagram delete --account <name> --post-url "<URL>" --expected-text "Text"
```

Reels (MP4/MOV) und Bild-Posts (JPG/JPEG/PNG/AVIF/HEIC/HEIF); Caption aus Titel, Text und Tags,
max. 2200 Zeichen. Kein Scheduling. Löschen verschiebt in „Recently deleted". `--headless`
schaltet den Kopfmodus ab (Login braucht das sichtbare Fenster).

### Status

```bash
sau status
```

Eine Zeile pro Plattform und Account: `COOKIE` zeigt, ob eine Cookie-Datei existiert, `PROFILES`
die gespeicherten Browser (`*` = hinterlegter Standard), `LAST USED` die jüngste Änderung und
`DEFAULT` das Standardprofil als `browser/account`. Der Befehl ändert nichts und legt nichts an.

`--verify` prüft zusätzlich jede Sitzung mit dem üblichen Plattform-Check und ergänzt die Spalte
`SESSION` (`valid`, `invalid`, `error`). Das startet pro Account einen Browser und dauert
dementsprechend; die Gründe für `invalid` und `error` stehen unter der Tabelle. Geprüft wird mit dem
konfigurierten Browser. `--verify-jobs N` legt fest, wie viele Prüfungen gleichzeitig laufen
(Standard 2, erlaubt 1–16); die Zeilenreihenfolge bleibt dabei unverändert.

### Profile

```bash
sau profile list                              # Browser, Account, Größe, letzte Nutzung
sau profile list --browser firefox
sau profile remove --account youtube_main --browser chrome
sau profile remove --platform youtube --account main --browser chrome
```

Profile entstehen nur mit `--profile` (oder `LOCAL_BROWSER_PROFILE = True`) und liegen unter
`profiles/<browser>/<account>`. `remove` löscht genau ein Profil; Cookie-Dateien und andere
Browser bleiben unberührt.

Statt Browser und Account getrennt zu nennen, wählt `--use-profile` ein vorhandenes Profil direkt:

```bash
sau profile list
sau youtube upload-video --use-profile firefox/youtube_main --file video.mp4 --title "Titel"
sau youtube upload-video --use-profile youtube_main --file video.mp4 --title "Titel"
```

Das Profil heißt `<platform>_<account>`; ohne Browser-Präfix wird es genommen, wenn es nur in
einem Browser existiert. `--use-profile` schaltet den Profilmodus ein und ersetzt damit
`--browser` und `--account`.

`profile use` macht ein Profil zum Standard, sodass der Account nicht in jedem Aufruf steht:

```bash
sau profile use firefox/youtube_main
sau youtube upload-video --file video.mp4 --title "Titel"   # nutzt firefox und youtube_main
sau profile use --clear                                      # Standard wieder entfernen
```

Ein Login legt das Profil selbst an und setzt es gleich als Standard — ein getrennter
`--profile`-Lauf entfällt:

```bash
sau youtube login --account main   # öffnet ein persistentes Profil, setzt youtube_main als Standard
```

Der Befehl schreibt `LOCAL_BROWSER`, `LOCAL_BROWSER_PROFILE = True` und `DEFAULT_PROFILE` in
`conf.py`; andere Zeilen und Kommentare bleiben unverändert. Der Standard gilt nur für seine
Plattform und nur, solange weder `--account` noch `--use-profile` angegeben ist. `sau profile list`
markiert ihn in der Spalte `DEFAULT`.

### Artikel-Rendering (lokal)

`upload-article` existierte nur für die entfernten chinesischen Plattformen; übrig ist der lokale
Renderer: `sau article setup`, `sau article themes`,
`sau article render --content-file examples/article.md --theme modern --output out.html`.
Details: [article.md](./article.md).

---

## English

`sau` is the only entry point. Subcommands: `youtube`, `facebook`, `facebook-page`, `instagram`,
`article`, `profile`, `status`. TikTok has no CLI command (see `.claude/skills/tiktok-upload/SKILL.md`).

Always verify flags yourself: `sau <platform> --help`, `sau <platform> upload-video --help`.
For a guided start: [handbuch.md](./handbuch.md).

### Shared conventions

- `--account <name>` — local alias for a saved session (`cookies/…`), one alias per account.
- `--result <path.json>` — where the result JSON is written.
- `--proxy "http://host:port"` or `--proxy ""` (ignore the environment variable, connect directly).
  Environment variables: `SAU_FACEBOOK_PROXY`, `SAU_FACEBOOK_PAGE_PROXY`, `SAU_INSTAGRAM_PROXY`.
- `--browser chrome|edge|chromium|opera-gx|firefox` — which browser is driven. Without the flag,
  `LOCAL_BROWSER` from `conf.py` applies, then `SAU_BROWSER`, then Chrome. Chrome, Edge, Chromium
  and Opera GX use the chromium engine (Opera GX is looked up in the usual install folders),
  Firefox uses Playwright's own Firefox build and needs `python -m playwright install firefox` once. `--browser-path`
  points at the browser program, e.g. an Opera GX install in an unusual location.
- `--profile` — keep a persistent browser profile (`profiles/<browser>/<account>`) instead of a
  cookie file: the login stays inside the profile and nothing is exported. `--profile-dir` sets the
  location; `LOCAL_BROWSER_PROFILE = True` in `conf.py` makes it the default.
- Videos: `--file`, `--title`, `--desc`, `--tags`. Image posts: `--images`, `--title`, `--note`.
- Result status values: `published` (confirmed), `processing` (accepted, in progress),
  `scheduled` (Page schedule confirmed), `submission_unknown` (unclear — check the account).

### YouTube

```bash
sau youtube login --account <name>
sau youtube check --account <name>
sau youtube upload-video --account <name> --file videos/demo.mp4 --title "Title" --desc "Description" \
  --tags tag1,tag2 --playlist "My series" --visibility public
# YouTube scheduling is not implemented in the browser flow: --schedule is rejected instead
# of publishing immediately. Pick the time in YouTube Studio.
```

Title ≤ 100 characters; `--visibility` = `public` | `unlisted` | `private`; `--thumbnail` sets a
cover. An upload publishes immediately; `--schedule` is rejected for YouTube with an error,
because the Studio dialog is not automated.

### Facebook profile

```bash
sau facebook login --account <name>
sau facebook check --account <name>
sau facebook upload-video --account <name> --file videos/demo.mp4 --title "Title" --desc "Text" --tags a,b
sau facebook upload-note  --account <name> --images images/1.jpg images/2.jpg --title "Title" --note "Text"
sau facebook verify --account <name> --post-url "<URL>" --owner-id "<ID>" --expected-text "Text"
sau facebook delete --account <name> --post-url "<URL>" --owner-id "<ID>" --expected-text "Text"
```

Title, description and tags are merged into one caption. No scheduling. Deletion moves the post
to the trash (`trashed`, 30 days); `--permanent` deletes immediately, and `--from-trash` is needed
additionally when the post already sits in the trash.

### Facebook Page

```bash
sau facebook-page login --account <name>
sau facebook-page check --account <name>
sau facebook-page upload-video --account <name> --page "My Page" --file videos/demo.mp4 \
  --title "Title" --desc "Text" --schedule "2026-11-20 18:00" --result .local/page.json
sau facebook-page upload-note  --account <name> --page "My Page" --images images/1.jpg --title "Title" --note "Text"
sau facebook-page verify --account <name> --page "My Page" --page-id "<ID>" --content-id "<ID>" --expected-text "Text" --scheduled
sau facebook-page delete --account <name> --page "My Page" --page-id "<ID>" --content-id "<ID>" --expected-text "Text" --scheduled
```

`--schedule` uses **Beijing time** (`Asia/Shanghai`) and must be at least 2 hours ahead; the
browser has to run in that timezone. Results default to `.local/meta-results/`.

### Instagram

```bash
sau instagram login --account <name>
sau instagram check --account <name>
sau instagram upload-video --account <name> --file videos/demo.mp4 --thumbnail cover.png \
  --title "Title" --desc "Text" --result .local/ig.json
sau instagram upload-note  --account <name> --images images/1.jpg images/2.jpg --title "Title" --note "Text"
sau instagram verify --account <name> --post-url "<URL>" --expected-text "Text"
sau instagram delete --account <name> --post-url "<URL>" --expected-text "Text"
```

Reels (MP4/MOV) and image posts (JPG/JPEG/PNG/AVIF/HEIC/HEIF); the caption combines title, text
and tags, at most 2200 characters. No scheduling. Deletion moves the post to "Recently deleted".
`--headless` disables the head mode (login needs the visible window).

### Status

```bash
sau status
```

One line per platform and account: `COOKIE` says whether a cookie file exists, `PROFILES` lists the
stored browsers (`*` marks the configured default), `LAST USED` the newest change and `DEFAULT` the
default profile as `browser/account`. The command changes and creates nothing.

`--verify` also checks every session with the platform's own check and adds a `SESSION` column
(`valid`, `invalid`, `error`). That starts one browser per account, so it is slow; the reasons for
`invalid` and `error` are printed below the table. Checking uses the configured browser.
`--verify-jobs N` sets how many checks run at once (default 2, allowed 1–16); the row order stays
the same.

### Profiles

```bash
sau profile list                              # browser, account, size, last use
sau profile list --browser firefox
sau profile remove --account youtube_main --browser chrome
sau profile remove --platform youtube --account main --browser chrome
```

Profiles only appear with `--profile` (or `LOCAL_BROWSER_PROFILE = True`) and live under
`profiles/<browser>/<account>`. `remove` deletes exactly one profile; cookie files and the other
browsers stay untouched.

Instead of naming the browser and the account separately, `--use-profile` selects a stored profile:

```bash
sau profile list
sau youtube upload-video --use-profile firefox/youtube_main --file video.mp4 --title "Title"
sau youtube upload-video --use-profile youtube_main --file video.mp4 --title "Title"
```

The profile is named `<platform>_<account>`; without a browser prefix it is used when it exists in
only one browser. `--use-profile` turns the profile mode on and replaces `--browser` and
`--account`.

`profile use` makes a profile the default, so the account is not repeated in every call:

```bash
sau profile use firefox/youtube_main
sau youtube upload-video --file video.mp4 --title "Title"   # uses firefox and youtube_main
sau profile use --clear                                     # drop the default again
```

A login creates the profile itself and stores it as the default right away, so no separate
`--profile` run is needed:

```bash
sau youtube login --account main   # opens a persistent profile, stores youtube_main as the default
```

The command writes `LOCAL_BROWSER`, `LOCAL_BROWSER_PROFILE = True` and `DEFAULT_PROFILE` into
`conf.py`; other lines and comments stay as they are. The default only applies to its platform and
only while neither `--account` nor `--use-profile` is given. `sau profile list` marks it in the
`DEFAULT` column.

### Local article rendering

`upload-article` only existed for the removed Chinese platforms; what remains is the local
renderer: `sau article setup`, `sau article themes`,
`sau article render --content-file examples/article.md --theme modern --output out.html`.
Details: [article.md](./article.md).
