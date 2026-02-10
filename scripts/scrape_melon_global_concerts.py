#!/usr/bin/env python3
"""
抓取（或解析）Melon Ticket Global 的 Concert 列表，并写入小程序日历数据。

入口：
  https://tkglobal.melon.com/main/index.htm?langCd=EN

注意：
  tkglobal.melon.com 对脚本/爬虫请求经常返回 403（WAF）。
  如果你本机/服务器可以直接请求成功，本脚本会自动抓取并解析；
  如果抓取失败，请在浏览器打开页面后「保存网页源代码」到本地文件，
  然后用 --html 指定该文件再运行（仍然可以产出数据）。

输出：
  miniprogram/data/melon_concerts.json
  miniprogram/data/melon_concerts.js
"""

from __future__ import annotations

import argparse
import base64
import email
import json
import os
import re
from datetime import date, datetime, timedelta
from html import unescape
from pathlib import Path
import quopri
from urllib.request import Request, urlopen


MELON_URL = "https://tkglobal.melon.com/main/index.htm?langCd=EN"
OUTPUT_JS = os.path.join(os.path.dirname(__file__), "..", "miniprogram", "data", "melon_concerts.js")
OUTPUT_JSON = os.path.join(os.path.dirname(__file__), "..", "miniprogram", "data", "melon_concerts.json")


def normalize(s: str) -> str:
    s = unescape(s or "")
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def infer_artist(title: str) -> str:
    title = normalize(title)
    if not title:
        return "Unknown"
    title2 = re.sub(r"^[\[\(［【].*?[\]\)］】]\s*", "", title)
    parts = re.split(r"\s+-\s+", title2)
    cand = parts[0].strip()
    return (cand or title2)[:50]


def parse_ymd_dot(s: str) -> date | None:
    s = normalize(s)
    m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", s)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d)
    except Exception:
        return None


def expand_range(start: date, end: date) -> list[str]:
    if end < start:
        start, end = end, start
    out = []
    cur = start
    while cur <= end:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def fetch_html(url: str) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(req, timeout=25) as resp:
        return resp.read().decode("utf-8", errors="replace")


def read_local_html(path: str) -> str:
    """
    支持：
    - .html/.htm：直接读取
    - .mhtml/.mht：从 multipart 中提取 text/html part，并按 quoted-printable/base64 解码
    """
    p = Path(path)
    raw = p.read_bytes()
    suffix = p.suffix.lower()
    if suffix in (".mhtml", ".mht"):
        msg = email.message_from_bytes(raw)
        # pick first text/html part
        for part in msg.walk():
            if part.get_content_type() != "text/html":
                continue
            cte = (part.get("Content-Transfer-Encoding") or "").lower()
            payload_bytes = part.get_payload(decode=True)
            if payload_bytes is None:
                payload = part.get_payload(decode=False)
                payload_bytes = payload.encode("utf-8", errors="replace")

            # email already decodes qp/base64 when decode=True, but keep a fallback
            if cte == "quoted-printable" and b"=3D" in payload_bytes:
                payload_bytes = quopri.decodestring(payload_bytes)
            elif cte == "base64":
                try:
                    payload_bytes = base64.b64decode(payload_bytes)
                except Exception:
                    pass
            return payload_bytes.decode("utf-8", errors="replace")

        # if no html part found, fallback to raw decode
        return raw.decode("utf-8", errors="replace")

    return raw.decode("utf-8", errors="replace")


