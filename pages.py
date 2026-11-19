# -*- coding: utf-8 -*-
"""発売カレンダーのHTMLを書く。日時の並びはここで決める。"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
WEEK = "月火水木金土日"

CSS = """
:root {
  --paper: #e9e2d6;
  --sheet: #f6f1e8;
  --ink: #1c1916;
  --muted: #6f675d;
  --line: #d5cdc0;
  --stamp: #8e2c2a;
  --sale: #1d5c40;
  --archive: #7a7268;
  --shadow: 0 1px 0 rgba(28, 25, 22, 0.04);
  font-family: "Zen Kaku Gothic New", "Hiragino Sans", "Yu Gothic", sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background:
    radial-gradient(circle at top left, rgba(142, 44, 42, 0.06), transparent 28rem),
    var(--paper);
  color: var(--ink);
}
a { color: inherit; }
.wrap { width: min(46rem, calc(100% - 2rem)); margin: 0 auto; padding: 2.2rem 0 4rem; }
.masthead { border-top: 2px solid var(--ink); padding-top: 0.9rem; }
.eyebrow {
  margin: 0;
  letter-spacing: 0.18em;
  font-size: 0.72rem;
  color: var(--muted);
}
h1 {
  margin: 0.35rem 0 0.4rem;
  font-family: "Zen Old Mincho", "Yu Mincho", serif;
  font-size: clamp(1.8rem, 4vw, 2.5rem);
  font-weight: 700;
  letter-spacing: 0.02em;
  line-height: 1.25;
}
.lead { margin: 0; max-width: 38rem; line-height: 1.75; color: var(--muted); }
.filters { display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 1.4rem 0 0.4rem; }
.filters button {
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
  border-radius: 999px;
  padding: 0.35rem 0.8rem;
  font: inherit;
  cursor: pointer;
}
.filters button[aria-pressed="true"] { background: var(--ink); color: var(--sheet); border-color: var(--ink); }
.section { margin-top: 1.8rem; }
.section h2 {
  margin: 0 0 0.7rem;
  font-size: 0.82rem;
  letter-spacing: 0.14em;
  font-weight: 500;
  color: var(--muted);
}
.card {
  display: grid;
  grid-template-columns: 6.6rem 1fr;
  gap: 0.9rem 1rem;
  padding: 1rem 0;
  border-top: 1px solid var(--line);
  background: transparent;
}
.when { padding-top: 0.15rem; border-top: 3px solid var(--ink); }
.card.upcoming .when { border-top-color: var(--stamp); }
.card.onsale .when { border-top-color: var(--sale); }
.card.archive .when { border-top-color: var(--archive); }
.when .md {
  display: block;
  font-family: "Zen Old Mincho", serif;
  font-size: 1.7rem;
  line-height: 1.1;
}
.when .sub, .when .label { display: block; color: var(--muted); font-size: 0.78rem; margin-top: 0.15rem; }
.card.upcoming .label { color: var(--stamp); }
.brands { margin: 0; font-size: 0.78rem; letter-spacing: 0.08em; color: var(--muted); }
.card h3 { margin: 0.15rem 0 0.35rem; font-family: "Zen Old Mincho", serif; font-size: 1.28rem; font-weight: 700; line-height: 1.4; }
.card h3 a { text-decoration: none; }
.card h3 a:hover { text-decoration: underline; }
.summary, .note, .cond { margin: 0.2rem 0; line-height: 1.7; }
.note { color: var(--muted); font-size: 0.92rem; }
.models { margin: 0.45rem 0 0; padding: 0; list-style: none; color: var(--ink); }
.models li { margin: 0.12rem 0; }
.actions { display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 0.7rem; }
.actions a {
  text-decoration: none;
  border: 1px solid var(--ink);
  padding: 0.28rem 0.6rem;
  border-radius: 999px;
  font-size: 0.86rem;
}
.actions a.quiet { border-color: var(--line); color: var(--muted); }
footer { margin-top: 2.4rem; color: var(--muted); font-size: 0.86rem; line-height: 1.7; }
.detail { padding-top: 1.2rem; }
.detail .back { color: var(--muted); text-decoration: none; }
.facts { margin: 1rem 0; padding: 0; list-style: none; }
.facts li { padding: 0.55rem 0; border-top: 1px solid var(--line); line-height: 1.6; }
.facts strong { display: inline-block; min-width: 6.5rem; }
@media (max-width: 640px) {
  .card { grid-template-columns: 1fr; gap: 0.45rem; }
  .when { display: flex; gap: 0.7rem; align-items: baseline; }
}
"""


def parse_when(value: str | None) -> tuple[datetime | None, bool]:
    if not value:
        return None, False
    if "T" not in value:
        year, month, day = (int(part) for part in value.split("-"))
        return datetime(year, month, day, tzinfo=JST), False
    return datetime.fromisoformat(value), True


def is_future(value: str | None, now: datetime) -> bool:
    moment, known = parse_when(value)
    if moment is None:
        return False
    if known:
        return moment > now
    return moment.date() >= now.date()


def group_of(item: dict, now: datetime) -> str:
    if item.get("status_override") == "ended":
        return "archive"
    if is_future(item.get("preorder_start"), now) or is_future(item.get("release_at"), now):
        return "upcoming"
    if item.get("preorder_start") and is_future(item.get("preorder_end"), now) and (
        not item.get("release_at") or is_future(item.get("release_at"), now)
    ):
        return "upcoming"
    if not item.get("release_at") and not item.get("preorder_start"):
        created, _known = parse_when(item.get("created_at"))
        if created is not None and (now.date() - created.date()).days <= 21:
            return "upcoming"
        return "archive"
    anchor, _known = parse_when(item.get("release_at") or item.get("preorder_start"))
    if anchor is not None and (now.date() - anchor.date()).days <= 45:
        return "onsale"
    return "archive"


def primary(item: dict, now: datetime) -> tuple[str | None, str]:
    group = group_of(item, now)
    if group == "upcoming":
        if is_future(item.get("preorder_start"), now):
            return item.get("preorder_start"), "先行予約"
        if is_future(item.get("preorder_end"), now):
            return item.get("preorder_end"), "予約締切"
        if item.get("release_at"):
            return item.get("release_at"), "発売"
        return None, "新着"
    if item.get("release_at"):
        return item.get("release_at"), "発売済"
    if item.get("preorder_start"):
        return item.get("preorder_start"), "告知"
    return item.get("created_at"), "記録"


def format_long(value: str | None) -> str:
    moment, known = parse_when(value)
    if moment is None:
        return "未記載"
    text = f"{moment.month}月{moment.day}日（{WEEK[moment.weekday()]}）"
    if known:
        return text + f" {moment.hour:02d}:{moment.minute:02d}"
    return text + "・時刻は出典で確認"


def format_yen(value: int) -> str:
    return f"{value:,}円"


def price_label(item: dict) -> str:
    prices = [model["price_jpy"] for model in item.get("models") or [] if model.get("price_jpy")]
    if not prices:
        return ""
    low, high = min(prices), max(prices)
    if low == high:
        return format_yen(low)
    return f"{format_yen(low)}〜"


def _esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def _links(item: dict, quiet: bool = False) -> str:
    parts = []
    shown: set[str] = set()
    for channel in item.get("channels") or []:
        if channel["url"] in shown:
            continue
        shown.add(channel["url"])
        parts.append(f'<a href="{_esc(channel["url"])}">{_esc(channel["name"])}</a>')
    for source in item.get("sources") or []:
        if source["url"] in shown:
            continue
        shown.add(source["url"])
        parts.append(f'<a class="quiet" href="{_esc(source["url"])}">{_esc(source["name"])}</a>')
    if not parts:
        return ""
    return f'<p class="actions">{"".join(parts)}</p>'


def _models(item: dict) -> str:
    rows = []
    for model in item.get("models") or []:
        bits = []
        if model.get("ref"):
            bits.append(_esc(model["ref"]))
        if model.get("detail"):
            bits.append(_esc(model["detail"]))
        if model.get("price_jpy"):
            bits.append(_esc(format_yen(model["price_jpy"])))
        if bits:
            rows.append(f"<li>{' / '.join(bits)}</li>")
    if not rows:
        return ""
    return f'<ul class="models">{"".join(rows)}</ul>'


def render_card(item: dict, now: datetime) -> str:
    group = group_of(item, now)
    when, label = primary(item, now)
    moment, known = parse_when(when)
    if moment is None:
        md, sub = ("未定", "") if label == "新着" else ("―", "")
    else:
        md = f"{moment.month}/{moment.day}"
        sub = f"{moment.hour:02d}:{moment.minute:02d}" if known else "時刻は出典"
    note = f'<p class="note">{_esc(item["note"])}</p>' if item.get("note") else ""
    conds = "".join(f'<p class="cond">{_esc(cond)}</p>' for cond in item.get("conditions") or [])
    brands = " × ".join(part for part in (item.get("partner_brand"), item.get("watch_brand")) if part)
    return f"""
