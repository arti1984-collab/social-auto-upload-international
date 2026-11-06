# social-auto-upload-international

[Deutsch](#deutsch) · [English](#english)

Ein Fork von [dreammis/social-auto-upload](https://github.com/dreammis/social-auto-upload) (MIT),
beschränkt auf die internationalen Plattformen: **YouTube, Facebook-Profil, Facebook-Page,
Instagram und TikTok**. Die chinesischen Plattformen des Originals sind entfernt, die CLI spricht
Deutsch und Englisch, und sie steuert auf Wunsch **Chrome, Edge, Opera GX, Chromium oder
Firefox** — wahlweise mit Cookie-Datei oder mit einem persistenten Browserprofil.

---

## Deutsch

`social-auto-upload` veröffentlicht Videos und Bild-Posts automatisiert. Es nutzt **keine
offiziellen APIs**, sondern steuert einen Browser über `patchright` (Playwright-Fork) und klickt
mit gespeicherter Session im Creator-Studio. Deshalb funktioniert es auch dort, wo es keine
Upload-API gibt — und bricht, wenn eine Plattform ihr Web-UI umbaut.

### Plattformen

| Plattform | CLI | Video | Bild-Post | Zeitplan |
| --- | --- | --- | --- | --- |
| YouTube | `sau youtube` | ✅ | – | über YouTube Studio |
| Facebook-Profil | `sau facebook` | ✅ | ✅ | – |
| Facebook-Page | `sau facebook-page` | ✅ | ✅ | ✅ (Peking-Zeit) |
| Instagram | `sau instagram` | Reels | Einzelbild/Karussell | – |
| TikTok | – (Python-Uploader) | ✅ | – | via `publish_date` |

Ein `sau`-Befehl existiert für TikTok **nicht**; siehe
[`.claude/skills/tiktok-upload/SKILL.md`](./.claude/skills/tiktok-upload/SKILL.md).

### Browser

Ohne Angabe gilt `LOCAL_BROWSER` aus `conf.py`, dann `SAU_BROWSER`, sonst Chrome. Chrome, Edge,
Chromium und Opera GX laufen über die Chromium-Engine (Opera GX wird in den üblichen
Installationsordnern gesucht), Firefox über den Firefox-Build von Playwright.

```powershell
sau youtube check --account creator --browser firefox
sau youtube upload-video --browser opera-gx --account creator --file videos/demo.mp4 --title "Titel"
sau youtube check --browser chrome --browser-path "D:\Portable\chrome.exe"
```

Firefox braucht einmalig `python -m playwright install firefox`; Chromium kommt mit
`patchright install chromium`.

### Profile statt Cookie-Dateien

Ein Login schreibt die Session in ein persistentes Profil unter `profiles/<browser>/<account>`
und merkt sich das Profil als Standard. Danach brauchen Uploads weder `--account` noch
`--browser`:

```powershell
sau youtube login --account creator     # anmelden im sichtbaren Browser
sau youtube upload-video --file videos/demo.mp4 --title "Titel" --desc "Beschreibung"
```

Profile verwalten:

```powershell
sau profile list                        # Browser, Account, Größe, letzte Nutzung, Standard
sau profile use firefox/youtube_creator # dauerhaft als Standard in conf.py
sau profile use --clear                 # Standard entfernen
sau profile remove --account creator --browser chrome
sau youtube check --use-profile firefox/youtube_creator
```

`--profile` erzwingt den Profilmodus, `--profile-dir` legt den Ort der Profile fest,
`LOCAL_BROWSER_PROFILE = True` in `conf.py` macht ihn zum Standard. Ohne Profil entsteht wie
bisher eine Cookie-Datei unter `cookies/`.

### Status

```powershell
sau status                # schnell: was existiert, wann zuletzt genutzt, welches Profil ist Standard
sau status --verify       # zusätzlich jede Sitzung im Browser prüfen (valid / invalid / error)
sau status --verify --verify-jobs 4   # Prüfungen parallel, Standard 2
```

`--verify` nutzt die Checks der Plattformen, also dieselbe Logik wie `sau youtube check`. Es startet
pro Account einen Browser; Gründe für `invalid` und `error` stehen unter der Tabelle.

### Installation

```powershell
uv venv
.venv\Scripts\Activate.ps1        # Linux/macOS: source .venv/bin/activate
uv pip install -e .               # registriert den Befehl `sau`
patchright install chromium       # und für Firefox: python -m playwright install firefox
Copy-Item conf.example.py conf.py # dann LOCAL_BROWSER etc. setzen
sau --help
```

Details: [docs/install.md](./docs/install.md). Update: [docs/update.md](./docs/update.md).
Alle Schalter: [docs/CLI.md](./docs/CLI.md).

### Erste Schritte

```powershell
sau youtube login --account creator
sau youtube check --account creator
sau youtube upload-video --account creator --file videos/demo.mp4 --title "Titel" --desc "Beschreibung" --tags a,b --visibility public

sau facebook upload-video --account creator --file videos/demo.mp4 --title "Titel" --desc "Text"
sau facebook-page upload-video --account creator --page "Meine Page" --file videos/demo.mp4 --title "Titel" --desc "Text" --schedule "2026-11-20 18:00"
sau instagram upload-note --account creator --images images/1.jpg images/2.jpg --title "Titel" --note "Text"
```

`--account` ist nur ein lokaler Alias für eine gespeicherte Session. Ergebnisse landen als JSON
unter `.local/` bzw. am mit `--result` angegebenen Pfad.

### Wichtig zu wissen

- Login, Captchas und 2FA machst **du** im sich öffnenden Browserfenster.
- `submission_unknown` heißt „unklar", nicht „fehlgeschlagen": erst am Account nachsehen, nicht
  blind erneut hochladen.
- Facebook-Page-Zeiten sind **Peking-Zeit** (`Asia/Shanghai`), mindestens 2 Stunden in der Zukunft.
- Instagram kann nicht planen, Facebook-Profile auch nicht.
- YouTube: Titel max. 100 Zeichen; Scheduling über den Studio-Dialog, dessen Datumsfelder du
  danach prüfen musst.
- Cookie-Automatisierung verstößt gegen die Nutzungsbedingungen der Plattformen und kann zu
  Risk-Control oder Sperren führen.
- Selektoren brechen, wenn eine Plattform ihr Web-UI umbaut; dann stoppen statt raten.

### Struktur

`uploader/` enthält die Browser-Flows (`meta_uploader` = Facebook + Page + Instagram,
`tk_uploader` = TikTok, `youtube_uploader`), `sau_commands/` die CLI-Parameter je Plattform samt
`profile.py` und `status.py`, `utils/browser.py` die Browser- und Profil-Auswahl,
`.claude/skills/` die Agent-Skills, `docs/` diese Dokumentation.
Agent-Regeln: [AGENTS.md](./AGENTS.md).

### Lizenz

MIT, siehe [LICENSE](./LICENSE). Die Skills unter `.claude/skills/` stehen wie im Original unter
MIT-0.

---

## English

A fork of [dreammis/social-auto-upload](https://github.com/dreammis/social-auto-upload) (MIT),
limited to the international platforms: **YouTube, Facebook profile, Facebook Page, Instagram and
TikTok**. The Chinese platforms of the original are gone, the CLI speaks German and English, and
it can drive **Chrome, Edge, Opera GX, Chromium or Firefox** — either with a cookie file or with a
persistent browser profile.

### How it works

It publishes videos and image posts automatically. It uses **no official APIs**: it drives a
browser through `patchright` (a Playwright fork) and clicks through the creator studios with a
saved session. That is why it works where no upload API exists — and why it breaks when a platform
redesigns its web UI.

### Platforms

| Platform | CLI | Video | Image post | Scheduling |
| --- | --- | --- | --- | --- |
| YouTube | `sau youtube` | yes | – | via YouTube Studio |
| Facebook profile | `sau facebook` | yes | yes | – |
| Facebook Page | `sau facebook-page` | yes | yes | yes (Beijing time) |
| Instagram | `sau instagram` | Reels | single image / carousel | – |
| TikTok | – (Python uploader) | yes | – | via `publish_date` |

There is **no** `sau` command for TikTok; see
[`.claude/skills/tiktok-upload/SKILL.md`](./.claude/skills/tiktok-upload/SKILL.md).

### Browsers

Without a flag the order is `LOCAL_BROWSER` from `conf.py`, then `SAU_BROWSER`, then Chrome.
Chrome, Edge, Chromium and Opera GX run on the Chromium engine (Opera GX is discovered in its
usual install folders), Firefox on Playwright's Firefox build.

```powershell
sau youtube check --account creator --browser firefox
sau youtube upload-video --browser opera-gx --account creator --file videos/demo.mp4 --title "Title"
sau youtube check --browser chrome --browser-path "D:\Portable\chrome.exe"
```

Firefox needs `python -m playwright install firefox` once; Chromium comes with
`patchright install chromium`.

### Profiles instead of cookie files

A login writes the session into a persistent profile under `profiles/<browser>/<account>` and
stores that profile as the default. Afterwards uploads need neither `--account` nor `--browser`:

```powershell
sau youtube login --account creator     # sign in yourself in the visible browser
sau youtube upload-video --file videos/demo.mp4 --title "Title" --desc "Description"
```

Manage profiles:

```powershell
sau profile list                        # browser, account, size, last used, default
sau profile use firefox/youtube_creator # store it as the default in conf.py
sau profile use --clear                 # drop the default
sau profile remove --account creator --browser chrome
sau youtube check --use-profile firefox/youtube_creator
```

`--profile` forces profile mode, `--profile-dir` sets where profiles live, and
`LOCAL_BROWSER_PROFILE = True` in `conf.py` makes it the default. Without a profile you get a
cookie file under `cookies/`, as before.

### Status

```powershell
sau status                # fast: what exists, when it was last used, which profile is the default
sau status --verify       # additionally check every session in a browser (valid / invalid / error)
sau status --verify --verify-jobs 4   # parallel checks, default 2
```

`--verify` reuses the platform checks, so it applies the same logic as `sau youtube check`. It
starts one browser per account; the reasons for `invalid` and `error` are printed below the table.

### Install

```powershell
uv venv
.venv\Scripts\Activate.ps1        # Linux/macOS: source .venv/bin/activate
uv pip install -e .               # registers the `sau` command
patchright install chromium       # and for Firefox: python -m playwright install firefox
Copy-Item conf.example.py conf.py # then set LOCAL_BROWSER etc.
sau --help
```

See [docs/install.md](./docs/install.md), [docs/update.md](./docs/update.md) and the full flag
reference in [docs/CLI.md](./docs/CLI.md).

### First steps

```powershell
sau youtube login --account creator
sau youtube check --account creator
sau youtube upload-video --account creator --file videos/demo.mp4 --title "Title" --desc "Description" --tags a,b --visibility public

sau facebook upload-video --account creator --file videos/demo.mp4 --title "Title" --desc "Text"
sau facebook-page upload-video --account creator --page "My Page" --file videos/demo.mp4 --title "Title" --desc "Text" --schedule "2026-11-20 18:00"
sau instagram upload-note --account creator --images images/1.jpg images/2.jpg --title "Title" --note "Text"
```

`--account` is only a local alias for a saved session. Results are written as JSON to `.local/` or
to the path given with `--result`.

### Worth knowing

- Sign-in, captchas and 2FA are done by you in the browser window that opens.
- `submission_unknown` means "unclear", not "failed": check the account before re-uploading.
- Facebook Page schedules use **Beijing time** (`Asia/Shanghai`) and must be at least 2 hours ahead.
- Instagram and Facebook profiles cannot schedule.
- YouTube: title ≤ 100 characters; scheduling uses the Studio dialog, so verify the date fields.
- Cookie automation violates the platforms' terms of service and can trigger risk control or
  account blocks.
- Selectors break when a platform redesigns its web UI; stop and report instead of guessing.

### Layout

`uploader/` holds the browser flows (`meta_uploader` = Facebook + Page + Instagram,
`tk_uploader` = TikTok, `youtube_uploader`), `sau_commands/` the per-platform CLI arguments
including `profile.py` and `status.py`, `utils/browser.py` the browser and profile selection,
`.claude/skills/` the agent skills, `docs/` this documentation. Agent rules:
[AGENTS.md](./AGENTS.md).

### License

MIT, see [LICENSE](./LICENSE). The skills in `.claude/skills/` are MIT-0, as upstream.
