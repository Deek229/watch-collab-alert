# -*- coding: utf-8 -*-
"""新しい発売告知を見て、一覧を更新する。案内メールは朝の「今日のタスク」に載せる。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import unicodedata
import urllib.error
from datetime import datetime
from pathlib import Path

from filter import is_collab_title, normalize
from parse_page import parse_release
from pages import JST, build_site, format_long
from sources import collect_candidates, fetch_text

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ITEMS_PATH = DATA / "items.json"
SEEN_PATH = DATA / "seen_urls.json"

PARTNER_SLUG = {
    "A.P.C.": "apc",
    "Café Kitsuné": "kitsune",
    "Maison Kitsuné": "kitsune",
    "MM6 Maison Margiela": "mm6",
    "MM6": "mm6",
    "XG": "xg",
}


def load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_items() -> list[dict]:
    if not ITEMS_PATH.exists():
        return []
    return json.loads(ITEMS_PATH.read_text(encoding="utf-8"))


def load_seen() -> set[str]:
    if not SEEN_PATH.exists():
        return set()
    return set(json.loads(SEEN_PATH.read_text(encoding="utf-8")))


def save_items(items: list[dict]) -> None:
    DATA.mkdir(exist_ok=True)
    ITEMS_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_seen(seen: set[str]) -> None:
    DATA.mkdir(exist_ok=True)
    SEEN_PATH.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slug(text: str) -> str:
    if text in PARTNER_SLUG:
        return PARTNER_SLUG[text]
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    if ascii_text:
        return ascii_text[:24]
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def make_title(partner: str, watch: str, models: list[dict]) -> str:
    refs = " ".join(model["ref"] for model in models if model.get("ref"))
    title = f"{partner} × {watch}"
    if refs:
        title += f" {refs}"
    return title


def make_summary(partner: str, watch: str, models: list[dict], dates: dict) -> str:
    refs = "、".join(model["ref"] for model in models if model.get("ref"))
    prices = [model["price_jpy"] for model in models if model.get("price_jpy")]
    bits = [f"{partner}と{watch}のコラボです。"]
    detail = []
    if refs:
        detail.append(refs)
    if prices:
        low = min(prices)
        detail.append(f"{low:,}円から" if len(set(prices)) > 1 else f"{low:,}円")
    if detail and dates.get("release_at"):
        bits.append(f"{'、'.join(detail)}。発売は{format_long(dates['release_at'])}。")
    elif dates.get("release_at"):
        bits.append(f"発売は{format_long(dates['release_at'])}。")
    elif detail:
        bits.append(f"{'、'.join(detail)}。")
    if dates.get("preorder_start"):
        bits.append(f"先行予約は{format_long(dates['preorder_start'])}。")
    return "".join(bits)


def make_id(partner: str, watch: str, models: list[dict], dates: dict) -> str:
    year = datetime.now(JST).year
    for key in ("release_at", "preorder_start"):
        if dates.get(key):
            year = int(dates[key][:4])
            break
    ref = next((model["ref"] for model in models if model.get("ref")), "")
    parts = [slug(partner), slug(watch)]
    if ref:
        parts.append(slug(ref))
    parts.append(str(year))
    return "-".join(parts)[:80]


def build_record(candidate: dict, parsed: dict) -> dict | None:
    watch = parsed.get("watch_brand")
    partner = parsed.get("partner_brand")
    models = [model for model in parsed.get("models") or [] if model.get("ref") or model.get("price_jpy")]
    if not watch or not partner:
        return None
    dates = {
        key: parsed[key]
        for key in ("preorder_start", "preorder_end", "release_at")
        if parsed.get(key)
    }
    if not dates and not models and not partner:
        return None
    record = {
        "id": make_id(partner, watch, models, dates),
        "watch_brand": watch,
        "partner_brand": partner,
        "title": make_title(partner, watch, models),
        "summary": make_summary(partner, watch, models, dates),
        "models": models,
        "conditions": parsed.get("conditions") or [],
        "channels": parsed.get("channels") or [],
        "sources": [{"name": candidate["source"], "url": candidate["url"]}],
        "notified": False,
        "reminded": [],
        "created_at": datetime.now(JST).replace(microsecond=0).isoformat(),
    }
    record.update(dates)
    source_urls = {item["url"] for item in record["channels"]}
    if candidate["url"] not in source_urls and "casio.co.jp/release" in candidate["url"]:
        record["channels"].insert(0, {"name": "公式の発表", "url": candidate["url"]})
    return record


def find_existing(items: list[dict], record: dict) -> dict | None:
    refs = {model["ref"].upper() for model in record.get("models") or [] if model.get("ref")}
    source_urls = {source["url"] for source in record.get("sources") or []}
    for old in items:
        old_refs = {model["ref"].upper() for model in old.get("models") or [] if model.get("ref")}
        if refs and old_refs & refs:
            return old
        old_urls = {source["url"] for source in old.get("sources") or []}
        if source_urls & old_urls:
            return old
    return None


def merge_record(old: dict, record: dict) -> bool:
    changed = False
    for key in ("preorder_start", "preorder_end", "release_at"):
        if record.get(key) and not old.get(key):
            old[key] = record[key]
            changed = True
    old_models = old.setdefault("models", [])
    have = {model["ref"].upper(): model for model in old_models if model.get("ref")}
    for model in record.get("models") or []:
        ref = model.get("ref") or ""
        current = have.get(ref.upper())
        if current is None and ref:
            old_models.append(model)
            have[ref.upper()] = model
            changed = True
        elif current is not None and not current.get("price_jpy") and model.get("price_jpy"):
            current["price_jpy"] = model["price_jpy"]
            changed = True
    for bucket in ("sources", "channels"):
        current_urls = {entry["url"] for entry in old.setdefault(bucket, [])}
        for entry in record.get(bucket) or []:
            if entry["url"] not in current_urls:
                old[bucket].append(entry)
                current_urls.add(entry["url"])
                changed = True
    for condition in record.get("conditions") or []:
        if condition not in old.setdefault("conditions", []):
            old["conditions"].append(condition)
            changed = True
    return changed


def run() -> None:
    load_env()
    now = datetime.now(JST).replace(microsecond=0)
    items = load_items()
    seen = load_seen()
    changed = False
    fresh: list[dict] = []
    fetched = 0
    limit = int(os.environ.get("MAX_FETCH") or "8")
    for candidate in collect_candidates():
        title = normalize(candidate["title"])
        if candidate["url"] in seen or not is_collab_title(title):
            continue
        if fetched >= limit:
            print("今回の確認はここまで。残りは次回見ます。")
            break
        try:
            page = fetch_text(candidate["url"])
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            print(f"ページを開けませんでした: {candidate['url']} ({error})")
            continue
        seen.add(candidate["url"])
        fetched += 1
        changed = True
        parsed = parse_release(page, candidate["url"], title, candidate.get("published"))
        record = build_record(candidate, parsed)
        if record is None:
            print(f"日時や相手ブランドが取れなかったので見送り: {title[:80]}")
            time.sleep(0.4)
            continue
        old = find_existing(items, record)
        if old is None:
            items.append(record)
            fresh.append(record)
            changed = True
            print(f"追加: {record['title']}")
        elif merge_record(old, record):
            changed = True
            print(f"追記: {old['title']}")
        else:
            print(f"掲載済み: {old['title']}")
        time.sleep(0.4)
    site_url = os.environ.get("SITE_URL", "").strip()
    if changed:
        save_items(items)
        save_seen(seen)
    build_site(items, now=now, site_url=site_url or "https://deek229.github.io/watch-collab-alert/")
    print(f"確認完了。新規 {len(fresh)}件、ページ上の合計 {len(items)}件。")


if __name__ == "__main__":
    run()
