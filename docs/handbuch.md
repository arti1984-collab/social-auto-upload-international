# Handbuch / Handbook

[Deutsch](#deutsch) · [English](#english)

Dieses Handbuch erklärt das Projekt von Anfang bis Ende: was es tut, wie es aufgebaut ist, wie du
es einrichtest, wie du pro Plattform veröffentlichst und was du tun kannst, wenn etwas klemmt.
Es ersetzt keine Detailreferenz — Flag für Flag steht alles in [CLI.md](./CLI.md).

This handbook explains the project end to end: what it does, how it is built, how to set it up,
how to publish on each platform and what to do when something gets stuck. It is not a flag
reference — that is [CLI.md](./CLI.md).

---

## Deutsch

### 1. Was das Projekt macht

`social-auto-upload-international` veröffentlicht Videos und Bild-Posts auf **YouTube,
Facebook-Profil, Facebook-Page, Instagram und TikTok**. Es benutzt **keine offiziellen APIs**,
sondern steuert einen echten Browser über `patchright` (ein Playwright-Fork) und klickt mit einer
gespeicherten Session durch die Creator-Studios.

Daraus folgen zwei Dinge, die du kennen solltest:

- Es funktioniert auch dort, wo es keine Upload-API gibt — aber es **bricht**, wenn eine Plattform
  ihr Web-UI umbaut. Dann ist Stoppen und Melden richtig, nicht Raten.
- Cookie-Automatisierung verstößt gegen die Nutzungsbedingungen der Plattformen und kann
  Risk-Control oder Sperren auslösen. Für ein wichtiges Konto ist das ein echtes Risiko.

| Plattform | Einstieg | Video | Bild-Post | Zeitplan |
| --- | --- | --- | --- | --- |
| YouTube | `sau youtube` | ja | – | im Studio selbst |
| Facebook-Profil | `sau facebook` | ja | ja | – |
| Facebook-Page | `sau facebook-page` | ja | ja | ja (lokale Zeit) |
| Instagram | `sau instagram` | Reels | Einzelbild/Karussell | – |
| TikTok | Python-Uploader (kein CLI) | ja | ja (1–35 Bilder) | via `publish_date` |

### 2. Wie es aufgebaut ist

| Ort | Inhalt |
| --- | --- |
| `sau_cli.py` | Einstiegspunkt, baut den Argumentbaum und verteilt an die Plattform |
| `sau_commands/` | ein Modul pro Plattform (`youtube.py`, `facebook.py`, …), `profile.py`, `status.py` |
| `uploader/` | die eigentlichen Browser-Flows: `youtube_uploader`, `meta_uploader` (Facebook, Page, Instagram), `tk_uploader` (TikTok) |
| `utils/browser.py` | Browser- und Profilauswahl, `open_session`, `launch_persistent` |
| `conf.py` | deine Konfiguration (nicht im Repo, aus `conf.example.py` erzeugt) |
| `cookies/` | Cookie-Dateien der Sessions (nicht im Repo) |
| `profiles/` | persistente Browserprofile je Browser/Account (nicht im Repo) |
| `.local/` | Ergebnis-JSONs der Läufe (nicht im Repo) |
| `logs/` | Lauf-Protokolle (nicht im Repo) |
| `.claude/skills/` | Anleitungen für Agenten je Plattform |

Ein Upload läuft immer in denselben fünf Schritten:

```
1. CLI liest Argumente        --account, --browser, --file, --title, …
2. Browser wählen             --browser → SAU_BROWSER → LOCAL_BROWSER → chrome
3. Session laden              Cookie-Datei ODER persistentes Profil
4. Flow im Studio             Upload, Titel/Text, Sichtbarkeit, Termin, Post
5. Ergebnis schreiben         JSON mit published / processing / scheduled / submission_unknown
```

Der letzte Schritt ist der wichtigste: **`submission_unknown` heißt „unklar", nicht
„fehlgeschlagen".** Sieh am Account nach, ob der Post da ist, statt blind erneut hochzuladen.

### 3. Installation

```powershell
uv venv
.venv\Scripts\Activate.ps1          # Linux/macOS: source .venv/bin/activate
uv pip install -e .                 # registriert `sau`
patchright install chromium         # Firefox nur bei Bedarf: python -m playwright install firefox
Copy-Item conf.example.py conf.py   # Linux/macOS: cp conf.example.py conf.py
sau --help
```

Voraussetzungen: Python 3.10–3.12, `uv` und ein Browser. Chrome, Edge und Opera GX werden aus
einer normalen Installation genommen; ohne diese läuft das von `patchright` geladene Chromium.
Details: [install.md](./install.md), Updates: [update.md](./update.md).

Wenn `sau` nicht gefunden wird: Ist die venv aktiv, und lief `uv pip install -e .`?

### 4. Die drei Grundbegriffe

**Account-Alias (`--account`).** Nur ein lokaler Name für eine gespeicherte Session, zum Beispiel
`--account creator`. Er hat nichts mit dem Plattform-Login zu tun und ist frei wählbar; ein Alias
pro Account.

**Cookie-Datei oder Profil.** Zwei Wege, dieselbe Session zu behalten:

| | Cookie-Datei | Persistentes Profil |
| --- | --- | --- |
| Ort | `cookies/<plattform>/<alias>.json` | `profiles/<browser>/<plattform>_<alias>` |
| Anlegen | ohne `--profile` | `--profile`, `LOCAL_BROWSER_PROFILE = True` oder jeder `login` |
| Vorteil | klein, portabel | näher am echten Browser, weniger Bot-Spuren |
| Nachteil | Export nötig, schnell veraltet | größer, an einen Browser gebunden |

Ein `sau <plattform> login` legt **immer** ein Profil an und setzt es gleich als Standard. Danach
brauchen Uploads weder `--account` noch `--browser`.

**Ergebnis-Status.** `published` (bestätigt), `processing` (angenommen, läuft noch), `scheduled`
(Page-Termin bestätigt), `submission_unknown` (unklar — nachsehen).

### 5. Erste Einrichtung, Schritt für Schritt

```powershell
# 1. Konfiguration anlegen und Browser setzen
Copy-Item conf.example.py conf.py
#    in conf.py: LOCAL_BROWSER = "chrome" | "edge" | "chromium" | "opera-gx" | "firefox"

# 2. Anmelden — das Browserfenster öffnet sich, DU meldest dich an (auch 2FA/Captcha)
sau youtube login --account creator

# 3. Prüfen, ob die Session gilt
sau youtube check --account creator

# 4. Erster Test-Upload, noch nicht öffentlich
sau youtube upload-video --account creator --file videos/demo.mp4 --title "Test" --visibility private
```

Punkt 2 ist bewusst Handarbeit: Login, Captchas und 2FA machst **du** im sichtbaren Fenster. Das
Projekt fragt nie nach Passwörtern und tippt keine Zugangsdaten ein.

### 6. Veröffentlichen pro Plattform

#### YouTube

```powershell
sau youtube login --account creator
sau youtube check --account creator
sau youtube upload-video --account creator --file videos/demo.mp4 --title "Titel" --desc "Beschreibung" ^
  --tags tag1,tag2 --playlist "Meine Serie" --visibility public --thumbnail cover.png
```

- Titel höchstens 100 Zeichen; `--visibility` = `public` | `unlisted` | `private`.
- **Ein Upload veröffentlicht sofort.** `--schedule` wird abgelehnt, weil der Studio-Dialog nicht
  automatisiert ist — den Termin setzt du im Studio selbst.
- `--playlist` ordnet das Video einer vorhandenen Playlist zu.

#### Facebook-Profil

```powershell
sau facebook login --account creator
sau facebook upload-video --account creator --file videos/demo.mp4 --title "Titel" --desc "Text" --tags a,b
sau facebook upload-note  --account creator --images images/1.jpg images/2.jpg --title "Titel" --note "Text"
sau facebook verify --account creator --post-url "<URL>" --owner-id "<ID>" --expected-text "Text"
sau facebook delete --account creator --post-url "<URL>" --owner-id "<ID>" --expected-text "Text"
```

Titel, Beschreibung und Tags werden zu **einer** Bildunterschrift zusammengeführt. Kein
Scheduling. Löschen verschiebt in den Papierkorb (`trashed`, 30 Tage); `--permanent` löscht sofort,
`--from-trash` ist zusätzlich nötig, wenn der Post schon im Papierkorb liegt.

#### Facebook-Page

```powershell
sau facebook-page login --account creator
sau facebook-page upload-video --account creator --page "Meine Page" --file videos/demo.mp4 ^
  --title "Titel" --desc "Text" --schedule "2026-11-20 18:00" --result .local/page.json
sau facebook-page upload-note --account creator --page "Meine Page" --images images/1.jpg --title "Titel" --note "Text"
```

`--schedule` gilt in der **lokalen Zeit des Rechners**, auf dem der Browser läuft, und muss
mindestens zwei Stunden in der Zukunft liegen. Ergebnisse landen standardmäßig unter
`.local/meta-results/`.

#### Instagram

```powershell
sau instagram login --account creator
sau instagram upload-video --account creator --file videos/demo.mp4 --thumbnail cover.png --title "Titel" --desc "Text"
sau instagram upload-note  --account creator --images images/1.jpg images/2.jpg --title "Titel" --note "Text"
sau instagram verify --account creator --post-url "<URL>" --expected-text "Text"
sau instagram delete --account creator --post-url "<URL>" --expected-text "Text"
```

Reels aus MP4/MOV, Bilder als JPG/JPEG/PNG/AVIF/HEIC/HEIF; die Caption entsteht aus Titel, Text und
Tags (max. 2200 Zeichen). Kein Scheduling. Löschen verschiebt nach „Recently deleted".

#### TikTok (kein CLI)

Für TikTok gibt es **keinen** `sau tiktok`-Befehl. Der Uploader ist eine Python-Klasse; das
vollständige Rezept steht in [`.claude/skills/tiktok-upload/SKILL.md`](../.claude/skills/tiktok-upload/SKILL.md).

```python
import asyncio
from pathlib import Path

import utils.browser as b
from uploader.tk_uploader.main_chrome import TiktokVideo

b.set_profile_root(Path("profiles"))
b.set_profile_mode(True)

async def main():
    # Video: ein Pfad / eine Liste mit einem Pfad
    video = TiktokVideo(
        "Titel",
        "videos/demo.mp4",
        ["tag1", "tag2"],
        0,                              # 0 = sofort, sonst datetime für die Planung
        "main.json",                   # Alias der Session im Profil
        visibility="private",           # public | friends | private
    )
    await video.main()

    # Bilder: Liste mit 1–35 Pfaden (jpg/jpeg/png/webp/heic)
    photos = TiktokVideo("Titel", ["videos/a.png", "videos/b.png"], ["tag"], 0,
                         "main.json", visibility="private")
    await photos.main()

asyncio.run(main())
```

Wichtig bei TikTok:

- **Sichtbarkeit wird geprüft, nicht nur geklickt.** Der Uploader wählt die Zielgruppe im
  Combobox (`[data-e2e="video_visibility_container"]`), liest das Label zurück und bricht **vor**
  dem Post ab, wenn es nicht bestätigt ist. Ein unbestätigter Privat-Upload wird also abgebrochen,
  nicht öffentlich veröffentlicht.
- **Eigenes Browserfenster statt Bot-Browser.** Wenn TikTok den gestarteten Chromium mit
  „Access Denied" (Akamai) abweist, starte deinen eigenen Browser mit offenem Debug-Port und
  übergib die Adresse als `cdp_url="http://127.0.0.1:9222"`. Der Uploader hängt sich dann an
  dein Fenster, benutzt einen **bereits geöffneten** Studio-Tab, lädt nichts neu und lässt den Tab
  am Ende offen.

  ```powershell
  # Opera GX komplett schließen, dann mit Debug-Port starten
  & "$env:LOCALAPPDATA\Programs\Opera GX\opera.exe" --remote-debugging-port=9222
  ```

  Danach einmal `https://www.tiktok.com/tiktokstudio/upload` in diesem Fenster öffnen, und den
  Uploader mit `cdp_url` starten. Er benutzt diesen Tab unverändert.
- Titel und Tags, aber **keine** Beschreibung: `TiktokVideo` kennt nur Titel und Tags.

### 7. Sichtbarkeit und Zeitplanung

| Plattform | Sichtbarkeit | Termin |
| --- | --- | --- |
| YouTube | `--visibility public\|unlisted\|private` | nein, im Studio setzen |
| Facebook-Profil | über den Post selbst | nein |
| Facebook-Page | über den Post selbst | `--schedule`, lokale Zeit, min. 2 h vorher |
| Instagram | über den Post selbst | nein |
| TikTok | `visibility="public"\|"friends"\|"private"` | `publish_date` als `datetime` |

Für Tests immer zuerst `private` (TikTok: „Only you") bzw. `unlisted`/`private` (YouTube) wählen und
im Studio gegenprüfen, bevor etwas öffentlich wird.

### 8. Profile und Sessions verwalten

```powershell
sau profile list                        # Browser, Account, Größe, letzte Nutzung, Standard
sau profile use firefox/youtube_creator # dauerhaft als Standard in conf.py
sau profile use --clear                 # Standard entfernen
sau profile remove --account creator --browser chrome
sau youtube upload-video --use-profile firefox/youtube_creator --file video.mp4 --title "Titel"
sau status                              # Übersicht: Cookie, Profile, letzte Nutzung, Standard
sau status --verify                     # zusätzlich jede Session im Browser prüfen
sau status --verify --verify-jobs 4     # parallele Prüfungen (Standard 2, erlaubt 1–16)
```

`--use-profile` ersetzt `--browser` und `--account` in einem Schritt. `status` ändert nichts und legt
nichts an; `--verify` startet pro Account einen Browser und kann deshalb dauern.

### 9. Wo deine Daten liegen

| Ort | Was | Im Repo? |
| --- | --- | --- |
| `conf.py` | deine Konfiguration | nein, ignoriert |
| `cookies/` | Cookie-Dateien der Sessions | nein, ignoriert |
| `profiles/` | Browserprofile inklusive Login | nein, ignoriert |
| `.local/` | Ergebnis-JSONs | nein, ignoriert |
| `logs/` | Lauf-Protokolle | nein, ignoriert |
| `videos/`, `images/` | deine Medien | Demo-Dateien ja, eigene Uploads nein |

Das Repository ist öffentlich. Vor jedem Commit und Push gilt deshalb die Regel aus
[`AGENTS.md`](../AGENTS.md): prüfen, ob persönliche Daten mitgehen, und das Ergebnis berichten.
`profiles/` ist der sensibelste Ordner überhaupt — dort liegt die echte, angemeldete Sitzung.

### 10. Wenn etwas schiefgeht

| Symptom | Ursache | Was tun |
| --- | --- | --- |
| `Access Denied`, `Reference #18…`, `errors.edgesuite.net` | Akamai-Bot-Abwehr gegen den gestarteten Browser | Eigenes Browserfenster per `cdp_url` benutzen (TikTok) bzw. später erneut versuchen; nicht in Schleife wiederholen |
| `submission_unknown` | Plattform hat nicht eindeutig bestätigt | Im Account/Studio nachsehen; erst dann erneut hochladen |
| `invalid` bei `sau status --verify` | Session abgelaufen | `sau <plattform> login --account <alias>` |
| Browser nicht gefunden | Chrome/Edge/Opera GX fehlt oder liegt ungewöhnlich | `--browser-path` setzen oder `patchright install chromium` |
| „Select video"/„Post" nicht gefunden | Plattform hat das UI umgebaut | Stoppen und melden — nicht raten |
| Post-Button bleibt grau | Upload wird noch verarbeitet oder ist fehlgeschlagen | Lauf abbrechen lassen, im Studio prüfen |
| `sau` nicht gefunden | venv nicht aktiv oder nicht installiert | venv aktivieren, `uv pip install -e .` |
| YouTube: `--schedule` abgelehnt | absichtlich nicht umgesetzt | Termin im YouTube Studio setzen |

### 11. Schonend arbeiten

Die Plattformen drosseln verdächtiges Verhalten. Deshalb:

- **Ein Lauf, dann Pause.** Nicht mehrere Uploads oder Prüfungen unmittelbar hintereinander.
- **Nicht in Schleifen wiederholen.** Nach einer Blockseite oder einem Fehler warten, nicht sofort
  erneut versuchen — jeder Versuch verlängert die Sperre.
- **Zuerst privat testen** und die Sichtbarkeit im Studio gegenprüfen.
- **Ein Test pro Änderung**, nicht drei parallel.

### 12. Befehls-Cheatsheet

```powershell
sau --help                              # Übersicht
sau <plattform> --help                  # Aktionen der Plattform
sau <plattform> <aktion> --help         # alle Schalter einer Aktion

sau <plattform> login --account <alias>
sau <plattform> check --account <alias>

sau youtube        upload-video --file v.mp4 --title "Titel" --desc "Text" --tags a,b --visibility private
sau facebook       upload-video --file v.mp4 --title "Titel" --desc "Text"
sau facebook       upload-note  --images 1.jpg 2.jpg --title "Titel" --note "Text"
sau facebook-page  upload-video --page "Page" --file v.mp4 --title "Titel" --desc "Text" --schedule "2026-11-20 18:00"
sau instagram      upload-video --file v.mp4 --thumbnail c.png --title "Titel" --desc "Text"
sau instagram      upload-note  --images 1.jpg 2.jpg --title "Titel" --note "Text"

sau profile list | use <browser/profil> | remove --account <alias> --browser <browser>
sau status [--verify] [--verify-jobs N]
```

### 13. Weiterlesen

- [README.md](../README.md) — Überblick, Deutsch und Englisch
- [CLI.md](./CLI.md) — jeder Schalter mit Bedeutung
- [install.md](./install.md) · [update.md](./update.md) — Einrichtung und Updates
- [article.md](./article.md) — lokaler Artikel-Renderer
- [`.claude/skills/`](../.claude/skills/) — Plattform-Anleitungen für Agenten
- [`AGENTS.md`](../AGENTS.md) — verbindliche Regeln für die Arbeit am Projekt

---

## English

### 1. What the project does

`social-auto-upload-international` publishes videos and image posts to **YouTube, Facebook
profile, Facebook Page, Instagram and TikTok**. It uses **no official APIs**: it drives a real
browser through `patchright` (a Playwright fork) and clicks through the creator studios with a
saved session.

Two consequences matter:

- It works where no upload API exists — and it **breaks** when a platform redesigns its web UI.
  Stopping and reporting is then correct, guessing is not.
- Cookie automation violates the platforms' terms of service and can trigger risk control or
  account blocks. On an important account that is a real risk.

| Platform | Entry point | Video | Image post | Scheduling |
| --- | --- | --- | --- | --- |
| YouTube | `sau youtube` | yes | – | in Studio yourself |
| Facebook profile | `sau facebook` | yes | yes | – |
| Facebook Page | `sau facebook-page` | yes | yes | yes (local time) |
| Instagram | `sau instagram` | Reels | single image/carousel | – |
| TikTok | Python uploader (no CLI) | yes | yes (1–35 images) | via `publish_date` |

### 2. How it is built

| Location | Contents |
| --- | --- |
| `sau_cli.py` | entry point, builds the argument tree and dispatches per platform |
| `sau_commands/` | one module per platform, plus `profile.py` and `status.py` |
| `uploader/` | the browser flows: `youtube_uploader`, `meta_uploader` (Facebook, Page, Instagram), `tk_uploader` (TikTok) |
| `utils/browser.py` | browser and profile selection, `open_session`, `launch_persistent` |
| `conf.py` | your configuration (not in the repo, created from `conf.example.py`) |
| `cookies/`, `profiles/`, `.local/`, `logs/` | sessions, browser profiles, result JSON, run logs — all local |

Every upload follows the same five steps:

```
1. CLI reads arguments      --account, --browser, --file, --title, …
2. Pick the browser         --browser → SAU_BROWSER → LOCAL_BROWSER → chrome
3. Load the session         cookie file OR persistent profile
4. Run the studio flow      upload, title/text, visibility, schedule, post
5. Write the result         JSON with published / processing / scheduled / submission_unknown
```

`submission_unknown` means **"unclear", not "failed"**: check the account instead of re-uploading.

### 3. Install

```powershell
uv venv
.venv\Scripts\Activate.ps1          # Linux/macOS: source .venv/bin/activate
uv pip install -e .                 # registers `sau`
patchright install chromium         # Firefox only when needed: python -m playwright install firefox
Copy-Item conf.example.py conf.py
sau --help
```

Requirements: Python 3.10–3.12, `uv` and a browser. Details: [install.md](./install.md),
updates: [update.md](./update.md).

### 4. Three basic concepts

**Account alias (`--account`).** A local name for a saved session, e.g. `--account creator`. It has
nothing to do with the platform login; one alias per account.

**Cookie file or profile.**

| | Cookie file | Persistent profile |
| --- | --- | --- |
| Location | `cookies/<platform>/<alias>.json` | `profiles/<browser>/<platform>_<alias>` |
| Created by | no `--profile` | `--profile`, `LOCAL_BROWSER_PROFILE = True`, or any `login` |
| Pro | small, portable | closer to a real browser, fewer bot traces |
| Con | must be exported, goes stale | larger, tied to one browser |

`sau <platform> login` always creates a profile and stores it as the default, so later uploads need
neither `--account` nor `--browser`.

**Result status.** `published` (confirmed), `processing` (accepted, still running), `scheduled`
(Page schedule confirmed), `submission_unknown` (unclear — check the account).

### 5. First-time setup

```powershell
Copy-Item conf.example.py conf.py     # then set LOCAL_BROWSER
sau youtube login --account creator   # the browser opens; YOU sign in (2FA, captcha)
sau youtube check --account creator
sau youtube upload-video --account creator --file videos/demo.mp4 --title "Test" --visibility private
```

Sign-in, captchas and 2FA are done by you in the visible window; the project never asks for
passwords and never types credentials.

### 6. Publishing per platform

**YouTube** — title ≤ 100 characters, `--visibility public|unlisted|private`, `--thumbnail`,
`--playlist`. An upload publishes immediately; `--schedule` is rejected on purpose because the
Studio dialog is not automated.

**Facebook profile** — `upload-video` / `upload-note`; title, description and tags are merged into
one caption; no scheduling; `delete` moves to the trash (30 days), `--permanent` deletes at once
and `--from-trash` is needed when the post already sits there.

**Facebook Page** — same commands plus `--page "My Page"`. `--schedule` uses the browser's **local
time**, must be at least two hours ahead, and results default to `.local/meta-results/`.

**Instagram** — Reels from MP4/MOV, images as JPG/JPEG/PNG/AVIF/HEIC/HEIF, caption from title, text
and tags (≤ 2200 characters), no scheduling, `delete` moves to "Recently deleted".

**TikTok** — there is **no** `sau tiktok` command; use the Python class (full recipe in
[`.claude/skills/tiktok-upload/SKILL.md`](../.claude/skills/tiktok-upload/SKILL.md)):

```python
import asyncio
from pathlib import Path

import utils.browser as b
from uploader.tk_uploader.main_chrome import TiktokVideo

b.set_profile_root(Path("profiles"))
b.set_profile_mode(True)

async def main():
    video = TiktokVideo("Title", "videos/demo.mp4", ["tag"], 0,
                        "main.json", visibility="private")
    await video.main()

    photos = TiktokVideo("Title", ["videos/a.png", "videos/b.png"], ["tag"], 0,
                         "main.json", visibility="private")   # 1–35 images
    await photos.main()

asyncio.run(main())
```

- The audience is selected in the composer's combobox and **read back**; the uploader aborts
  **before** clicking Post when the label is missing or unconfirmed, so an unconfirmed private
  upload never goes public.
- If TikTok answers with "Access Denied" (Akamai) for the launched Chromium, start your own browser
  with an open debug port and pass `cdp_url="http://127.0.0.1:9222"`. The uploader then attaches to
  your window, **reuses an already open** studio tab, loads nothing again and leaves the tab open.
- `TiktokVideo` takes a title and tags, but no description.

### 7. Visibility and scheduling

| Platform | Visibility | Schedule |
| --- | --- | --- |
| YouTube | `--visibility public\|unlisted\|private` | no, set it in Studio |
| Facebook profile | in the post itself | no |
| Facebook Page | in the post itself | `--schedule`, local time, ≥ 2 h ahead |
| Instagram | in the post itself | no |
| TikTok | `visibility="public"\|"friends"\|"private"` | `publish_date` as `datetime` |

Always test privately (`private` / `unlisted`) and verify in the studio before anything goes public.

### 8. Profiles and sessions

```powershell
sau profile list                        # browser, account, size, last use, default
sau profile use firefox/youtube_creator # store as the default in conf.py
sau profile use --clear
sau profile remove --account creator --browser chrome
sau youtube upload-video --use-profile firefox/youtube_creator --file video.mp4 --title "Title"
sau status [--verify] [--verify-jobs N]
```

`--use-profile` replaces `--browser` and `--account`. `status` changes nothing; `--verify` starts
one browser per account and therefore takes a while.

### 9. Where your data lives

`conf.py`, `cookies/`, `profiles/`, `.local/` and `logs/` stay local and are ignored by Git.
`profiles/` is the most sensitive folder of all — it contains the real signed-in session. The
repository is public, so before every commit and push the rule in [`AGENTS.md`](../AGENTS.md)
applies: check whether personal data would go along, and report the result.

### 10. Troubleshooting

| Symptom | Cause | What to do |
| --- | --- | --- |
| `Access Denied`, `Reference #18…`, `errors.edgesuite.net` | Akamai bot defence against the launched browser | Use your own browser window via `cdp_url` (TikTok) or retry much later; never loop |
| `submission_unknown` | the platform did not confirm clearly | Check the account/studio first, then decide |
| `invalid` in `sau status --verify` | session expired | `sau <platform> login --account <alias>` |
| browser not found | Chrome/Edge/Opera GX missing or unusual path | `--browser-path`, or `patchright install chromium` |
| "Select video"/"Post" not found | the platform changed its UI | stop and report, do not guess |
| Post button stays grey | upload still processing or failed | let the run end, check the studio |
| `sau` not found | venv inactive or not installed | activate the venv, `uv pip install -e .` |
| YouTube rejects `--schedule` | deliberately not implemented | set the time in YouTube Studio |

### 11. Working gently

Platforms throttle suspicious behaviour. Run one upload or check at a time, pause in between, do
not retry in a loop after a block page (every attempt extends it), and test privately first.

### 12. Cheat sheet

```powershell
sau --help
sau <platform> --help
sau <platform> <action> --help

sau <platform> login --account <alias>
sau <platform> check --account <alias>

sau youtube        upload-video --file v.mp4 --title "Title" --desc "Text" --visibility private
sau facebook       upload-video --file v.mp4 --title "Title" --desc "Text"
sau facebook       upload-note  --images 1.jpg 2.jpg --title "Title" --note "Text"
sau facebook-page  upload-video --page "Page" --file v.mp4 --schedule "2026-11-20 18:00"
sau instagram      upload-note  --images 1.jpg 2.jpg --title "Title" --note "Text"
sau profile list | use <browser/profile> | remove --account <alias> --browser <browser>
sau status [--verify]
```

### 13. Further reading

[README.md](../README.md) · [CLI.md](./CLI.md) · [install.md](./install.md) ·
[update.md](./update.md) · [article.md](./article.md) ·
[`.claude/skills/`](../.claude/skills/) · [`AGENTS.md`](../AGENTS.md)
