#!/usr/bin/env python3
"""
爬取演唱会平台列表页（目前包含 3 个来源）并合并写入日历数据：

1) NOL World（Interpark global）
   https://world.nol.com/en/ticket/genre/CONCERT/products

2) YES24 Ticket（English / Concert）
   https://ticket.yes24.com/Pages/English/Perf/FnPerfList.aspx?Genre=15456

3) Ticketlink（Global / Performance / Concert）
   https://m.ticketlink.co.kr/global/en/performance/14

输出到 miniprogram/data/ticket_concerts.js / ticket_concerts.json，供小程序日历卡片展示。
跨日会按天拆成多条记录（方便日历点）。
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from html import unescape
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

NOL_URL = "https://world.nol.com/en/ticket/genre/CONCERT/products"
NOL_TICKET_URL = "https://world.nol.com/en/ticket"  # 主站票务页含更多场次（含 ZEROBASEONE 等）
NOL_BASE = "https://world.nol.com"
YES24_URL = "https://ticket.yes24.com/Pages/English/Perf/FnPerfList.aspx?Genre=15456"
YES24_BASE = "https://ticket.yes24.com"
TICKETLINK_URL = "https://m.ticketlink.co.kr/global/en/performance/14"
TICKETLINK_API = "https://mapi.ticketlink.co.kr/mapi/productList/show"
TICKETLINK_PRODUCT_BASE = "https://m.ticketlink.co.kr/global/en/product/"
OUTPUT_JS = os.path.join(os.path.dirname(__file__), "..", "miniprogram", "data", "ticket_concerts.js")
OUTPUT_JSON = os.path.join(os.path.dirname(__file__), "..", "miniprogram", "data", "ticket_concerts.json")

KST = ZoneInfo("Asia/Seoul")


def normalize(s: str) -> str:
    s = unescape(s or "")
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_ymd_zh(s: str) -> date | None:
    s = normalize(s)
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", s)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d)
    except Exception:
        return None


NOL_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def parse_nol_date_range_en(text: str) -> list[str]:
    """
    NOL EN 日期示例：
    - Mar 14, 2026 - Mar 15, 2026
    - Apr 11, 2026
    - Mar 07-08, 2026
    """
    text = normalize(text)
    if not text:
        return []
    t = text.replace("~", "-").replace("–", "-")
    t = re.sub(r"\s+", " ", t).strip()

    def mk(y: int, m: int, d: int) -> date | None:
        try:
            return date(y, m, d)
        except Exception:
            return None

    m = re.search(r"\b([A-Za-z]{3})\s+(\d{1,2})\s*-\s*(\d{1,2})\s*,\s*(\d{4})\b", t)
    if m:
        mon = NOL_MONTHS.get(m.group(1).lower())
        d1, d2, y = int(m.group(2)), int(m.group(3)), int(m.group(4))
        if not mon:
            return []
        start = mk(y, mon, d1)
        end = mk(y, mon, d2)
        if not start or not end:
            return []
        out = []
        cur = start
        while cur <= end:
            out.append(cur.isoformat())
            cur += timedelta(days=1)
        return out

    m = re.search(r"\b([A-Za-z]{3})\s+(\d{1,2})\s*,\s*(\d{4})\s*-\s*([A-Za-z]{3})\s+(\d{1,2})\s*,\s*(\d{4})\b", t)
    if m:
        m1 = NOL_MONTHS.get(m.group(1).lower())
        m2 = NOL_MONTHS.get(m.group(4).lower())
        d1, y1 = int(m.group(2)), int(m.group(3))
        d2, y2 = int(m.group(5)), int(m.group(6))
        if not m1 or not m2:
            return []
        start = mk(y1, m1, d1)
        end = mk(y2, m2, d2)
        if not start or not end:
            return []
        out = []
        cur = start
        while cur <= end:
            out.append(cur.isoformat())
            cur += timedelta(days=1)
        return out

    m = re.search(r"\b([A-Za-z]{3})\s+(\d{1,2})\s*,\s*(\d{4})\b", t)
    if m:
        mon = NOL_MONTHS.get(m.group(1).lower())
        d1, y = int(m.group(2)), int(m.group(3))
        if not mon:
            return []
        dt = mk(y, mon, d1)
        return [dt.isoformat()] if dt else []

    return []


def expand_date_range(date_text: str) -> list[str]:
    """
    输入示例：
    - 2026年3月14日 - 2026年3月15日
    - 2026年4月11日
    输出：['YYYY-MM-DD', ...]
    """
    date_text = normalize(date_text)
    parts = [p.strip() for p in re.split(r"\s*-\s*", date_text) if p.strip()]
    if not parts:
        return []
    if len(parts) == 1:
        d1 = parse_ymd_zh(parts[0])
        return [d1.isoformat()] if d1 else []
    d1 = parse_ymd_zh(parts[0])
    d2 = parse_ymd_zh(parts[1])
    if not d1 or not d2:
        return []
    if d2 < d1:
        d1, d2 = d2, d1
    out = []
    cur = d1
    while cur <= d2:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def infer_artist(title: str) -> str:
    title = normalize(title)
    # try split like "ARTIST ...", keep short
    if not title:
        return "Unknown"
    # Remove bracketed package prefix like [Play&Stay]
    title2 = re.sub(r"^[\[\(［【].*?[\]\)］】]\s*", "", title)
    # only split on " - " (space-hyphen-space). Avoid splitting inside words like "B-Day".
    parts = re.split(r"\s+-\s+", title2)
    cand = parts[0].strip()
    return cand[:50] if cand else title2[:50]


def infer_type(title: str) -> str:
    """
    简单规则：含 Fansign / Fan Meeting / Fan-Con / Fan Concert 归为「签售」，其余归为「演唱会」。
    """
    t = normalize(title).lower()
    if re.search(r"fan\s*(meeting|con\b|con-|concert|sign)", t, re.I) or "fansign" in t:
        return "签售"
    return "演唱会"


def fetch_html(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
    with urlopen(req, timeout=25) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_json(url: str) -> dict:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": TICKETLINK_URL,
        },
    )
    with urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def expand_date_range_ms(start_ms: int | None, end_ms: int | None) -> list[str]:
    if not start_ms:
        return []
    if not end_ms:
        end_ms = start_ms
    try:
        d1 = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc).astimezone(KST).date()
        d2 = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc).astimezone(KST).date()
    except Exception:
        return []
    if d2 < d1:
        d1, d2 = d2, d1
    out = []
    cur = d1
    while cur <= d2:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _parse_nol_rsc_blocks(html: str, filter_genre_concert: bool) -> list[dict]:
    """
    从 NOL 页内 RSC 内联数据中解析商品块（避免错爬 preload 等）。
    filter_genre_concert: True 时只保留 genreName==Concert（用于 /en/ticket）；False 时全部保留（用于 CONCERT/products）。
    返回 [{"goodsCode", "placeCode", "goodsName", "playStartDate", "playEndDate", "placeName", "coverImage?"}, ...]
    """
    raw: list[dict] = []
    # RSC 中为 \"goodsKey\":\"…\"（单反斜杠转义引号）
    blocks = re.split(r'\\"goodsKey\\":\\"', html)
    for block in blocks[1:]:
        m = re.match(r"(\d+):(\d+)\\\"", block)
        if not m:
            continue
        goods_code, place_code = m.group(1), m.group(2)
        nm = re.search(r'\\"goodsName\\":\\"([^"]+)\\"', block)
        gn = re.search(r'\\"genreName\\":\\"([^"]+)\\"', block)
        ps = re.search(r'\\"playStartDate\\":\\"([^"]*)\\"', block)
        pe = re.search(r'\\"playEndDate\\":\\"([^"]*)\\"', block)
        pn = re.search(r'\\"placeName\\":\\"([^"]*)\\"', block)
        if not nm or not ps:
            continue
        if filter_genre_concert and (not gn or gn.group(1) != "Concert"):
            continue
        cover = ""
        # 优先海报大图，其次小图
        im = re.search(r'\\"posterImageUrl\\":\\"([^"]*)\\"', block) or re.search(r'\\"goodsLargeImageUrl\\":\\"([^"]*)\\"', block)
        if im and im.group(1):
            cover = normalize(im.group(1))
        if not cover:
            im = re.search(r'\\"goodsSmallImageUrl\\":\\"([^"]*)\\"', block)
            if im and im.group(1):
                cover = normalize(im.group(1))
        raw.append(
            {
                "goodsCode": goods_code,
                "placeCode": place_code,
                "goodsName": normalize(nm.group(1)),
                "playStartDate": ps.group(1) if ps else "",
                "playEndDate": pe.group(1) if pe else "",
                "placeName": normalize(pn.group(1)) if pn else "",
                "coverImage": cover,
            }
        )
    return raw


def _rsc_blocks_to_items(raw_blocks: list[dict]) -> list[dict]:
    """把 RSC 解析出的商品块转成日历项（按天展开），并去重。"""
    items: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for b in raw_blocks:
        detail_url = f"{NOL_BASE}/en/ticket/genre/CONCERT/products/{b['goodsCode']}?placeCode={b['placeCode']}"
        start_s = (b.get("playStartDate") or "").strip()
        end_s = (b.get("playEndDate") or "").strip() or start_s
        if not start_s:
            continue
        try:
            d1 = date.fromisoformat(start_s)
            d2 = date.fromisoformat(end_s) if end_s else d1
        except Exception:
            continue
        if d2 < d1:
            d1, d2 = d2, d1
        cur = d1
        while cur <= d2:
            dk = cur.isoformat()
            key = (detail_url, dk)
            if key in seen:
                cur += timedelta(days=1)
                continue
            seen.add(key)
            title = (b.get("goodsName") or "")[:120]
            artist = infer_artist(title)
            items.append(
                {
                    "artist": artist,
                    "type": "演唱会",
                    "date": dk[5:],
                    "dateKey": dk,
                    "detail": title,
                    "detailUrl": detail_url,
                    "ticketPlatform": "NOL World",
                    "ticketTime": "",
                    "venue": b.get("placeName") or "",
                    "locationText": "",
                    "showTime": "",
                    "coverImage": b.get("coverImage") or "",
                }
            )
            cur += timedelta(days=1)
    items.sort(key=lambda x: (x["dateKey"], x["artist"], x["detailUrl"]))
    for i, it in enumerate(items):
        it["id"] = i + 1
    return items


def extract_items_nol(html: str, *, from_concert_products: bool = True) -> list[dict]:
    """
    从 NOL 页面内 RSC 内联数据提取演唱会项，避免错爬 preload/其他结构。
    from_concert_products: True 表示来自 /genre/CONCERT/products（全部为 Concert）；False 表示来自 /en/ticket（需按 genreName 过滤）。
    """
    filter_genre = not from_concert_products
    raw = _parse_nol_rsc_blocks(html, filter_genre_concert=filter_genre)
    return _rsc_blocks_to_items(raw)


YES24_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def parse_yes24_date_range(text: str) -> list[str]:
    """
    YES24 Date/Time 示例：
    - Apr 16, 2026
    - Mar 27-29, 2026
    - Feb 28 - Mar 01, 2026
    - Mar 28, 2026 ~ Mar 29, 2026
    """
    text = normalize(text)
    if not text:
        return []
    t = text.replace("~", "-").replace("–", "-")
    t = re.sub(r"\s+", " ", t).strip()

    def mk(y: int, m: int, d: int) -> date | None:
        try:
            return date(y, m, d)
        except Exception:
            return None

    # Same-month range: "Mar 27-29, 2026"
    m = re.search(r"\b([A-Za-z]{3})\s+(\d{1,2})\s*-\s*(\d{1,2})\s*,\s*(\d{4})\b", t)
    if m:
        mon = YES24_MONTHS.get(m.group(1).lower())
        d1, d2, y = int(m.group(2)), int(m.group(3)), int(m.group(4))
        if not mon:
            return []
        start = mk(y, mon, d1)
        end = mk(y, mon, d2)
        if not start or not end:
            return []
        out = []
        cur = start
        while cur <= end:
            out.append(cur.isoformat())
            cur += timedelta(days=1)
        return out

    # Cross-month range in one year: "Feb 28 - Mar 01, 2026"
    m = re.search(r"\b([A-Za-z]{3})\s+(\d{1,2})\s*-\s*([A-Za-z]{3})\s+(\d{1,2})\s*,\s*(\d{4})\b", t)
    if m:
        m1 = YES24_MONTHS.get(m.group(1).lower())
        m2 = YES24_MONTHS.get(m.group(3).lower())
        d1, d2, y = int(m.group(2)), int(m.group(4)), int(m.group(5))
        if not m1 or not m2:
            return []
        start = mk(y, m1, d1)
        end = mk(y, m2, d2)
        if not start or not end:
            return []
        out = []
        cur = start
        while cur <= end:
            out.append(cur.isoformat())
            cur += timedelta(days=1)
        return out

    # Two explicit dates with years: "Mar 28, 2026 - Mar 29, 2026"
    m = re.search(
        r"\b([A-Za-z]{3})\s+(\d{1,2})\s*,\s*(\d{4})\s*-\s*([A-Za-z]{3})\s+(\d{1,2})\s*,\s*(\d{4})\b",
        t,
    )
    if m:
        m1 = YES24_MONTHS.get(m.group(1).lower())
        m2 = YES24_MONTHS.get(m.group(4).lower())
        d1, y1 = int(m.group(2)), int(m.group(3))
        d2, y2 = int(m.group(5)), int(m.group(6))
        if not m1 or not m2:
            return []
        start = mk(y1, m1, d1)
        end = mk(y2, m2, d2)
        if not start or not end:
            return []
        out = []
        cur = start
        while cur <= end:
            out.append(cur.isoformat())
            cur += timedelta(days=1)
        return out

    # Single date: "Apr 16, 2026"
    m = re.search(r"\b([A-Za-z]{3})\s+(\d{1,2})\s*,\s*(\d{4})\b", t)
    if m:
        mon = YES24_MONTHS.get(m.group(1).lower())
        d1, y = int(m.group(2)), int(m.group(3))
        if not mon:
            return []
        dt = mk(y, mon, d1)
        return [dt.isoformat()] if dt else []

    return []


def extract_items_yes24(html: str) -> list[dict]:
    """
    YES24 页面结构：每条记录包含：
      <ul class="list_wrap"> ... <h3><a href="/Pages/English/Perf/FnPerfDeail.aspx?IdPerf=...">TITLE</a></h3> ... </ul>
      <div class="btn"><a href="..."><span class="btntxt">Booking</span></a></div>
    """
    items: list[dict] = []
    seen = set()  # (detailUrl, dateKey)

    for m in re.finditer(r'(?is)<ul\s+class="list_wrap">([\s\S]*?)</ul>\s*<div\s+class="btn">([\s\S]*?)</div>', html):
        ul = m.group(1)
        btn = m.group(2)

        tm = re.search(r'(?is)<h3>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>\s*</h3>', ul)
        if not tm:
            continue
        href = tm.group(1)
        title = normalize(re.sub(r"<[^>]+>", "", tm.group(2)))
        if not title:
            continue
        detail_url = urljoin(YES24_BASE, href)

        im = re.search(r'(?is)<li\s+class="poster"[\s\S]*?<img[^>]+src="([^"]+)"', ul)
        cover = normalize(im.group(1)) if im else ""

        date_text = ""
        venue = ""
        show_time = ""
        for k_raw, v_raw in re.findall(r"(?is)<li>\s*<span>([^<]+)</span>\s*:\s*([^<]+)</li>", ul):
            k = normalize(k_raw).lower()
            v = normalize(v_raw)
            if k.startswith("date/time"):
                date_text = v
                tm = re.search(r"(\d{1,2}:\d{2}\s*(?:AM|PM)?)", v, re.I)
                if tm:
                    show_time = tm.group(1).strip()
            elif k.startswith("venue"):
                venue = v

        date_keys = parse_yes24_date_range(date_text)
        if not date_keys:
            continue

        bm = re.search(r'(?is)href="([^"]+)"[^>]*>\s*<span[^>]*>\s*Booking\s*</span>', btn)
        if bm:
            detail_url = urljoin(YES24_BASE, bm.group(1))

        artist = infer_artist(title)
        # 你的需求：票务平台页（NOL/YES24/Ticketlink）统一归到「演唱会」tab
        event_type = "演唱会"
        detail = title[:120]

        for dk in date_keys:
            key = (detail_url, dk)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "artist": artist,
                    "type": event_type,
                    "date": dk[5:],
                    "dateKey": dk,
                    "detail": detail,
                    "detailUrl": detail_url,
                    "ticketPlatform": "YES24",
                    "ticketTime": "",
                    "venue": venue,
                    "locationText": "",
                    "showTime": show_time,
                    "coverImage": cover,
                }
            )

    items.sort(key=lambda x: (x["dateKey"], x["artist"], x["detailUrl"]))
    for i, it in enumerate(items):
        it["id"] = i + 1
    return items


def extract_items_ticketlink(category2_id: int = 14) -> list[dict]:
    """
    Ticketlink Global Concert 列表通过 mapi 接口获取：
      GET https://mapi.ticketlink.co.kr/mapi/productList/show?categoryId=14&page=1
    返回字段包含：
      productId/productName/productImagePath/hallName/locationName/startDate/endDate/category2Id/category2Name...
    """
    items: list[dict] = []
    seen = set()  # (detailUrl, dateKey)

    page = 1
    page_count = 1
    while page <= page_count:
        url = f"{TICKETLINK_API}?categoryId={category2_id}&page={page}"
        obj = fetch_json(url)
        data = obj.get("data") or {}
        paging = data.get("paging") or {}
        page_count = int(paging.get("pageCount") or page_count or 1)
        results = data.get("result") or []
        if not isinstance(results, list) or not results:
            break

        for it in results:
            try:
                product_id = it.get("productId")
                title = normalize(it.get("productName") or "")
                if not product_id or not title:
                    continue
                # Ensure this is the expected subcategory (concert)
                if it.get("category2Id") is not None and int(it.get("category2Id")) != int(category2_id):
                    continue

                detail_url = f"{TICKETLINK_PRODUCT_BASE}{product_id}"
                cover = normalize(it.get("productImagePath") or "")
                if cover.startswith("//"):
                    cover = "https:" + cover

                hall = normalize(it.get("hallName") or "")
                loc = normalize(it.get("locationName") or "")
                venue = hall or loc

                date_keys = expand_date_range_ms(it.get("startDate"), it.get("endDate"))
                if not date_keys:
                    continue

                artist = infer_artist(title)
                # Ticketlink 这里是 콘서트 카테고리（category2Id=14），即使标题含 FANMEETING 等关键字，
                # 也按你的需求统一归入「演唱会」tab，避免跑到「签售」里。
                event_type = "演唱会"
                detail = title[:120]

                for dk in date_keys:
                    key = (detail_url, dk)
                    if key in seen:
                        continue
                    seen.add(key)
                    items.append(
                        {
                            "artist": artist,
                            "type": event_type,
                            "date": dk[5:],
                            "dateKey": dk,
                            "detail": detail,
                            "detailUrl": detail_url,
                            "ticketPlatform": "Ticketlink",
                            "ticketTime": "",
                            "venue": hall,
                            "locationText": loc if loc != hall else "",
                            "showTime": "",
                            "coverImage": cover,
                        }
                    )
            except Exception:
                continue

        page += 1

    items.sort(key=lambda x: (x["dateKey"], x["artist"], x["detailUrl"]))
    for i, it in enumerate(items):
        it["id"] = i + 1
    return items


def main() -> None:
    print("正在请求 NOL CONCERT 列表:", NOL_URL)
    try:
        nol_products_html = fetch_html(NOL_URL)
    except Exception as e:
        print("NOL CONCERT 请求失败:", e)
        nol_products_html = ""

    print("正在请求 NOL 票务主站（更多场次）:", NOL_TICKET_URL)
    try:
        nol_ticket_html = fetch_html(NOL_TICKET_URL)
    except Exception as e:
        print("NOL 票务主站 请求失败:", e)
        nol_ticket_html = ""

    items = []
    if nol_products_html:
        nol_products_items = extract_items_nol(nol_products_html, from_concert_products=True)
        items.extend(nol_products_items)
        print("NOL CONCERT 列表 解析:", len(nol_products_items), "条")
    if nol_ticket_html:
        nol_ticket_items = extract_items_nol(nol_ticket_html, from_concert_products=False)
        items.extend(nol_ticket_items)
        print("NOL 票务主站 解析:", len(nol_ticket_items), "条")

    print("正在请求 YES24:", YES24_URL)
    try:
        yes24_html = fetch_html(YES24_URL)
    except Exception as e:
        print("YES24 请求失败:", e)
        yes24_html = ""

    print("正在请求 Ticketlink:", TICKETLINK_URL)
    try:
        ticketlink_items = extract_items_ticketlink(14)
    except Exception as e:
        print("Ticketlink 请求失败:", e)
        ticketlink_items = []

    if yes24_html:
        items.extend(extract_items_yes24(yes24_html))
    if ticketlink_items:
        items.extend(ticketlink_items)

    # 防误收：部分票务接口会把专辑商品或售卖期误当成演出日期区间。
    # 同一链接拆出超过 31 天，或标题明显是专辑版本时，不进入正式日历。
    link_counts = {}
    for it in items:
        link = it.get("detailUrl") or ""
        link_counts[link] = link_counts.get(link, 0) + 1

    # merge + re-id
    seen = set()
    merged = []
    today = datetime.now(KST).date()
    max_date = today + timedelta(days=550)
    for it in items:
        title = "%s %s" % (it.get("artist") or "", it.get("detail") or "")
        try:
            event_date = date.fromisoformat(it.get("dateKey") or "")
        except Exception:
            continue
        if event_date > max_date:
            continue
        if link_counts.get(it.get("detailUrl") or "", 0) > 31:
            continue
        if re.search(r"\b(?:mini|full|single)\s+album\b|\b[ABC]\s+Ver\.|fanclub.*(?:recruit|모집)", title, re.I):
            continue
        key = (it.get("ticketPlatform"), it.get("detailUrl"), it.get("dateKey"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(it)

    merged.sort(key=lambda x: (x.get("dateKey") or "", x.get("type") or "", x.get("artist") or "", x.get("ticketPlatform") or "", x.get("detailUrl") or ""))
    for i, it in enumerate(merged):
        it["id"] = i + 1

    print("解析到", len(merged), "条（跨日已拆分，已合并 NOL + YES24 + Ticketlink）")

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    js = "// 由 scripts/scrape_nol_concerts.py 从 NOL World + YES24 + Ticketlink 抓取\nmodule.exports = " + json.dumps(merged, ensure_ascii=False) + ";"
    with open(OUTPUT_JS, "w", encoding="utf-8") as f:
        f.write(js)

    print("已写入:", OUTPUT_JS)
    print("已写入:", OUTPUT_JSON)


if __name__ == "__main__":
    main()
