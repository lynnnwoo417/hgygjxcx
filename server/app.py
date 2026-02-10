#!/usr/bin/env python3
"""
回归预告机 - 日程 API 服务
- GET /api/schedules：返回合并后的全部日程（回归+演唱会+签售），供小程序拉取
- 每 12 小时自动执行一次爬虫（kpopofficial 回归、kpopofficial 演唱会/签售、NOL/Melon/YES24），
  网站有更新时小程序下次打开即可拿到新数据。
运行方式（在项目根目录）：python server/app.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# 项目根目录（miniprogram-1）
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "miniprogram" / "data"
SCRIPTS_DIR = ROOT / "scripts"


def run_scrapers():
    """执行三个爬虫脚本，更新 miniprogram/data/*.json"""
    env = os.environ.copy()
    for name, script in [
        ("回归", "scrape_kpopofficial.py"),
        ("演唱会/签售", "scrape_concerts.py"),
        ("票务站", "scrape_kr_tickets.py"),
    ]:
        try:
            subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / script)],
                cwd=str(ROOT),
                env=env,
                timeout=120,
                capture_output=True,
            )
        except Exception as e:
            print(f"[scheduler] {name} 执行异常: {e}")


def load_merged_schedules():
    """从 data 目录读取三份 JSON 并合并为统一列表"""
    list_ = []
    id_ = 0

    for filename in ("comebacks.json", "concerts.json", "ticket_concerts.json"):
        path = DATA_DIR / filename
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for item in data:
            id_ += 1
            list_.append({
                "id": id_,
                "artist": item.get("artist") or "未知",
                "type": item.get("type") or "回归",
                "date": item.get("date") or (item.get("dateKey") or "")[5:],
                "dateKey": item.get("dateKey") or "",
                "detail": item.get("detail") or "回归",
            })
    list_.sort(key=lambda x: (x["dateKey"], x["type"], x["artist"]))
    return list_


@app.route("/api/schedules", methods=["GET"])
def api_schedules():
    """返回合并后的日程列表，供小程序 wx.request 使用"""
    try:
        data = load_merged_schedules()
    except Exception as e:
        return jsonify({"error": str(e), "schedules": []}), 500
    return jsonify({"schedules": data})


def scheduled_job():
    run_scrapers()


if __name__ == "__main__":
    # 启动时先跑一次爬虫，再开启 12 小时定时
    print("首次执行爬虫...")
    run_scrapers()
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_job, "interval", hours=12)
    scheduler.start()
    print("已设置每 12 小时执行一次爬虫")
    # 开发环境可开 debug；部署时建议关掉
    app.run(host="0.0.0.0", port=5000, debug=False)