def extract_concerts(text: str) -> list[dict]:
    """
    解析 Melon Global 首页的列表卡片：
    - 以 prodId 链接为锚点，回溯到所属 <li>，抽取 title/date/venue/genre/cover
    - 只保留 genre=Concert 的条目
    """
    text = unescape(text or "")
    items: list[dict] = []
    seen = set()  # (detailUrl, dateKey)

    link_re = re.compile(r'href="(https?://tkglobal\.melon\.com/performance/index\.htm\?[^"]*prodId=(\d+)[^"]*)"', re.I)
    for m in link_re.finditer(text):
        detail_url = m.group(1).replace("&amp;", "&")
        prod_id = m.group(2)

        # narrow to its <li> fragment for stable extraction
        li_start = text.rfind("<li", 0, m.start())
        li_end = text.find("</li>", m.end())
        if li_start == -1 or li_end == -1:
            start = max(0, m.start() - 2000)
            end = min(len(text), m.end() + 2000)
            frag = text[start:end]
        else:
            frag = text[li_start : li_end + 5]

        # title
        tm = re.search(r"(?is)<h2[^>]*>(.*?)</h2>", frag)
        title = normalize(re.sub(r"<[^>]+>", "", tm.group(1))) if tm else ""
        if not title:
            continue

        # cover image
        cover = ""
        im = re.search(r'(?is)<img[^>]+src="([^"]+)"', frag)
        if im:
            cover = normalize(im.group(1))
            # strip query/transform params
            cover = cover.split("?", 1)[0]

        # dt/dd pairs
        fields = {}
        for dt_raw, dd_raw in re.findall(r"(?is)<dt>\s*([^<]+)\s*</dt>\s*<dd>\s*([\s\S]*?)\s*</dd>", frag):
            k = normalize(re.sub(r"<[^>]+>", "", dt_raw)).lower()
            v = normalize(re.sub(r"<[^>]+>", "", dd_raw))
            fields[k] = v

        genre = (fields.get("genre") or "").strip()
        if genre.lower() != "concert":
            continue

        date_text = fields.get("date") or ""
        # example: 2026.02.09 - 2026.03.21 (sometimes line-broken)
        dm = re.search(r"(\d{4}\.\d{2}\.\d{2})\s*-\s*(\d{4}\.\d{2}\.\d{2})", date_text)
        if dm:
            d1 = parse_ymd_dot(dm.group(1))
            d2 = parse_ymd_dot(dm.group(2))
        else:
            d1 = parse_ymd_dot(date_text)
            d2 = d1
        if not d1 or not d2:
            continue

        venue = fields.get("venue") or ""

        artist = infer_artist(title)
        detail = title[:120]
        for dk in expand_range(d1, d2):
            k = (detail_url, dk)
            if k in seen:
                continue
            seen.add(k)
            items.append(
                {
                    "artist": artist,
                    "type": "演唱会",
                    "date": dk[5:],
                    "dateKey": dk,
                    "detail": detail,
                    "detailUrl": detail_url,
                    "ticketPlatform": "Melon Ticket Global",
                    "ticketTime": venue,
                    "showTime": "",
                    "coverImage": cover,
                    "prodId": prod_id,
                }
            )

    items.sort(key=lambda x: (x.get("dateKey") or "", x.get("artist") or "", x.get("detailUrl") or ""))
    for i, it in enumerate(items):
        it["id"] = i + 1
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", default=None, help="本地保存的页面源代码/文本文件路径（抓取失败时用）")
    args = parser.parse_args()

    html = ""
    if args.html:
        html = read_local_html(args.html)
    else:
        try:
            print("正在请求:", MELON_URL)
            html = fetch_html(MELON_URL)
        except Exception as e:
            print("请求失败（常见原因：403）:", e)
            print("请用浏览器打开页面后“保存网页源代码”为本地文件，然后运行：")
            print("  python3 scripts/scrape_melon_global_concerts.py --html /path/to/melon.html")
            return

    items = extract_concerts(html)
    print("解析到", len(items), "条 Melon Concert（跨日已拆分）")

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    js = "// 由 scripts/scrape_melon_global_concerts.py 抓取/解析，请勿手改\nmodule.exports = " + json.dumps(items, ensure_ascii=False) + ";"
    with open(OUTPUT_JS, "w", encoding="utf-8") as f:
        f.write(js)

    print("已写入:", OUTPUT_JS)
    print("已写入:", OUTPUT_JSON)


if __name__ == "__main__":
    main()

