#!/usr/bin/env python3
"""把统一 event schema 写入 Supabase：不存在 INSERT，有变化 UPDATE，完全相同只更新 last_checked_at。"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(ROOT, "api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

import _lib  # noqa: E402

COMPARE_FIELDS = _lib.COMPARE_FIELDS


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def changed(old: Dict[str, Any], new: Dict[str, Any]) -> bool:
    for key in COMPARE_FIELDS:
        if _norm(old.get(key)) != _norm(new.get(key)):
            return True
    return False


def upsert_events(events: List[Dict[str, Any]]) -> Dict[str, int]:
    stats = {"insert": 0, "update": 0, "skip": 0, "error": 0}
    now = _now()
    for ev in events:
        sid = ev.get("source_event_id") or ""
        if not sid:
            stats["error"] += 1
            print("[ERROR] missing source_event_id:", ev.get("title") or ev.get("artist"))
            continue
        try:
            existing = _lib.rest_get(
                "events",
                {"select": "*", "source_event_id": "eq." + sid, "limit": "1"},
            )
            row = existing[0] if isinstance(existing, list) and existing else None
            payload = dict(ev)
            payload.pop("id", None)
            payload["last_checked_at"] = now
            if not row:
                payload["created_at"] = now
                payload["updated_at"] = now
                _lib.rest_upsert([payload])
                stats["insert"] += 1
                continue
            if changed(row, payload):
                payload["updated_at"] = now
                _lib.rest_patch(sid, payload)
                stats["update"] += 1
            else:
                _lib.rest_patch(sid, {"last_checked_at": now})
                stats["skip"] += 1
        except Exception as e:
            stats["error"] += 1
            print("[ERROR] upsert %s: %s" % (sid[:12], e))
    return stats
