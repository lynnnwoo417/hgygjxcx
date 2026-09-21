#!/usr/bin/env python3
"""多数据源爬虫入口。单个源失败不影响其它源。"""
from __future__ import annotations

import os
import sys
import traceback

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from crawler.sources import kpopofficial_comebacks  # noqa: E402
from crawler.utils.store import upsert_events  # noqa: E402
from crawler.analyze import report  # noqa: E402

SOURCES = [
    ("kpopofficial_comebacks", kpopofficial_comebacks.fetch_events),
]


def run() -> int:
    total_insert = total_update = total_skip = total_error = 0
    for name, fetch in SOURCES:
        try:
            events = fetch()
            stats = upsert_events(events)
            print(
                "[OK] %s: %s events  [INSERT] %s  [UPDATE] %s  [SKIP] %s  [ERROR] %s"
                % (
                    name,
                    len(events),
                    stats["insert"],
                    stats["update"],
                    stats["skip"],
                    stats["error"],
                )
            )
            total_insert += stats["insert"]
            total_update += stats["update"]
            total_skip += stats["skip"]
            total_error += stats["error"]
        except Exception as e:
            total_error += 1
            print("[ERROR] %s %s" % (name, e))
            traceback.print_exc()
    print(
        "[DONE] insert=%s update=%s skip=%s error=%s"
        % (total_insert, total_update, total_skip, total_error)
    )
    try:
        report()
    except Exception as e:
        print("[REPORT] skipped:", e)
    return 0 if total_error == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
