#!/usr/bin/env python3
"""MH Intelligence Radar collector.

Collects fresh official AI news, deduplicates by canonical URL, sorts newest first,
and writes the frontend contract expected by MH-INTELLIGENCE.
"""
from __future__ import annotations

import email.utils
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

OUT = Path(__file__).with_name("noticias.json")
MAX_ITEMS = 80
USER_AGENT = "MH-Intelligence-Radar/1.0 (+https://github.com/MALAHIERBA87IA/mh-intelligence-data)"

FEEDS = [
    ("OpenAI News", "https://openai.com/news/rss.xml"),
    ("Google AI", "https://blog.google/technology/ai/rss/"),
    ("Google Developers", "https://developers.googleblog.com/feeds/posts/default/-/AI"),
    ("Hugging Face - Blog", "https://huggingface.co/blog/feed.xml"),
]

AI_TERMS = re.compile(
    r"\b(ai|artificial intelligence|gemini|openai|gpt|chatgpt|agent|agents|mcp|model|models|"
    r"machine learning|llm|vlm|video|image generation|audio|voice|developer|api|sdk|automation|"
    r"workflow|hugging face|transformers|suno|runway|kling|veo|nano banana)\b",
    re.I,
)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read()


def text(node: ET.Element | None) -> str:
    return "" if node is None or node.text is None else node.text.strip()


def first_text(entry: ET.Element, names: Iterable[str]) -> str:
    for name in names:
        found = entry.find(name)
        value = text(found)
        if value:
            return value
    return ""


def parse_date(value: str) -> datetime:
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed:
            return parsed.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


def parse_feed(source: str, payload: bytes) -> list[dict]:
    root = ET.fromstring(payload)
    items: list[dict] = []

    entries = root.findall(".//item")
    atom = False
    if not entries:
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        atom = True

    for entry in entries:
        if atom:
            title = first_text(entry, ["{http://www.w3.org/2005/Atom}title"])
            date_raw = first_text(entry, ["{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"])
            link = ""
            for link_node in entry.findall("{http://www.w3.org/2005/Atom}link"):
                href = (link_node.attrib.get("href") or "").strip()
                rel = link_node.attrib.get("rel", "alternate")
                if href and rel in ("alternate", ""):
                    link = href
                    break
        else:
            title = first_text(entry, ["title"])
            link = first_text(entry, ["link"])
            date_raw = first_text(entry, ["pubDate", "{http://purl.org/dc/elements/1.1/}date"])

        if not title or not link:
            continue
        searchable = f"{title} {source}"
        if source.startswith("Google") and not AI_TERMS.search(searchable):
            continue

        published = parse_date(date_raw)
        items.append({
            "titulo": title,
            "link": link.split("#", 1)[0],
            "fecha": email.utils.format_datetime(published),
            "fuente": source,
            "_ts": published.timestamp(),
        })
    return items


def load_existing() -> list[dict]:
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def main() -> None:
    collected: list[dict] = []
    failures: list[str] = []

    for source, url in FEEDS:
        try:
            batch = parse_feed(source, fetch(url))
            collected.extend(batch)
            print(f"OK {source}: {len(batch)}")
        except Exception as exc:
            failures.append(f"{source}: {exc}")
            print(f"WARN {source}: {exc}")

    if not collected:
        raise SystemExit("Radar aborted: no live source returned usable items. Existing noticias.json preserved.")

    # Keep existing records too, so a temporary source outage does not erase radar history.
    for item in load_existing():
        item = dict(item)
        item["_ts"] = parse_date(str(item.get("fecha", ""))).timestamp()
        collected.append(item)

    by_url: dict[str, dict] = {}
    for item in collected:
        url = str(item.get("link", "")).strip()
        if url and url not in by_url:
            by_url[url] = item

    fresh = sorted(by_url.values(), key=lambda x: x.get("_ts", 0), reverse=True)[:MAX_ITEMS]
    for item in fresh:
        item.pop("_ts", None)

    OUT.write_text(json.dumps(fresh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Radar wrote {len(fresh)} unique articles to {OUT.name}")
    if failures:
        print("Partial source failures: " + " | ".join(failures))


if __name__ == "__main__":
    main()
