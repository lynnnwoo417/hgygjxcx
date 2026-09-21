#!/usr/bin/env python3
"""Demo 数据源：KPOP OFFICIAL 回归列表页（公开页面，项目里已有可用解析器）。"""
from __future__ import annotations

import importlib.util
import os
from typing import Dict, List
from urllib.parse import urlparse

from crawler.utils.http import fetch_text
from crawler.utils.ids import make_source_event_id

SOURCE_NAME = "kpopofficial"
URL = "https://kpopofficial.com/kpop-comebacks/"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load_legacy_parser():
    path = os.path.join(ROOT, "scripts", "scrape_kpopofficial.py")
    spec = importlib.util.spec_from_file_location("scrape_kpopofficial", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("找不到 scripts/scrape_kpopofficial.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _native_id(detail_url: str) -> str:
    if not detail_url:
        return ""
    path = urlparse(detail_url).path.rstrip("/")
    slug = path.split("/")[-1] if path else ""
    return slug


def fetch_events() -> List[Dict]:
    html = fetch_text(URL, timeout=20)
    parser = _load_legacy_parser()
    items = parser.extract_comebacks_from_html(html)
    out: List[Dict] = []
    for it in items or []:
        artist = (it.get("artist") or "").strip()
        title = (it.get("detail") or "回归").strip()
        event_date = (it.get("dateKey") or "").strip()
        source_url = (it.get("detailUrl") or URL).strip()
        native = _native_id(source_url)
        sid = make_source_event_id(
            SOURCE_NAME,
            artist=artist,
            event_type="comeback",
            event_date=event_date,
            title=title,
            source_native_id=native,
        )
        out.append(
            {
                "source_event_id": sid,
                "artist": artist or "未知",
                "title": title,
                "event_type": "comeback",
                "event_date": event_date or None,
                "event_time": (it.get("showTime") or "").strip() or None,
                "end_time": None,
                "venue": (it.get("venue") or "").strip() or None,
                "city": (it.get("locationText") or "").strip() or None,
                "region": "KR",
                "ticket_platform": (it.get("ticketPlatform") or "").strip() or None,
                "ticket_open_time": (it.get("ticketTime") or "").strip() or None,
                "official_url": (it.get("officialUrl") or source_url).strip() or None,
                "source_url": source_url,
                "source_name": SOURCE_NAME,
                "status": "upcoming",
                "cover_url": (it.get("coverImage") or "").strip() or None,
            }
        )
    return out
