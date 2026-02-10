#!/usr/bin/env python3
"""
抓取 kpopofficial.com 演唱会/签售活动详情页正文（full sections），
生成 rich-text 友好的 contentHtml，并缓存到 server/data/event_details/ 供后端 API 返回。

输入：miniprogram/data/concerts.json（由 scrape_kpopofficial_concerts.py 生成）
输出：
  - server/data/event_details/<sha1(detailUrl)>.json
  - server/data/event_details_index.json
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from html import unescape
from urllib.request import Request, urlopen

ROOT = os.path.join(os.path.dirname(__file__), "..")
CONCERTS_JSON = os.path.join(ROOT, "miniprogram", "data", "concerts.json")
OUT_DIR = os.path.join(ROOT, "server", "data", "event_details")
OUT_INDEX = os.path.join(ROOT, "server", "data", "event_details_index.json")

FETCH_DELAY = 0.6
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def sha1_hex(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize(s: str) -> str:
    if not s:
        return ""
    s = unescape(s)
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def strip_tags(html: str) -> str:
    # minimal tag stripper
    html = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    return normalize(html)


def extract_div_balanced(html: str, start_idx: int) -> str | None:
    """
    从 start_idx 指向的 <div ...> 开始，按 div 嵌套匹配提取完整片段（包含外层 div）。
    """
    open_m = re.search(r"(?is)<div\b[^>]*>", html[start_idx:])
    if not open_m:
        return None
    i = start_idx + open_m.start()
    j = start_idx + open_m.end()
    depth = 1

    tag_re = re.compile(r"(?is)<div\b[^>]*>|</div\s*>")
    for m in tag_re.finditer(html, j):
        if m.group(0).lower().startswith("<div"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return html[i : m.end()]
    return None


def extract_entry_content(html: str) -> str | None:
    # locate entry-content container
    m = re.search(r'(?is)<div[^>]+class="[^"]*\bentry-content\b[^"]*"[^>]*>', html)
    if not m:
        return None
    frag = extract_div_balanced(html, m.start())
    return frag


def truncate_noise(content_html: str) -> str:
    """
    裁剪掉页面正文里不需要的尾部杂项（More upcoming / Share / Subscribe / Comments 等）。
    """
    lower = content_html.lower()
    markers = [
        "more upcoming kpop events",
        "share this",
        "wpdiscuz",
        "loading comments",
        "<form",  # comment forms
    ]
    cut = None
    for mk in markers:
        idx = lower.find(mk)
        if idx != -1:
            cut = idx if cut is None else min(cut, idx)
    if cut is not None and cut > 0:
        return content_html[:cut]
    return content_html


def sanitize_for_rich_text(content_html: str) -> str:
    """
    生成 rich-text 友好的 HTML：
    - 删除 script/style/iframe 等
    - 表格转段落（避免 rich-text 表格兼容问题）
    - 限制为正文内容块内的 HTML（不再包含外层 entry-content div）
    """
    # remove outer entry-content wrapper div if present
    content_html = re.sub(r"(?is)^<div\b[^>]*\bentry-content\b[^>]*>", "", content_html).strip()
    content_html = re.sub(r"(?is)</div>\s*$", "", content_html).strip()

    content_html = re.sub(r"(?is)<script[^>]*>.*?</script>", "", content_html)
    content_html = re.sub(r"(?is)<style[^>]*>.*?</style>", "", content_html)
    content_html = re.sub(r"(?is)<iframe[^>]*>.*?</iframe>", "", content_html)
    content_html = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", "", content_html)

    # remove table-of-contents toggle widgets if present
    content_html = re.sub(r"(?is)<div[^>]*class=\"[^\"]*\btable-of-contents\b[^\"]*\"[^>]*>.*?</div>", "", content_html)

    # convert tables to paragraph lines
    def table_to_p(match: re.Match) -> str:
        table = match.group(0)
        rows = re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", table)
        lines = []
        for r in rows:
            tds = re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", r)
            if len(tds) >= 2:
                k = strip_tags(tds[0])
                v_html = tds[1]
                # keep links text; if there is an anchor, preserve as link
                href = None
                a = re.search(r'(?is)<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', v_html)
                if a:
                    href = a.group(1)
                    v_text = strip_tags(a.group(2)) or strip_tags(v_html)
                    v = f'<a href="{href}">{v_text}</a>'
                else:
                    v = strip_tags(v_html)
                if k and v:
                    lines.append(f"<p><strong>{k}</strong>：{v}</p>")
        return "<div>" + "".join(lines) + "</div>" if lines else ""

    content_html = re.sub(r"(?is)<table[^>]*>.*?</table>", table_to_p, content_html)

    # collapse excessive whitespace between tags
    content_html = re.sub(r">\s+<", "><", content_html)
    return content_html.strip()


def extract_extracted_info(html: str) -> dict:
    """
    从详情页 HTML 中尽量提取结构化信息（Event Info 表等）。
    """
    info: dict[str, str] = {}

    entry = extract_entry_content(html) or html
    # Scan all table rows inside entry content and pick likely key-value pairs.
    for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", entry):
        cells = re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row)
        if len(cells) < 2:
            continue
        k = strip_tags(cells[0])
        if not k or len(k) > 60:
            continue
        v_html = cells[1]
        # preserve first link if exists
        a = re.search(r'(?is)<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', v_html)
        if a:
            href = a.group(1)
            v_text = strip_tags(a.group(2)) or strip_tags(v_html)
            v = f"{v_text} ({href})" if href else v_text
        else:
            v = strip_tags(v_html)
        v = normalize(v)
        if not v:
            continue
        # Only keep a curated subset to reduce noise
        if k.lower() in {"event", "date", "venue", "buy ticket", "official source", "ticket price", "tickets", "deal score"}:
            info[k] = v[:500]

    return info


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=25) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main() -> None:
    if not os.path.exists(CONCERTS_JSON):
        print("找不到 concerts.json，请先运行 scrape_kpopofficial_concerts.py")
        return

    with open(CONCERTS_JSON, "r", encoding="utf-8") as f:
        items = json.load(f)
    if not isinstance(items, list):
        print("concerts.json 格式不正确")
        return

    urls = []
    for it in items:
        u = (it or {}).get("detailUrl") or ""
        if u and isinstance(u, str):
            urls.append(u)
    unique_urls = sorted(set(urls))
    print(f"将抓取 {len(unique_urls)} 个活动详情页")

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(OUT_INDEX), exist_ok=True)

    index: dict[str, str] = {}
    ok = 0
    for i, url in enumerate(unique_urls, start=1):
        h = sha1_hex(url)
        out_path = os.path.join(OUT_DIR, f"{h}.json")
        index[url] = h

        # Skip if already cached and recent enough (optional); for now always refresh if missing
        if os.path.exists(out_path):
            ok += 1
            continue

        try:
            html = fetch(url)
        except Exception as e:
            print(f"[{i}/{len(unique_urls)}] 抓取失败: {url} -> {e}")
            continue

        entry = extract_entry_content(html)
        if not entry:
            print(f"[{i}/{len(unique_urls)}] 未找到 entry-content: {url}")
            continue

        entry = truncate_noise(entry)
        content_html = sanitize_for_rich_text(entry)
        extracted_info = extract_extracted_info(html)

        title = ""
        tm = re.search(r"(?is)<h1[^>]*class=\"[^\"]*entry-title[^\"]*\"[^>]*>(.*?)</h1>", html)
        if tm:
            title = strip_tags(tm.group(1))

        record = {
            "detailUrl": url,
            "hash": h,
            "fetchedAt": now_iso(),
            "title": title,
            "contentHtml": content_html,
            "extractedInfo": extracted_info,
        }

        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False)
            ok += 1
            print(f"[{i}/{len(unique_urls)}] OK {url}")
        except Exception as e:
            print(f"[{i}/{len(unique_urls)}] 写入失败: {out_path} -> {e}")

        time.sleep(FETCH_DELAY)

    with open(OUT_INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"完成：缓存 {ok}/{len(unique_urls)} 个详情页")
    print("index:", OUT_INDEX)


if __name__ == "__main__":
    main()

