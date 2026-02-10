#!/usr/bin/env python3
"""
爬取 r/kpop wiki 回归档：https://www.reddit.com/r/kpop/wiki/upcoming-releases/archive
按年/月抓取所有 Scheduled Releases 表格，输出 miniprogram/data/comebacks.js 与 comebacks.json。
若有发布时间（Time 列），写入 showTime（如 12:00 KST）。
数据来源：Reddit r/kpop wiki，仅供个人学习使用。
"""
from __future__ import annotations

import json
import os
import re
import time
import base64
from urllib.parse import urlencode
from urllib.request import Request, urlopen

WIKI_ARCHIVE_URL = "https://www.reddit.com/r/kpop/wiki/upcoming-releases/archive/"
WIKI_MONTH_URL = "https://www.reddit.com/r/kpop/wiki/upcoming-releases/{year}/{month}"
OUTPUT_JS = os.path.join(os.path.dirname(__file__), "..", "miniprogram", "data", "comebacks.js")
OUTPUT_JSON = os.path.join(os.path.dirname(__file__), "..", "miniprogram", "data", "comebacks.json")
USER_AGENT = "Mozilla/5.0 (compatible; KpopScheduleBot/1.0)"

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


_oauth_token_cache: dict | None = None


def _get_oauth_token() -> str | None:
    """
    通过 Reddit OAuth 获取 app-only token。
    需要环境变量：
      - REDDIT_CLIENT_ID
      - REDDIT_CLIENT_SECRET
      - REDDIT_USER_AGENT（可选，默认 USER_AGENT）
    """
    global _oauth_token_cache
    if _oauth_token_cache and _oauth_token_cache.get("access_token"):
        return _oauth_token_cache["access_token"]

    client_id = os.getenv("REDDIT_CLIENT_ID") or ""
    client_secret = os.getenv("REDDIT_CLIENT_SECRET") or ""
    ua = os.getenv("REDDIT_USER_AGENT") or USER_AGENT
    if not client_id or not client_secret:
        return None

    token_url = "https://www.reddit.com/api/v1/access_token"
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    data = urlencode({"grant_type": "client_credentials"}).encode("utf-8")
    req = Request(
        token_url,
        data=data,
        headers={
            "User-Agent": ua,
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        token = payload.get("access_token")
        if token:
            _oauth_token_cache = payload
            return token
    except Exception:
        return None
    return None


def _to_oauth_url(url: str) -> str:
    # wiki endpoint 在 oauth 域下通常不需要 .json，但 .json 也能工作（取决于端点）
    return url.replace("https://www.reddit.com", "https://oauth.reddit.com")


def fetch_html(url: str) -> str:
    """
    获取 Reddit wiki HTML 页面。
    1) 直接抓取（无凭证）
    2) 若被 403 Blocked 且配置了 OAuth，则改走 oauth.reddit.com
    """
    ua = os.getenv("REDDIT_USER_AGENT") or USER_AGENT

    def _req(u: str, headers: dict) -> str:
        req = Request(u, headers=headers)
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")

    try:
        return _req(url, {"User-Agent": ua, "Accept": "text/html,application/xhtml+xml"})
    except Exception as e:
        if "403" not in str(e):
            raise

    token = _get_oauth_token()
    if not token:
        raise RuntimeError(
            "Reddit 返回 403（被拦截）。如需继续抓取，请配置环境变量 REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT 后重试。"
        )
    oauth_url = _to_oauth_url(url)
    return _req(oauth_url, {"User-Agent": ua, "Authorization": f"bearer {token}", "Accept": "text/html,application/xhtml+xml"})


def fetch_json(url: str) -> dict:
    """
    获取 Reddit wiki JSON（用于月份页面）。
    1) 直接抓取（无凭证）
    2) 若被 403 Blocked 且配置了 OAuth，则改走 oauth.reddit.com
    """
    ua = os.getenv("REDDIT_USER_AGENT") or USER_AGENT

    def _req(u: str, headers: dict) -> dict:
        req = Request(u, headers=headers)
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    try:
        return _req(url, {"User-Agent": ua, "Accept": "application/json"})
    except Exception as e:
        if "403" not in str(e):
            raise

    token = _get_oauth_token()
    if not token:
        raise RuntimeError(
            "Reddit 返回 403（被拦截）。如需继续抓取，请配置环境变量 REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT 后重试。"
        )
    oauth_url = _to_oauth_url(url)
    return _req(oauth_url, {"User-Agent": ua, "Authorization": f"bearer {token}", "Accept": "application/json"})


def extract_month_links_from_archive_html(html: str) -> list[tuple[int, str]]:
    """从 archive 页的 HTML 中解析出 (year, month_lower) 列表，如 (2026, 'february')。"""
    out: list[tuple[int, str]] = []
    # HTML 链接格式: <a href="/r/kpop/wiki/upcoming-releases/2026/february">February 2026</a>
    # 或: <a href="https://www.reddit.com/r/kpop/wiki/upcoming-releases/2026/february">February 2026</a>
    patterns = [
        r'href="[^"]*wiki/upcoming-releases/(\d{4})/([a-z]+)"',
        r'href="/r/kpop/wiki/upcoming-releases/(\d{4})/([a-z]+)"',
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, html, re.I):
            year = int(m.group(1))
            month_str = m.group(2).lower()
            if month_str in MONTH_NAMES:
                out.append((year, month_str))
    # 去重
    return list(dict.fromkeys(out))


def strip_cell(s: str) -> str:
    """去掉 markdown 链接 [text](url)、*italic*、多余空白。"""
    s = (s or "").strip()
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\*+([^*]*)\*+", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:200]


def ordinal_to_day(cell: str) -> int | None:
    """'2nd' -> 2, '21st' -> 21。"""
    cell = (cell or "").strip()
    m = re.match(r"(\d+)(?:st|nd|rd|th)?\s*$", cell, re.I)
    if m:
        d = int(m.group(1))
        if 1 <= d <= 31:
            return d
    return None


def parse_table_for_month(md: str, year: int, month: int) -> list[dict]:
    """
    解析「Scheduled Releases」表格。
    表头: |Day|Time|Artist|Album Title|Album Type|Title Track|Streaming
    行内可能为空表示沿用上一行的 Day/Time。
    返回 list of { artist, dateKey, date, detail, showTime }。
    """
    rows: list[dict] = []
    current_day: int | None = None
    current_time: str = ""

    # 只处理 Scheduled Releases 表（内容可能含 \r\n）
    scheduled = re.search(
        r"###\s*Scheduled\s*Releases:?\s*\r?\n\r?\n(\|[^\r\n]+\r?\n\|[-\s|]+\r?\n(?:\|[^\r\n]+\r?\n?)*)",
        md,
        re.I | re.DOTALL,
    )
    if not scheduled:
        return rows
    table = scheduled.group(1)
    lines = [ln.strip() for ln in re.split(r"\r?\n", table) if ln.strip().startswith("|")]
    if len(lines) < 2:
        return rows

    for line in lines[1:]:  # skip header
        parts = [p.strip() for p in line.split("|")]
        if parts and parts[0] == "":
            parts = parts[1:]
        if len(parts) < 4:
            continue
        # 列: Day, Time, Artist, Album Title, Album Type, Title Track, ...
        day_cell = parts[0] if len(parts) > 0 else ""
        time_cell = parts[1] if len(parts) > 1 else ""
        artist_cell = parts[2] if len(parts) > 2 else ""
        album_title = parts[3] if len(parts) > 3 else ""
        album_type = parts[4] if len(parts) > 4 else ""
        title_track = parts[5] if len(parts) > 5 else ""

        if day_cell:
            d = ordinal_to_day(day_cell)
            if d is not None:
                current_day = d
        if time_cell and re.match(r"^\d{1,2}:\d{2}", time_cell):
            current_time = time_cell.strip()  # e.g. 12:00 or 18:00 (KST per wiki)
        artist = strip_cell(artist_cell)
        if not artist:
            continue
        if current_day is None:
            continue
        try:
            date_key = f"{year}-{month:02d}-{current_day:02d}"
        except Exception:
            continue
        album_type_clean = strip_cell(album_type)
        detail = album_type_clean or "Release"
        if album_title:
            detail = f"{album_type_clean} – {strip_cell(album_title)}" if album_type_clean else strip_cell(album_title)
        elif title_track:
            detail = f"{detail} – {strip_cell(title_track)}" if detail != "Release" else strip_cell(title_track)
        detail = detail[:120] or "回归"
        show_time = ""
        if current_time:
            show_time = f"{current_time} KST"
        rows.append({
            "artist": artist[:50],
            "type": "回归",
            "date": date_key[5:],  # MM-DD
            "dateKey": date_key,
            "detail": detail,
            "showTime": show_time,
        })
    return rows


def main() -> None:
    print("正在请求 archive 索引:", WIKI_ARCHIVE_URL)
    try:
        archive_html = fetch_html(WIKI_ARCHIVE_URL)
    except Exception as e:
        print("Archive 请求失败:", e)
        return
    month_links = extract_month_links_from_archive_html(archive_html)
    # 只抓 2024 及以后，减少请求量
    month_links = [(y, m) for y, m in month_links if y >= 2024]
    print("解析到", len(month_links), "个月份页面")
    all_rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for year, month_name in month_links:
        month_num = MONTH_NAMES[month_name]
        url = WIKI_MONTH_URL.format(year=year, month=month_name)
        try:
            # 尝试 JSON 端点（更可靠）
            json_url = url + ".json"
            try:
                data = fetch_json(json_url)
                content = (data.get("data") or {}).get("content_md") or ""
            except:
                # 如果 JSON 失败，尝试 HTML（但需要解析 markdown，这里简化处理）
                html = fetch_html(url)
                # 从 HTML 中提取 markdown（Reddit wiki HTML 通常包含 <div class="md"> 或类似结构）
                md_match = re.search(r'<div[^>]*class="[^"]*md[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL | re.I)
                if md_match:
                    content = md_match.group(1)
                    # 简单清理 HTML 标签，保留文本
                    content = re.sub(r'<[^>]+>', '', content)
                else:
                    content = ""
            items = parse_table_for_month(content, year, month_num)
            for it in items:
                key = (it["dateKey"], it["artist"], (it.get("detail") or "")[:80])
                if key in seen:
                    continue
                seen.add(key)
                all_rows.append(it)
            print(" ", year, month_name, "->", len(items), "条")
        except Exception as e:
            print(" ", year, month_name, "失败:", e)
        time.sleep(0.3)
    all_rows.sort(key=lambda x: (x["dateKey"], x["artist"], x.get("detail") or ""))
    for i, r in enumerate(all_rows, 1):
        r["id"] = i
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, ensure_ascii=False, indent=2)
    js_content = "// 由 scripts/scrape_reddit_comebacks.py 从 r/kpop wiki 抓取，请勿手改\nmodule.exports = " + json.dumps(all_rows, ensure_ascii=False) + ";"
    with open(OUTPUT_JS, "w", encoding="utf-8") as f:
        f.write(js_content)
    print("共", len(all_rows), "条，已写入:", OUTPUT_JS, OUTPUT_JSON)


if __name__ == "__main__":
    main()
