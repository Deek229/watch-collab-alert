# -*- coding: utf-8 -*-
"""告知ページから、発売日・予約日・型番・価格だけを取り出す。本文は保存しない。"""

from __future__ import annotations

import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from filter import normalize, partner_brand, watch_brand

JST = ZoneInfo("Asia/Tokyo")

DATE_RE = re.compile(
    r"(?:(?P<year>20\d{2})年\s*)?"
    r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日"
    r"(?:\s*[（(][月火水木金土日祝・]+[）)])?"
    r"(?:\s*(?P<ampm>午前|午後|AM|PM|am|pm))?"
    r"(?:\s*(?P<hour>\d{1,2})\s*(?:[:：](?P<minute>\d{2})|時))?"
)
MODEL_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{1,5}-\d{2,4}[A-Z0-9]{0,8})(?![A-Z0-9])")
PRICE_MAN_RE = re.compile(r"(\d+)\s*万\s*(\d{3,4})\s*円")
PRICE_RE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d{3,6})\s*円")
QUOTED_RE = re.compile(r"[「『\"]([^」』\"]{1,30})[」』\"]")
HREF_RE = re.compile(r"""href=["'](https?://[^"'#]+)["']""", re.I)
CUT_MARKERS = (
    "関連記事",
    "こちらも読まれて",
    "おすすめ記事",
    "最新記事",
    "この記事をシェア",
    "ランキング",
)
SHOP_HOSTS = (
    "casio.co.jp",
    "casio.com",
    "gshock.casio.com",
    "apcjp.com",
    "beams.co.jp",
    "zozotown.com",
    "timex.com",
    "timex.jp",
    "seikowatches.com",
    "citizen.co.jp",
    "united-arrows.co.jp",
    "maisonkitsune.com",
)


def clip_html(raw: str) -> str:
    cut = len(raw)
    for marker in CUT_MARKERS:
        index = raw.find(marker)
        if index != -1:
            cut = min(cut, index)
    return raw[:cut]


def meta_description(raw: str) -> str:
    patterns = (
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, raw, re.I | re.S)
        if match:
            return " ".join(html.unescape(match.group(1)).split())
    return ""


def article_html(raw: str) -> str:
    match = re.search(r"(?is)<main\b[^>]*>(.*)</main>", raw)
    chunk = match.group(1) if match else raw
    chunk = html.unescape(html.unescape(chunk))
    chunk = re.sub(r"(?is)<(header|nav|footer)\b.*?</\1>", " ", chunk)
    return clip_html(chunk)


def html_to_text(raw: str) -> str:
    clipped = article_html(raw)
    clipped = re.sub(r"(?is)<script\b.*?</script>", " ", clipped)
    clipped = re.sub(r"(?is)<style\b.*?</style>", " ", clipped)
    clipped = re.sub(r"(?is)<[^>]+>", " ", clipped)
    text = html.unescape(clipped).replace("\u3000", " ")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    description = meta_description(raw)
    if description and description not in text:
        text = description + "\n" + text
    return text[:8000]


def _hour(ampm: str | None, hour: str | None, minute: str | None) -> tuple[int, int] | None:
    if hour is None:
        return None
    value = int(hour)
    minute_value = int(minute or "0")
    mark = (ampm or "").upper()
    if mark in {"午後", "PM"} and value < 12:
        value += 12
    if mark in {"午前", "AM"} and value == 12:
        value = 0
    if value > 23 or minute_value > 59:
        return None
    return value, minute_value


def _kind(text: str, start: int, end: int) -> str | None:
    after = text[end : end + 36]
    after = re.split(r"[（(]", after)[0]
    before = text[max(0, start - 24) : start]
    if any(word in after for word in ("予約", "受付", "先行")):
        if "まで" in after[:8]:
            return "preorder_end"
        return "preorder_start"
    if "発売" in after:
        return "release"
    if "～" in after[:3] or "〜" in after[:3]:
        window = text[max(0, start - 40) : end + 40]
        if any(word in window for word in ("予約", "受付", "先行")):
            return "preorder_start"
    if any(word in before[-8:] for word in ("～", "〜")):
        return "preorder_end"
    if any(word in before for word in ("予約", "受付", "先行")):
        return "preorder_start"
    if "発売" in before:
        return "release"
    return None


def find_dates(text: str, default_year: int) -> dict[str, str]:
    ranked: list[tuple[str, int, int, str]] = []
    for match in DATE_RE.finditer(text):
        month = int(match.group("month"))
        day = int(match.group("day"))
        if not (1 <= month <= 12 and 1 <= day <= 31):
            continue
        kind = _kind(text, match.start(), match.end())
        if kind is None:
            continue
        year = int(match.group("year") or default_year)
        clock = _hour(match.group("ampm"), match.group("hour"), match.group("minute"))
        try:
            if clock is None:
                iso = f"{year:04d}-{month:02d}-{day:02d}"
            else:
                hour, minute = clock
                iso = datetime(year, month, day, hour, minute, tzinfo=JST).isoformat()
        except ValueError:
            continue
        after = text[match.end() : match.end() + 20]
        score = 2 if any(word in after for word in ("発売", "予約", "受付", "先行")) else 1
        ranked.append((kind, score, match.start(), iso))
    found: dict[str, str] = {}
    for kind in ("preorder_start", "preorder_end", "release"):
        rows = [row for row in ranked if row[0] == kind]
        if not rows:
            continue
        rows.sort(key=lambda row: (-row[1], row[2]))
        found[kind] = rows[0][3]
    return found


