# -*- coding: utf-8 -*-
"""決めたニュース一覧から、新しい記事の見出しとURLだけを集める。"""

from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


def load_sources() -> list[dict]:
    return json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))


def fetch_bytes(url: str, timeout: int = 25) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_text(url: str) -> str:
    raw = fetch_bytes(url)
    return raw.decode("utf-8", errors="replace")


def _item_link(item: ET.Element) -> str:
    link = (item.findtext("link") or "").strip()
    if link:
        return link
    for child in item:
        if child.tag.endswith("link"):
            href = (child.attrib.get("href") or child.text or "").strip()
            if href:
                return href
    return ""


def rss_candidates(source: dict) -> list[dict]:
    raw = fetch_bytes(source["url"]).lstrip(b"\xef\xbb\xbf").lstrip()
    root = ET.fromstring(raw)
    found: list[dict] = []
    for item in root.findall(".//item")[: int(source.get("max_items") or 20)]:
        title = " ".join((item.findtext("title") or "").split())
        link = _item_link(item)
        if not title or not link:
            continue
        published = (item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or "").strip()
        found.append(
            {
                "title": html.unescape(title),
                "url": link,
                "source": source["name"],
                "published": published,
            }
        )
    return found


def html_candidates(source: dict) -> list[dict]:
    page = fetch_text(source["url"])
    found: list[dict] = []
    pattern = re.compile(r"""<a[^>]+href=["']([^"']+)["'][^>]*>(.*?)</a>""", re.I | re.S)
    for href, inner in pattern.findall(page):
        if "/release/20" not in href:
            continue
        text = " ".join(re.sub(r"<[^>]+>", " ", html.unescape(inner)).split())
        if len(text) < 8:
            continue
        url = href if href.startswith("http") else "https://www.casio.co.jp" + href
        found.append({"title": text, "url": url, "source": source["name"], "published": ""})
        if len(found) >= int(source.get("max_links") or 25):
            break
    return found


def collect_candidates() -> list[dict]:
    gathered: list[dict] = []
    seen: set[str] = set()
    for source in load_sources():
        try:
            if source["type"] == "rss":
                rows = rss_candidates(source)
            elif source["type"] == "html":
                rows = html_candidates(source)
            else:
                continue
        except (urllib.error.URLError, ET.ParseError, TimeoutError, OSError) as error:
            print(f"取得できませんでした: {source['name']} ({error})")
            continue
        print(f"{source['name']}: {len(rows)}件")
        for row in rows:
            if row["url"] in seen:
                continue
            seen.add(row["url"])
            gathered.append(row)
    return gathered
