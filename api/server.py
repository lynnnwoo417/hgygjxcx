#!/usr/bin/env python3
"""本地 Serverless API。不把密钥写进代码，只读环境变量。

运行（项目根目录）：
  python3 api/server.py

接口：
  GET /api/events
  GET /api/events/search?q=
  GET /api/events/calendar?year=&month=
  GET /api/events/<id>
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _lib  # noqa: E402


def _send(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[api] " + (fmt % args) + "\n")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        status, payload = _lib.handle_route(parsed.path, parse_qs(parsed.query))
        _send(self, status, payload)


def main() -> None:
    _lib.load_env_file()
    port = int(os.environ.get("API_PORT") or "5001")
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("API 已启动 http://127.0.0.1:%s" % port)
    print("  GET /api/events")
    print("  GET /api/events/search?q=aespa")
    print("  GET /api/events/calendar?year=2026&month=10")
    print("  GET /api/events/1")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
