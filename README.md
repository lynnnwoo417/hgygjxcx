# 回归预告机 - K-pop 日程管理小程序

一个微信小程序，用于管理 K-pop 艺人的回归、演唱会、签售和活动日程。

## 功能特性

- 📅 **日历视图**：按日期查看所有日程
- 🔍 **搜索功能**：快速搜索艺人或活动
- 🎯 **分类筛选**：回归、演唱会、签售、活动
- ⭐ **收藏功能**：收藏感兴趣的日程
- 📝 **记录功能**：记录已完成的日程
- 🔔 **提醒功能**：设置日程提醒

## 数据来源

- **回归数据**：Reddit r/kpop wiki (https://www.reddit.com/r/kpop/wiki/upcoming-releases/archive/)
- **演唱会/签售**：KPOP OFFICIAL (https://kpopofficial.com/kpop-concerts/)
- **票务信息**：NOL、Melon Global、YES24、Ktown4u

## 项目结构

```
miniprogram-1/
├── miniprogram/          # 小程序前端代码
│   ├── pages/           # 页面
│   ├── data/            # 本地数据文件
│   └── utils/           # 工具函数
├── scripts/             # 爬虫脚本
│   ├── scrape_reddit_comebacks.py      # Reddit 回归爬虫
│   ├── scrape_kpopofficial.py          # KPOP OFFICIAL 回归爬虫
│   └── scrape_kpopofficial_concerts.py # KPOP OFFICIAL 演唱会爬虫
└── server/              # 后端 API（可选）
```

## 爬虫使用

### Reddit 回归爬虫

```bash
# 基础使用（需要网络可访问 Reddit）
python3 scripts/scrape_reddit_comebacks.py

# 如果遇到 403，使用 OAuth
export REDDIT_CLIENT_ID="your_client_id"
export REDDIT_CLIENT_SECRET="your_client_secret"
export REDDIT_USER_AGENT="Mozilla/5.0 (compatible; KpopScheduleBot/1.0)"
python3 scripts/scrape_reddit_comebacks.py
```

### KPOP OFFICIAL 爬虫

```bash
# 全量爬取
python3 scripts/scrape_kpopofficial.py

# 只更新指定月份（增量合并）
python3 scripts/scrape_kpopofficial.py --month=3
```

## 开发

1. 使用微信开发者工具打开项目
2. 配置 `miniprogram/utils/config.ts` 中的 `SCHEDULE_API_BASE`（如果需要后端 API）
3. 运行爬虫脚本更新数据
4. 编译并预览

## 数据说明

- 数据文件位于 `miniprogram/data/` 目录
- 格式：`.js` 文件用于小程序加载，`.json` 文件用于查看
- 数据包含 2024-2026 年的回归日程（2821条）

## License

仅供个人学习使用。数据来源：
- Reddit r/kpop wiki
- KPOP OFFICIAL (https://kpopofficial.com)