<article class="card {group}" data-group="{group}">
  <div class="when">
    <span class="md">{_esc(md)}</span>
    <span class="sub">{_esc(sub)}</span>
    <span class="label">{_esc(label)}</span>
  </div>
  <div>
    <p class="brands">{_esc(brands)}</p>
    <h3><a href="items/{_esc(item["id"])}.html">{_esc(item["title"])}</a></h3>
    <p class="summary">{_esc(item.get("summary"))}</p>
    {note}
    {_models(item)}
    {conds}
    {_links(item)}
  </div>
</article>"""


def render_detail(item: dict, now: datetime) -> str:
    when, label = primary(item, now)
    facts = [
        ("いちばん近い予定", f"{label} {format_long(when)}" if when else "未記載"),
        ("先行予約", format_long(item.get("preorder_start")) if item.get("preorder_start") else ""),
        ("予約の終了", format_long(item.get("preorder_end")) if item.get("preorder_end") else ""),
        ("一般発売", format_long(item.get("release_at")) if item.get("release_at") else ""),
        ("価格", price_label(item)),
    ]
    fact_html = "".join(
        f"<li><strong>{_esc(name)}</strong>{_esc(value)}</li>" for name, value in facts if value
    )
    conds = "".join(f"<li>{_esc(cond)}</li>" for cond in item.get("conditions") or [])
    brands = " × ".join(part for part in (item.get("partner_brand"), item.get("watch_brand")) if part)
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(item["title"])}｜コラボ時計の発売予定</title>
  <link rel="stylesheet" href="../style.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@400;500&family=Zen+Old+Mincho:wght@500;700&display=swap">
</head>
<body>
  <div class="wrap detail">
    <p><a class="back" href="../index.html">← 一覧へ</a></p>
    <p class="eyebrow">{_esc(brands)}</p>
    <h1>{_esc(item["title"])}</h1>
    <p class="lead">{_esc(item.get("summary"))}</p>
    {f'<p class="note">{_esc(item["note"])}</p>' if item.get("note") else ""}
    <ul class="facts">{fact_html}{conds}</ul>
    {_models(item)}
    {_links(item)}
  </div>
</body>
</html>
"""


