# -*- coding: utf-8 -*-
"""フィードの見出しが、時計コラボの告知らしいかを判定する。"""

from __future__ import annotations

import re
import unicodedata

WATCH_BRANDS = (
    ("G-SHOCK", ("G-SHOCK", "Gショック", "ジーショック")),
    ("BABY-G", ("BABY-G", "ベビージー")),
    ("OCEANUS", ("OCEANUS", "オシアナス")),
    ("EDIFICE", ("EDIFICE", "エディフィス")),
    ("PRO TREK", ("PRO TREK", "プロトレック")),
    ("CASIO", ("CASIO", "カシオ", "CASIO CLASSIC", "カシオクラシック")),
    ("SEIKO", ("GRAND SEIKO", "グランドセイコー", "SEIKO", "セイコー")),
    ("CITIZEN", ("CITIZEN", "シチズン")),
    ("TIMEX", ("TIMEX", "タイメックス")),
    ("ORIENT", ("ORIENT STAR", "オリエントスター", "ORIENT", "オリエント")),
    ("SWATCH", ("SWATCH", "スウォッチ")),
    ("HAMILTON", ("HAMILTON", "ハミルトン")),
    ("TISSOT", ("TISSOT", "ティソ")),
)

# 見出しに名前があるだけでコラボ候補にする相手ブランド。
PARTNER_BRANDS = (
    "A.P.C.",
    "APC",
    "アー・ペー・セー",
    "アーペーセー",
    "BEAMS",
    "ビームス",
    "MM6",
    "マルジェラ",
    "Margiela",
    "sacai",
    "サカイ",
    "Café Kitsuné",
    "Cafe Kitsune",
    "カフェ キツネ",
    "メゾン キツネ",
    "メゾンキツネ",
    "Kitsuné",
    "NEIGHBORHOOD",
    "ネイバーフッド",
    "WTAPS",
    "fragment",
    "フラグメント",
    "HUMAN MADE",
    "ヒューマンメイド",
    "PORTER",
    "ポーター",
    "STUSSY",
    "ステューシー",
    "Supreme",
    "シュプリーム",
    "BAPE",
    "ベイプ",
    "FACETASM",
    "KAPITAL",
    "nonnative",
    "N.HOOLYWOOD",
    "mastermind",
    "BRIEFING",
    "ブリーフィング",
    "MAMMUT",
    "マムート",
    "WM ブラウン",
    "WM Brown",
    "Wm Brown",
    "XG",
    "エックスジー",
    "ITZY",
    "イッジ",
)

CASIO_CONTEXT = (
    "時計",
    "ウオッチ",
    "ウォッチ",
    "腕時計",
    "G-SHOCK",
    "Gショック",
    "BABY-G",
    "CLASSIC",
    "クラシック",
    "EDIFICE",
    "OCEANUS",
    "PRO TREK",
    "オシアナス",
)

COLLAB_WORDS = ("コラボ", "別注", "タッグ")
CROSS = re.compile(r"\s*[×ｘ]\s*|\s+[xX]\s+")
STOP_SIDE = (
    "文字盤",
    "文字板",
    "ベゼル",
    "ダイヤル",
    "DLC",
    "レザー",
    "ナイロン",
    "ラバー",
    "ステンレス",
    "メタル",
    "仕様",
    "搭載",
    "ムーブ",
    "ブラック",
    "ホワイト",
    "ゴールド",
    "シルバー",
    "レッド",
    "ブルー",
    "グリーン",
    "ネイビー",
    "ピンク",
    "グレー",
    "ブラウン",
    "ベージュ",
    "パープル",
    "イエロー",
    "オレンジ",
    "深紅",
    "紺",
    "黒",
    "白",
    "赤",
    "青",
    "緑",
    "金",
    "銀",
    "の",
    "モデル",
    "新作",
    "限定",
    "カラー",
    "IP",
)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    return " ".join(text.split())


