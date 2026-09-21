#!/usr/bin/env python3
"""
抓取 Ktown4u 的 Event/SIGNING 列表（用于「签售」tab）并写入小程序日历数据。

来源页面：
  https://cn.ktown4u.com/searchList?goodsTextSearch=Event

实际数据接口（站点内部使用）：
  https://apis.ktown4u.com/vador/v2/search/goods-list

输出：
  miniprogram/data/fansigns.json
  miniprogram/data/fansigns.js
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import date, datetime, timedelta
from html import unescape
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://apis.ktown4u.com/vador"
LIST_ENDPOINT = API_BASE + "/v2/search/goods-list"
DETAIL_BASE = "https://cn.ktown4u.com/iteminfo?goods_no="
SHOP_NO_CN = 164

OUTPUT_JS = os.path.join(os.path.dirname(__file__), "..", "miniprogram", "data", "fansigns.js")
OUTPUT_JSON = os.path.join(os.path.dirname(__file__), "..", "miniprogram", "data", "fansigns.json")


def normalize(s: str) -> str:
    s = unescape(s or "")
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_event_date_from_goods_name(goods_nm: str) -> date | None:
    """
    goodsNm 中一般会带：[26-03-10] 这样的日期（YY-MM-DD）。
    """
    goods_nm = normalize(goods_nm)
    m = re.search(r"\[(\d{2})-(\d{2})-(\d{2})\]", goods_nm)
    if not m:
        return None
    yy, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
    year = 2000 + yy
    try:
        return date(year, mm, dd)
    except Exception:
        return None


def parse_ymd(s: str) -> date | None:
    s = normalize(s)
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def pick_event_date(it: dict) -> date | None:
    """
    优先级：
    1) goodsNm 内的 [YY-MM-DD]（部分线下签售会写在标题里）
    2) releaseDt（页面列表右侧常见日期，很多 event 只有这个）
    3) relDt（备用）
    """
    d = parse_event_date_from_goods_name(it.get("goodsNm") or "")
    if d:
        return d
    d = parse_ymd(it.get("releaseDt") or "")
    if d:
        return d
    d = parse_ymd(it.get("relDt") or "")
    if d:
        return d
    return None


def infer_artist(grp_nm: str, goods_nm: str) -> str:
    grp_nm = normalize(grp_nm)
    if grp_nm:
        return grp_nm[:50]

    # fallback: 从标题里猜
    t = normalize(goods_nm)
    t = re.sub(r"^\s*SIGNING\s*", "", t, flags=re.I)
    t = re.sub(r"^\s*(?:\[[^\]]+\]\s*)+", "", t)  # strip leading [..] blocks
    if " - " in t:
        return normalize(t.split(" - ", 1)[0])[:50]
    if " : " in t:
        after = normalize(t.split(" : ", 1)[1])
        first = after.split(" ", 1)[0].strip()
        return (first or after)[:50]
    return (t.split(" ", 1)[0] if t else "Unknown")[:50]


def build_detail(goods_no: int | str) -> str:
    return DETAIL_BASE + str(goods_no)


def fetch_page(keyword: str, page: int, category_no: str, sort_type: str, timeout_ms: int = 5000) -> dict:
    params = {
        "categoryNo": category_no,
        "keyword": keyword,
        "page": page,
        "shopNo": SHOP_NO_CN,
        "sortType": sort_type,
    }
    url = LIST_ENDPOINT + "?" + urlencode(params)
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://cn.ktown4u.com/searchList?goodsTextSearch=Event",
        },
        method="GET",
    )
    with urlopen(req, timeout=max(5, int(timeout_ms / 1000))) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", default="Event")
    parser.add_argument("--category-no", default="107931", help="页面默认 All tab 的 category number")
    parser.add_argument("--sort-type", default="newgoods", choices=["newgoods", "bestgoods", "pricedesc", "priceasc"])
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="最多翻页数。0 表示全量抓取到接口返回的 pageRange（历史页全量）。",
    )
    parser.add_argument("--sleep", type=float, default=0.2, help="每页之间延迟（秒）")
    parser.add_argument("--min-date", default=None, help="可选：YYYY-MM-DD，过滤早于该日期的事件")
    parser.add_argument("--max-date", default=None, help="可选：YYYY-MM-DD，过滤晚于该日期的事件")
    args = parser.parse_args()

    min_d = datetime.strptime(args.min_date, "%Y-%m-%d").date() if args.min_date else None
    max_d = datetime.strptime(args.max_date, "%Y-%m-%d").date() if args.max_date else None

    all_items: list[dict] = []
    seen_goods = set()

    # 先请求第一页，拿到 pageRange（最后一页页码）
    first = fetch_page(args.keyword, 1, args.category_no, args.sort_type)
    page_range = int(first.get("pageRange") or 1)
    max_pages = page_range if (args.max_pages or 0) <= 0 else min(int(args.max_pages), page_range)
    print("pageRange =", page_range, "| maxPages =", max_pages)

    for page in range(1, max_pages + 1):
        obj = first if page == 1 else fetch_page(args.keyword, page, args.category_no, args.sort_type)
        data = obj.get("data") or []
        next_flag = bool(obj.get("next"))
        if page == 1 or page % 10 == 0 or (not next_flag and page == max_pages):
            print(f"page {page}/{max_pages} -> {len(data)} items, next={next_flag}")

        for it in data:
            goods_no = it.get("goodsNo")
            if not goods_no or goods_no in seen_goods:
                continue
            seen_goods.add(goods_no)
            all_items.append(it)

        if args.sleep:
            time.sleep(args.sleep)

    schedules: list[dict] = []
    seen = set()  # (detailUrl, dateKey)
    for it in all_items:
        goods_no = it.get("goodsNo")
        goods_nm = normalize(it.get("goodsNm") or "")
        grp_nm = normalize(it.get("grpNm") or "")
        cover = normalize(it.get("imgPath") or "")

        d = pick_event_date(it)
        if not d:
            continue
        if min_d and d < min_d:
            continue
        if max_d and d > max_d:
            continue

        date_key = d.isoformat()
        detail_url = build_detail(goods_no)

        artist = infer_artist(grp_nm, goods_nm)
        # detail 保留更完整信息（含活动类型）
        detail = goods_nm[:120] if goods_nm else "签售活动"

        k = (detail_url, date_key)
        if k in seen:
            continue
        seen.add(k)

        schedules.append(
            {
                "artist": artist,
                "type": "签售",
                "date": date_key[5:],
                "dateKey": date_key,
                "detail": detail,
                "detailUrl": detail_url,
                "ticketPlatform": "Ktown4u",
                "ticketTime": "",
                "showTime": "",
                "coverImage": cover,
            }
        )

    schedules.sort(key=lambda x: (x.get("dateKey") or "", x.get("artist") or "", x.get("detailUrl") or ""))
    for i, s in enumerate(schedules):
        s["id"] = i + 1

    # 上游接口改版、限流或返回空页时，不允许用空数组覆盖现有签售库。
    if not schedules:
        raise RuntimeError("Ktown4u 本次未返回有效签售记录，已停止写入并保留旧数据")

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=2)

    js = "// 由 scripts/scrape_ktown4u_events.py 从 cn.ktown4u.com 抓取，请勿手改\nmodule.exports = " + json.dumps(schedules, ensure_ascii=False) + ";"
    with open(OUTPUT_JS, "w", encoding="utf-8") as f:
        f.write(js)

    print("解析到", len(schedules), "条签售事件")
    print("已写入:", OUTPUT_JS)
    print("已写入:", OUTPUT_JSON)


if __name__ == "__main__":
    main()
