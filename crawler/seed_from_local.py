#!/usr/bin/env python3
"""把现有本地真实 JSON 导入 Supabase（不是假数据）。等爬虫跑通后可用来一次性补齐历史场次。"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from crawler.utils.ids import make_source_event_id
from crawler.utils.store import upsert_events

ZH_TO_TYPE = {
    "回归": "comeback",
    "演唱会": "concert",
    "签售": "fansign",
    "活动": "popup",
}

FILES = [
    ("comebacks.json", "local_comebacks"),
    ("concerts.json", "local_concerts"),
    ("ticket_concerts.json", "local_tickets"),
    ("fansigns.json", "local_fansigns"),
    ("festas.json", "local_festas"),
]


def main() -> int:
    data_dir = os.path.join(ROOT, "miniprogram", "data")
    events = []
    for filename, source_name in FILES:
        path = os.path.join(data_dir, filename)
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            rows = json.load(f)
        if not isinstance(rows, list):
            continue
        for it in rows:
            zh = it.get("type") or "活动"
            et = ZH_TO_TYPE.get(zh, "other")
            artist = (it.get("artist") or "").strip()
            title = (it.get("detail") or zh).strip()
            event_date = (it.get("dateKey") or "").strip()
            source_url = (it.get("detailUrl") or "").strip()
            sid = make_source_event_id(
                source_name,
                artist=artist,
                event_type=et,
                event_date=event_date,
                title=title,
                source_native_id=source_url,
            )
            events.append(
                {
                    "source_event_id": sid,
                    "artist": artist or "未知",
                    "title": title,
                    "event_type": et,
                    "event_date": event_date or None,
                    "event_time": (it.get("showTime") or None),
                    "venue": (it.get("venue") or None),
                    "city": (it.get("locationText") or None),
                    "ticket_platform": (it.get("ticketPlatform") or None),
                    "ticket_open_time": (it.get("ticketTime") or None),
                    "official_url": (it.get("officialUrl") or source_url or None),
                    "source_url": source_url or None,
                    "source_name": source_name,
                    "status": "upcoming",
                    "cover_url": (it.get("coverImage") or None),
                }
            )
    print("准备导入", len(events), "条本地真实记录")
    stats = upsert_events(events)
    print(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
