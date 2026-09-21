#!/usr/bin/env python3
"""Supabase 查询 + 转成小程序现有字段。密钥只从环境变量读取。"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Any, Dict, List, Optional

TYPE_TO_ZH = {
    "comeback": "回归",
    "prerecording": "回归",
    "concert": "演唱会",
    "fansign": "签售",
    "popup": "活动",
    "other": "活动",
}

ZH_TO_TYPE = {
    "回归": "comeback",
    "演唱会": "concert",
    "签售": "fansign",
    "活动": "popup",
}

COMPARE_FIELDS = (
    "artist",
    "title",
    "event_type",
    "event_date",
    "event_time",
    "end_time",
    "venue",
    "city",
    "region",
    "ticket_platform",
    "ticket_open_time",
    "official_url",
    "source_url",
    "source_name",
    "status",
    "cover_url",
)


def load_env_file() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    path = os.path.join(root, ".env")
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, val = raw.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def use_postgres() -> bool:
    load_env_file()
    return bool(os.environ.get("DATABASE_PASSWORD") and os.environ.get("DATABASE_HOST"))


def pg_connect():
    import psycopg2
    from psycopg2.extras import RealDictCursor

    load_env_file()
    return psycopg2.connect(
        host=os.environ.get("DATABASE_HOST"),
        port=int(os.environ.get("DATABASE_PORT") or "6543"),
        dbname=os.environ.get("DATABASE_NAME") or "postgres",
        user=os.environ.get("DATABASE_USER"),
        password=os.environ.get("DATABASE_PASSWORD"),
        sslmode="require",
        connect_timeout=15,
        cursor_factory=RealDictCursor,
    )


def pg_fetch(sql: str, args: tuple = ()) -> List[Dict[str, Any]]:
    conn = pg_connect()
    try:
        cur = conn.cursor()
        cur.execute(sql, args)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def pg_execute(sql: str, args: tuple = ()) -> None:
    conn = pg_connect()
    try:
        cur = conn.cursor()
        cur.execute(sql, args)
        conn.commit()
    finally:
        conn.close()


def supabase_config() -> Dict[str, str]:
    load_env_file()
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
    return {"url": url, "key": key}


def _headers(key: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    h = {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def rest_get(path: str, params: Optional[Dict[str, str]] = None) -> Any:
    params = params or {}
    if use_postgres() and path.strip("/") == "events":
        where = ["1=1"]
        args: list = []
        for key, raw in params.items():
            if key in ("select", "order"):
                continue
            if key == "limit":
                continue
            if isinstance(raw, str) and raw.startswith("eq."):
                where.append("%s = %%s" % key)
                args.append(raw[3:])
        limit = int(params.get("limit") or "20")
        sql = "select * from public.events where %s limit %s" % (" and ".join(where), limit)
        return pg_fetch(sql, tuple(args))
    cfg = supabase_config()
    q = ("?" + urllib.parse.urlencode(params, safe=",.*()")) if params else ""
    req = urllib.request.Request(
        cfg["url"] + "/rest/v1/" + path.lstrip("/") + q,
        headers=_headers(cfg["key"]),
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body) if body else []


def rest_upsert(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    if use_postgres():
        cols = [
            "source_event_id", "artist", "title", "event_type", "event_date", "event_time",
            "end_time", "venue", "city", "region", "ticket_platform", "ticket_open_time",
            "official_url", "source_url", "source_name", "status", "cover_url",
        ]
        conn = pg_connect()
        try:
            cur = conn.cursor()
            for row in rows:
                values = [row.get(c) for c in cols]
                placeholders = ",".join(["%s"] * len(cols))
                updates = ",".join(
                    ["%s = excluded.%s" % (c, c) for c in cols if c != "source_event_id"]
                )
                sql = (
                    "insert into public.events (%s) values (%s) "
                    "on conflict (source_event_id) do update set %s, updated_at = now(), last_checked_at = now()"
                    % (",".join(cols), placeholders, updates)
                )
                cur.execute(sql, values)
            conn.commit()
        finally:
            conn.close()
        return
    cfg = supabase_config()
    data = json.dumps(rows, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        cfg["url"] + "/rest/v1/events?on_conflict=source_event_id",
        data=data,
        headers=_headers(
            cfg["key"],
            {"Prefer": "resolution=merge-duplicates,return=minimal"},
        ),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError("Supabase upsert 失败: %s %s" % (e.code, err)) from e


def rest_patch(source_event_id: str, fields: Dict[str, Any]) -> None:
    if use_postgres():
        fields = dict(fields)
        fields.pop("id", None)
        if not fields:
            return
        sets = ", ".join(["%s = %%s" % k for k in fields.keys()])
        args = list(fields.values()) + [source_event_id]
        pg_execute("update public.events set %s where source_event_id = %%s" % sets, tuple(args))
        return
    cfg = supabase_config()
    data = json.dumps(fields, ensure_ascii=False).encode("utf-8")
    filt = urllib.parse.quote("eq." + source_event_id, safe=".")
    req = urllib.request.Request(
        cfg["url"] + "/rest/v1/events?source_event_id=" + filt,
        data=data,
        headers=_headers(cfg["key"], {"Prefer": "return=minimal"}),
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        resp.read()


def _date_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    return text[:10] if len(text) >= 10 else text


def to_miniprogram(row: Dict[str, Any]) -> Dict[str, Any]:
    event_date = _date_str(row.get("event_date"))
    event_type = (row.get("event_type") or "other").strip()
    zh_type = TYPE_TO_ZH.get(event_type, row.get("type") or "活动")
    return {
        "id": int(row["id"]) if row.get("id") is not None else 0,
        "sourceEventId": row.get("source_event_id") or "",
        "artist": row.get("artist") or "未知",
        "type": zh_type,
        "date": event_date[5:] if len(event_date) >= 10 else "",
        "dateKey": event_date,
        "detail": row.get("title") or zh_type,
        "ticketPlatform": row.get("ticket_platform") or "",
        "ticketTime": row.get("ticket_open_time") or "",
        "venue": row.get("venue") or "",
        "showTime": row.get("event_time") or "",
        "detailUrl": row.get("source_url") or "",
        "officialUrl": row.get("official_url") or "",
        "locationText": row.get("city") or "",
        "coverImage": row.get("cover_url") or "",
        "region": row.get("region") or "",
        "status": row.get("status") or "upcoming",
    }


def list_events(
    start_date: str = "",
    end_date: str = "",
    event_type: str = "",
    artist: str = "",
    status: str = "",
    limit: int = 8000,
) -> List[Dict[str, Any]]:
    if use_postgres():
        where = ["1=1"]
        args: list = []
        if start_date:
            where.append("event_date >= %s")
            args.append(start_date)
        if end_date:
            where.append("event_date <= %s")
            args.append(end_date)
        if event_type:
            where.append("event_type = %s")
            args.append(ZH_TO_TYPE.get(event_type, event_type))
        if artist:
            where.append("artist ilike %s")
            args.append("%" + artist + "%")
        if status:
            where.append("status = %s")
            args.append(status)
        sql = (
            "select * from public.events where %s order by event_date asc nulls last, artist asc limit %s"
            % (" and ".join(where), max(1, min(limit, 10000)))
        )
        rows = pg_fetch(sql, tuple(args))
        return [to_miniprogram(r) for r in rows]
    params: Dict[str, str] = {
        "select": "*",
        "order": "event_date.asc,artist.asc",
        "limit": str(max(1, min(limit, 10000))),
    }
    if start_date:
        params["event_date"] = "gte." + start_date
    if end_date:
        # PostgREST 多个同名过滤要用 and
        if "event_date" in params:
            params["and"] = "(event_date.gte.%s,event_date.lte.%s)" % (start_date, end_date)
            del params["event_date"]
        else:
            params["event_date"] = "lte." + end_date
    if event_type:
        mapped = ZH_TO_TYPE.get(event_type, event_type)
        params["event_type"] = "eq." + mapped
    if artist:
        params["artist"] = "ilike.*" + artist + "*"
    if status:
        params["status"] = "eq." + status
    rows = rest_get("events", params)
    if not isinstance(rows, list):
        return []
    return [to_miniprogram(r) for r in rows if isinstance(r, dict)]


def search_events(q: str, limit: int = 80) -> List[Dict[str, Any]]:
    q = (q or "").strip()
    if not q:
        return []
    if use_postgres():
        like = "%" + q + "%"
        rows = pg_fetch(
            """
            select * from public.events
            where artist ilike %s or title ilike %s or city ilike %s or venue ilike %s
            order by event_date asc nulls last
            limit %s
            """,
            (like, like, like, like, limit),
        )
        return [to_miniprogram(r) for r in rows]
    safe = q.replace(",", " ").replace("(", " ").replace(")", " ")
    params = {
        "select": "*",
        "or": "(artist.ilike.*{0}*,title.ilike.*{0}*,city.ilike.*{0}*,venue.ilike.*{0}*)".format(safe),
        "order": "event_date.asc",
        "limit": str(limit),
    }
    rows = rest_get("events", params)
    if not isinstance(rows, list):
        return []
    return [to_miniprogram(r) for r in rows if isinstance(r, dict)]


def get_event(event_id: str) -> Optional[Dict[str, Any]]:
    if not event_id:
        return None
    if use_postgres():
        if event_id.isdigit():
            rows = pg_fetch("select * from public.events where id = %s limit 1", (int(event_id),))
        else:
            rows = pg_fetch("select * from public.events where source_event_id = %s limit 1", (event_id,))
        if rows:
            return to_miniprogram(rows[0])
        return None
    if event_id.isdigit():
        rows = rest_get("events", {"select": "*", "id": "eq." + event_id, "limit": "1"})
    else:
        rows = rest_get("events", {"select": "*", "source_event_id": "eq." + event_id, "limit": "1"})
    if isinstance(rows, list) and rows:
        return to_miniprogram(rows[0])
    return None


def calendar_events(year: int, month: int) -> Dict[str, Any]:
    start = "%04d-%02d-01" % (year, month)
    if month == 12:
        end = "%04d-12-31" % year
    else:
        end = "%04d-%02d-01" % (year, month + 1)
        # 用 lt 下月 1 号；这里用 lte 当月末近似，list_events 支持 lte
        # 更精确：取该月最后一天
        from calendar import monthrange

        last = monthrange(year, month)[1]
        end = "%04d-%02d-%02d" % (year, month, last)
    events = list_events(start_date=start, end_date=end, limit=3000)
    dates = sorted({e.get("dateKey") for e in events if e.get("dateKey")})
    return {"year": year, "month": month, "dates": dates, "schedules": events}


def json_bytes(payload: Any, status: int = 200) -> tuple:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return status, body


def handle_route(path: str, qs: dict) -> tuple:
    def one(name: str, default: str = "") -> str:
        vals = qs.get(name) or []
        return (vals[0] if vals else default).strip()

    try:
        if path == "/api/events" or path == "/api/schedules":
            rows = list_events(
                start_date=one("start_date"),
                end_date=one("end_date"),
                event_type=one("event_type") or one("type"),
                artist=one("artist"),
                status=one("status"),
            )
            return 200, {"schedules": rows, "count": len(rows)}

        if path == "/api/events/search":
            q = one("q")
            if not q:
                return 400, {"error": "missing q", "schedules": []}
            rows = search_events(q)
            return 200, {"schedules": rows, "count": len(rows), "q": q}

        if path == "/api/events/calendar":
            year = int(one("year") or "0")
            month = int(one("month") or "0")
            if year < 2000 or month < 1 or month > 12:
                return 400, {"error": "year/month invalid", "schedules": [], "dates": []}
            return 200, calendar_events(year, month)

        if path.startswith("/api/events/"):
            event_id = path[len("/api/events/") :].strip("/")
            if not event_id or event_id in ("search", "calendar"):
                return 404, {"error": "not found"}
            item = get_event(event_id)
            if not item:
                return 404, {"error": "not found", "event": None}
            return 200, {"event": item}

        if path in ("/", "/health"):
            return 200, {"ok": True, "service": "hgygj-api"}

        return 404, {"error": "not found"}
    except RuntimeError as e:
        return 500, {"error": str(e), "schedules": []}
    except Exception as e:
        return 500, {"error": str(e), "schedules": []}
