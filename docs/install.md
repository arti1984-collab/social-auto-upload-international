# Installation / Install

[Deutsch](#deutsch) · [English](#english)

## Deutsch

Voraussetzungen: Python 3.10–3.12, `uv` und ein Browser: Chrome, Edge oder Opera GX aus einer
normalen Installation, sonst das von `patchright` geladene Chromium bzw. Firefox.

```powershell
# 1. Umgebung
uv venv
.venv\Scripts\Activate.ps1          # Linux/macOS: source .venv/bin/activate

# 2. Projekt installieren (registriert `sau`)
uv pip install -e .

# 3. Browser (Chromium über patchright; Firefox über Playwright, nur bei Bedarf)
patchright install chromium
# python -m playwright install firefox

# 4. Konfiguration
Copy-Item conf.example.py conf.py   # Linux/macOS: cp conf.example.py conf.py
```

In `conf.py` relevante Schlüssel:

| Schlüssel | Bedeutung |
| --- | --- |
| `BASE_DIR` | Projektwurzel (Pfad für `cookies/`, `videos/`, `logs/`) |
| `LOCAL_CHROME_PATH` | optionaler Pfad zu einem installierten Chrome/Chromium |
| `LOCAL_BROWSER` | Standardbrowser: `chrome`, `edge`, `chromium`, `opera-gx`, `firefox` |
| `LOCAL_BROWSER_PROFILE` | persistente Profile je Browser/Account statt Cookie-Dateien |
| `LOCAL_CHROME_HEADLESS` | Standard für den Kopfmodus |
| `DEBUG_MODE` | ausführlichere Ausgaben |
| `YT_PROXY` | optionaler Proxy für YouTube (`chromium` nutzt keinen System-Proxy) |

Funktionstest:

```powershell
sau --help
sau youtube --help
sau facebook --help
sau facebook-page --help
sau instagram --help
sau article --help
```

Wenn `sau` nicht gefunden wird: ist die venv aktiv, und wurde `uv pip install -e .` ausgeführt?

Docker: `docker build -t sau .` und dann `docker run --rm sau youtube --help`. Der Container
startet `sau`; die Browser-Automatisierung braucht ein sichtbares Display, weshalb dort vor allem
`--help` und headless-fähige Läufe sinnvoll sind.

## English

Requirements: Python 3.10–3.12, `uv` and a browser: Chrome, Edge or Opera GX from a regular
installation, otherwise the Chromium or Firefox build downloaded by `patchright`.

```powershell
# 1. Environment
uv venv
.venv\Scripts\Activate.ps1          # Linux/macOS: source .venv/bin/activate

# 2. Install the project (registers `sau`)
uv pip install -e .

# 3. Browsers (Chromium via patchright; Firefox via Playwright, only when needed)
patchright install chromium
# python -m playwright install firefox

# 4. Configuration
Copy-Item conf.example.py conf.py   # Linux/macOS: cp conf.example.py conf.py
```

Relevant keys in `conf.py`:

| Key | Meaning |
| --- | --- |
| `BASE_DIR` | project root (base for `cookies/`, `videos/`, `logs/`) |
| `LOCAL_CHROME_PATH` | optional path to an installed Chrome/Chromium |
| `LOCAL_BROWSER` | default browser: `chrome`, `edge`, `chromium`, `opera-gx`, `firefox` |
| `LOCAL_BROWSER_PROFILE` | persistent profiles per browser/account instead of cookie files |
| `LOCAL_CHROME_HEADLESS` | default head mode |
| `DEBUG_MODE` | more verbose output |
| `YT_PROXY` | optional proxy for YouTube (`chromium` ignores the system proxy) |

Smoke test:

```powershell
sau --help
sau youtube --help
sau facebook --help
sau facebook-page --help
sau instagram --help
sau article --help
```

If `sau` is not found: is the venv active, and did `uv pip install -e .` run?

Docker: `docker build -t sau .` then `docker run --rm sau youtube --help`. The container starts
`sau`; browser automation needs a visible display, so mainly `--help` and headless runs make sense
there.
