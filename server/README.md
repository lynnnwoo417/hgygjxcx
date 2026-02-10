# 回归预告机 - 日程 API（每 12 小时爬一次）

后端负责**每 12 小时**执行一次爬虫（kpopofficial 回归、演唱会/签售，NOL/Melon/YES24），小程序打开时请求 `GET /api/schedules` 即可拿到最新合并日程，网站有更新时小程序也能及时更新。

## 本地运行

在**项目根目录**（`miniprogram-1`）执行：

```bash
pip install -r server/requirements.txt
python server/app.py
```

- 首次启动会先跑一遍三个爬虫，再开始每 12 小时定时任务。
- 接口地址：`http://localhost:5000/api/schedules`。
- 小程序开发时在 `miniprogram/utils/config.ts` 里把 `SCHEDULE_API_BASE` 设为 `'http://localhost:5000'`（或你本机 IP），并在微信开发者工具中勾选「不校验合法域名」即可请求。

## 部署到线上

1. 将本后端部署到任意支持 Python 的服务器（需 **HTTPS**，微信小程序要求请求域名走 HTTPS）。
2. 在**微信公众平台** → 开发 → 开发管理 → 开发设置 → **服务器域名**中，将你的接口域名加入 request 合法域名。
3. 在 `miniprogram/utils/config.ts` 中把 `SCHEDULE_API_BASE` 改为你的接口根地址，例如：`'https://your-domain.com'`。

## 接口说明

- **GET /api/schedules**  
  返回 JSON：`{ "schedules": [ { "id", "artist", "type", "date", "dateKey", "detail" }, ... ] }`  
  `type` 为 `回归` | `演唱会` | `签售`。
