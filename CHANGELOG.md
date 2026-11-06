# Änderungen / Changes

[Deutsch](#deutsch) · [English](#english)

## Deutsch

Das Projekt ist auf die internationalen Plattformen ausgelegt. Die frühere chinesische Historie
wurde nicht übernommen, weil sie nur die nicht enthaltenen Plattformen betraf.

- **Plattformen:** YouTube, Facebook-Profil, Facebook-Page, Instagram, TikTok (ohne CLI).
- **Entfernt:** Douyin, Kuaishou, Xiaohongshu, WeChat-Video-Kanal, Bilibili, Baijiahao, Dayu,
  Alipay-Live, Weibo, Hupu, Xueqiu, Zhihu — inklusive `sau_commands/*.py`,
  `uploader/*_uploader/`, Beispielen, Tests und Doku.
- **Entfernt:** der reine Legacy-Web-Stack (`sau_backend.py`, `sau_backend/`, `sau_frontend/`,
  `myUtils/`) und das SQLite-Schema `db/`.
- **Skills:** nach `.claude/skills/` verschoben und ins Englische übersetzt (MIT-0).
- **Doku:** README und `docs/` zweisprachig (deutsch/englisch) neu geschrieben.
- **Build:** `Dockerfile` und `start-win.bat` starten die CLI statt Backend und Frontend;
  `pyproject.toml` ohne `myUtils*` und ohne das Flask-Extra.

## English

The project targets the international platforms. The earlier Chinese history was not carried over
because it only covered platforms this tool does not include.

- **Platforms:** YouTube, Facebook profile, Facebook Page, Instagram, TikTok (no CLI).
- **Removed:** Douyin, Kuaishou, Xiaohongshu, WeChat Channels, Bilibili, Baijiahao, Dayu, Alipay
  Live, Weibo, Hupu, Xueqiu, Zhihu — including `sau_commands/*.py`, `uploader/*_uploader/`,
  examples, tests and docs.
- **Removed:** the legacy web stack (`sau_backend.py`, `sau_backend/`, `sau_frontend/`,
  `myUtils/`) and the SQLite schema in `db/`.
- **Skills:** moved to `.claude/skills/` and translated to English (MIT-0).
- **Docs:** README and `docs/` rewritten bilingually (German/English).
- **Build:** `Dockerfile` and `start-win.bat` now start the CLI instead of backend and frontend;
  `pyproject.toml` without `myUtils*` and without the Flask extra.
