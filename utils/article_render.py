"""Shared article input and Markdown  theme rendering; this module never logs in or uploads and ignores platform limits."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from html import escape
from pathlib import Path

from utils.article_content import ArticleDocument


ARTICLE_THEMES = {
    "plain": "native: converts the structure only, no theme styling",
    "default": "classic: centred headings with an accent colour",
    "grace": "graceful: rounded quotes and soft decoration",
    "simple": "simple: generous whitespace with light decoration",
    "modern": "modern: warm colours, rounded corners, loose line height",
}
ARTICLE_MARKDOWN_EXTENSIONS = {".md", ".markdown"}
ARTICLE_HTML_EXTENSIONS = {".html", ".htm"}
ARTICLE_RENDERER_DIR = Path(__file__).with_name("article_renderer")


def load_article(content_file: str | Path, theme: str | None = None) -> ArticleDocument:
    """Resources resolve relative to the source document; long content travels over stdin, never through argv."""
    path = Path(content_file).expanduser().resolve()
    source = path.read_text(encoding="utf-8-sig")
    suffix = path.suffix.lower()
    metadata = {}
    if suffix in ARTICLE_MARKDOWN_EXTENSIONS:
        theme = theme or "default"
        if theme not in ARTICLE_THEMES:
            raise ValueError(f"Theme must be one of: {', '.join(ARTICLE_THEMES)}")
        node = shutil.which("node")
        if not node or not (ARTICLE_RENDERER_DIR / "node_modules/baoyu-md").is_dir():
            raise RuntimeError("Markdown rendering needs Node.js 22+  and its dependencies; run sau article setup")
        completed = subprocess.run(
            [node, str(ARTICLE_RENDERER_DIR / "render.mjs")],
            input=json.dumps({"content": source, "theme": theme}, ensure_ascii=False),
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        if completed.returncode:
            raise RuntimeError(f"Markdown Rendering failed: {completed.stderr.strip()}")
        payload = json.loads(completed.stdout)
        source, metadata = payload["html"], payload["metadata"]
    elif suffix in ARTICLE_HTML_EXTENSIONS | {".txt"}:
        if theme is not None:
            raise ValueError("--theme only applies to Markdown; HTML and TXT output is not re-themed")
        if suffix == ".txt":
            source = "".join(f"<p>{escape(line) if line else '<br>'}</p>" for line in source.splitlines())
    else:
        raise ValueError("Content files may be .html/.htm, .md/.markdown or a compatible .txt")
    document = ArticleDocument(source, path.parent)
    document.source_format = "markdown" if suffix in ARTICLE_MARKDOWN_EXTENSIONS else ("text" if suffix == ".txt" else "html")
    document.theme = theme
    document.metadata = metadata
    return document


def render_article_file(content_file: str | Path, output: str | Path,
                        theme: str | None = None, overwrite: bool = False) -> dict:
    """Save standalone-previewable HTML; local images still resolve when the output path differs."""
    source = Path(content_file).expanduser().resolve()
    target = Path(output).expanduser().resolve()
    if target == source:
        raise ValueError("The output file must not overwrite the source document")
    if target.suffix.lower() not in ARTICLE_HTML_EXTENSIONS:
        raise ValueError("--output must be an .html or .htm file")
    if target.exists() and not overwrite:
        raise FileExistsError(f"Output file exists; use --overwrite to overwrite it explicitly: {target}")
    document = load_article(source, theme)
    title = escape(document.metadata.get("title", source.stem))
    html = ('<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{title}</title></head><body>{document.content_html}</body></html>')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return {"output": str(target), "format": document.source_format,
            "theme": document.theme, "image_count": len(document.images)}


def setup_article_renderer() -> None:
    """Install local rendering dependencies from the lockfile; nothing is downloaded while rendering or publishing."""
    node = shutil.which("node")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not node or not npm:
        raise RuntimeError("Install Node.js 22+with npm first, then run sau article setup")
    version = subprocess.check_output([node, "--version"], text=True).strip()
    if int(version.lstrip("v").split(".")[0]) < 22:
        raise RuntimeError(f"Article rendering needs Node.js 22+ but found {version}")
    subprocess.run([npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
                   cwd=ARTICLE_RENDERER_DIR, check=True, timeout=180)
