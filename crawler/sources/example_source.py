#!/usr/bin/env python3
"""示例 parser：展示如何把任意网页结果转成统一 event schema。不会假装抓到真实场次。"""
from __future__ import annotations

from typing import Dict, List

from crawler.utils.ids import make_source_event_id

SOURCE_NAME = "example"


def fetch_events() -> List[Dict]:
    # 只作为结构示例。正式数据源见 kpopofficial_comebacks.py
    return []


def parse_to_schema(_raw: object) -> List[Dict]:
    return []
