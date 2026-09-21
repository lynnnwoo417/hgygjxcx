#!/usr/bin/env python3
"""每次爬完后打印人能看懂的数据健康报告。"""
from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
API_DIR = os.path.join(ROOT, "api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

import _lib as lib  # noqa: E402

TYPE_ZH = {
    "comeback": "回归",
    "concert": "演唱会",
    "fansign": "签售",
    "popup": "活动",
    "other": "其他",
}


def report() -> None:
    rows = lib.pg_fetch(
        """
        select artist, event_type, event_date::text as event_date, venue,
               official_url, source_url, source_name
        from public.events
        """
    )
    today = date.today().isoformat()
    total = len(rows)
    future = [r for r in rows if r.get("event_date") and r["event_date"] >= today]
    types = Counter(r.get("event_type") or "other" for r in rows)
    sources = Counter(r.get("source_name") or "unknown" for r in rows)
    no_url = sum(1 for r in rows if not (r.get("official_url") or r.get("source_url")))
    concert_no_venue = sum(
        1
        for r in rows
        if (r.get("event_type") in ("concert", "fansign", "popup")) and not (r.get("venue") or "").strip()
    )
    print("[REPORT] 总场次 %s · 今天及以后 %s 场" % (total, len(future)))
    print(
        "[REPORT] 类型 "
        + " · ".join("%s %s" % (TYPE_ZH.get(k, k), v) for k, v in types.most_common())
    )
    print("[REPORT] 来源 " + " · ".join("%s %s" % (k, v) for k, v in sources.most_common()))
    print("[REPORT] 缺官方/来源链接 %s · 演唱会/签售/活动缺场馆 %s" % (no_url, concert_no_venue))
    upcoming_art = Counter(r.get("artist") for r in future)
    if upcoming_art:
        top = ", ".join("%s %s场" % (a, n) for a, n in upcoming_art.most_common(8))
        print("[REPORT] 即将到来最多：" + top)


if __name__ == "__main__":
    report()
