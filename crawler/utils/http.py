#!/usr/bin/env python3
"""带超时的网页抓取。"""
from __future__ import annotations

from urllib.request import Request, urlopen


def fetch_text(url: str, timeout: int = 20) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; KpopScheduleBot/1.0; +https://github.com/lynnnwoo417/hgygjxcx)"
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")
