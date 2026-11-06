# Update / Aktualisieren

[Deutsch](#deutsch) · [English](#english)

## Deutsch

```powershell
git pull
uv pip install -e .          # bei Änderungen an CLI, Einstiegspunkten oder Abhängigkeiten
patchright install chromium  # nur wenn sich die Browser-Anforderung geändert hat
```

Danach kurz prüfen:

```powershell
sau --help
sau youtube --help
sau facebook --help
sau facebook-page --help
sau instagram --help
sau youtube check --account <name>
```

Für Agenten: `pyproject.toml` ist die Wahrheit für Abhängigkeiten, `requirements.txt` ist eine
Altlast aus frühen Versionen. Wenn sich nach dem Update ein Login-Flow geändert hat und eine lokale
QR-Code-Grafik erzeugt wird, diese Grafik direkt anzeigen — nicht nur den Dateipfad nennen.

## English

```powershell
git pull
uv pip install -e .          # when CLI, entry points or dependencies changed
patchright install chromium  # only if the browser requirement changed
```

Then check:

```powershell
sau --help
sau youtube --help
sau facebook --help
sau facebook-page --help
sau instagram --help
sau youtube check --account <name>
```

For agents: `pyproject.toml` is the source of truth for dependencies; `requirements.txt` is an
leftover from early versions. If a login flow now writes a local QR code image, show that image to the user
instead of only printing the path.
