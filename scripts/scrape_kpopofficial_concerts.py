#!/usr/bin/env python3
"""
爬取 https://kpopofficial.com/kpop-concerts/ 的演唱会/签售日程（列表页轻量字段），
输出为 miniprogram/data/concerts.js 和 concerts.json，供小程序日历使用。

数据来源：KPOP OFFICIAL (https://kpopofficial.com)，仅供个人学习使用。
"""

from __future__ import annotations

import json
import os
import re
from html import unescape
from urllib.parse import urljoin
from urllib.request import Request, urlopen

URL = "https://kpopofficial.com/kpop-concerts/"
OUTPUT_JS = os.path.join(os.path.dirname(__file__), "..", "miniprogram", "data", "concerts.js")
OUTPUT_JSON = os.path.join(os.path.dirname(__file__), "..", "miniprogram", "data", "concerts.json")

MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def _normalize_text(s: str) -> str:
    if not s:
        return ""
    s = unescape(s)
    # normalize dashes
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    s = s.replace("&#8211;", "-").replace("&#x2013;", "-").replace("&#8212;", "-")
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_date_range(text: str, default_year: int = 2026) -> list[str]:
    """
    解析日期或日期范围，返回 dateKey 列表（YYYY-MM-DD）。
    支持：
    - February 9, 2026
    - February 13 - 15, 2026
    - February 13 - 15, 2026 · Friday · Saturday · Sunday
    - May 8 -10, 2026
    """
    text = _normalize_text(text)
    if not text:
        return []

    year = default_year
    ym = re.search(r"\b(20\d{2})\b", text)
    if ym:
        year = int(ym.group(1))

    month = None
    for name, num in MONTH_NAMES.items():
        if re.search(r"\b" + re.escape(name) + r"\b", text, re.I):
            month = num
            break
    if not month:
        return []

    # range first
    rm = re.search(r"\b(\d{1,2})\s*-\s*(\d{1,2})\b", text)
    if rm:
        d1, d2 = int(rm.group(1)), int(rm.group(2))
        if d1 <= d2:
            return [f"{year}-{month:02d}-{d:02d}" for d in range(d1, d2 + 1)]

    # single day
    sm = re.search(
        r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})\b",
        text,
        re.I,
    )
    if sm:
        day = int(sm.group(1))
        return [f"{year}-{month:02d}-{day:02d}"]

    return []


def infer_type(title: str) -> str:
    t = (title or "").lower()
    if "fansign" in t or "fan sign" in t:
        return "签售"
    return "演唱会"


def infer_artist(title: str, slug: str) -> str:
    title = _normalize_text(title)
    if title:
        # split on dash-like separators
        parts = re.split(r"\s*[–\-]\s*", title)
        if parts:
            cand = re.sub(r"\[(?:canceled|cancelled|postponed)\]\s*", "", parts[0], flags=re.I).strip()
            if 1 < len(cand) <= 50:
                return cand
    # fallback
    slug = (slug or "").strip().strip("/")
    if not slug:
        return "Unknown"
    return slug.replace("-", " ").title()[:50]


def pick_cover_image(block: str) -> str | None:
    # collect wp-content images; ignore obvious icons
    urls = re.findall(r'src="(https?://[^"]+wp-content/uploads/[^"]+)"', block, re.I)
    if not urls:
        return None
    cleaned = []
    for u in urls:
        if any(x in u for x in ("icon-location", "fire-logo", "most-viewed", "smile.svg", "wpdiscuz", "gravatar")):
            continue
        cleaned.append(u)
    if not cleaned:
        return None
    # prefer cover images
    for u in cleaned:
        if "cover-" in u or "Cover-" in u or "Kpop-Concerts-Schedule" in u:
            return u
    return cleaned[0]


def extract_location_text(block: str) -> str | None:
    # heuristic: icon-location followed by text node
    block2 = _normalize_text(block)
    m = re.search(r"icon-location[^>]*>\s*([^<]{2,120}?)\s*(?:Views|View Details|Daily Views|Total Views)", block2, re.I)
    if m:
        return m.group(1).strip("· ").strip()[:120]

    # fallback: pick first comma-separated place-like text near icon-location
    m = re.search(r"icon-location[^>]*>\s*([^<]{2,120})", block2, re.I)
    if m:
        return m.group(1).strip("· ").strip()[:120]
    return None


