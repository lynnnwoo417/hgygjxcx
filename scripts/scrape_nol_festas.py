#!/usr/bin/env python3
"""
抓取 NOL World（Interpark global）的「活动 / festas」并写入小程序日历数据。

目标页面（默认首尔 region）：
  https://world.nol.com/zh-CN/regions/b263b346-9a60-49d5-949a-dc88dfbea53e/festas

页面本质上通过 GraphQL 获取「指定日期当天可见」的活动列表：
  POST https://world.nol.com/api/graphql

为了覆盖整段时间内的所有活动，需要对“每一天”发起一次查询，
把返回的活动 items 合并去重后，再按活动 duration(start/end) 展开成每天一条记录。

输出：
  miniprogram/data/festas.json
  miniprogram/data/festas.js
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import unescape
from typing import Any
from urllib.request import Request, urlopen

from zoneinfo import ZoneInfo


REGION_ID_SEOUL = "b263b346-9a60-49d5-949a-dc88dfbea53e"
LANG = "zh-CN"
GRAPHQL_ENDPOINT = "https://world.nol.com/api/graphql"
DETAIL_BASE = "https://world.nol.com/zh-CN/content/festas/"

OUTPUT_JS = os.path.join(os.path.dirname(__file__), "..", "miniprogram", "data", "festas.js")
OUTPUT_JSON = os.path.join(os.path.dirname(__file__), "..", "miniprogram", "data", "festas.json")

KST = ZoneInfo("Asia/Seoul")

CATEGORY_MAP_ZH = {
    "ENTER": "娱乐",
    "NEWS": "新闻",
    "POP-UP": "快闪店",
    "FESTIVAL": "庆典",
}


QUERY = """
query getFestasInDate($regionId: String!, $schedule: String!) {
  festas: getFestasBySchedule(
    args: { regionIds: [$regionId], schedule: $schedule }
  ) {
    items {
      id
      title
      subtitle
      duration { start end }
      headImage {
        sizes {
          small_square { url }
        }
      }
      areas { names { primary } }
      category
    }
  }
}
""".strip()


def normalize(s: str) -> str:
    s = unescape(s or "")
    s = s.replace("\xa0", " ")
    s = " ".join(s.split())
    return s.strip()


def parse_ymd(s: str) -> date | None:
    s = normalize(s)
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def daterange(start: date, end: date) -> list[date]:
    if end < start:
        start, end = end, start
    out = []
    cur = start
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=1)
    return out


def post_graphql(schedule_ymd: str, region_id: str) -> dict[str, Any]:
    payload = {"query": QUERY, "variables": {"regionId": region_id, "schedule": schedule_ymd}}
    req = Request(
        GRAPHQL_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # 与站点一致的 headers（见 Kint5ApiHeaders）
            "X-Service-Origin": "global",
            "X-Triple-User-Lang": LANG,
        },
        method="POST",
    )
    with urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


@dataclass(frozen=True)
class FestaItem:
    id: str
    title: str
    subtitle: str
    category: str
    area_primary: str
    start: date
    end: date
    cover: str

    @property
    def detail_url(self) -> str:
        return DETAIL_BASE + self.id

    @property
    def location_text(self) -> str:
        cat = normalize(CATEGORY_MAP_ZH.get(self.category, self.category))
        parts = [p for p in [cat, normalize(self.area_primary)] if p]
        return " · ".join(parts)


def extract_items(obj: dict[str, Any]) -> list[FestaItem]:
    data = (obj.get("data") or {}).get("festas") or {}
    raw_items = data.get("items") or []
    out: list[FestaItem] = []
    for it in raw_items:
        try:
            fid = str(it.get("id") or "").strip()
            title = normalize(it.get("title") or "")
            subtitle = normalize(it.get("subtitle") or "")
            category = normalize(it.get("category") or "")
            area_primary = ""
            areas = it.get("areas") or []
            if isinstance(areas, list) and areas:
                names = areas[0].get("names") if isinstance(areas[0], dict) else None
                if isinstance(names, dict):
                    area_primary = normalize(names.get("primary") or "")
            duration = it.get("duration") or {}
            start = parse_ymd(duration.get("start") or "")
            end = parse_ymd(duration.get("end") or "")
            cover = normalize(
                (((((it.get("headImage") or {}).get("sizes") or {}).get("small_square") or {}).get("url")) or "")
            )
            if not fid or not title or not start or not end:
                continue
            out.append(
                FestaItem(
                    id=fid,
                    title=title,
                    subtitle=subtitle,
                    category=category,
                    area_primary=area_primary,
                    start=start,
                    end=end,
                    cover=cover,
                )
            )
        except Exception:
            continue
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region-id", default=REGION_ID_SEOUL)
    parser.add_argument("--start", default=None, help="YYYY-MM-DD，默认取韩国时区当天")
    parser.add_argument("--days", type=int, default=90, help="抓取多少天（每一天请求一次 GraphQL）")
    parser.add_argument("--sleep", type=float, default=0.2, help="每次请求之间的延迟（秒）")
    args = parser.parse_args()

    if args.start:
        start_day = parse_ymd(args.start)
        if not start_day:
            raise SystemExit("Invalid --start, expected YYYY-MM-DD")
    else:
        start_day = datetime.now(tz=KST).date()
    end_day = start_day + timedelta(days=max(1, args.days) - 1)

    print("NOL festas region:", args.region_id)
    print("抓取窗口:", start_day.isoformat(), "->", end_day.isoformat(), f"({args.days} 天)")

    # 1) 每天请求一次，收集 union items
    by_id: dict[str, FestaItem] = {}
    for i, d in enumerate(daterange(start_day, end_day), start=1):
        ymd = d.isoformat()
        try:
            obj = post_graphql(ymd, args.region_id)
            items = extract_items(obj)
            for it in items:
                by_id[it.id] = it
            print(f"[{i:03d}/{args.days}] {ymd} -> {len(items)} items (union {len(by_id)})")
        except Exception as e:
            print(f"[{i:03d}/{args.days}] {ymd} -> ERROR:", e)
        if args.sleep:
            time.sleep(args.sleep)

    # 2) 展开成每天一条记录（仅在抓取窗口内展开，避免常设 2099-12-31 爆炸）
    schedules: list[dict[str, Any]] = []
    seen = set()  # (id, dateKey)
    for it in by_id.values():
        span_start = max(it.start, start_day)
        span_end = min(it.end, end_day)
        for d in daterange(span_start, span_end):
            date_key = d.isoformat()
            k = (it.id, date_key)
            if k in seen:
                continue
            seen.add(k)
            schedules.append(
                {
                    "artist": it.title,  # 复用字段：卡片大标题
                    "type": "活动",
                    "date": date_key[5:],
                    "dateKey": date_key,
                    "detail": it.subtitle or it.category or "活动",
                    "detailUrl": it.detail_url,
                    "locationText": it.location_text,
                    "coverImage": it.cover,
                }
            )

    schedules.sort(key=lambda x: (x.get("dateKey") or "", x.get("artist") or "", x.get("detailUrl") or ""))
    for idx, s in enumerate(schedules):
        s["id"] = idx + 1

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=2)

    js = "// 由 scripts/scrape_nol_festas.py 从 world.nol.com 抓取，请勿手改\nmodule.exports = " + json.dumps(schedules, ensure_ascii=False) + ";"
    with open(OUTPUT_JS, "w", encoding="utf-8") as f:
        f.write(js)

    print("解析到", len(schedules), "条活动（日历按天展开，已限制在抓取窗口内）")
    print("已写入:", OUTPUT_JS)
    print("已写入:", OUTPUT_JSON)


if __name__ == "__main__":
    main()

