# Artikel-Rendering / Article rendering

[Deutsch](#deutsch) · [English](#english)

## Deutsch

`sau article` rendert Artikel lokal (Markdown/HTML → HTML mit Theme). Für das Veröffentlichen auf
Plattformen wird es in diesem Fork nicht mehr gebraucht, weil die chinesischen Artikel-Plattformen
entfernt wurden; es bleibt als lokales Werkzeug.

```powershell
sau article themes
sau article setup                                            # Node.js 22+ nötig, einmalig
sau article render --content-file examples/article.md --theme modern --output output/article.html
sau article render --content-file article.html --output output/preview.html
```

Themes: `default`, `grace`, `simple`, `modern`, `plain`. Markdown ohne `--theme` nutzt `default`;
HTML/TXT akzeptiert `--theme` nicht. Die Ausgabedatei wird nicht überschrieben, außer mit
`--overwrite`.

Unterstützt werden Überschriften, Listen, Zitate, Code, Tabellen, Links und lokale Bilder
(relativ zum Original-Dokument). Netzwerkbilder, `data:`/`file:`-URLs, externe Stylesheets,
Skripte, iframes und SVG sind nicht erlaubt; Diagramme vorher als lokale Bilder exportieren.

## English

`sau article` renders articles locally (Markdown/HTML → themed HTML). Publishing to platforms no
longer uses it in this fork, because the Chinese article platforms were removed; it stays as a
local tool.

```powershell
sau article themes
sau article setup                                            # requires Node.js 22+, once
sau article render --content-file examples/article.md --theme modern --output output/article.html
sau article render --content-file article.html --output output/preview.html
```

Themes: `default`, `grace`, `simple`, `modern`, `plain`. Markdown without `--theme` uses
`default`; HTML/TXT does not accept `--theme`. The output file is not overwritten unless you pass
`--overwrite`.

Supported: headings, lists, quotes, code, tables, links and local images (relative to the source
document). Network images, `data:`/`file:` URLs, external stylesheets, scripts, iframes and SVG are
rejected; export diagrams as local images first.
