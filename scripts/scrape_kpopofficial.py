#!/usr/bin/env python3
"""
爬取 https://kpopofficial.com/kpop-comebacks/ 的 K-pop 回归日程，
输出为小程序可用的 data/comebacks.js。
数据来源：KPOP OFFICIAL (https://kpopofficial.com)，仅供个人学习使用。
支持 --month=N 增量更新指定月份（如 --month=3 只抓三月并合并到本地历史记录）。
"""
import re
import json
import os
import argparse
from datetime import datetime
from urllib.request import Request, urlopen
from html.parser import HTMLParser

URL = "https://kpopofficial.com/kpop-comebacks/"
OUTPUT_JS = os.path.join(os.path.dirname(__file__), "..", "miniprogram", "data", "comebacks.js")
OUTPUT_JSON = os.path.join(os.path.dirname(__file__), "..", "miniprogram", "data", "comebacks.json")

MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def parse_date_to_yyyymmdd(text, default_year=2026):
    """从页面文本解析出 YYYY-MM-DD。支持 January 21 (Wed)、February 27, 2026、JAN 21 等。"""
    if not text:
        return None
    text = text.strip().lower()
    # 先尝试 "February 27, 2026" 或 "March 20, 2026"
    m = re.search(r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:\s*,\s*(\d{4}))?", text, re.I)
    if m:
        month_name, day, year = m.group(1), int(m.group(2)), m.group(3)
        month = MONTH_NAMES.get(month_name.lower())
        if month:
            y = int(year) if year else default_year
            return f"{y}-{month:02d}-{day:02d}"

    # "January 21 (Wed) · 6 PM KST"
    m = re.search(r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})\s*(?:\([^)]*\))?", text, re.I)
    if m:
        month_name, day = m.group(1), int(m.group(2))
        month = MONTH_NAMES.get(month_name.lower())
        if month:
            return f"{default_year}-{month:02d}-{day:02d}"

    # "JAN 21", "FEB 27"
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*\.?\s*(\d{1,2})\b", text, re.I)
    if m:
        month_name, day = m.group(1), int(m.group(2))
        month = MONTH_NAMES.get(month_name.lower())
        if month:
            return f"{default_year}-{month:02d}-{day:02d}"

    return None


def extract_comebacks_from_html(html: str):
    """从 HTML 中提取回归条目。"""
    comebacks = []
    seen = set()  # (artist, dateKey) 去重

    # 1) 匹配卡片式：链接到 /album/xxx，附近有月份+日期和艺人名
    # 例：JAN 21 ... [M.O.N.T] ... January 21 (Wed) · 12 PM KST ... Digital Single – History
    album_link_re = re.compile(r'href="(https?://[^"]*kpopofficial\.com/album/[^"/]+)"', re.I)
    # 找所有 /album/ 链接所在的大块（用段落或列表项）
    blocks = re.split(r'<[aA]\s+[^>]*href="[^"]*kpopofficial\.com/album/', html)
    for i, block in enumerate(blocks):
        if i == 0:
            continue
        # block 开头可能是 "/xxx")>...</a>..."
        link_match = re.search(r'([^"/]+)"', block)
        slug = link_match.group(1).strip() if link_match else ""
        # 在这一块里找 JAN/FEB/... 数字 或 January 21 / February 27, 2026
        date_key = None
        for date_candidate in re.finditer(
            r"(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s*\.?\s*\d{1,2}|"
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:\s*,\s*\d{4})?(?:\s*\([^)]*\))?",
            block, re.I
        ):
            date_key = parse_date_to_yyyymmdd(block[date_candidate.start():date_candidate.end() + 50])
            if date_key:
                break
        if not date_key:
            continue

        # 艺人名：找第一个「像艺人名」的 >...<（不含 HTML 标签、class= 等）
        artist = ""
        for m in re.finditer(r'>([^<]{2,80}?)</a>', block):
            cand = m.group(1).strip()
            cand = re.sub(r"\s+", " ", cand)
            cand = cand.replace("&#038;", "&").replace("&#8211;", "–").replace("&#8220;", '"').replace("&#8221;", '"')
            # 排除 HTML/控件/噪音
            if not cand or "class=" in cand or "span" in cand.lower() or cand.startswith((">", "<", "=")) or not re.search(r"[A-Za-z\u4e00-\u9fff]", cand):
                continue
            if cand.lower() in ("view details", "show more", "coming soon", "tab-image"):
                continue
            # 若整段是 "ARTIST – Album/Single ..."，取 – 前的部分为艺人
            if " – " in cand or " – " in cand:
                artist = cand.split("–")[0].split("−")[0].strip()[:50]
            else:
                artist = cand[:50]
            break
        if not artist:
            artist = slug.replace("-", " ").title() if slug and len(slug) > 2 else ""

        detail_match = re.search(r"(?:Album|Single|Mini Album|Digital Single|EP|Title|Pre-release|Pre-Release)\s*[–\-]\s*[^<\n]+", block, re.I)
        detail = detail_match.group(0).strip()[:100] if detail_match else "回归"
        detail = re.sub(r"<[^>]+>", "", detail)
        detail = detail.replace("&#038;", "&").replace("&#8211;", "–").replace("&#8220;", '"').replace("&#8221;", '"').strip()

        # 丢弃明显解析错误的条目（艺人名像标签或过长乱码）
        if artist and ("<" in artist or ">" in artist or "class=" in artist or "=" in artist[:3] or len(artist) > 55):
            continue
        key = (artist or slug, date_key)
        if key in seen:
            continue
        seen.add(key)
        if not artist:
            artist = slug.replace("-", " ").title() if slug else "Unknown"
        comebacks.append({
            "artist": artist[:50],
            "type": "回归",
            "date": date_key[-5:] if date_key else "",
            "dateKey": date_key,
            "detail": detail[:100] or "回归"
        })

    # 2) 补充：从 "### [BTS – 5th Album "ARIRANG"]" 和 "March 20, 2026 · Friday" 这类块抓取
    trend_blocks = re.findall(
        r'###\s*\[([^\]"]+)(?:"[^"]*")?\][^<]*</a>\s*[^<]*'
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:\s*,\s*(\d{4}))?\s*[·\-]",
        html, re.I | re.DOTALL
    )
    for artist_part, month_name, day, year in trend_blocks:
        month = MONTH_NAMES.get(month_name.lower())
        if not month:
            continue
        y = int(year) if year else 2026
        date_key = f"{y}-{month:02d}-{int(day):02d}"
        artist = artist_part.split("–")[0].split("−")[0].strip()
        artist = re.sub(r"<[^>]+>", "", artist).strip()[:50]
        key = (artist, date_key)
        if key not in seen:
            seen.add(key)
            comebacks.append({
                "artist": artist or "Unknown",
                "type": "回归",
                "date": f"{month:02d}-{int(day):02d}",
                "dateKey": date_key,
                "detail": "回归"
            })

    # 按日期排序，同日期按艺人名
    comebacks.sort(key=lambda x: (x["dateKey"], x["artist"]))
    # 去重 + 过滤无效艺人名 + 规范化
    final = []
    seen2 = set()
    for c in comebacks:
        a = c["artist"]
        if not a or not re.search(r"[A-Za-z\u4e00-\u9fff]", a):
            continue
        if any(x in a for x in ("class=", "><", "Title=", "title-element", "SCHEDULE 2026", "wp-post-image", "srcset=")):
            continue
        if a.startswith((">", "=")):
            continue
        # 规范化艺人名
        if " Comeback " in a and " 2026" in a:
            a = a.split(" Comeback ")[0].strip()
        if re.match(r"^(.+?)\s+(?:Pre-release|Digital Single|1st|2nd|3rd|\d+th)\s+(?:Album|Single|EP|Mini)", a, re.I):
            a = re.match(r"^(.+?)\s+(?:Pre-release|Digital Single|1st|2nd|3rd|\d+th)\s+", a, re.I).group(1).strip()
        a = re.sub(r"\s+(?:Single|Digital Single|1st Full Album|2nd Album)\s*$", "", a, flags=re.I)
        c["artist"] = a[:50]
        k = (c["dateKey"], c["artist"])
        if k in seen2:
            continue
        seen2.add(k)
        c["id"] = len(final) + 1
        final.append(c)
    return final


