#!/usr/bin/env python3
"""稳定 source_event_id：优先用源站 ID，否则用 source+艺人+类型+日期+标题 做 hash。"""
from __future__ import annotations

import hashlib


def make_source_event_id(
    source_name: str,
    artist: str = "",
    event_type: str = "",
    event_date: str = "",
    title: str = "",
    source_native_id: str = "",
) -> str:
    if source_native_id:
        raw = "%s|id|%s" % (source_name, source_native_id)
    else:
        raw = "|".join(
            [
                source_name or "",
                (artist or "").strip().lower(),
                (event_type or "").strip().lower(),
                (event_date or "").strip(),
                (title or "").strip().lower(),
            ]
        )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
