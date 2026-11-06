"""Platform-independent article body: safely inlined HTML with body order and image paths relative to the source document."""
from __future__ import annotations

import re
from collections import Counter
from hashlib import sha256
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import tinycss2


ARTICLE_TAGS = {
    "section", "div", "p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "span",
    "strong", "b", "em", "i", "u", "s", "del", "blockquote", "ol", "ul", "li",
    "hr", "img", "a", "pre", "code", "table", "thead", "tbody", "tfoot", "tr",
    "th", "td", "figure", "figcaption", "sup", "sub",
}
ARTICLE_FORMAT_TAGS = ARTICLE_TAGS - {"section", "div", "p", "br", "span", "img", "b", "i"}


def validate_article_style(style: str) -> None:
    """Keeps layout declarations but rejects CSS with external resources or executable content; input styles are never dropped silently."""
    def inspect(tokens):
        for token in tokens:
            if token.type in {"error", "url", "at-keyword"}:
                raise ValueError("Body CSS must not contain syntax errors, external resources or @ rules")
            if token.type == "function":
                if token.lower_name in {"url", "expression", "var"}:
                    raise ValueError(f"Body CSS does not support {token.name}(); provide an inlined concrete value instead")
                inspect(token.arguments)
            if hasattr(token, "content"):
                inspect(token.content)
    for declaration in tinycss2.parse_declaration_list(style, skip_comments=True, skip_whitespace=True):
        if declaration.type != "declaration" or declaration.lower_name.startswith(("--", "-moz-binding")):
            raise ValueError("The body style must be a concrete CSS declaration; variables and rule blocks are not supported")
        if declaration.lower_name in {"behavior", "-ms-behavior"}:
            raise ValueError("Body CSS must not contain executable behaviour")
        inspect(declaration.value)


class ArticleDocument(HTMLParser):
    """Keeps styles, text and/ image positions after parsing; a platform may still add its own restrictions."""

    VOID_TAGS = {"br", "hr", "img"}

    def __init__(self, html: str, base_dir: Path):
        super().__init__(convert_charrefs=True)
        self.base_dir = base_dir.resolve()
        self.parts: list[str | Path] = []
        self.text: list[str] = []
        self.sequence: list[str] = []
        self.images: list[Path] = []
        self.image_attributes: list[dict] = []
        self.formats: Counter = Counter()
        self.tags: Counter = Counter()
        self.attributes: dict[str, set[str]] = {}
        self.stack: list[str] = []
        self.in_head = False
        self.body_style = ""
        self.html_style = ""
        self.source_format = "html"
        self.theme: str | None = None
        self.metadata: dict = {}
        self.feed(html)
        self.close()
        if self.stack:
            raise ValueError(f"Unclosed HTML tag in body: {self.stack[-1]}")
        if not "".join(self.text).strip():
            raise ValueError("The post body must not be empty; provide some text")
        image_index = 0
        content = []
        for part in self.parts:
            content.append(self.image_html(image_index) if isinstance(part, Path) else part)
            if isinstance(part, Path):
                image_index += 1
        self.content_html = "".join(content)
        normalize = lambda value: re.sub(r"[\s\u200b\ufeff]+", "", value)
        self.manifest = {
            "text_sha256": sha256(normalize("".join(self.text)).encode()).hexdigest(),
            "structure_sha256": sha256(normalize("".join(self.sequence)).encode()).hexdigest(),
            "image_count": len(self.images), "formats": dict(self.formats),
        }

    def image_html(self, index: int) -> str:
        """Rebuild images keeping layout attributes and use absolute paths so resources survive a moved output file."""
        attrs = {**self.image_attributes[index], "src": quote(self.images[index].as_posix(), safe="/:")}
        return "<img" + "".join(f' {key}="{escape(value or "", quote=True)}"' for key, value in attrs.items()) + ">"

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "head":
            self.in_head = True
            return
        if tag in {"script", "iframe", "object", "embed", "link", "style"}:
            raise ValueError(f"Body does not support <{tag}>; use inline element style instead and never reference external resources")
        if self.in_head:
            return
        if tag == "html":
            if set(attributes) - {"lang", "style"}:
                raise ValueError("<html> supports the lang and style attributes only")
            self.html_style = attributes.get("style") or ""
            if self.html_style.strip():
                validate_article_style(self.html_style)
                self.parts.append(f'<section style="{escape(self.html_style, quote=True)}">')
            return
        if tag == "body":
            if set(attributes) - {"style", "class", "id"}:
                raise ValueError("<body> supports only style, class and id attributes")
            self.body_style = attributes.get("style") or ""
            if self.body_style.strip():
                validate_article_style(self.body_style)
                self.parts.append(f'<section style="{escape(self.body_style, quote=True)}">')
            return
        if tag not in ARTICLE_TAGS:
            raise ValueError(f"Body does not support <{tag}>")
        self.attributes.setdefault(tag, set()).update(attributes)
        allowed = {"style", "class", "id", "title"}
        if tag == "img":
            allowed |= {"src", "alt", "width", "height"}
        if tag == "a":
            allowed |= {"href"}
        if tag in {"th", "td"}:
            allowed |= {"colspan", "rowspan", "align"}
        if tag == "ol":
            allowed |= {"start"}
        if set(attributes) - allowed - {key for key in attributes if key.startswith("data-")}:
            raise ValueError(f"<{tag}> does not support these attributes: {', '.join(sorted(set(attributes) - allowed))}")
        if "style" in attributes:
            validate_article_style(attributes["style"] or "")
        if tag == "a" and "href" in attributes:
            href = attributes["href"] or ""
            if not href.startswith("#") and urlsplit(href).scheme not in {"http", "https", "mailto"}:
                raise ValueError("Body links support only http/https, mailto or in-page anchors")
        if tag == "img":
            source = unquote(attributes.pop("src", "") or "")
            if (not source or source.startswith("//") or
                    (not Path(source).is_absolute() and re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", source))):
                raise ValueError("Body image src must be a local relative or absolute path; network, file and data URLs are not supported")
            image = (self.base_dir / Path(source).expanduser()).resolve()
            if not image.is_file():
                raise FileNotFoundError(f"Image not found: {image}")
            self.parts.append(image)
            self.images.append(image)
            self.image_attributes.append(attributes)
            self.sequence.append("\x00IMG\x00")
            return
        normalized = {"b": "strong", "i": "em"}.get(tag, tag)
        self.tags[normalized] += 1
        self.parts.append("<" + normalized + "".join(
            f' {key}="{escape(value or "", quote=True)}"' for key, value in attributes.items()) + ">")
        if tag == "hr":
            self.sequence.append("\x00HR\x00")
        if normalized in ARTICLE_FORMAT_TAGS:
            self.formats[normalized] += 1
        if tag not in self.VOID_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID_TAGS and tag not in {"meta", "link"}:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False
            return
        if self.in_head:
            return
        if tag == "html":
            if self.html_style.strip():
                self.parts.append("</section>")
            return
        if tag == "body":
            if self.body_style.strip():
                self.parts.append("</section>")
            return
        if not self.stack or self.stack.pop() != tag:
            raise ValueError(f"HTML tag not closed correctly in body: </{tag}>")
        normalized = {"b": "strong", "i": "em"}.get(tag, tag)
        self.parts.append(f'</{normalized}>')

    def handle_data(self, data):
        if not self.in_head:
            self.parts.append(escape(data))
            self.text.append(data)
            self.sequence.append(data)