def find_prices(text: str) -> list[int]:
    prices: list[int] = []
    occupied: list[tuple[int, int]] = []
    for match in PRICE_MAN_RE.finditer(text):
        prices.append(int(match.group(1)) * 10000 + int(match.group(2)))
        occupied.append(match.span())
    for match in PRICE_RE.finditer(text):
        if any(start <= match.start() < end for start, end in occupied):
            continue
        raw = match.group(1).replace(",", "")
        value = int(raw)
        if 3000 <= value <= 500000:
            prices.append(value)
    unique: list[int] = []
    for price in prices:
        if price not in unique:
            unique.append(price)
    return unique[:4]


def find_models(text: str) -> list[str]:
    models: list[str] = []
    for match in MODEL_RE.finditer(normalize(text)):
        ref = match.group(1)
        if ref not in models:
            models.append(ref)
    return models[:4]


def guess_partner(text: str, watch: str | None) -> str | None:
    named = partner_brand(text)
    if named and named.casefold() not in (watch or "").casefold():
        return _pretty_partner(named)
    for match in QUOTED_RE.finditer(text):
        quoted = match.group(1).strip()
        if watch_brand(quoted) or len(quoted) < 1:
            continue
        if quoted.casefold() in {"g-shock", "baby-g", "casio", "seiko"}:
            continue
        return quoted
    return None


def _pretty_partner(name: str) -> str:
    table = {
        "APC": "A.P.C.",
        "アー・ペー・セー": "A.P.C.",
        "アーペーセー": "A.P.C.",
        "Cafe Kitsune": "Café Kitsuné",
        "カフェ キツネ": "Café Kitsuné",
        "メゾン キツネ": "Maison Kitsuné",
        "メゾンキツネ": "Maison Kitsuné",
        "Kitsuné": "Café Kitsuné",
        "エックスジー": "XG",
        "マルジェラ": "MM6 Maison Margiela",
        "Margiela": "MM6 Maison Margiela",
    }
    return table.get(name, name)


def find_channels(raw_html: str) -> list[dict[str, str]]:
    clipped = article_html(raw_html)
    channels: list[dict[str, str]] = []
    seen: set[str] = set()
    for href in HREF_RE.findall(clipped):
        url = html.unescape(href).strip()
        if url in seen or any(skip in url for skip in ("javascript:", "mailto:", "twitter.", "facebook.", "instagram.", "/support", "email-subscription", "/information", "/service/", "/login")):
            continue
        host = re.sub(r"^https?://", "", url).split("/")[0].lower()
        if not any(shop in host for shop in SHOP_HOSTS):
            continue
        seen.add(url)
        path = re.sub(r"^https?://[^/]+", "", url)
        if "/release/" in url:
            label = "公式の発表"
        elif path in {"", "/"}:
            label = "公式サイト"
        elif "/contents/" in url:
            label = "特設ページ"
        elif "gshock.casio.com" in url or "/watches/" in url or "product." in url:
            label = "公式の商品ページ"
        else:
            label = "販売・特設ページ"
        channels.append({"name": label, "url": url})
        if len(channels) >= 4:
            break
    return channels


def default_year_from(url: str, published: str | None) -> int:
    match = re.search(r"/(20\d{2})/", url or "")
    if match:
        return int(match.group(1))
    if published:
        year = re.search(r"(20\d{2})", published)
        if year:
            return int(year.group(1))
    return datetime.now(JST).year


def parse_release(raw_html: str, page_url: str, title: str, published: str | None = None) -> dict:
    text = html_to_text(raw_html)
    heading = title or ""
    combined = f"{heading}\n{text[:4000]}"
    year = default_year_from(page_url, published)
    dates = find_dates(combined, year)
    if "release" in dates:
        dates["release_at"] = dates.pop("release")
    models = find_models(combined)
    prices = find_prices(text[:4000])
    watch = watch_brand(heading) or watch_brand(combined)
    partner = guess_partner(heading, watch) or guess_partner(text[:1200], watch)
    paired = []
    for index, ref in enumerate(models):
        entry: dict[str, object] = {"ref": ref}
        if index < len(prices):
            entry["price_jpy"] = prices[index]
        elif len(models) == 1 and prices:
            entry["price_jpy"] = prices[0]
        paired.append(entry)
    if not paired and prices:
        paired.append({"ref": "", "price_jpy": prices[0], "detail": "出典に書かれた価格"})
    conditions: list[str] = []
    head = text[:1800]
    if any(word in head for word in ("メンバーシップ", "会員登録")):
        conditions.append("オンラインでの予約には会員登録が必要です")
    if "整理券" in head:
        conditions.append("一部の店舗は整理券での案内です")
    return {
        "watch_brand": watch,
        "partner_brand": partner,
        "models": [model for model in paired if model.get("ref") or model.get("price_jpy")],
        "conditions": conditions,
        "channels": find_channels(raw_html),
        **dates,
    }


def _demo() -> None:
    xg = "『GM-6900XG』を11月27日に発売します。39,600円（税込）"
    parsed = find_dates(xg, 2026)
    if parsed.get("release") != "2026-11-27":
        raise SystemExit(f"xg date {parsed}")
    apc = "11月17日 PM4:00 発売開始（11月12日 AM10:00より受付開始）となる。"
    parsed = find_dates(apc, 2026)
    if parsed.get("release") != "2026-11-17T16:00:00+09:00":
        raise SystemExit(f"apc release {parsed}")
    if parsed.get("preorder_start") != "2026-11-12T10:00:00+09:00":
        raise SystemExit(f"apc preorder {parsed}")
    if find_prices("1万5400円と39,600円（税込）") != [15400, 39600]:
        raise SystemExit("price")
    if "GM-6900XG" not in find_models(xg):
        raise SystemExit("model")
    print("parse ok")


if __name__ == "__main__":
    _demo()