def render_index(items: list[dict], now: datetime) -> str:
    groups = {"upcoming": [], "onsale": [], "archive": []}
    for item in items:
        groups[group_of(item, now)].append(item)

    def sort_time(item: dict) -> datetime:
        value, _label = primary(item, now)
        moment, _known = parse_when(value)
        return moment or datetime.min.replace(tzinfo=JST)

    def sort_upcoming(item: dict) -> datetime:
        _when, label = primary(item, now)
        if label == "新着":
            return datetime(9999, 1, 1, tzinfo=JST)
        return sort_time(item)

    groups["upcoming"].sort(key=sort_upcoming)
    groups["onsale"].sort(key=sort_time, reverse=True)
    groups["archive"].sort(key=sort_time, reverse=True)
    titles = {"upcoming": "これから", "onsale": "販売中", "archive": "記録"}
    sections = []
    for key in ("upcoming", "onsale", "archive"):
        cards = "".join(render_card(item, now) for item in groups[key])
        if not cards:
            cards = '<p class="note">いま、この区分の情報はありません。</p>'
        sections.append(f'<section class="section" id="{key}"><h2>{titles[key]}</h2>{cards}</section>')
    count = len(items)
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>コラボ時計の発売予定</title>
  <meta name="description" content="大手時計メーカーとファッションブランドやアーティストの限定コラボについて、先行予約と発売日、購入ページを集めます。">
  <link rel="stylesheet" href="style.css">
  <link rel="alternate" type="application/rss+xml" title="コラボ時計の発売予定" href="feed.xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@400;500&family=Zen+Old+Mincho:wght@500;700&display=swap">