def main():
    parser = argparse.ArgumentParser(description="爬取 kpopofficial.com 回归日程")
    parser.add_argument(
        "--month",
        type=int,
        choices=range(1, 13),
        metavar="N",
        help="增量更新指定月份（1–12），如 --month=3 只更新三月并保留本地其它月份",
    )
    parser.add_argument(
        "--force-replace",
        action="store_true",
        help="允许在不指定 --month 时覆盖写入 comebacks.json（若检测到像 Reddit 爬虫数据则默认拒绝覆盖）",
    )
    args = parser.parse_args()

    print("正在请求:", URL)
    req = Request(URL, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
    try:
        with urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print("请求失败:", e)
        return

    def _load_existing_items():
        if not os.path.exists(OUTPUT_JSON):
            return []
        try:
            with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception as e:
            print("读取本地历史记录失败，将以本次抓取为准：", e)
            return []

    def _item_key(item):
        date_key = (item or {}).get("dateKey")
        artist = ((item or {}).get("artist") or "").strip()
        if not date_key or not artist:
            return None
        return (date_key, artist)

    items_all = extract_comebacks_from_html(html)
    if args.month is not None:
        month_str = f"-{args.month:02d}-"
        items_month = [c for c in items_all if c.get("dateKey") and month_str in c["dateKey"]]

        existing = _load_existing_items()
        merged_by_key = {}
        extras = []
        for it in existing:
            k = _item_key(it)
            if k:
                merged_by_key[k] = it
            else:
                extras.append(it)

        before = len(merged_by_key)
        for it in items_month:
            k = _item_key(it)
            if k:
                merged_by_key[k] = it
            else:
                extras.append(it)
        after = len(merged_by_key)

        items = list(merged_by_key.values()) + extras
        items.sort(key=lambda x: ((x.get("dateKey") or "9999-99-99"), (x.get("artist") or "")))
        for i, c in enumerate(items, 1):
            c["id"] = i

        print(f"三月增量更新：本次解析到 {len(items_month)} 条，合并后总计 {len(items)} 条（新增 {max(0, after - before)} 条）")
    else:
        existing = _load_existing_items()
        # 保护：如果当前 comebacks.json 看起来来自 Reddit（含 showTime 字段），默认不允许被 KPOP OFFICIAL 全量覆盖
        if (not args.force_replace) and any(isinstance(x, dict) and ("showTime" in x) for x in existing):
            print("检测到本地 comebacks.json 可能来自 Reddit（含 showTime）。")
            print("为避免误覆盖，请用 --month=N 做增量合并，或显式加 --force-replace 允许覆盖。")
            return
        items = items_all
        print(f"解析到 {len(items)} 条回归日程")

    os.makedirs(os.path.dirname(OUTPUT_JS), exist_ok=True)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    js_content = "// 由 scripts/scrape_kpopofficial.py 从 kpopofficial.com 抓取，请勿手改\nmodule.exports = " + json.dumps(items, ensure_ascii=False) + ";"
    with open(OUTPUT_JS, "w", encoding="utf-8") as f:
        f.write(js_content)

    print("已写入:", OUTPUT_JS)
    print("已写入:", OUTPUT_JSON)


if __name__ == "__main__":
    main()