def watch_brand(text: str) -> str | None:
    folded = normalize(text).casefold()
    for display, names in WATCH_BRANDS:
        for name in names:
            if name.casefold() in folded:
                return display
    return None


def _has_name(text: str, name: str) -> bool:
    folded = normalize(text).casefold()
    token = name.casefold()
    if re.search(r"[a-z0-9]", token) and not re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", name):
        return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", folded) is not None
    return token in folded


def partner_brand(text: str) -> str | None:
    hits = [name for name in PARTNER_BRANDS if _has_name(text, name)]
    if not hits:
        return None
    hits.sort(key=len, reverse=True)
    return hits[0]


def _casio_only(text: str) -> bool:
    brand = watch_brand(text)
    if brand != "CASIO":
        return False
    folded = normalize(text).casefold()
    return not any(word.casefold() in folded for word in CASIO_CONTEXT)


def _meaningful_side(side: str) -> bool:
    head = re.split(r"[、,。]", side or "")[0]
    cleaned = head
    for word in STOP_SIDE:
        cleaned = re.sub(re.escape(word), "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[\s・.\"'「」『』()（）\[\]【】〜~～×xXｘ\-]+", "", cleaned)
    return len(cleaned) >= 2


def _cross_is_collab(text: str) -> bool:
    parts = CROSS.split(normalize(text))
    if len(parts) < 2:
        return False
    for left, right in zip(parts, parts[1:]):
        left_head = re.split(r"[、,。]", left)[-1]
        right_head = re.split(r"[、,。]", right)[0]
        left_watch = watch_brand(left_head)
        right_watch = watch_brand(right_head)
        if left_watch and _meaningful_side(right_head) and not watch_brand(right_head):
            return True
        if right_watch and _meaningful_side(left_head) and not left_watch:
            return True
        if left_watch and right_watch and left_watch != right_watch:
            return True
    return False


def is_collab_title(title: str) -> bool:
    text = normalize(title)
    if not text or watch_brand(text) is None or _casio_only(text):
        return False
    if any(word in text for word in ("人事異動", "決算", "リコール", "機構改革")):
        return False
    if "イベント" in text and "発売" not in text and "予約" not in text:
        return False
    entertainment = any(word in text for word in ("映画", "アニメ", "ゲーム"))
    has_partner = partner_brand(text) is not None
    if entertainment and not has_partner:
        return False
    collab_word = any(word in text for word in COLLAB_WORDS)
    if has_partner and (collab_word or _cross_is_collab(text) or "発売" in text or "予約" in text):
        return True
    if collab_word:
        return True
    return _cross_is_collab(text)


def _demo() -> None:
    yes = [
        "「XG」×“G-SHOCK”のコラボレーションモデル第二弾",
        "Introducing: WM ブラウン × タイメックス",
        "【国産時計カシオクラシック】A.P.C.とのコラボモデル第2弾、11月12日のAM10:00より予約受付開始",
        "CASIO CLASSICとカフェ キツネのコラボウオッチ",
        "MM6 MAISON MARGIELA × TIMEXのT80ギフトセット",
    ]
    no = [
        "深紅の文字盤×ブラックDLC、シチズン・ミヨタ製ムーヴメント搭載ウオッチ",
        "カシオ“G-SHOCK”新作【ブラックIPメタルベゼル仕様GBM-2100】",
        "【ハミルトン最新時計】映画『オデュッセイア』との限定コラボモデル",
        "サンエックスユニバースのラベルが作れるラベルプリンター",
        "子どもと地域の未来を育む多彩な体験プログラムを展開",
    ]
    bad = [title for title in yes if not is_collab_title(title)]
    leaked = [title for title in no if is_collab_title(title)]
    if bad or leaked:
        raise SystemExit(f"判定ミス yes={bad} no={leaked}")
    print("filter ok", len(yes), len(no))


if __name__ == "__main__":
    _demo()
