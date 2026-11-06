"""Deterministic captions and hashtags for posts; no AI service, no network.

The text comes from your title and notes plus one fixed call to action per
platform, and the hashtags come from the significant words of title and notes.
The same input always produces the same output, and the result stays inside the
limits the platforms accept.
"""
from __future__ import annotations

import re

# Title characters (0 = the platform has no title field of its own), caption
# characters and the number of hashtags that still look intentional.
PLATFORM_LIMITS = {
    "youtube": {"title": 100, "caption": 5000, "hashtags": 15},
    "facebook": {"title": 0, "caption": 60000, "hashtags": 5},
    "facebook-page": {"title": 0, "caption": 60000, "hashtags": 5},
    "instagram": {"title": 0, "caption": 2200, "hashtags": 10},
    "tiktok": {"title": 0, "caption": 2200, "hashtags": 8},
}

CALL_TO_ACTION = {
    "de": {
        "youtube": "Danke fürs Zuschauen – Feedback gern in die Kommentare.",
        "facebook": "Gern teilen und kommentieren.",
        "facebook-page": "Gern teilen und kommentieren.",
        "instagram": "Speichern, teilen oder kommentieren.",
        "tiktok": "Mehr davon? Folge dem Account.",
    },
    "en": {
        "youtube": "Thanks for watching – feedback is welcome in the comments.",
        "facebook": "Feel free to share and comment.",
        "facebook-page": "Feel free to share and comment.",
        "instagram": "Save, share or comment.",
        "tiktok": "Want more? Follow the account.",
    },
}

_LANGUAGES = tuple(CALL_TO_ACTION)

_UMLAUTS = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"}
)

_STOPWORD_WORDS = {
    "de": (
        "und", "oder", "aber", "denn", "dass", "wenn", "als", "auch", "nicht", "noch",
        "nur", "sehr", "mehr", "schon", "immer", "wieder", "dann", "dort", "hier",
        "heute", "jetzt", "gestern", "morgen", "der", "die", "das", "den", "dem",
        "des", "ein", "eine", "einen", "einem", "einer", "eines", "ist", "sind",
        "war", "waren", "wird", "werden", "wurde", "hat", "haben", "hatte", "kann",
        "können", "muss", "müssen", "soll", "sollen", "man", "sich", "ich", "wir",
        "du", "ihr", "sie", "es", "mein", "meine", "meinen", "dein", "deine",
        "unser", "unsere", "euer", "eure", "sein", "seine", "ihre", "für", "mit",
        "ohne", "von", "vom", "aus", "auf", "bei", "beim", "nach", "über", "unter",
        "vor", "durch", "gegen", "zwischen", "zum", "zur", "ins", "ans", "im", "in",
        "am", "an", "zu", "so", "um", "wie", "was", "warum", "wieso", "welche",
        "welcher", "welches", "diese", "dieser", "dieses", "diesem", "gibt", "geht",
        "macht", "machen", "tun", "video", "videos", "bild", "bilder", "teil",
    ),
    "en": (
        "the", "and", "but", "or", "for", "nor", "with", "without", "from", "into",
        "about", "above", "after", "before", "over", "under", "between", "this",
        "that", "these", "those", "there", "here", "when", "where", "which", "what",
        "why", "how", "who", "your", "yours", "you", "our", "ours", "their",
        "theirs", "his", "her", "hers", "its", "are", "was", "were", "been", "being",
        "will", "would", "can", "could", "should", "must", "have", "has", "had",
        "not", "than", "then", "them", "they", "just", "more", "most", "very",
        "also", "too", "again", "all", "any", "each", "both", "some", "such",
        "only", "own", "same", "out", "off", "up", "down", "one", "two", "how",
        "video", "videos", "image", "images", "photo", "photos",
    ),
}


def _cut(text: str, limit: int) -> str:
    """Trim to a limit without leaving half a word behind."""
    text = text.strip()
    if limit <= 0 or len(text) <= limit:
        return text
    clipped = text[:limit].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0].rstrip(" ,.;:-–")
    return clipped


def normalize_tag(word: str) -> str:
    """ASCII-only tag body, so every platform accepts the hashtag."""
    return re.sub(r"[^a-z0-9]+", "", word.translate(_UMLAUTS).lower())


STOPWORDS = {
    language: {normalize_tag(word) for word in words}
    for language, words in _STOPWORD_WORDS.items()
}


def keywords(text: str) -> list[str]:
    """Significant words in order of appearance, without duplicates."""
    stop = STOPWORDS["de"] | STOPWORDS["en"]
    result: list[str] = []
    for word in re.findall(r"[0-9A-Za-zÄÖÜäöüß]+", text):
        tag = normalize_tag(word)
        if len(tag) < 3 or tag.isdigit() or tag in stop or tag in result:
            continue
        result.append(tag)
    return result


def suggest_tags(platform: str, title: str, notes: str = "", lang: str = "de") -> list[str]:
    """Hashtag bodies for one platform, capped to a readable number."""
    _check(platform, lang)
    return keywords(f"{title} {notes}")[: PLATFORM_LIMITS[platform]["hashtags"]]


def description(platform: str, title: str, notes: str = "", lang: str = "de") -> str:
    """Notes plus one platform-appropriate call to action, within the caption limit."""
    _check(platform, lang)
    parts = [part.strip() for part in (notes, CALL_TO_ACTION[lang][platform]) if part.strip()]
    return _cut("\n\n".join(parts), PLATFORM_LIMITS[platform]["caption"])


def build(platform: str, title: str, notes: str = "", lang: str = "de") -> dict:
    """Everything one post needs: title, description, tags, hashtags and the final caption."""
    _check(platform, lang)
    limits = PLATFORM_LIMITS[platform]
    clean_title = _cut(title, limits["title"]) if limits["title"] else title.strip()
    text = description(platform, clean_title, notes, lang)
    tags = suggest_tags(platform, clean_title, notes, lang)
    hashtags = [f"#{tag}" for tag in tags]
    caption = _cut(f"{text}\n\n{' '.join(hashtags)}", limits["caption"]) if hashtags else text
    return {
        "platform": platform,
        "language": lang,
        "title": clean_title,
        "description": text,
        "tags": tags,
        "hashtags": hashtags,
        "caption": caption,
        "limits": dict(limits),
    }


def merge_tags(existing, generated, limit: int = 0) -> list[str]:
    """Your own tags first, then the suggestions, without duplicates."""
    merged: list[str] = []
    seen: set[str] = set()
    for tag in list(existing) + list(generated):
        cleaned = str(tag).strip().lstrip("#")
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        merged.append(cleaned)
    return merged[:limit] if limit else merged


def apply_caption(
    platform: str,
    title: str,
    text: str,
    tags,
    *,
    auto_desc: bool = False,
    auto_tags: bool = False,
    lang: str = "de",
) -> tuple[str, list[str]]:
    """Fill description and tags for an upload command; your own text always wins."""
    if not (auto_desc or auto_tags):
        return text, list(tags)
    generated = build(platform, title, notes=text, lang=lang)
    result_text = text
    if auto_desc and not text.strip():
        result_text = generated["description"]
    result_tags = list(tags)
    if auto_tags:
        result_tags = merge_tags(result_tags, generated["tags"], PLATFORM_LIMITS[platform]["hashtags"])
    return result_text, result_tags


def _check(platform: str, lang: str) -> None:
    if platform not in PLATFORM_LIMITS:
        raise ValueError(f"Unsupported platform for captions: {platform}")
    if lang not in _LANGUAGES:
        raise ValueError(f"Unsupported caption language: {lang}")