</head>
<body>
  <div class="wrap">
    <header class="masthead">
      <p class="eyebrow">COLLAB WATCH CALENDAR</p>
      <h1>コラボ時計の発売予定</h1>
      <p class="lead">大手時計メーカーと、ファッションブランドやアーティストの限定モデルについて、先行予約と発売日、買う場所だけを集めています。記事の本文は載せず、公式とニュースへリンクします。</p>
      <div class="filters">
        <button type="button" data-filter="all" aria-pressed="true">すべて</button>
        <button type="button" data-filter="upcoming" aria-pressed="false">これから</button>
        <button type="button" data-filter="onsale" aria-pressed="false">販売中</button>
        <button type="button" data-filter="archive" aria-pressed="false">記録</button>
      </div>
    </header>
    {"".join(sections)}
    <footer>
      <p>掲載 {count}件。新しい告知は、決めたニュース一覧を1日1回確認して足しています。</p>
      <p>発売日や予約条件は変わることがあります。買う前に、リンク先の最新案内を見てください。</p>
      <p><a href="feed.xml">更新フィード</a></p>
    </footer>
  </div>
  <script>
    const buttons = document.querySelectorAll("[data-filter]");
    buttons.forEach((button) => {{
      button.addEventListener("click", () => {{
        const filter = button.dataset.filter;
        buttons.forEach((other) => other.setAttribute("aria-pressed", other === button ? "true" : "false"));
        document.querySelectorAll(".card").forEach((card) => {{
          card.hidden = filter !== "all" && card.dataset.group !== filter;
        }});
        document.querySelectorAll(".section").forEach((section) => {{
          section.hidden = filter !== "all" && section.id !== filter;
        }});
      }});
    }});
  </script>
</body>
</html>
"""


def render_feed(items: list[dict], site_url: str) -> str:
    site_url = site_url.rstrip("/") + "/"
    rows = []
    ordered = sorted(items, key=lambda item: item.get("created_at") or "", reverse=True)
    for item in ordered[:30]:
        link = site_url + "items/" + item["id"] + ".html"
        title = _esc(item["title"])
        summary = _esc(item.get("summary") or "")
        stamp = _esc(item.get("created_at") or "")
        rows.append(
            f"<item><title>{title}</title><link>{_esc(link)}</link>"
            f"<guid>{_esc(link)}</guid><pubDate>{stamp}</pubDate>"
            f"<description>{summary}</description></item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        "<title>コラボ時計の発売予定</title>"
        f"<link>{_esc(site_url)}</link>"
        "<description>先行予約と発売日の更新</description>"
        + "".join(rows)
        + "</channel></rss>"
    )


def build_site(items: list[dict], now: datetime | None = None, site_url: str = "") -> None:
    now = now or datetime.now(JST)
    DOCS.mkdir(exist_ok=True)
    (DOCS / "items").mkdir(exist_ok=True)
    (DOCS / "style.css").write_text(CSS, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    (DOCS / "index.html").write_text(render_index(items, now), encoding="utf-8")
    for item in items:
        (DOCS / "items" / f"{item['id']}.html").write_text(render_detail(item, now), encoding="utf-8")
    if site_url:
        (DOCS / "feed.xml").write_text(render_feed(items, site_url), encoding="utf-8")
