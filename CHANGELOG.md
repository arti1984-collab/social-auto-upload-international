# Änderungen in diesem Fork / Changes in this fork

[Deutsch](#deutsch) · [English](#english)

## Deutsch

Dieser Fork basiert auf `dreammis/social-auto-upload` (MIT) und ist auf die internationalen
Plattformen reduziert. Die chinesische Upstream-Historie wurde entfernt, weil sie nur die
gestrichenen Plattformen betraf.

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

This fork is based on `dreammis/social-auto-upload` (MIT) and is reduced to the international
platforms. The Chinese upstream history was dropped because it only covered the removed platforms.

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