def extract_title(block: str) -> str | None:
    # Prefer heading link text: <h2 ...><a ...>TITLE</a></h2>
    m = re.search(r"<h2[^>]*>[\s\S]*?<a[^>]*>([^<]{5,200})</a>", block, re.I)
    if m:
        return _normalize_text(m.group(1))
    # fallback: markdown-ish "## [Title]" if present in transformed content
    m = re.search(r"##\s*\[([^\]]{5,200})\]", block)
    if m:
        return _normalize_text(m.group(1))
    # fallback: any link text (skip View Details)
    for m in re.finditer(r">([^<]{5,200})</a>", block):
        t = _normalize_text(m.group(1))
        if not t or "view details" in t.lower():
            continue
        return t
    return None


def extract_date_text(block: str) -> str | None:
    block2 = _normalize_text(block)
    # month name + day (range optional) + year optional
    m = re.search(
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:\s*-\s*\d{1,2})?(?:\s*,\s*20\d{2})?\b",
        block2,
        re.I,
    )
    return _normalize_text(m.group(0)) if m else None


def extract_events_from_html(html: str) -> list[dict]:
    events: list[dict] = []
    seen = set()  # (detailUrl, dateKey)

    # Find all event links; analyze surrounding context.
    for m in re.finditer(r'href="([^"]*/event/[^"/]+/?)(?:\?[^"]*)?"', html, re.I):
        href = m.group(1)
        detail_url = urljoin(URL, href)
        # Keep a window around the link to parse date/title/location/cover.
        start = max(0, m.start() - 1800)
        end = min(len(html), m.end() + 1400)
        block = html[start:end]

        title = extract_title(block)
        if not title:
            continue

        date_text = extract_date_text(block)
        if not date_text:
            continue
        date_keys = parse_date_range(date_text)
        if not date_keys:
            continue

        slug = detail_url.split("/event/")[-1].strip("/").split("?")[0]
        event_type = infer_type(title)
        artist = infer_artist(title, slug)
        cover = pick_cover_image(block)
        loc = extract_location_text(block)

        # detail field: prefer full title; append location if it seems short and location exists
        detail = title
        if loc and len(detail) < 80 and loc.lower() not in detail.lower():
            detail = f"{detail} · {loc}"
        detail = _normalize_text(detail)[:120]

        for dk in date_keys:
            key = (detail_url, dk)
            if key in seen:
                continue
            seen.add(key)
            events.append(
                {
                    "artist": artist[:50],
                    "type": event_type,
                    "date": dk[5:],
                    "dateKey": dk,
                    "detail": detail,
                    "detailUrl": detail_url,
                    "coverImage": cover or "",
                    "locationText": loc or "",
                    "dateTextRaw": date_text,
                }
            )

    # deterministic ordering + assign ids
    events.sort(key=lambda x: (x.get("dateKey") or "", x.get("type") or "", x.get("artist") or "", x.get("detailUrl") or ""))
    for i, ev in enumerate(events):
        ev["id"] = i + 1
    return events


def main() -> None:
    print("正在请求:", URL)
    req = Request(URL, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
    try:
        with urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print("请求失败:", e)
        return

    items = extract_events_from_html(html)
    print(f"解析到 {len(items)} 条演唱会/签售日程（跨日已按天拆分）")

    os.makedirs(os.path.dirname(OUTPUT_JS), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    js_content = "// 由 scripts/scrape_kpopofficial_concerts.py 从 kpopofficial.com/kpop-concerts 抓取\nmodule.exports = " + json.dumps(items, ensure_ascii=False) + ";"
    with open(OUTPUT_JS, "w", encoding="utf-8") as f:
        f.write(js_content)

    print("已写入:", OUTPUT_JS)
    print("已写入:", OUTPUT_JSON)


if __name__ == "__main__":
    main()

